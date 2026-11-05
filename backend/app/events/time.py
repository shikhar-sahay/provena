"""Source-declared timestamps and explicitly configured interpretation assumptions."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.ai.normalize import timestamp_details

MONTHS = {name: i for i, name in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}


def event_time(raw, config):
    result = {'original': raw, 'utc': None, 'certainty': 'missing' if not raw else 'unknown',
              'precision': None, 'assumptions': [], 'warnings': []}
    if not raw:
        return result
    convention = config.get('timestamp_convention', 'source')
    is_yearless = bool(re.match(r'^[A-Z][a-z]{2}\s+\d', raw))
    if (convention == 'iso8601' and is_yearless) or (convention == 'syslog' and not is_yearless):
        result['warnings'].append('Timestamp does not match the selected convention; UTC withheld.')
        return result
    # Windows XML commonly records seven or nine fractional digits. Retain
    # them verbatim; the query projection has explicit microsecond precision.
    projection = re.sub(r'(\d{2}:\d{2}:\d{2}\.)(\d{7,9})', lambda m: m[1] + m[2][:6], raw)
    details = timestamp_details(projection)
    if projection != raw:
        result['warnings'].append('UTC query projection is truncated to microseconds; original fractional timestamp preserved.')
        result['source_fraction_digits'] = len(re.search(r'\.(\d+)', raw)[1])
    naive = None
    if details:
        result['precision'] = details['precision']
        result['source_offset'] = details['source_offset']
        if details['timezone_status'] == 'explicit_offset':
            result.update(utc=details['utc'], certainty='source_offset')
            return result
        naive = datetime.fromisoformat(details['normalized_value'])
    else:
        match = re.fullmatch(r'([A-Z][a-z]{2})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2})', raw)
        if match and match[1] in MONTHS:
            result['precision'] = 'second'
            if config.get('year') is None:
                result['warnings'].append('Yearless source timestamp; no year configured.')
                return result
            try:
                naive = datetime.strptime(f"{config['year']}-{MONTHS[match[1]]:02d}-{int(match[2]):02d} {match[3]}", '%Y-%m-%d %H:%M:%S')
                result['assumptions'].append({'field': 'year', 'value': config['year'], 'origin': 'analyst_profile'})
            except ValueError:
                pass
        if naive is None:
            result['warnings'].append('Unsupported or invalid timestamp representation.')
            return result
    zone = config.get('timezone')
    if not zone:
        result['warnings'].append('Source timezone unknown; UTC is not established.')
        return result
    if raw.endswith(('-00:00', '-0000')):
        result['warnings'].append('Source declares unknown offset; profile timezone is an interpretation assumption.')
    result['assumptions'].append({'field': 'timezone', 'value': zone, 'origin': 'analyst_profile'})
    if re.fullmatch(r'[+-]\d{2}:\d{2}', zone):
        minutes = (int(zone[1:3]) * 60 + int(zone[4:])) * (-1 if zone[0] == '-' else 1)
        result.update(utc=naive.replace(tzinfo=timezone(timedelta(minutes=minutes))).astimezone(timezone.utc).isoformat(), certainty='profile_offset')
        return result
    tz = ZoneInfo(zone)
    possibilities = set()
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(tz).replace(tzinfo=None) == naive:
            possibilities.add(candidate)
    if len(possibilities) == 1:
        result.update(utc=possibilities.pop().isoformat(), certainty='profile_zone')
    else:
        result['certainty'] = 'ambiguous' if possibilities else 'nonexistent'
        result['warnings'].append('Local time is ambiguous or nonexistent in the configured timezone; UTC withheld.')
    return result
