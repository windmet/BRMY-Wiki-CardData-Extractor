"""Resolve event missions by typed owner, preserving sequence evidence."""
from collections import Counter, defaultdict

from ..core.rewards import RewardResolver


def extract_event_missions(tables):
    events = tables.group_by('mst_event', 'EventId', required=False)
    masters = tables.group_by('mst_mission', 'MissionId', required=False)
    sequences = tables.group_by('mst_mission_sequence', 'MissionId', required=False)
    resolver = RewardResolver(tables)
    result = defaultdict(list)
    audit = {'EventMissions': [], 'ExcludedOwners': [], 'Issues': []}
    for mid, records in sorted(masters.items()):
        selected = [r for r in records if r.get('SpecialTabTypeCode') == 1]
        for row in records:
            if row.get('SpecialTabTypeCode') != 1:
                audit['ExcludedOwners'].append({
                    'MissionId': mid, 'SpecialTabTypeCode': row.get('SpecialTabTypeCode'),
                    'SpecialTabTargetId': row.get('SpecialTabTargetId'),
                })
        if not selected:
            continue
        if len(records) != 1:
            audit['Issues'].append({'MissionId': mid, 'Status': 'ambiguous_mission', 'Records': records})
            continue
        row = selected[0]
        owner = row.get('SpecialTabTargetId')
        matches = events.get(owner, [])
        entry = {'MissionId': mid, 'EventId': owner, 'RawMission': row, 'Sequences': []}
        audit['EventMissions'].append(entry)
        if len(matches) != 1:
            audit['Issues'].append({'MissionId': mid, 'EventId': owner,
                                    'Status': 'missing_event' if not matches else 'ambiguous_event'})
            continue
        seqs = sequences.get(mid, [])
        if not seqs:
            audit['Issues'].append({'MissionId': mid, 'Status': 'missing_sequence'})
        counts = Counter(s.get('MissionSequenceNo') for s in seqs)
        for seq in sorted(seqs, key=lambda s: s.get('MissionSequenceNo', 0)):
            number = seq.get('MissionSequenceNo')
            if counts[number] != 1:
                audit['Issues'].append({'MissionId': mid, 'SequenceNo': number,
                                        'Status': 'ambiguous_sequence', 'RawSequence': seq})
                continue
            before = len(resolver.issues)
            rewards = resolver.direct(seq.get('DirectRewardGroupId'))
            for issue in resolver.issues[before:]:
                audit['Issues'].append(dict(issue, MissionId=mid, SequenceNo=number))
            description = row.get('Description', '') or ''
            border = seq.get('Border')
            entry['Sequences'].append({
                'SequenceNo': number, 'Border': border,
                'Description': description.replace('#', str(border)) if border is not None else description,
                'IsHidden': seq.get('IsHidden'), 'OnlyAccounting': seq.get('OnlyAccounting'),
                'Rewards': rewards, 'RawSequence': seq,
            })
        result[owner].append(entry)
    return dict(result), audit
