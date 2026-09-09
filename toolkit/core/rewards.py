"""Typed Wiki reward references; no cross-type or title-screen fallback."""
from .tables import TableCatalog
from collections import defaultdict


def reward_reference_index(tables):
    """Reverse typed reward references without claiming an acquisition entry."""
    result = defaultdict(list)
    for table, group_key in (
        ('mst_direct_reward', 'DirectRewardGroupId'), ('mst_present', 'PresentId'),
        ('mst_event_ojt_prize_box_reward', 'PrizeBoxRewardId'),
        ('mst_event_ojt_prize_box_reward_random', 'PrizeBoxRewardRandomId'),
    ):
        for row in tables.rows(table, active_only=True):
            key = (row.get('RewardTypeCode'), row.get('RewardTargetId'))
            result[key].append({'SourceTable': table, 'GroupKey': group_key,
                                'GroupId': row.get(group_key), 'RawReward': row})
    return dict(result)


# key, label, table, primary key, human-readable field
REWARD_TARGETS = {
    1: ('card', '卡牌', 'mst_character_card', 'CharacterCardId', 'CharacterCardName'),
    2: ('item', '道具', 'mst_item', 'ItemId', 'ItemName'),
    3: ('home_background', '主页背景', 'mst_home_background', 'BackgroundId', 'DisplayName'),
    4: ('costume_model', '角色服装', 'mst_costume_model', 'CostumeModelId', 'CostumeModelName'),
    5: ('costume_mini', '迷你角色服装', 'mst_costume_mini', 'CostumeMiniId', 'CostumeMiniName'),
    6: ('honor', '称号', 'mst_honor', 'HonorId', 'HonorName'),
    7: ('pin', 'Pin', 'mst_pin', 'PinId', 'PinName'),
    8: ('music', '音乐', 'mst_music', 'MusicId', 'DisplayName'),
    9: ('spin_album_release_item', 'Spin相册解锁道具', 'mst_spin_album_release_item',
        'SpinAlbumReleaseItemId', 'DisplayName'),
    10: ('home_voice_product', '主页语音', 'mst_home_voice_product', 'HomeVoiceProductId', 'DisplayName'),
    101: ('ingredient', '活动材料', 'mst_event_ingredient', 'IngredientId', 'IngredientName'),
}
REWARD_TYPE_MAP = {code: {'Key': spec[0], 'Label': spec[1]}
                   for code, spec in REWARD_TARGETS.items()}
REWARD_TYPE_MAP.update({
    99: {'Key': 'information', 'Label': '信息'},
    100: {'Key': 'event_item', 'Label': '活动道具'},
    102: {'Key': 'travel_coin', 'Label': '旅行币'},
})


class RewardResolver:
    """Resolve targets and reward groups, retaining unresolved evidence.

    Target identity and display-name availability are separate. Historical or
    inactive target records remain identifiable, but are never called available.
    Group expansion follows active reward rows, matching existing event exports.
    """

    def __init__(self, tables: TableCatalog, *, card_names=None):
        self.tables = tables
        self.card_names = card_names or {}
        self.issues = []
        self._targets = {
            code: tables.group_by(spec[2], spec[3], active_only=False, required=False)
            for code, spec in REWARD_TARGETS.items()
        }
        self._groups = {
            'mst_direct_reward': tables.group_by('mst_direct_reward', 'DirectRewardGroupId', required=False),
            'mst_present': tables.group_by('mst_present', 'PresentId', required=False),
        }

    def resolve(self, row):
        code, target = row.get('RewardTypeCode'), row.get('RewardTargetId')
        kind = REWARD_TYPE_MAP.get(code, {'Key': f'type_{code}', 'Label': f'未知类型{code}'})
        result = {
            'RewardTypeCode': code, 'RewardType': kind['Key'],
            'RewardTypeLabel': kind['Label'], 'RewardTargetId': target,
            'RewardName': f"{kind['Label']}({target})", 'RewardCount': row.get('RewardCount'),
            'Resolution': 'unknown_type', 'RawReward': dict(row),
        }
        if code in REWARD_TARGETS:
            _, _, table, key, field = REWARD_TARGETS[code]
            result.update(TargetTable=table, TargetKey=key)
            matches = self._targets[code].get(target, [])
            if table not in self.tables.names:
                result['Resolution'] = 'missing_table'
            elif not matches:
                result['Resolution'] = 'missing_target'
            elif len(matches) != 1:
                result['Resolution'] = 'ambiguous_target'
            else:
                record = matches[0]
                result.update(Resolution='resolved', TargetActive=record.get('IsActive', True),
                              TargetRecord=dict(record))
                name = self.card_names.get(target) if code == 1 else record.get(field)
                if not name:
                    name = record.get(field)
                if name and str(name).strip():
                    result['RewardName'] = str(name)
                else:
                    result['Resolution'] = 'name_unavailable'
        elif code in (99, 100, 102):
            # No verified global target table: e.g. travel coin uses target 0.
            result['Resolution'] = 'context_required'
        if result['Resolution'] != 'resolved':
            self.issues.append({k: result[k] for k in (
                'RewardTypeCode', 'RewardTargetId', 'Resolution', 'RawReward')})
        return result

    def _expand(self, table, key, sequence, group_id):
        if group_id in (None, 0):
            return []
        rows = self._groups[table].get(group_id, [])
        if not rows:
            self.issues.append({'Resolution': 'missing_reward_group',
                                'Table': table, 'Key': key, 'Id': group_id})
        return [dict(self.resolve(row), SourceTable=table, SourceKey=key, SourceId=group_id)
                for row in sorted(rows, key=lambda r: r.get(sequence, 0))]

    def direct(self, group_id):
        return self._expand('mst_direct_reward', 'DirectRewardGroupId', 'DirectRewardSequenceNo', group_id)

    def present(self, present_id):
        return self._expand('mst_present', 'PresentId', 'PresentSequenceNo', present_id)
