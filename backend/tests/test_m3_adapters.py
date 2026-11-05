"""M3 profile validation and conservative authentication/context adapters."""
import pytest
from pydantic import ValidationError
from app.events.adapters import adapt, SECURITY_PROVIDER, SYSMON_PROVIDER
from app.events.records import parse_records, RecordError
from app.events.time import event_time
from app.modules.events.schemas import ProfileConfig


def config(adapter='linux_auth', fmt='syslog', **kw):
    return ProfileConfig(adapter=adapter, format=fmt, **kw).model_dump()


@pytest.mark.parametrize('message,typ,outcome,method', [
 ('Failed password for invalid user mira from 192.0.2.1 port 2222 ssh2','logon','failure','password'),
 ('Accepted password for mira from 2001:db8::1 port 2222 ssh2','logon','success','password'),
 ('Accepted publickey for mira from 192.0.2.1 port 22 ssh2: ED25519 SHA256:synthetic','logon','success','publickey'),
 ('Invalid user mira from 2001:db8::1 port 22','invalid_user','failure',None),
 ('pam_unix(sshd:auth): authentication failure; uid=0 rhost=192.0.2.1 user=mira','pam_authentication','failure','pam_unix'),
 ('pam_unix(sshd:session): session opened for user mira(uid=1000) by (uid=0)','session_opened','success','pam_unix'),
 ('pam_unix(sshd:session): session closed for user mira','session_closed','success','pam_unix'),
 ('User mira from 192.0.2.1 not allowed because account is locked','account_denied','failure',None),
])
def test_linux_supported_patterns(message,typ,outcome,method):
    event=adapt('Nov  5 10:20:30 synthetic-host sshd[123]: '+message,config())
    assert event['event_type']==typ and event['outcome']==outcome and event['username']=='mira'
    assert event['hostname']=='synthetic-host' and event['attributes']['process_id']=='123'
    assert event['attributes'].get('authentication_method')==method


def test_unrecognized_text_not_keyword_detection():
    for line in ['a user says Failed password', 'Nov  5 10:20:30 host app: Accepted password for mira',
                 'sshd: note: Accepted password for mira from 192.0.2.1 port 22', 'sshd: Failed something']:
        assert adapt(line,config()) is None
    event=adapt('sshd: Accepted password for mira from not-an-ip port 0',config(source_host='assumed-host'))
    assert event['source_ip'] is None and event['source_port'] is None and event['warnings']
    assert event['attributes']['hostname_origin']=='analyst_profile'


@pytest.mark.parametrize('event_id,typ,outcome', [('4624','logon','success'),('4625','logon','failure'),
 ('4634','logoff','success'),('4648','explicit_credentials','unknown'),('4740','account_lockout','unknown')])
def test_windows_security_fields(event_id,typ,outcome):
    row={'Event':{'System':{'Provider':{'@Name':SECURITY_PROVIDER},'Channel':'Security','EventID':event_id,
        'TimeCreated':{'@SystemTime':'2026-11-05T12:00:00.1234567Z'},'Computer':'WIN-SYNTH','EventRecordID':'17'},
        'EventData':{'Data':[{'@Name':k,'#text':v} for k,v in {'SubjectUserName':'operator','TargetUserName':'mira',
            'TargetDomainName':'LAB','IpAddress':'2001:db8::8','IpPort':'4422','LogonType':'3'}.items()]}}}
    event=adapt(row,config('windows_security','json'))
    assert event['event_type']==typ and event['outcome']==outcome
    assert event['username']=='mira' and event['attributes']['subject_username']=='operator'
    assert event['source_ip']=='2001:db8::8' and event['attributes']['event_record_id']=='17'
    temporal=event_time(event['original_timestamp'],{})
    assert temporal['utc'].endswith('.123456+00:00')
    assert temporal['precision']=='fraction_7' and temporal['utc_projection_precision']=='microsecond'


@pytest.mark.parametrize('id,typ', [('1','process_created'),('3','network_connection')])
def test_sysmon_is_context_never_authentication(id,typ):
    row={'ProviderName':SYSMON_PROVIDER,'EventID':id,'Channel':'Microsoft-Windows-Sysmon/Operational',
         'EventData':{'User':'LAB\\mira','ProcessGuid':'synthetic-guid','ProcessId':'123','Image':'C:\\demo.exe',
                      'CommandLine':'demo.exe --synthetic','SourceIp':'192.0.2.10','DestinationIp':'2001:db8::2',
                      'DestinationPort':'443','UtcTime':'2026-11-05 12:00:00'}}
    event=adapt(row,config('sysmon','jsonl'))
    assert event['event_type']==typ and event['outcome']=='unknown'
    assert event['attributes']['process_guid']=='synthetic-guid'
    assert event['attributes']['timestamp_field']=='UtcTime'


def test_wrong_provider_placeholder_and_arbitrary_ids():
    cfg=config('windows_security','json')
    assert adapt({'Id':4624,'ProviderName':'Unrelated'},cfg) is None
    assert adapt({'EventID':4624,'Channel':'Application'},cfg) is None
    assert adapt({'number':4624},cfg) is None
    row=adapt({'EventID':4625,'TargetUserName':'-','IpAddress':'-','IpPort':'0'},cfg)
    assert row['username'] is None and row['source_ip'] is None and row['source_port'] is None
    assert row['warnings']


def test_profiles_timestamp_uncertainty_and_dst():
    raw='Nov  5 10:20:30'
    assert event_time(raw,config())['utc'] is None
    assert event_time(raw,config(year=2026))['utc'] is None
    known=event_time(raw,config(year=2026,timezone='+05:30'))
    assert known['utc']=='2026-11-05T04:50:30+00:00' and len(known['assumptions'])==2
    for raw,status in [('2026-11-01 01:30:00','ambiguous'),('2026-03-08 02:30:00','nonexistent')]:
        result=event_time(raw,config(timezone='America/New_York'))
        assert result['certainty']==status and result['utc'] is None
    assert event_time('2026-11-05T12:00:00Z',config(timezone='+05:30'))['certainty']=='source_offset'
    for kw in [dict(adapter='linux_auth',format='json'),dict(adapter='windows_security',format='csv',year=2026),
               dict(adapter='linux_auth',format='syslog',timezone='unknown'),dict(adapter='linux_auth',format='syslog',year=0)]:
        with pytest.raises(ValidationError):
            ProfileConfig(**kw)


def test_record_accounting_coordinates_and_limits(monkeypatch):
    cfg=config('windows_security','jsonl')
    batch=parse_records(b'{"EventID":4625}\r\n{bad}\n{"EventID":4625}\n',cfg)
    assert [r.locator['line'] for r in batch.records]==[1,2,3]
    assert batch.records[1].error and batch.records[0].fingerprint==batch.records[2].fingerprint
    monkeypatch.setattr('app.events.records.MAX_RECORDS',1)
    batch=parse_records(b'{"EventID":4625}\n{"EventID":4625}\n',cfg)
    assert batch.coverage['omitted']==1 and batch.coverage['status']=='partial'
    with pytest.raises(RecordError): parse_records(b'{"EventID":1,"EventID":2}',config('sysmon','json'))
    with pytest.raises(RecordError): parse_records(b'\xff',cfg)
    with pytest.raises(RecordError): parse_records(b'x'* (10*1024*1024+1),config())

def test_utf8_crlf_csv_and_long_records(monkeypatch):
    cfg=config('windows_security','csv')
    batch=parse_records('EventID,TargetUserName,IpAddress\r\n4625,mira,2001:db8::1\r\n4624,orion,-\r\n'.encode(),cfg)
    assert [r.locator['row'] for r in batch.records]==[1,2]
    assert adapt(batch.records[0].value,cfg)['source_ip']=='2001:db8::1'
    cfg=config()
    batch=parse_records(('sshd: '+'x'*33000).encode(),cfg)
    assert batch.records[0].error and batch.records[0].value is None
    with pytest.raises(RecordError):
        parse_records(b'[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]',config('windows_security','json'))
    unknown=event_time('Nov  5 12:00:00',config(timestamp_convention='iso8601',year=2026,timezone='+00:00'))
    assert unknown['utc'] is None and unknown['warnings']


def test_adversarial_nul_fields_rejected_before_database():
    from app.events.adapters import AdapterReject
    with pytest.raises(AdapterReject):
        adapt('sshd: Failed password for mi\x00ra from 192.0.2.1 port 22',config())
    with pytest.raises(AdapterReject):
        adapt({'EventID':4625,'TargetUserName':'mi\x00ra'},config('windows_security','json'))
    with pytest.raises(ValidationError):
        ProfileConfig(adapter='linux_auth',format='syslog',source_host='\x00')
