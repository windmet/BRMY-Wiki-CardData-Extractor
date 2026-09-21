"""Regression tests for GROOVE drop/consumable source joins.

Drop into tests/test_groove_drop.py after replacing toolkit/domains/groove.py.
"""
import unittest

from toolkit.core.tables import TableCatalog
from toolkit.domains.groove import build_dataset


def _catalog():
    names = [
        "mst_character",
        "mst_character_card",
        "mst_item",
        "mst_item_groove_stamina_recover",
        "mst_music",
        "mst_groove_music",
        "mst_groove_music_bonus_runner",
        "mst_groove_card_level_exp",
        "mst_groove_runner_bonus",
        "mst_groove_music_stage",
        "mst_groove_relation",
        "mst_groove_constant",
        "mst_groove_wish_list_item",
        "mst_groove_wish_list_lottery_rate_level",
        "mst_groove_chance_box_color",
        "mst_groove_play_quality_reward_rate",
        "mst_groove_music_unlock_condition",
        "mst_spin_film",
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
            {"CharacterCardId": 1, "CharacterId": 1, "IsActive": True},
            {"CharacterCardId": 2, "CharacterId": 2, "IsActive": True},
        ],
        [
            {"ItemId": 1, "IsActive": True, "ItemName": "Crystal",
             "ItemNameMultiLine": "Crystal", "ItemTypeCode": 1,
             "ItemRarityCode": 99, "ItemAttributeCode": 0,
             "ItemGroupCode": 0, "ItemRouteCode": 0,
             "ItemDescription1": "", "ItemDescription2": "",
             "ItemDescription3": "", "ItemFileName": "crystal"},
            {"ItemId": 3, "IsActive": True, "ItemName": "Coin",
             "ItemNameMultiLine": "Coin", "ItemTypeCode": 4,
             "ItemRarityCode": 1, "ItemAttributeCode": 0,
             "ItemGroupCode": 0, "ItemRouteCode": 0,
             "ItemDescription1": "", "ItemDescription2": "",
             "ItemDescription3": "", "ItemFileName": "coin"},
            {"ItemId": 559, "IsActive": True, "ItemName": "Shoes Charge",
             "ItemNameMultiLine": "Shoes Charge", "ItemTypeCode": 23,
             "ItemRarityCode": 100, "ItemAttributeCode": 0,
             "ItemGroupCode": 0, "ItemRouteCode": 0,
             "ItemDescription1": "recover", "ItemDescription2": "recover",
             "ItemDescription3": "recover", "ItemFileName": "shoe"},
            {"ItemId": 560, "IsActive": True, "ItemName": "Drink A",
             "ItemNameMultiLine": "Drink A", "ItemTypeCode": 24,
             "ItemRarityCode": 100, "ItemAttributeCode": 0,
             "ItemGroupCode": 0, "ItemRouteCode": 0,
             "ItemDescription1": "timing", "ItemDescription2": "timing",
             "ItemDescription3": "timing", "ItemFileName": "drink_a"},
            {"ItemId": 563, "IsActive": True, "ItemName": "Drink D",
             "ItemNameMultiLine": "Drink D", "ItemTypeCode": 24,
             "ItemRarityCode": 100, "ItemAttributeCode": 0,
             "ItemGroupCode": 0, "ItemRouteCode": 0,
             "ItemDescription1": "better items", "ItemDescription2": "better items",
             "ItemDescription3": "better items", "ItemFileName": "drink_d"},
        ],
        [
            {"ItemId": 1, "IsActive": True, "RecoveryAmount": 5},
            {"ItemId": 559, "IsActive": True, "RecoveryAmount": 5},
        ],
        [
            {"MusicId": 10, "IsActive": True, "DisplayName": "Track",
             "ArtistName": "Artist", "ArtistNameInformal": ""},
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
        [
            {"ConstantKey": 1, "IsActive": True,
             "RelationLotteryRateDenominator": 100,
             "WishListItemLotteryRateDenominator": 10_000_000,
             "ChanceBoxPinCustomItemLotteryRateMax": 2_500_000,
             "ChanceBoxWishListItemMaxRate": 3_000_000,
             "ConsumeGrooveStaminaRecoveryCrystal": 5,
             "GrooveBoostItemId1": 560,
             "GrooveBoostItemId4": 563,
             "MaxScore": 1_000_000},
        ],
        [
            {"ItemId": 3, "IsActive": True, "LotteryRate": 1_940_741,
             "ReleaseDateTime": "2001-01-01T00:00:00+00:00",
             "EndTime": "9999-01-01T00:00:00+00:00", "SortOrder": 0},
        ],
        [
            {"GrooveWishListLotteryRateLevelId": 1, "IsActive": True,
             "BorderLotteryRate": 4000, "Text": "rare"},
        ],
        [
            {"ChanceBoxItemRarity": 1, "ChanceBoxColor": 1,
             "IsActive": True, "LotteryRate": 100},
        ],
        [
            {"PlayQualityRewardRateId": 1, "IsActive": True,
             "Rainbow": 100, "Gold": 100, "Silver": 100, "Copper": 100},
            {"PlayQualityRewardRateId": 2, "IsActive": True,
             "Rainbow": 125, "Gold": 100, "Silver": 75, "Copper": 50},
        ],
        [],
        [
            {"FilmId": 22, "IsActive": True, "CharacterIds": [2, 1],
             "FilmRarityCode": 2, "SpinSetIds": [200001]},
        ],
    ])


def test_direct_item_links_are_joined_but_unproven_links_stay_separate():
    result = build_dataset(_catalog())

    assert [item["ItemId"] for item in result["BoostItems"]] == [560, 563]
    assert result["BoostItems"][0]["ItemName"] == "Drink A"

    assert result["StaminaRecoveryItems"][1]["ItemId"] == 559
    assert result["StaminaRecoveryItems"][1]["RecoveryAmount"] == 5

    assert result["WishListItems"][0]["ItemName"] == "Coin"
    assert result["WishListItems"][0]["LotteryRate"] == 1_940_741
    assert result["DropConstants"][0]["WishListItemLotteryRateDenominator"] == 10_000_000

    # Raw profile tables are exported, but the extractor does NOT claim they are
    # foreign-key linked to ItemId 563 or ItemRarityCode.
    assert result["PlayQualityRewardRates"][1]["PlayQualityRewardRateId"] == 2
    unresolved = {row["Key"] for row in result["UnresolvedAssociations"]}
    assert "boost_item_to_play_quality_reward_rate" in unresolved
    assert "item_rarity_to_chance_box_item_rarity" in unresolved
    assert "wish_list_rate_level_application" in unresolved

    # Missing achievement tables in this drop-only fixture fail closed.
    assert all(issue['Status'] == 'unresolved_stage_challenge' for issue in result['Issues'])


class GrooveDropTests(unittest.TestCase):
    def test_direct_links(self):
        test_direct_item_links_are_joined_but_unproven_links_stay_separate()

    def test_missing_item_is_an_audit_error_not_a_guessed_join(self):
        tables = _catalog()
        tables.rows('mst_groove_wish_list_item')[0]['ItemId'] = 999
        result = build_dataset(tables)
        self.assertEqual('', result['WishListItems'][0]['ItemName'])
        self.assertIn('groove_wish_list_missing_item', [row['Status'] for row in result['Issues']])

    def test_inactive_drink_is_not_joined(self):
        tables = _catalog()
        tables.rows('mst_item')[-1]['IsActive'] = False
        result = build_dataset(tables)
        self.assertIn('groove_boost_item_missing_item', [row['Status'] for row in result['Issues']])

    def test_duplicate_item_and_wish_ids_are_not_silently_accepted(self):
        tables = _catalog()
        tables.rows('mst_item').append(dict(tables.rows('mst_item')[0]))
        tables.rows('mst_groove_wish_list_item').append(dict(tables.rows('mst_groove_wish_list_item')[0]))
        statuses = [row['Status'] for row in build_dataset(tables)['Issues']]
        self.assertIn('duplicate_drop_identity', statuses)
        self.assertIn('duplicate_groove_wish_list_item', statuses)

    def test_future_external_references_remain_review_only(self):
        tables = _catalog()
        tables.rows('mst_item')[-1].update(PlayQualityRewardRateId=2, ChanceBoxItemRarity=1)
        result = build_dataset(tables)
        self.assertEqual(2, sum(row['Status'] == 'needs_review' for row in result['UnresolvedAssociations']))
        self.assertNotIn('PlayQualityRewardRateId', result['BoostItems'][-1])
        self.assertNotIn('ChanceBoxItemRarity', result['BoostItems'][-1])

    def test_raw_facts_survive_without_derived_probability_or_labels(self):
        result = build_dataset(_catalog())
        wish = result['WishListItems'][0]
        self.assertEqual(wish['LotteryRate'], wish['Raw']['LotteryRate'])
        self.assertEqual('Coin', wish['RawItem']['ItemName'])
        self.assertNotIn('Probability', wish)
        self.assertNotIn('GrooveWishListLotteryRateLevelId', wish)
        self.assertEqual(100, result['BoostItems'][0]['ItemRarityCode'])
