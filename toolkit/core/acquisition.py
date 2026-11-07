"""Verified reward-group consumers; unsupported consumers remain unresolved."""
from collections import defaultdict

SECTION_SOURCES = (
    ('mst_main_story_section', ('MainStoryThreadNo', 'MainStoryChapterNo', 'MainStorySectionNo'),
     'mst_main_story_chapter', ('MainStoryThreadNo', 'MainStoryChapterNo'), 'story_main', 'ReadDirectRewardGroupId', 'mst_direct_reward'),
    ('mst_character_story_section', ('CharacterId', 'CharacterStoryChapterNo', 'CharacterStorySectionNo'),
     'mst_character_story', ('CharacterId', 'CharacterStoryChapterNo'), 'story_character', 'ReadDirectRewardGroupId', 'mst_direct_reward'),
    ('mst_character_card_story_section', ('CharacterCardId', 'CharacterCardStorySectionNo'),
     'mst_character_card_story', ('CharacterCardId',), 'story_card', 'ReadDirectRewardGroupId', 'mst_direct_reward'),
    ('mst_login_bonus_daily_sequence', ('LoginBonusDailyId', 'Sequence'),
     'mst_login_bonus_daily', ('LoginBonusDailyId',), 'login_daily', 'PresentId', 'mst_present'),
    ('mst_login_bonus_special_sequence', ('LoginBonusSpecialId', 'Sequence'),
     'mst_login_bonus_special', ('LoginBonusSpecialId',), 'login_special', 'PresentId', 'mst_present'),
    ('mst_login_bonus_total', ('LoginBonusTotalId',), None, (), 'login_total', 'PresentId', 'mst_present'),
    ('mst_login_bonus_user_birthday', ('Year',), None, (), 'login_user_birthday', 'PresentId', 'mst_present'),
)

SUPPORTED_FIELDS = {
    'mst_event_ranking_reward': ('PresentId',),
    'mst_event_sales_reward': ('DirectRewardGroupId',),
    'mst_event_accumulate_item_reward': ('DirectRewardGroupId',),
    'mst_event_recipe': ('DirectRewardGroupId',),
    'mst_event_story_section': ('ReadDirectRewardGroupId',),
    'mst_exchange_product': ('DirectRewardGroupId',),
    'mst_mission_sequence': ('DirectRewardGroupId',),
    'mst_present_serial_code': ('PresentId',),
    'mst_character_birthday_login_bonus_sequence': ('PresentId',),
    'mst_character_birthday': ('TapRewardNo1', 'TapRewardNo2', 'TapRewardNo3', 'TapRewardSecretPin'),
    'mst_event_ojt_prize_box': ('PrizeBoxRewardId', 'PrizeBoxRewardRandomId'),
    'mst_event_ojt_training_reward': ('DirectRewardGroupId',),
}
SUPPORTED_FIELDS.update({table: (field,) for table, _, _, _, _, field, _ in SECTION_SOURCES})

SOURCE_LABELS = {'event': '活动奖励', 'exchange': '兑换所', 'event_mission': '活动任务',
                 'campaign_mission': 'Campaign任务', 'mission': '一般任务', 'serial_code': '序列码',
                 'character_birthday': '角色年度生日', 'ojt_training': 'OJT训练',
                 'ojt_fixed_box': 'OJT固定奖励池', 'ojt_random_box': 'OJT随机奖励池'}
SOURCE_LABELS.update({'story_main': '主线阅读奖励', 'story_character': '角色剧情阅读奖励',
                      'story_card': '卡牌剧情阅读奖励', 'login_daily': '每日登录奖励',
                      'login_special': '特别登录奖励', 'login_total': '累计登录奖励',
                      'login_user_birthday': '玩家生日登录奖励'})


def acquisition_coverage(tables):
    """Inventory recognizable reference fields, not a claim to all game sources."""
    fields = []
    reward_tables = {'mst_direct_reward', 'mst_present', 'mst_event_ojt_prize_box_reward',
                     'mst_event_ojt_prize_box_reward_random'}
    for table in tables.names:
        if table in reward_tables:
            continue
        rows = tables.rows(table, active_only=True)
        keys = {key for row in rows for key in row
                if key.endswith(('DirectRewardGroupId', 'PresentId')) or key in SUPPORTED_FIELDS.get(table, ())}
        for key in sorted(keys):
            fields.append({'SourceTable': table, 'Field': key,
                           'NonzeroRows': sum(row.get(key) not in (None, 0, '') for row in rows),
                           'AdapterStatus': 'supported' if key in SUPPORTED_FIELDS.get(table, ()) else 'not_adapted'})
    return {'Scope': 'active_rows_recognized_reference_fields_only', 'CompleteAcquisitionGuide': False,
            'Fields': fields}


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
        else:
            issues.append({'Status': 'missing_or_ambiguous_exchange', 'Table': 'mst_exchange_product', 'Raw': row})
    for row in tables.rows('mst_mission_sequence', active_only=True):
        matched = missions.get(row.get('MissionId'), [])
        if len(matched) != 1:
            issues.append({'Status': 'missing_or_ambiguous_mission', 'Table': 'mst_mission_sequence', 'Raw': row})
            continue
        mission = matched[0]; code = mission.get('SpecialTabTypeCode'); target = mission.get('SpecialTabTargetId')
        if code not in (0, 1, 2):
            issues.append({'Status': 'unsupported_mission_owner_type', 'Table': 'mst_mission_sequence',
                           'Raw': row, 'Mission': mission})
            continue
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
    for table, keys, parent_table, parent_keys, kind, field, reward_table in SECTION_SOURCES:
        parents = defaultdict(list)
        for parent in tables.rows(parent_table, active_only=True) if parent_table else []:
            parents[tuple(parent.get(key) for key in parent_keys)].append(parent)
        rows_by_key = defaultdict(list)
        for row in tables.rows(table, active_only=True):
            rows_by_key[tuple(row.get(key) for key in keys)].append(row)
        for key, rows in rows_by_key.items():
            if None in key or len(rows) != 1:
                issues.append({'Status': 'missing_or_ambiguous_source_key', 'Table': table, 'Key': list(key), 'Rows': rows})
                continue
            row = rows[0]
            parent_key = tuple(row.get(key) for key in parent_keys)
            matched = parents.get(parent_key, []) if parent_table else []
            if parent_table and (None in parent_key or len(matched) != 1):
                issues.append({'Status': 'missing_or_ambiguous_source_parent', 'Table': table,
                               'ParentTable': parent_table, 'Key': list(key), 'Raw': row})
                continue
            add(reward_table, row.get(field), table, row, kind, list(key),
                row.get('TitleName') or SOURCE_LABELS[kind], matched)
    return dict(result), issues
