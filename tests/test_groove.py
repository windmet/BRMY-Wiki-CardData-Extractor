"""Focused tests for toolkit.domains.groove."""
from toolkit.core.tables import TableCatalog
from toolkit.domains.groove import build_dataset
import unittest
from toolkit.core.domain_contracts import validate_domain_input
from toolkit.resolve import build_plan, MASTER_KEY


def _catalog():
    names = [
        "mst_character",
        "mst_music",
        "mst_groove_music",
        "mst_groove_music_bonus_runner",
        "mst_groove_card_level_exp",
        "mst_groove_runner_bonus",
        "mst_groove_music_stage",
        "mst_groove_relation",
        "mst_groove_music_unlock_condition",
        "mst_groove_constant",
        "mst_spin_film",
        "mst_character_card",
        "mst_item",
        "mst_item_groove_stamina_recover",
        "mst_groove_wish_list_item",
        "mst_groove_wish_list_lottery_rate_level",
        "mst_groove_chance_box_color",
        "mst_groove_play_quality_reward_rate",
    ]
    directory = {name: [0, 0] for name in names}
    return TableCatalog([
        directory,
        [
            {"CharacterId": 1, "IsActive": True, "CharacterNameJpn": "A",
             "CharacterNameEng": "A", "CharacterGroupCode": 1,
             "IconFileName": "a", "MiniCharaIconFileName": "a_mini"},
            {"CharacterId": 2, "IsActive": True, "CharacterNameJpn": "B",
             "CharacterNameEng": "B", "CharacterGroupCode": 1,
             "IconFileName": "b", "MiniCharaIconFileName": "b_mini"},
        ],
        [
            {"MusicId": 10, "IsActive": True, "DisplayName": "Track",
             "ArtistName": "Artist", "ArtistNameInformal": "", "MusicType": 1},
        ],
        [
            {"MusicId": 10, "IsActive": True, "GrooveMusicType": 1,
             "ReleaseDateTime": "2026-01-01T00:00:00+00:00",
             "EndTime": "9999-01-01T00:00:00+00:00",
             "GrooveMusicUnlockConditionIdA": 0,
             "GrooveMusicUnlockConditionIdB": 0, "SortOrder": 1},
        ],
        [
            {"MusicId": 10, "CharacterId": 1, "IsActive": True,
             "GrooveRunnerBonusLevel": 2},
        ],
        [
            {"GrooveRunnerStatus": 4, "IsActive": True,
             "CardLevelExpRunner1": 1, "CardLevelExpRunner2": 2,
             "CardLevelExpRunner3": 3, "CardLevelExpRunner4": 4},
        ],
        [
            {"GrooveRunnerBonusLevel": 1, "IsActive": True,
             "CardLevelExpIncreaseCount": 1,
             "ChanceBoxLotteryIncreaseCount": 1},
            {"GrooveRunnerBonusLevel": 2, "IsActive": True,
             "CardLevelExpIncreaseCount": 2,
             "ChanceBoxLotteryIncreaseCount": 2},
        ],
        [
            {"MusicId": 10, "GrooveMusicStageType": 1, "IsActive": True,
             "StageFileName": "track_A", "GrooveMusicStageDifficulty": 3,
             "PreviewMusicCueId": 100, "RelationLotteryRateIncreaseRate": 0,
             "GrooveAchievementRewardId": 1, "GrooveCommonRewardId": 1,
             "GrooveExtraAchievementId1": 1, "GrooveExtraAchievementId2": 2,
             "GrooveExtraAchievementId3": 3, "GrooveExtraAchievementId4": 4},
        ],
        [
            {"GrooveRelationId": 1, "IsActive": True,
             "CharacterIds": [1, 2], "LotteryRate": 33,
             "RelationText": "A+B"},
        ],
        [],
        [
            {"ConstantKey": 1, "GrooveReleaseRank": 2,
             "RelationLotteryRateDenominator": 100, "MaxScore": 1000000},
        ],
        [
            {"FilmId": 22, "IsActive": True, "CharacterIds": [2, 1],
             "FilmRarityCode": 2, "SpinSetIds": [200001]},
        ],
        [{"CharacterId": 1, "IsActive": True}, {"CharacterId": 2, "IsActive": True}],
        [], [], [], [], [], [],
    ])


def check_build_dataset_links_bonus_relation_and_spin():
    result = build_dataset(_catalog())

    assert result["Tracks"][0]["DisplayName"] == "Track"
    assert result["Tracks"][0]["BonusRunnerCount"] == 1

    bonus = result["BonusRunners"][0]
    assert bonus["CharacterName"] == "A"
    assert bonus["GrooveRunnerBonusLevel"] == 2
    assert bonus["CardLevelExpIncreaseCount"] == 2

    relation = result["Relations"][0]
    assert relation["CharacterIds"] == [1, 2]
    assert relation["CharacterSetKey"] == "1|2"
    assert relation["SpinExisting"] is True
    assert relation["SpinFilmId"] == 22

    assert result["RunnerPositions"][0]["Runner4"] == 4
    assert result["Stages"][0]["Side"] == "A"
    assert result["Issues"] == []
    assert all(row['HasStaffCard'] for row in result['Characters'])


class GrooveTests(unittest.TestCase):
    def test_links_and_raw_order(self):
        check_build_dataset_links_bonus_relation_and_spin()

    def test_missing_tables_fail(self):
        with self.assertRaises(KeyError):
            build_dataset(TableCatalog([{}]))
        with self.assertRaises(ValueError):
            validate_domain_input('groove', TableCatalog([{}]))

    def test_masterdata_only_plan(self):
        plan = build_plan(['groove'], {MASTER_KEY: None})
        self.assertEqual([], plan['errors'])
        self.assertEqual([MASTER_KEY], [row['key'] for row in plan['resources']])
