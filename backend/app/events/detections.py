"""Bounded authentication pattern evaluation. Severity is review priority, not probability."""
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
import hashlib
import json

VERSION = '1.1'
RULES = ('repeated_failures', 'password_spray', 'success_after_failures', 'lockout_concentration', 'activity_burst')
LIMIT = 10000
RULE_DEFINITIONS = {
    'repeated_failures': {'required_fields':['username','hostname','outcome'], 'criteria':'At least max(min_failures,min_occurrences) distinct observations of failures in window_seconds.', 'severity':'medium'},
    'password_spray': {'required_fields':['username','hostname','source_ip','outcome'], 'criteria':'At least spray_min_accounts exact scoped accounts; no account exceeds spray_max_per_account failures in the qualifying window.', 'severity':'medium'},
    'success_after_failures': {'required_fields':['username','hostname','source_ip','outcome'], 'criteria':'A success strictly after min_failures failures in the same account/host/source scope, outside timestamp precision plus clock_uncertainty_seconds.', 'severity':'high'},
    'lockout_concentration': {'required_fields':['hostname','event_type','provider'], 'criteria':'At least lockout_min_events explicit source-reported lockouts involving lockout_min_accounts scoped accounts.', 'severity':'medium'},
    'activity_burst': {'required_fields':['hostname','username','outcome'], 'criteria':'At least burst_min_attempts across burst_min_accounts, containing successes and failures, with the declared minimum failure fraction.', 'severity':'medium'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def observation(event):
    """Ignore storage identity and export wrapping, retain source-declared relationships."""
    fields = ('provider', 'event_id', 'category', 'event_type', 'outcome', 'username',
              'account_domain', 'hostname', 'source_ip', 'destination_ip', 'source_port',
              'destination_port', 'original_timestamp')
    attrs = {k: v for k, v in event.get('attributes', {}).items()
             if k not in ('hostname_origin', 'source_provider', 'source_channel')}
    return digest({**{k: event.get(k) for k in fields}, 'attributes': attrs})


def account(event):
    if not event.get('username') or not event.get('hostname'):
        return None
    return (event.get('account_domain'), event['username'], event['hostname'],
            None if event.get('account_domain') else event['provider'])


def explicit_lockout(event):
    return (event.get('provider') == 'Microsoft-Windows-Security-Auditing' and
            event.get('event_id') == '4740' and event.get('event_type') == 'account_lockout') or (
            event.get('provider') in ('sshd', 'login', 'su', 'sudo') and
            event.get('event_type') == 'account_denied' and
            event.get('attributes', {}).get('denial_reason') == 'source reports account locked')


def projected(event, config):
    semantics = event.get('time_semantics', {})
    certainty = semantics.get('certainty')
    allowed = {'source_offset', 'source_utc_field'}
    if config['allow_assumed_time']:
        allowed |= {'profile_offset', 'profile_zone'}
    if certainty not in allowed or semantics.get('precision') in (None, 'minute', 'day'):
        return None
    value = event.get('timestamp_utc')
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        # ORM SQLite strips offsets; the normalized column contains UTC projections only.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def precision_interval(event):
    precision=event['time_semantics'].get('precision','second')
    if precision.startswith('fraction_'):
        digits=precision.removeprefix('fraction_')
        if digits.isdecimal():
            return timedelta(microseconds=10 ** max(0,6-min(6,int(digits))))
    return timedelta(seconds=1)


def evaluate(events, config):
    if len(events) > LIMIT:
        raise ValueError('Event set exceeds evaluation budget.')
    unique, eligible, excluded = {}, [], defaultdict(int)
    for event in sorted(events, key=lambda e: e['semantic_key']):
        key = observation(event)
        if key in unique:
            excluded['duplicate_observation'] += 1
            continue
        unique[key] = event
        if event.get('category') != 'authentication' and not explicit_lockout(event):
            excluded['non_authentication'] += 1
            continue
        time = projected(event, config)
        if time is None:
            excluded['unsupported_time'] += 1
            continue
        eligible.append((time, event))
    eligible.sort(key=lambda pair: (pair[0], pair[1]['semantic_key']))
    results, accounting = [], {}
    window = timedelta(seconds=config['window_seconds'])
    limitations = ['Patterns do not establish malicious intent or actor identity.',
                  'Source clocks are not independently validated or proven synchronized.',
                  'Exact repeated observations are counted once; copied logs are not independent corroboration.']

    def emit(rule, group, members, explanation, severity='medium'):
        keys = sorted(e['semantic_key'] for _, e in members)
        results.append(dict(rule_id='auth.' + rule, rule_version=VERSION,
            title=rule.replace('_', ' ').capitalize() + ' candidate', summary=explanation,
            severity=severity, severity_rationale=('Review priority based on the declared threshold and observed pattern; not compromise probability.'),
            entities={'group': list(group)}, event_keys=keys, count=len(keys),
            time_start=members[0][0].isoformat(), time_end=members[-1][0].isoformat(),
            limitations=limitations + (['Profile-based time assumptions were permitted.'] if config['allow_assumed_time'] else [])))

    for rule in RULES:
        groups = defaultdict(list)
        for time, event in eligible:
            identity = account(event)
            if rule in ('repeated_failures', 'success_after_failures'):
                if not identity:
                    continue
                group = identity
                if rule == 'success_after_failures' or config['grouping'] == 'account_host_source':
                    if not event.get('source_ip'):
                        continue
                    group += (event['source_ip'],)
                elif config['grouping'] == 'host' and rule == 'repeated_failures':
                    group = (event['hostname'], event['provider'])
            elif rule == 'password_spray':
                if not identity or not event.get('source_ip'):
                    continue
                group = (event['source_ip'], event['hostname'], event.get('account_domain'), identity[3])
            else:
                if not event.get('hostname'):
                    continue
                group = (event['hostname'], event.get('account_domain'), event['provider'])
            groups[group].append((time, event))
        before = len(results)
        for group in sorted(groups, key=lambda g: json.dumps(g)):
            current = deque()
            counts = defaultdict(int)
            outcomes = defaultdict(int)
            for time, event in groups[group]:
                while current and time + precision_interval(event) - current[0][0] > window:
                    _, expired = current.popleft()
                    identity = account(expired)
                    if identity in counts:
                        counts[identity] -= 1
                        if not counts[identity]:
                            del counts[identity]
                    outcomes[expired['outcome']] -= 1
                failure = event['outcome'] == 'failure'
                lockout = explicit_lockout(event)
                if rule == 'success_after_failures':
                    if event['outcome'] == 'success':
                        # Second-resolution timestamps represent intervals, not exact instants.
                        prior = [(t,e) for t,e in current if time - t > precision_interval(e) + timedelta(seconds=config['clock_uncertainty_seconds'])]
                        if len(prior) >= config['min_failures']:
                            emit(rule, group, prior + [(time,event)], 'A success followed the required failures for the same exact account, host and source IP. This does not establish compromise or a shared actor.', 'high')
                            current.clear()
                    elif failure:
                        current.append((time,event))
                    continue
                if rule in ('repeated_failures', 'password_spray') and not failure:
                    continue
                if rule == 'lockout_concentration' and not lockout:
                    continue
                if rule == 'activity_burst' and event['outcome'] not in ('success', 'failure'):
                    continue
                current.append((time,event))
                if account(event):
                    counts[account(event)] += 1
                outcomes[event['outcome']] += 1
                triggers = {
                    'repeated_failures': len(current) >= max(config['min_failures'], config['min_occurrences']),
                    'password_spray': len(counts) >= config['spray_min_accounts'] and max(counts.values(), default=0) <= config['spray_max_per_account'],
                    'lockout_concentration': len(current) >= config['lockout_min_events'] and len(counts) >= config['lockout_min_accounts'],
                    'activity_burst': len(current) >= config['burst_min_attempts'] and len(counts) >= config['burst_min_accounts'] and
                        outcomes['success'] > 0 and outcomes['failure']/len(current) >= config['burst_min_failure_fraction'],
                }
                if triggers.get(rule):
                    text = {
                        'repeated_failures': 'Repeated failed authentications meet the configured count and time window. A brute-force hypothesis requires analyst validation.',
                        'password_spray': 'One source IP has failures against distinct scoped accounts within the configured window. Shared NAT, services or misconfiguration may explain the pattern.',
                        'lockout_concentration': 'Explicit source-reported account lockouts meet the configured concentration threshold. Ordinary failures are not classified as lockouts.',
                        'activity_burst': 'Mixed successful and failed authentication across multiple scoped accounts meets the configured volume and failure fraction. This is a threshold-based burst, not a learned anomaly.',
                    }[rule]
                    emit(rule, group, list(current), text)
                    current.clear()
                    counts.clear()
                    outcomes.clear()
        proposals = results[before:]
        del results[before:]
        cap = config['result_limit']
        results.extend(proposals[:cap])
        accounting[rule] = {'candidates':len(proposals), 'returned':min(len(proposals),cap), 'omitted':max(0,len(proposals)-cap),
                            'eligible_required_fields':sum(len(g) for g in groups.values()),
                            'excluded_required_fields':len(eligible)-sum(len(g) for g in groups.values())}
    for result in results:
        result['configuration'] = config
        result['semantic_key'] = digest(result)
    return results, {'evaluated':len(events), 'eligible':len(eligible), 'excluded':dict(excluded),
                     'rules':accounting, 'result_count':len(results), 'budget_exhausted':False,
                     'window_policy':'Earliest qualifying non-overlapping rolling windows per exact group.'}
