"""Date-window evidence, independent of account unlock and record inclusion."""
from datetime import datetime, timezone


def assessment_time(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('as_of 必须包含时区，例如 2026-09-09T00:00:00+00:00')
    return result.astimezone(timezone.utc)


def date_window(start, end, *, as_of, active=True):
    now = assessment_time(as_of)
    result = {'Status': 'unknown', 'AsOf': now.isoformat(), 'Timezone': 'UTC',
              'RawStart': start, 'RawEnd': end, 'IsActive': active,
              'AccountUnlock': 'not_assessed', 'Boundary': '[start,end)'}
    try:
        first = assessment_time(start) if start else None
        last = assessment_time(end) if end else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        result['Reason'] = 'invalid_or_timezone_missing'
        return result
    if first and first.year >= 3000:
        result.update(Status='unreleased_placeholder', Reason='placeholder_start')
        return result
    if last and 3000 <= last.year < 9999:
        result.update(Status='unreleased_placeholder', Reason='placeholder_end')
        return result
    if last and last.year == 9999:
        last = None
        result['EndUnbounded'] = True
    if first is None or (last is None and not result.get('EndUnbounded')):
        result['Reason'] = 'missing_boundary'
    elif last is not None and last <= first:
        result['Reason'] = 'invalid_interval'
    elif now < first:
        result['Status'] = 'scheduled'
    elif last is not None and now >= last:
        result['Status'] = 'expired'
    else:
        result['Status'] = 'within_window'
    return result


STATUS_LABELS = {'unknown': '时间状态未知', 'unreleased_placeholder': '占位日期',
                 'scheduled': '未开始', 'expired': '已结束', 'within_window': '日期区间内'}
