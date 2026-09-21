"""Character/color metadata with typed identities and unmodified color records."""
from collections import defaultdict


def character_metadata(tables):
    characters = tables.rows('mst_character')
    colors = tables.rows('mst_color_code')
    by_character, by_group = defaultdict(list), defaultdict(list)
    for row in characters:
        by_character[row.get('CharacterId')].append(row)
        by_group[row.get('CharacterGroupCode')].append(row)
    color_records = []
    for row in colors:
        code, target = row.get('ColorTargetType'), row.get('ColorTargetId')
        matches = by_character.get(target, []) if code == 1 else by_group.get(target, []) if code == 2 else []
        status = ('unsupported_target_type' if code not in (1, 2) else
                  'missing_target' if not matches else
                  'ambiguous_character' if code == 1 and len(matches) != 1 else 'linked')
        color_records.append({'Raw': row, 'TargetStatus': status,
                              'TargetKey': 'CharacterId' if code == 1 else 'CharacterGroupCode' if code == 2 else None,
                              'CharacterRecords': matches, 'LocationMeaning': 'unconfirmed'})
    return {'Characters': characters, 'Colors': color_records,
            'GroupBasis': 'membership_by_CharacterGroupCode_not_a_separate_department_table',
            'ProfilePolicy': 'raw_metadata_not_verified_editorial_biography',
            'ColorPolicy': 'raw_codes_only_not_applied_to_GUI'}
