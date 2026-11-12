"""Player-facing families, with the raw discriminator evidence retained.

Codes follow Coly.S2BShared.Enums.EventFormat / EventAType in the 2.1.0 client.
"""

FAMILIES = {
    1: ('exchange', '交换所活动'),         # A
    2: ('non_medal', '无奖章活动'),        # ANonMedal
    3: ('making', '营业（摇酒）活动'),      # B
    4: ('making', '营业（摇酒）活动'),      # BSpecial
    5: ('ojt', 'OJT'),                    # C
    6: ('vignette', 'Vignette 活动'),     # AAccumulateItem
}
NON_MEDAL_SUBTYPES = {
    2: ('travel_prequel', 'Travel / Prequel'),         # ExchangeAndRanking
    4: ('no_ranking', '无排名特别活动'),                  # NoRanking: 半周年、新年、RMX FES
    5: ('step_mission', '阶段任务周年活动'),               # SpecialStepMission: 整周年
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
        subtype, sublabel = NON_MEDAL_SUBTYPES.get(a_type, ('unknown', f'未知 EventAType ({a_type})'))
        # The shared type code cannot distinguish these named series on its own.
        if a_type == 2:
            title = event.get('EventTitle', '')
            for prefix in ('Prequel', 'Travelogue'):
                if title == prefix or title.startswith(prefix + ' '):
                    subtype, sublabel = prefix.lower(), prefix
                    basis.append('EventTitle prefix')
                    break
    elif code in (3, 4):
        subtype, sublabel = ('standard', '常规') if code == 3 else ('special', '特别版')
    elif code in (5, 6):
        subtype, sublabel = family, label
    return {
        'Family': family, 'FamilyLabel': label,
        'Subtype': subtype, 'SubtypeLabel': sublabel,
        'DisplayLabel': f'{label} · {sublabel}' if code in (2, 4) else label,
        'EventFormat': code, 'EventAType': a_type, 'Basis': basis,
        'Status': 'unknown' if 'unknown' in (family, subtype) else 'classified',
    }
