"""Verified reward-group consumers; unsupported consumers remain unresolved."""
from collections import defaultdict


def acquisition_index(tables):
    result = defaultdict(list)
    issues = []
    def owners(table, key):
        return tables.group_by(table, key, required=False)
    events = owners('mst_event', 'EventId')
    exchanges = owners('mst_exchange', 'ExchangeId')
    missions = owners('mst_mission', 'MissionId')
    campaigns = owners('mst_campaign', 'CampaignId')

    def add(reward_table, group, source, raw, kind, owner_id, name, evidence=()):
        if group:
            result[(reward_table, group)].append({'Kind': kind, 'OwnerId': owner_id, 'Name': name,
                'SourceTable': source, 'Raw': raw, 'OwnerEvidence': list(evidence)})

    for table, field, reward_table in (
        ('mst_event_ranking_reward', 'PresentId', 'mst_present'),
        ('mst_event_sales_reward', 'DirectRewardGroupId', 'mst_direct_reward'),
        ('mst_event_accumulate_item_reward', 'DirectRewardGroupId', 'mst_direct_reward'),
        ('mst_event_recipe', 'DirectRewardGroupId', 'mst_direct_reward'),
        ('mst_event_story_section', 'ReadDirectRewardGroupId', 'mst_direct_reward'),
    ):
        for row in tables.rows(table, active_only=True):
            matched = events.get(row.get('EventId'), [])
            if len(matched) == 1:
                add(reward_table, row.get(field), table, row, 'event', row['EventId'], matched[0].get('EventTitle', ''), matched)
            else:
                issues.append({'Status': 'missing_or_ambiguous_event', 'Table': table, 'Raw': row})
    for row in tables.rows('mst_exchange_product', active_only=True):
        matched = exchanges.get(row.get('ExchangeId'), [])
        if len(matched) == 1:
            add('mst_direct_reward', row.get('DirectRewardGroupId'), 'mst_exchange_product', row,
                'exchange', row['ExchangeId'], matched[0].get('ExchangeName', ''), matched)
    for row in tables.rows('mst_mission_sequence', active_only=True):
        matched = missions.get(row.get('MissionId'), [])
        if len(matched) != 1:
            continue
        mission = matched[0]; code = mission.get('SpecialTabTypeCode'); target = mission.get('SpecialTabTargetId')
        parent = events.get(target, []) if code == 1 else campaigns.get(target, []) if code == 2 else []
        if code in (1, 2) and len(parent) != 1:
            issues.append({'Status': 'missing_mission_owner', 'Raw': mission})
            continue
        kind = 'event_mission' if code == 1 else 'campaign_mission' if code == 2 else 'mission'
        add('mst_direct_reward', row.get('DirectRewardGroupId'), 'mst_mission_sequence', row, kind,
            target if code in (1, 2) else row['MissionId'],
            (mission.get('Description', '') or '').replace('#', str(row.get('Border'))), [mission, *parent])
    for row in tables.rows('mst_present_serial_code', active_only=True):
        add('mst_present', row.get('PresentId'), 'mst_present_serial_code', row, 'serial_code', row.get('PresentId'), '序列码兑换')
    for row in tables.rows('mst_character_birthday_login_bonus_sequence', active_only=True):
        add('mst_present', row.get('PresentId'), 'mst_character_birthday_login_bonus_sequence', row,
            'character_birthday', [row.get('CharacterId'), row.get('Year')], '角色年度生日登录奖励')
    for row in tables.rows('mst_character_birthday', active_only=True):
        for field in ('TapRewardNo1', 'TapRewardNo2', 'TapRewardNo3', 'TapRewardSecretPin'):
            add('mst_direct_reward', row.get(field), 'mst_character_birthday', dict(row, RewardField=field),
                'character_birthday', [row.get('CharacterId'), row.get('Year')], '角色年度生日点击奖励')
    shifts = owners('mst_event_ojt_shift', 'OjtShiftId')
    for table in ('mst_event_ojt_prize_box', 'mst_event_ojt_training_reward'):
        for row in tables.rows(table, active_only=True):
            matched = shifts.get(row.get('OjtShiftId'), [])
            event = events.get(matched[0].get('EventId'), []) if len(matched) == 1 else []
            if len(matched) != 1 or len(event) != 1 or event[0].get('EventFormat') != 5:
                issues.append({'Status': 'missing_or_ambiguous_ojt_owner', 'Table': table, 'Raw': row})
                continue
            if table == 'mst_event_ojt_training_reward':
                targets = [('mst_direct_reward', 'DirectRewardGroupId', 'ojt_training')]
            else:
                targets = [('mst_event_ojt_prize_box_reward', 'PrizeBoxRewardId', 'ojt_fixed_box'),
                           ('mst_event_ojt_prize_box_reward_random', 'PrizeBoxRewardRandomId', 'ojt_random_box')]
            for reward_table, field, kind in targets:
                add(reward_table, row.get(field), table, row, kind, event[0]['EventId'],
                    event[0].get('EventTitle', ''), [*matched, *event])
    return dict(result), issues
