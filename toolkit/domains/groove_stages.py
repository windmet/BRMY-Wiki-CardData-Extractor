"""Explicit stage -> achievement -> direct reward joins. No common-reward inference."""
from ..core.rewards import RewardResolver


class StageChallenges:
    def __init__(self, tables):
        self.conditions = tables.group_by('mst_groove_extra_achievement', 'GrooveExtraAchievementId', required=False)
        self.profiles = tables.group_by('mst_groove_achievement_reward', 'GrooveAchievementRewardId', required=False)
        self.groups = tables.group_by('mst_direct_reward', 'DirectRewardGroupId', required=False)
        self.resolver = RewardResolver(tables)

    def project(self, stage, issues):
        challenges = []
        profiles = self.profiles.get(stage.get('GrooveAchievementRewardId'), [])
        profile = profiles[0] if len(profiles) == 1 else None
        for slot in range(1, 5):
            condition_id = stage.get(f'GrooveExtraAchievementId{slot}')
            if not condition_id:
                continue
            matches = self.conditions.get(condition_id, [])
            condition = matches[0] if len(matches) == 1 else None
            group_id = profile.get(f'RewardGrooveExtra{slot}') if profile else None
            rewards = []
            for row in self.groups.get(group_id, []):
                resolved = self.resolver.resolve(row)
                rewards.append({k: resolved.get(k) for k in ('RewardTypeCode', 'RewardTargetId', 'RewardName', 'RewardCount', 'Resolution')})
            status = 'resolved' if condition and profile and rewards and all(r['Resolution'] == 'resolved' for r in rewards) else 'unresolved'
            challenges.append({'Slot': slot, 'AchievementId': condition_id,
                               'Description': condition.get('Description', '') if condition else '',
                               'AchievementType': condition.get('GrooveExtraAchievementType') if condition else None,
                               'Value1': condition.get('Value1') if condition else None,
                               'Value2': condition.get('Value2') if condition else None,
                               'ClearRequireCount': condition.get('ClearRequireCount') if condition else None,
                               'DirectRewardGroupId': group_id, 'Rewards': rewards, 'Resolution': status})
            if status != 'resolved':
                issues.append({'Status': 'unresolved_stage_challenge', 'MusicId': stage.get('MusicId'),
                               'StageType': stage.get('GrooveMusicStageType'), 'Slot': slot, 'AchievementId': condition_id})
        return challenges
