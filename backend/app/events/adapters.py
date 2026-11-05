"""Conservative record adapters. No detection rules or inferred session joins."""
import ipaddress
from importlib.metadata import version
import re

ADAPTER_VERSION = '1.1'
NORMALIZATION_VERSION = '1.tz' + version('tzdata')
SECURITY_PROVIDER = 'Microsoft-Windows-Security-Auditing'
SYSMON_PROVIDER = 'Microsoft-Windows-Sysmon'
SYSLOG = re.compile(r'^(?P<time>(?:[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?))\s+(?P<host>[^\s]{1,256})\s+(?P<process>sshd|login|su|sudo)(?:\[(?P<pid>\d{1,12})\])?:\s*(?P<message>.*)$')
SSH = re.compile(r'^(Failed|Accepted) (password|publickey) for (?:(invalid user) )?([^\s]{1,256}) from ([^\s]{1,100}) port (\d{1,5})(?: ssh2)?(?:[: ].*)?$')
INVALID = re.compile(r'^Invalid user ([^\s]{1,256}) from ([^\s]{1,100}) port (\d{1,5})(?: .*)?$')
PAM_FAIL = re.compile(r'^pam_unix\((sshd|login|su|sudo):auth\): authentication failure;(.*)$')
SESSION = re.compile(r'^pam_unix\((sshd|login|su|sudo):session\): session (opened|closed) for user ([^\s(]{1,256})(?:\(uid=\d+\))?(?: by .*)?$')
DENIAL = re.compile(r'^User ([^\s]{1,256}) from ([^\s]{1,100}) not allowed because account is locked(?: .*)?$')


class AdapterReject(ValueError):
    pass


def scalar(value, limit=256):
    if value is None or value in ('', '-', '(null)', 'N/A'):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise AdapterReject('Expected a scalar field.')
    value = str(value).strip()
    if len(value) > limit:
        raise AdapterReject('Normalized field exceeds its supported length.')
    return value or None


def ip(value, warnings):
    value = scalar(value, 100)
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        warnings.append('Invalid IP address withheld.')
        return None


def port(value, warnings):
    value = scalar(value, 20)
    if not value:
        return None
    if value.isdecimal() and 0 < int(value) <= 65535:
        return int(value)
    warnings.append('Invalid or placeholder port withheld.')
    return None


def core(provider, category, typ, outcome):
    return dict(provider=provider, category=category, event_type=typ, outcome=outcome,
        event_id=None, username=None, account_domain=None, hostname=None,
        source_ip=None, destination_ip=None, source_port=None, destination_port=None,
        original_timestamp=None, attributes={}, warnings=[])


def linux(record, config):
    if not isinstance(record, str):
        raise AdapterReject('Linux adapter requires a text record.')
    header = SYSLOG.fullmatch(record)
    if header:
        raw_time, host, process, pid, message = (header[k] for k in ('time','host','process','pid','message'))
    else:
        # Explicit missing-header form: a trusted program prefix is still required.
        prefix = re.fullmatch(r'(sshd|login|su|sudo)(?:\[(\d{1,12})\])?:\s*(.*)', record)
        if not prefix:
            return None
        process, pid, message = prefix.groups()
        raw_time, host = None, None
    event = core(process, 'authentication', '', 'unknown')
    event.update(hostname=host, original_timestamp=raw_time)
    event['attributes']['process_id'] = pid
    match = SSH.fullmatch(message) if process == 'sshd' else None
    if match:
        state, method, invalid, user, address, remote_port = match.groups()
        event.update(event_type='logon', outcome='success' if state == 'Accepted' else 'failure', username=user,
            source_ip=ip(address,event['warnings']), source_port=port(remote_port,event['warnings']))
        event['attributes'].update(authentication_method=method, invalid_user=bool(invalid))
    elif process == 'sshd' and (match := INVALID.fullmatch(message)):
        event.update(event_type='invalid_user', outcome='failure', username=match[1],
            source_ip=ip(match[2],event['warnings']), source_port=port(match[3],event['warnings']))
    elif (match := PAM_FAIL.fullmatch(message)) and match[1] == process:
        fields = dict(re.findall(r'(?:^|\s)([a-z_]+)=([^\s;]*)', match[2]))
        event.update(event_type='pam_authentication', outcome='failure', username=scalar(fields.get('user')),
                     source_ip=ip(fields.get('rhost'),event['warnings']))
        event['attributes'].update(authentication_method='pam_unix')
    elif (match := SESSION.fullmatch(message)) and match[1] == process:
        event.update(category='session', event_type='session_opened' if match[2]=='opened' else 'session_closed',
                     outcome='success', username=match[3])
        event['attributes']['authentication_method'] = 'pam_unix'
    elif process == 'sshd' and (match := DENIAL.fullmatch(message)):
        event.update(event_type='account_denied', outcome='failure', username=match[1],
                     source_ip=ip(match[2],event['warnings']))
        event['attributes']['denial_reason'] = 'source reports account locked'
    else:
        return None
    return event


def structured(record, config):
    if not isinstance(record, dict):
        raise AdapterReject('Expected a structured event object.')
    root = record.get('Event', record)
    if not isinstance(root, dict):
        raise AdapterReject('Invalid Event wrapper.')
    if isinstance(root.get('System'), dict):
        system = root['System']
        data = root.get('EventData', {})
        provider = system.get('Provider')
        provider = provider.get('Name', provider.get('@Name')) if isinstance(provider,dict) else provider
        event_id = system.get('EventID')
        event_id = event_id.get('#text', event_id.get('Value')) if isinstance(event_id,dict) else event_id
        channel, host, record_id = system.get('Channel'), system.get('Computer'), system.get('EventRecordID')
        time = system.get('TimeCreated')
        time = time.get('SystemTime',time.get('@SystemTime')) if isinstance(time,dict) else time
        if isinstance(data, dict) and isinstance(data.get('Data'), list):
            mapped = {}
            for field in data['Data']:
                if not isinstance(field,dict):
                    raise AdapterReject('EventData Data entries require named fields.')
                name = field.get('Name',field.get('@Name'))
                if not isinstance(name,str) or name in mapped:
                    raise AdapterReject('EventData fields must have unique names.')
                mapped[name] = field.get('#text',field.get('Value'))
            data = mapped
    else:
        provider = root.get('ProviderName', root.get('Provider'))
        event_id, channel = root.get('EventID', root.get('Id')), root.get('Channel', root.get('LogName'))
        host, record_id = root.get('Computer',root.get('MachineName')), root.get('EventRecordID',root.get('RecordId'))
        time = root.get('TimeCreated',root.get('UtcTime'))
        data = root.get('EventData', root)
    if not isinstance(data,dict):
        raise AdapterReject('Expected named EventData fields, not positional properties.')
    provider, channel = scalar(provider,100), scalar(channel,100)
    expected = SECURITY_PROVIDER if config['adapter']=='windows_security' else SYSMON_PROVIDER
    expected_channel = 'Security' if config['adapter']=='windows_security' else 'Microsoft-Windows-Sysmon/Operational'
    # The explicit profile selects the family when exported provider/channel are absent.
    if (provider is not None and provider != expected) or (channel is not None and channel != expected_channel):
        return None
    event_id = scalar(event_id,32)
    allowed = {'4624':('authentication','logon','success'), '4625':('authentication','logon','failure'),
        '4634':('session','logoff','success'), '4648':('authentication','explicit_credentials','unknown'),
        '4740':('account','account_lockout','unknown')} if config['adapter']=='windows_security' else {
        '1':('process','process_created','unknown'), '3':('network','network_connection','unknown')}
    if event_id not in allowed:
        return None
    event = core(expected,*allowed[event_id])
    event.update(event_id=event_id,hostname=scalar(host),original_timestamp=scalar(time,128))
    attrs, warnings = event['attributes'], event['warnings']
    if provider is None or channel is None:
        warnings.append('Provider/channel absent; event family selected by analyst profile.')
    attrs.update(event_record_id=scalar(record_id,64), source_provider=provider, source_channel=channel)
    if config['adapter']=='windows_security':
        event.update(username=scalar(data.get('TargetUserName')), account_domain=scalar(data.get('TargetDomainName')),
            source_ip=ip(data.get('IpAddress'),warnings), source_port=port(data.get('IpPort'),warnings))
        for key, source in {'subject_username':'SubjectUserName','subject_domain':'SubjectDomainName',
            'subject_logon_id':'SubjectLogonId','target_logon_id':'TargetLogonId','logon_type':'LogonType',
            'authentication_method':'AuthenticationPackageName','process_id':'ProcessId','process_name':'ProcessName',
            'caller_computer':'CallerComputerName','target_server':'TargetServerName',
            'status':'Status','substatus':'SubStatus','failure_reason':'FailureReason'}.items():
            attrs[key] = scalar(data.get(source),512)
    else:
        event.update(username=scalar(data.get('User')), source_ip=ip(data.get('SourceIp'),warnings),
            destination_ip=ip(data.get('DestinationIp'),warnings), source_port=port(data.get('SourcePort'),warnings),
            destination_port=port(data.get('DestinationPort'),warnings))
        if not event['original_timestamp'] or (not root.get('TimeCreated') and root.get('UtcTime')):
            event['original_timestamp'] = scalar(data.get('UtcTime'),128)
            if event['original_timestamp']:
                # Sysmon's documented UtcTime field declares UTC, unlike generic naive times.
                attrs['timestamp_field'] = 'UtcTime'
        for key, source in {'process_id':'ProcessId','process_guid':'ProcessGuid','image':'Image',
            'command_line':'CommandLine','parent_process_guid':'ParentProcessGuid','protocol':'Protocol',
            'initiated':'Initiated'}.items():
            attrs[key] = scalar(data.get(source),2048 if key=='command_line' else 512)
    return event


def adapt(record, config):
    event = linux(record,config) if config['adapter']=='linux_auth' else structured(record,config)
    if event is None:
        return None
    host = config.get('source_host')
    if not event['hostname'] and host:
        event['hostname'] = host
        event['attributes']['hostname_origin'] = 'analyst_profile'
    elif host and event['hostname'] != host:
        event['warnings'].append('Source hostname differs from configured profile host; source value retained.')
    return event
