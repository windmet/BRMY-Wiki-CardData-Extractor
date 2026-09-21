"""Player-facing families, with the raw discriminator evidence retained."""

FAMILIES = {
    1: ('points', '常规积分活动'),
    2: ('story_travel', '剧情 / Travel 活动'),
    3: ('making', 'Making / 摇酒活动'),
    4: ('making', 'Making / 摇酒活动'),
    5: ('ojt', 'OJT'),
    6: ('vignette', 'Vignette / 累积道具活动'),
}


def classify_event(event, event_a=None):
    code = event.get('EventFormat')
    a_type = (event_a or {}).get('EventAType')
    family, label = FAMILIES.get(code, ('unknown', '未知活动类型'))
    subtype, sublabel = 'unknown', '未知子型'
    basis = ['EventFormat']
    if code == 1:
        subtype, sublabel = 'standard', '常规'
    elif code == 2:
        basis.append('mst_event_a.EventAType')
        subtype, sublabel = {
            2: ('travel_prequel', 'Travel / Prequel'),
            4: ('special', '特殊活动'),
            5: ('anniversary', '周年活动'),
        }.get(a_type, ('unknown', f'未知 EventAType ({a_type})'))
        # The shared type code cannot distinguish these named series on its own.
        if a_type == 2:
            title = event.get('EventTitle', '')
            for prefix in ('Prequel', 'Travelogue'):
                if title == prefix or title.startswith(prefix + ' '):
                    subtype, sublabel = prefix.lower(), prefix
                    basis.append('EventTitle prefix')
                    break
    elif code in (3, 4):
        subtype, sublabel = ('standard', '常规') if code == 3 else ('special', '特殊版本')
    elif code in (5, 6):
        subtype, sublabel = family, label
    return {
        'Family': family, 'FamilyLabel': label,
        'Subtype': subtype, 'SubtypeLabel': sublabel,
        'DisplayLabel': f'{label} · {sublabel}' if code in (2, 4) else label,
        'EventFormat': code, 'EventAType': a_type, 'Basis': basis,
        'Status': 'unknown' if 'unknown' in (family, subtype) else 'classified',
    }
