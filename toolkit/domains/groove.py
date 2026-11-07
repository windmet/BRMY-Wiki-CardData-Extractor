"""GROOVE mode source extraction for team/runner optimizers.

This module deliberately exports source facts only. It does not choose an
"optimal" team, because the optimizer objective (EXP / chance-box rarity /
relation preference / expected runner status) belongs in a later UI layer.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import re

from ..core.exporter import audit_path, json_path, write_workbook, xlsx_path
from ..core.output import record_warning
from ..core.scanner import load_json, save_json
from ..core.tables import TableCatalog
from .groove_stages import StageChallenges


INPUT_JSON = "master_data.json"
SIDE_NAMES = {1: "A", 2: "B", 3: "C"}

CORE_TABLES = (
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
)


def _active(tables, name):
    return tables.rows(name, active_only=True)


def _character_name(character_by_id, character_id):
    row = character_by_id.get(character_id)
    return row.get("CharacterNameJpn", "") if row else ""


def _music_name(music_by_id, music_id):
    row = music_by_id.get(music_id)
    return row.get("DisplayName", "") if row else ""


def _music_artist(music_by_id, music_id):
    row = music_by_id.get(music_id)
    if not row:
        return ""
    return row.get("ArtistNameInformal", "") or row.get("ArtistName", "")


def _canonical_character_key(character_ids):
    return "|".join(str(value) for value in sorted(character_ids))


def _item_projection(item):
    """Project mst_item fields without inventing GROOVE semantics."""
    if not item:
        return {
            "ItemName": "",
            "ItemNameMultiLine": "",
            "ItemTypeCode": None,
            "ItemRarityCode": None,
            "ItemAttributeCode": None,
            "ItemGroupCode": None,
            "ItemRouteCode": None,
            "ItemDescription1": "",
            "ItemDescription2": "",
            "ItemDescription3": "",
            "ItemFileName": "",
        }
    return {
        "ItemName": item.get("ItemName", ""),
        "ItemNameMultiLine": item.get("ItemNameMultiLine", ""),
        "ItemTypeCode": item.get("ItemTypeCode"),
        "ItemRarityCode": item.get("ItemRarityCode"),
        "ItemAttributeCode": item.get("ItemAttributeCode"),
        "ItemGroupCode": item.get("ItemGroupCode"),
        "ItemRouteCode": item.get("ItemRouteCode"),
        "ItemDescription1": item.get("ItemDescription1", ""),
        "ItemDescription2": item.get("ItemDescription2", ""),
        "ItemDescription3": item.get("ItemDescription3", ""),
        "ItemFileName": item.get("ItemFileName", ""),
    }


def _tables_with_field(tables, field):
    """Return tables that physically contain a field; used only for audit evidence."""
    result = []
    for table_name in tables.names:
        if any(
            isinstance(row, dict) and field in row
            for row in tables.rows(table_name)
        ):
            result.append(table_name)
    return result


def build_dataset(tables):
    """Build a machine-readable GROOVE source model from a TableCatalog."""
    missing = [name for name in CORE_TABLES if name not in tables.names]
    if missing:
        raise KeyError(f"required GROOVE tables are missing: {missing}")

    issues = []
    for table_name, fields in (
        ('mst_item', ('ItemId',)),
        ('mst_item_groove_stamina_recover', ('ItemId',)),
        ('mst_groove_constant', ('ConstantKey',)),
        ('mst_groove_wish_list_lottery_rate_level', ('GrooveWishListLotteryRateLevelId',)),
        ('mst_groove_chance_box_color', ('ChanceBoxItemRarity', 'ChanceBoxColor')),
        ('mst_groove_play_quality_reward_rate', ('PlayQualityRewardRateId',)),
    ):
        counts = Counter(tuple(row.get(field) for field in fields) for row in _active(tables, table_name))
        for identity, count in counts.items():
            if count > 1:
                issues.append({'Status': 'duplicate_drop_identity', 'Table': table_name,
                               'Identity': dict(zip(fields, identity)), 'Count': count})
    character_by_id = tables.by_id(
        "mst_character", "CharacterId", active_only=True
    )
    music_by_id = tables.by_id(
        "mst_music", "MusicId", active_only=True
    )
    item_by_id = tables.by_id(
        "mst_item", "ItemId", active_only=True
    )
    bonus_effect_by_level = tables.by_id(
        "mst_groove_runner_bonus",
        "GrooveRunnerBonusLevel",
        active_only=True,
    )
    unlock_by_id = tables.by_id(
        "mst_groove_music_unlock_condition",
        "GrooveMusicUnlockConditionId",
        active_only=True,
        required=False,
    )

    groove_music_rows = _active(tables, "mst_groove_music")
    bonus_rows = _active(tables, "mst_groove_music_bonus_runner")
    runner_exp_rows = _active(tables, "mst_groove_card_level_exp")
    stage_rows = _active(tables, "mst_groove_music_stage")
    relation_rows = _active(tables, "mst_groove_relation")
    constant_rows = _active(tables, "mst_groove_constant")
    wish_list_rows = _active(tables, "mst_groove_wish_list_item")
    wish_rate_level_rows = _active(tables, "mst_groove_wish_list_lottery_rate_level")
    chance_box_color_rows = _active(tables, "mst_groove_chance_box_color")
    play_quality_rate_rows = _active(tables, "mst_groove_play_quality_reward_rate")
    stamina_recovery_rows = _active(tables, "mst_item_groove_stamina_recover")

    # Optional: only used to mark whether a relation already existed as a Spin film.
    spin_films = tables.rows("mst_spin_film", active_only=True)
    spin_by_combo = defaultdict(list)
    for row in spin_films:
        ids = row.get("CharacterIds") or []
        if len(ids) >= 2:
            spin_by_combo[_canonical_character_key(ids)].append(row)

    groove_music_counts = Counter(row.get("MusicId") for row in groove_music_rows)
    for music_id, count in groove_music_counts.items():
        if music_id is not None and count > 1:
            issues.append({
                "Status": "duplicate_groove_music_id",
                "MusicId": music_id,
                "Count": count,
            })

    groove_music_ids = {
        row.get("MusicId")
        for row in groove_music_rows
        if row.get("MusicId") is not None
    }

    # --- Track list ---------------------------------------------------------
    bonus_by_music = defaultdict(list)
    for row in bonus_rows:
        bonus_by_music[row.get("MusicId")].append(row)

    stages_by_music = defaultdict(list)
    for row in stage_rows:
        stages_by_music[row.get("MusicId")].append(row)

    tracks = []
    for row in sorted(
        groove_music_rows,
        key=lambda value: (value.get("SortOrder", 0), value.get("MusicId", 0)),
    ):
        music_id = row.get("MusicId")
        music = music_by_id.get(music_id)
        if not music:
            issues.append({
                "Status": "missing_music_record",
                "MusicId": music_id,
                "Raw": row,
            })

        unlock_a = unlock_by_id.get(row.get("GrooveMusicUnlockConditionIdA"))
        unlock_b = unlock_by_id.get(row.get("GrooveMusicUnlockConditionIdB"))

        bonuses = sorted(
            bonus_by_music.get(music_id, []),
            key=lambda value: (
                -int(value.get("GrooveRunnerBonusLevel", 0) or 0),
                int(value.get("CharacterId", 0) or 0),
            ),
        )
        tracks.append({
            "MusicId": music_id,
            "DisplayName": _music_name(music_by_id, music_id),
            "ArtistName": _music_artist(music_by_id, music_id),
            "GrooveMusicType": row.get("GrooveMusicType"),
            "ReleaseDateTime": row.get("ReleaseDateTime"),
            "EndTime": row.get("EndTime"),
            "SortOrder": row.get("SortOrder"),
            "UnlockConditionIdA": row.get("GrooveMusicUnlockConditionIdA"),
            "UnlockDescriptionA": (unlock_a or {}).get("Description", ""),
            "UnlockConditionIdB": row.get("GrooveMusicUnlockConditionIdB"),
            "UnlockDescriptionB": (unlock_b or {}).get("Description", ""),
            "BonusRunnerCount": len(bonuses),
            "BonusSummary": " / ".join(
                f"{_character_name(character_by_id, item.get('CharacterId'))}"
                f" Lv{item.get('GrooveRunnerBonusLevel', 0)}"
                for item in bonuses
            ),
            "StageCount": len(stages_by_music.get(music_id, [])),
            "Raw": row,
        })

    # --- Per-music bonus runners -------------------------------------------
    bonus_pairs = Counter(
        (row.get("MusicId"), row.get("CharacterId")) for row in bonus_rows
    )
    bonus_runners = []
    for row in sorted(
        bonus_rows,
        key=lambda value: (
            value.get("MusicId", 0),
            -int(value.get("GrooveRunnerBonusLevel", 0) or 0),
            value.get("CharacterId", 0),
        ),
    ):
        music_id = row.get("MusicId")
        character_id = row.get("CharacterId")
        level = row.get("GrooveRunnerBonusLevel")
        effect = bonus_effect_by_level.get(level)

        if music_id not in groove_music_ids:
            issues.append({
                "Status": "bonus_runner_music_not_in_groove",
                "MusicId": music_id,
                "Raw": row,
            })
        if character_id not in character_by_id:
            issues.append({
                "Status": "bonus_runner_unknown_character",
                "CharacterId": character_id,
                "Raw": row,
            })
        if effect is None:
            issues.append({
                "Status": "bonus_runner_unknown_level",
                "GrooveRunnerBonusLevel": level,
                "Raw": row,
            })
        if bonus_pairs[(music_id, character_id)] > 1:
            issues.append({
                "Status": "duplicate_music_character_bonus",
                "MusicId": music_id,
                "CharacterId": character_id,
                "Count": bonus_pairs[(music_id, character_id)],
            })

        bonus_runners.append({
            "MusicId": music_id,
            "DisplayName": _music_name(music_by_id, music_id),
            "CharacterId": character_id,
            "CharacterName": _character_name(character_by_id, character_id),
            "GrooveRunnerBonusLevel": level,
            "CardLevelExpIncreaseCount":
                (effect or {}).get("CardLevelExpIncreaseCount"),
            "ChanceBoxLotteryIncreaseCount":
                (effect or {}).get("ChanceBoxLotteryIncreaseCount"),
            "Raw": row,
        })

    # Matrix is only a convenience view. Raw BonusRunners above remains canonical.
    active_character_ids = sorted(character_by_id)
    bonus_matrix = []
    bonus_level_lookup = defaultdict(dict)
    for row in bonus_runners:
        music_id = row["MusicId"]
        character_id = row["CharacterId"]
        value = row.get("GrooveRunnerBonusLevel") or 0
        old = bonus_level_lookup[music_id].get(character_id)
        # Do not lose a duplicate entirely in the convenience matrix.
        bonus_level_lookup[music_id][character_id] = max(old or 0, value)

    for track in tracks:
        music_id = track["MusicId"]
        bonus_matrix.append({
            "MusicId": music_id,
            "DisplayName": track["DisplayName"],
            "Levels": {
                str(character_id): bonus_level_lookup[music_id].get(character_id, 0)
                for character_id in active_character_ids
            },
        })

    # --- Runner slot/status EXP table --------------------------------------
    runner_positions = []
    for row in sorted(
        runner_exp_rows, key=lambda value: value.get("GrooveRunnerStatus", 0)
    ):
        runner_positions.append({
            "GrooveRunnerStatus": row.get("GrooveRunnerStatus"),
            "Runner1": row.get("CardLevelExpRunner1"),
            "Runner2": row.get("CardLevelExpRunner2"),
            "Runner3": row.get("CardLevelExpRunner3"),
            "Runner4": row.get("CardLevelExpRunner4"),
            "Raw": row,
        })

    bonus_levels = []
    for row in sorted(
        _active(tables, "mst_groove_runner_bonus"),
        key=lambda value: value.get("GrooveRunnerBonusLevel", 0),
    ):
        bonus_levels.append({
            "GrooveRunnerBonusLevel": row.get("GrooveRunnerBonusLevel"),
            "CardLevelExpIncreaseCount": row.get("CardLevelExpIncreaseCount"),
            "ChanceBoxLotteryIncreaseCount":
                row.get("ChanceBoxLotteryIncreaseCount"),
            "Raw": row,
        })

    # --- GROOVE consumables / wish-list / Chance Box raw facts -------------
    #
    # Important boundary:
    # - Direct foreign keys are joined here.
    # - Tables that merely "look related" are kept separate.
    # - No probability / EV formula is invented in this extractor.

    boost_items = []
    seen_boost_item_ids = set()
    for constant in constant_rows:
        constant_key = constant.get("ConstantKey")
        boost_fields = sorted(
            (
                key for key in constant
                if re.fullmatch(r"GrooveBoostItemId\d+", str(key))
            ),
            key=lambda key: int(re.search(r"\d+$", key).group()),
        )
        for field in boost_fields:
            item_id = constant.get(field)
            if item_id in (None, 0):
                continue
            item = item_by_id.get(item_id)
            if not item:
                issues.append({
                    "Status": "groove_boost_item_missing_item",
                    "ConstantKey": constant_key,
                    "SourceField": field,
                    "ItemId": item_id,
                })
            if item_id in seen_boost_item_ids:
                issues.append({
                    "Status": "duplicate_groove_boost_item",
                    "ItemId": item_id,
                    "ConstantKey": constant_key,
                    "SourceField": field,
                })
            seen_boost_item_ids.add(item_id)
            boost_items.append({
                "ConstantKey": constant_key,
                "SourceField": field,
                "BoostSlot": int(re.search(r"\d+$", field).group()),
                "ItemId": item_id,
                **_item_projection(item),
                "RawConstant": constant,
                "RawItem": item,
            })

    stamina_recovery_items = []
    for row in sorted(stamina_recovery_rows, key=lambda value: value.get("ItemId", 0)):
        item_id = row.get("ItemId")
        item = item_by_id.get(item_id)
        if not item:
            issues.append({
                "Status": "groove_stamina_recovery_missing_item",
                "ItemId": item_id,
                "Raw": row,
            })
        stamina_recovery_items.append({
            "ItemId": item_id,
            "RecoveryAmount": row.get("RecoveryAmount"),
            **_item_projection(item),
            "Raw": row,
            "RawItem": item,
        })

    wish_list_items = []
    wish_item_ids = Counter(row.get("ItemId") for row in wish_list_rows)
    for row in sorted(
        wish_list_rows,
        key=lambda value: (value.get("SortOrder", 0), value.get("ItemId", 0)),
    ):
        item_id = row.get("ItemId")
        item = item_by_id.get(item_id)
        if not item:
            issues.append({
                "Status": "groove_wish_list_missing_item",
                "ItemId": item_id,
                "Raw": row,
            })
        if wish_item_ids[item_id] > 1:
            issues.append({
                "Status": "duplicate_groove_wish_list_item",
                "ItemId": item_id,
                "Count": wish_item_ids[item_id],
            })
        wish_list_items.append({
            "ItemId": item_id,
            "LotteryRate": row.get("LotteryRate"),
            "ReleaseDateTime": row.get("ReleaseDateTime"),
            "EndTime": row.get("EndTime"),
            "SortOrder": row.get("SortOrder"),
            **_item_projection(item),
            # Do not derive a final probability here. The denominator is exported
            # separately in DropConstants.
            "Raw": row,
            "RawItem": item,
        })

    wish_list_rate_levels = [
        {
            "GrooveWishListLotteryRateLevelId":
                row.get("GrooveWishListLotteryRateLevelId"),
            "BorderLotteryRate": row.get("BorderLotteryRate"),
            "Text": row.get("Text", ""),
            "Raw": row,
        }
        for row in sorted(
            wish_rate_level_rows,
            key=lambda value: value.get("GrooveWishListLotteryRateLevelId", 0),
        )
    ]

    chance_box_color_rates = [
        {
            "ChanceBoxItemRarity": row.get("ChanceBoxItemRarity"),
            "ChanceBoxColor": row.get("ChanceBoxColor"),
            "LotteryRate": row.get("LotteryRate"),
            "Raw": row,
        }
        for row in sorted(
            chance_box_color_rows,
            key=lambda value: (
                value.get("ChanceBoxItemRarity", 0),
                value.get("ChanceBoxColor", 0),
            ),
        )
    ]

    play_quality_reward_rates = [
        {
            "PlayQualityRewardRateId": row.get("PlayQualityRewardRateId"),
            "Rainbow": row.get("Rainbow"),
            "Gold": row.get("Gold"),
            "Silver": row.get("Silver"),
            "Copper": row.get("Copper"),
            "Raw": row,
        }
        for row in sorted(
            play_quality_rate_rows,
            key=lambda value: value.get("PlayQualityRewardRateId", 0),
        )
    ]

    drop_constants = []
    for row in constant_rows:
        drop_constants.append({
            "ConstantKey": row.get("ConstantKey"),
            "RelationLotteryRateDenominator":
                row.get("RelationLotteryRateDenominator"),
            "WishListItemLotteryRateDenominator":
                row.get("WishListItemLotteryRateDenominator"),
            "ChanceBoxPinCustomItemLotteryRateMax":
                row.get("ChanceBoxPinCustomItemLotteryRateMax"),
            "ChanceBoxWishListItemMaxRate":
                row.get("ChanceBoxWishListItemMaxRate"),
            "ConsumeGrooveStaminaRecoveryCrystal":
                row.get("ConsumeGrooveStaminaRecoveryCrystal"),
            "MaxScore": row.get("MaxScore"),
            "Raw": row,
        })

    # These are intentionally NOT linked automatically. Their absence is an
    # important part of the data contract so downstream code does not guess.
    unresolved_associations = []

    play_quality_ref_tables = [
        name for name in _tables_with_field(tables, "PlayQualityRewardRateId")
        if name != "mst_groove_play_quality_reward_rate"
    ]
    if not play_quality_ref_tables:
        unresolved_associations.append({
            "Key": "boost_item_to_play_quality_reward_rate",
            "Status": "unresolved",
            "Left": "mst_groove_constant.GrooveBoostItemId* -> mst_item",
            "Right": "mst_groove_play_quality_reward_rate.PlayQualityRewardRateId",
            "Evidence": (
                "No external PlayQualityRewardRateId field exists in this masterdata "
                "snapshot. Do not bind アターレC (ItemId 563) to rate profile 2 by order/name."
            ),
        })
    else:
        unresolved_associations.append({
            "Key": "play_quality_reward_rate_external_references",
            "Status": "needs_review",
            "ReferenceTables": play_quality_ref_tables,
            "Evidence": (
                "A future/current table references PlayQualityRewardRateId; review the "
                "business relation before enabling a formula."
            ),
        })

    chance_rarity_ref_tables = [
        name for name in _tables_with_field(tables, "ChanceBoxItemRarity")
        if name != "mst_groove_chance_box_color"
    ]
    if not chance_rarity_ref_tables:
        unresolved_associations.append({
            "Key": "item_rarity_to_chance_box_item_rarity",
            "Status": "unresolved",
            "Left": "mst_item.ItemRarityCode",
            "Right": "mst_groove_chance_box_color.ChanceBoxItemRarity",
            "Evidence": (
                "No external ChanceBoxItemRarity reference exists. Numeric similarity "
                "is not a verified foreign key; keep the two rarity concepts separate."
            ),
        })

    else:
        unresolved_associations.append({
            "Key": "item_rarity_to_chance_box_item_rarity",
            "Status": "needs_review",
            "ReferenceTables": chance_rarity_ref_tables,
            "Evidence": "External rarity references require review; no item-rarity mapping is inferred.",
        })

    unresolved_associations.append({
        "Key": "wish_list_rate_level_application",
        "Status": "unresolved",
        "Left": "mst_groove_wish_list_item.LotteryRate",
        "Right": "mst_groove_wish_list_lottery_rate_level.BorderLotteryRate/Text",
        "Evidence": (
            "The threshold table is present, but no explicit level id/reference is stored "
            "on wish-list item rows. Export thresholds raw; do not silently assign labels."
        ),
    })

    # --- Relations ----------------------------------------------------------
    relations = []
    relation_keys = Counter(
        _canonical_character_key(row.get("CharacterIds") or [])
        for row in relation_rows
    )
    for row in sorted(
        relation_rows, key=lambda value: value.get("GrooveRelationId", 0)
    ):
        ids = list(row.get("CharacterIds") or [])
        key = _canonical_character_key(ids)
        unknown = [value for value in ids if value not in character_by_id]
        if unknown:
            issues.append({
                "Status": "relation_unknown_character",
                "GrooveRelationId": row.get("GrooveRelationId"),
                "CharacterIds": unknown,
            })
        if relation_keys[key] > 1:
            issues.append({
                "Status": "duplicate_relation_character_set",
                "CharacterSetKey": key,
                "Count": relation_keys[key],
            })

        spin_matches = spin_by_combo.get(key, [])
        if len(spin_matches) > 1:
            issues.append({
                "Status": "ambiguous_spin_relation_match",
                "GrooveRelationId": row.get("GrooveRelationId"),
                "CharacterSetKey": key,
                "SpinFilmIds": [item.get("FilmId") for item in spin_matches],
            })

        relations.append({
            "GrooveRelationId": row.get("GrooveRelationId"),
            "RelationText": row.get("RelationText", ""),
            # Preserve raw order. Do not assume CharacterIds order is a runner order.
            "CharacterIds": ids,
            "CharacterNames": [
                _character_name(character_by_id, value) for value in ids
            ],
            # Canonical set key is only for matching/deduplication.
            "CharacterSetKey": key,
            "MemberCount": len(ids),
            "LotteryRate": row.get("LotteryRate"),
            "SpinExisting": bool(spin_matches),
            "SpinFilmId": spin_matches[0].get("FilmId") if len(spin_matches) == 1 else None,
            "SpinSetIds": (
                list(spin_matches[0].get("SpinSetIds") or [])
                if len(spin_matches) == 1 else []
            ),
            "Raw": row,
        })

    # --- Stages -------------------------------------------------------------
    challenge_source = StageChallenges(tables)
    stages = []
    for row in sorted(
        stage_rows,
        key=lambda value: (
            value.get("MusicId", 0),
            value.get("GrooveMusicStageType", 0),
        ),
    ):
        music_id = row.get("MusicId")
        if music_id not in groove_music_ids:
            issues.append({
                "Status": "stage_music_not_in_groove",
                "MusicId": music_id,
                "Raw": row,
            })
        stages.append({
            "MusicId": music_id,
            "DisplayName": _music_name(music_by_id, music_id),
            "StageType": row.get("GrooveMusicStageType"),
            "Side": SIDE_NAMES.get(
                row.get("GrooveMusicStageType"),
                str(row.get("GrooveMusicStageType", "")),
            ),
            "Difficulty": row.get("GrooveMusicStageDifficulty"),
            "StageFileName": row.get("StageFileName", ""),
            "PreviewMusicCueId": row.get("PreviewMusicCueId"),
            "RelationLotteryRateIncreaseRate":
                row.get("RelationLotteryRateIncreaseRate"),
            "GrooveAchievementRewardId":
                row.get("GrooveAchievementRewardId"),
            "GrooveCommonRewardId": row.get("GrooveCommonRewardId"),
            "CommonRewardResolution": "unresolved",
            "Challenges": challenge_source.project(row, issues),
            "ExtraAchievementIds": [
                row.get("GrooveExtraAchievementId1"),
                row.get("GrooveExtraAchievementId2"),
                row.get("GrooveExtraAchievementId3"),
                row.get("GrooveExtraAchievementId4"),
            ],
            "Raw": row,
        })

    staff_character_ids = {
        row.get("CharacterId")
        for row in _active(tables, "mst_character_card")
        if row.get("CharacterId") is not None
    }
    characters = []
    for character_id in active_character_ids:
        row = character_by_id[character_id]
        characters.append({
            "CharacterId": character_id,
            "CharacterNameJpn": row.get("CharacterNameJpn", ""),
            "CharacterNameEng": row.get("CharacterNameEng", ""),
            "CharacterGroupCode": row.get("CharacterGroupCode"),
            "HasStaffCard": character_id in staff_character_ids,
            "IconFileName": row.get("IconFileName", ""),
            "MiniCharaIconFileName": row.get("MiniCharaIconFileName", ""),
        })

    constants = [dict(row) for row in constant_rows]

    return {
        "Tracks": tracks,
        "BonusRunners": bonus_runners,
        "BonusMatrix": bonus_matrix,
        "RunnerPositions": runner_positions,
        "BonusLevels": bonus_levels,
        "Relations": relations,
        "Stages": stages,
        "Characters": characters,
        "BoostItems": boost_items,
        "StaminaRecoveryItems": stamina_recovery_items,
        "WishListItems": wish_list_items,
        "WishListRateLevels": wish_list_rate_levels,
        "ChanceBoxColorRates": chance_box_color_rates,
        "PlayQualityRewardRates": play_quality_reward_rates,
        "DropConstants": drop_constants,
        "UnresolvedAssociations": unresolved_associations,
        "Constants": constants,
        "Issues": issues,
    }


def extract(session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    data = build_dataset(tables)

    output = json_path("Groove_Optimizer_Source.json")
    save_json(data, output)

    audit = {
        "TrackCount": len(data["Tracks"]),
        "BonusRunnerCount": len(data["BonusRunners"]),
        "RelationCount": len(data["Relations"]),
        "StageCount": len(data["Stages"]),
        "BoostItemCount": len(data["BoostItems"]),
        "StaminaRecoveryItemCount": len(data["StaminaRecoveryItems"]),
        "WishListItemCount": len(data["WishListItems"]),
        "WishListRateLevelCount": len(data["WishListRateLevels"]),
        "ChanceBoxColorRateCount": len(data["ChanceBoxColorRates"]),
        "PlayQualityRewardRateCount": len(data["PlayQualityRewardRates"]),
        "UnresolvedAssociationCount": len(data["UnresolvedAssociations"]),
        "UnresolvedAssociations": data["UnresolvedAssociations"],
        "IssueCount": len(data["Issues"]),
        "Issues": data["Issues"],
    }
    save_json(audit, audit_path("groove_optimizer_audit.json"))
    if data["Issues"]:
        record_warning(
            f"GROOVE 原始数据有 {len(data['Issues'])} 条关系异常，"
            "详见 groove_optimizer_audit.json"
        )

    print(
        f"[+] GROOVE: {len(data['Tracks'])} 首曲目 / "
        f"{len(data['BonusRunners'])} 条 Bonus Runner / "
        f"{len(data['Relations'])} 条 Relation / "
        f"{len(data['WishListItems'])} 条 Wish List Item / "
        f"{len(data['BoostItems'])} 个携带饮料"
    )
    return data


def export(data=None):
    if data is None:
        data = load_json(json_path("Groove_Optimizer_Source.json"))

    characters = data["Characters"]
    character_ids = [item["CharacterId"] for item in characters]
    character_names = {
        item["CharacterId"]: item["CharacterNameJpn"] for item in characters
    }

    track_rows = []
    for item in data["Tracks"]:
        track_rows.append([
            item["MusicId"],
            item["DisplayName"],
            item["ArtistName"],
            item["GrooveMusicType"],
            item["ReleaseDateTime"],
            item["EndTime"],
            item["SortOrder"],
            item["UnlockConditionIdA"],
            item["UnlockDescriptionA"],
            item["UnlockConditionIdB"],
            item["UnlockDescriptionB"],
            item["BonusRunnerCount"],
            item["BonusSummary"],
            item["StageCount"],
        ])

    bonus_rows = []
    for item in data["BonusRunners"]:
        bonus_rows.append([
            item["MusicId"],
            item["DisplayName"],
            item["CharacterId"],
            item["CharacterName"],
            item["GrooveRunnerBonusLevel"],
            item["CardLevelExpIncreaseCount"],
            item["ChanceBoxLotteryIncreaseCount"],
        ])

    matrix_rows = []
    for item in data["BonusMatrix"]:
        matrix_rows.append([
            item["MusicId"],
            item["DisplayName"],
            *[
                item["Levels"].get(str(character_id), 0)
                for character_id in character_ids
            ],
        ])

    runner_position_rows = [
        [
            item["GrooveRunnerStatus"],
            item["Runner1"],
            item["Runner2"],
            item["Runner3"],
            item["Runner4"],
        ]
        for item in data["RunnerPositions"]
    ]

    bonus_level_rows = [
        [
            item["GrooveRunnerBonusLevel"],
            item["CardLevelExpIncreaseCount"],
            item["ChanceBoxLotteryIncreaseCount"],
        ]
        for item in data["BonusLevels"]
    ]

    relation_rows = []
    for item in data["Relations"]:
        relation_rows.append([
            item["GrooveRelationId"],
            item["RelationText"],
            ",".join(str(value) for value in item["CharacterIds"]),
            " × ".join(item["CharacterNames"]),
            item["CharacterSetKey"],
            item["MemberCount"],
            item["LotteryRate"],
            "是" if item["SpinExisting"] else "否",
            item["SpinFilmId"],
            ",".join(str(value) for value in item["SpinSetIds"]),
        ])

    stage_rows_out = []
    for item in data["Stages"]:
        stage_rows_out.append([
            item["MusicId"],
            item["DisplayName"],
            item["StageType"],
            item["Side"],
            item["Difficulty"],
            item["StageFileName"],
            item["PreviewMusicCueId"],
            item["RelationLotteryRateIncreaseRate"],
            item["GrooveAchievementRewardId"],
            item["GrooveCommonRewardId"],
            ",".join(
                "" if value is None else str(value)
                for value in item["ExtraAchievementIds"]
            ),
        ])

    character_rows = [
        [
            item["CharacterId"],
            item["CharacterNameJpn"],
            item["CharacterNameEng"],
            item["CharacterGroupCode"],
            item["IconFileName"],
            item["MiniCharaIconFileName"],
        ]
        for item in characters
    ]

    boost_item_rows = [
        [
            item["BoostSlot"],
            item["SourceField"],
            item["ItemId"],
            item["ItemName"],
            item["ItemTypeCode"],
            item["ItemRarityCode"],
            item["ItemDescription1"],
            item["ItemFileName"],
        ]
        for item in data["BoostItems"]
    ]

    stamina_recovery_rows_out = [
        [
            item["ItemId"],
            item["ItemName"],
            item["RecoveryAmount"],
            item["ItemTypeCode"],
            item["ItemDescription1"],
            item["ItemFileName"],
        ]
        for item in data["StaminaRecoveryItems"]
    ]

    wish_list_rows_out = [
        [
            item["ItemId"],
            item["ItemName"],
            item["LotteryRate"],
            item["ReleaseDateTime"],
            item["EndTime"],
            item["SortOrder"],
            item["ItemTypeCode"],
            item["ItemRarityCode"],
            item["ItemRouteCode"],
            item["ItemDescription1"],
        ]
        for item in data["WishListItems"]
    ]

    wish_rate_level_rows_out = [
        [
            item["GrooveWishListLotteryRateLevelId"],
            item["BorderLotteryRate"],
            item["Text"],
        ]
        for item in data["WishListRateLevels"]
    ]

    chance_box_color_rows_out = [
        [
            item["ChanceBoxItemRarity"],
            item["ChanceBoxColor"],
            item["LotteryRate"],
        ]
        for item in data["ChanceBoxColorRates"]
    ]

    play_quality_rows_out = [
        [
            item["PlayQualityRewardRateId"],
            item["Rainbow"],
            item["Gold"],
            item["Silver"],
            item["Copper"],
        ]
        for item in data["PlayQualityRewardRates"]
    ]

    drop_constant_rows_out = [
        [
            item["ConstantKey"],
            item["RelationLotteryRateDenominator"],
            item["WishListItemLotteryRateDenominator"],
            item["ChanceBoxPinCustomItemLotteryRateMax"],
            item["ChanceBoxWishListItemMaxRate"],
            item["ConsumeGrooveStaminaRecoveryCrystal"],
            item["MaxScore"],
        ]
        for item in data["DropConstants"]
    ]

    unresolved_rows_out = [
        [
            item.get("Key"),
            item.get("Status"),
            item.get("Left", ""),
            item.get("Right", ""),
            item.get("Evidence", ""),
            ",".join(item.get("ReferenceTables", [])),
        ]
        for item in data["UnresolvedAssociations"]
    ]

    constant_rows = []
    if data["Constants"]:
        keys = sorted({
            key for row in data["Constants"] for key in row.keys()
        })
        for row in data["Constants"]:
            constant_rows.append([row.get(key) for key in keys])
    else:
        keys = []

    sheets = [
        {
            "title": "Groove曲目",
            "headers": [
                "MusicId", "曲目名", "Artist", "GrooveMusicType",
                "ReleaseDateTime", "EndTime", "SortOrder",
                "UnlockIdA", "Unlock说明A", "UnlockIdB", "Unlock说明B",
                "Bonus人数", "Bonus概览", "Stage数",
            ],
            "rows": track_rows,
            "col_widths": {
                "A": 10, "B": 28, "C": 28, "D": 18,
                "E": 24, "F": 24, "G": 10, "H": 12, "I": 42,
                "J": 12, "K": 42, "L": 10, "M": 48, "N": 10,
            },
            "wrap_cols": [9, 11, 13],
        },
        {
            "title": "曲目BonusRunner",
            "headers": [
                "MusicId", "曲目名", "CharacterId", "角色",
                "BonusLevel", "卡Lv经验增量", "ChanceBox稀有抽选增量",
            ],
            "rows": bonus_rows,
            "col_widths": {
                "A": 10, "B": 30, "C": 12, "D": 18,
                "E": 12, "F": 16, "G": 24,
            },
        },
        {
            "title": "Bonus矩阵",
            "headers": [
                "MusicId", "曲目名",
                *[character_names[character_id] for character_id in character_ids],
            ],
            "rows": matrix_rows,
            "col_widths": {"A": 10, "B": 28},
        },
        {
            "title": "Runner位次EXP",
            "headers": ["GrooveRunnerStatus", "1号位", "2号位", "3号位", "4号位"],
            "rows": runner_position_rows,
            "col_widths": {
                "A": 22, "B": 12, "C": 12, "D": 12, "E": 12,
            },
        },
        {
            "title": "Bonus等级效果",
            "headers": [
                "BonusLevel", "CardLevelExpIncreaseCount",
                "ChanceBoxLotteryIncreaseCount",
            ],
            "rows": bonus_level_rows,
            "col_widths": {"A": 14, "B": 28, "C": 32},
        },
        {
            "title": "Groove关系",
            "headers": [
                "GrooveRelationId", "RelationText", "CharacterIds(原顺序)",
                "角色组合", "CharacterSetKey(仅匹配用)", "人数",
                "LotteryRate", "Spin既存", "SpinFilmId", "SpinSetIds",
            ],
            "rows": relation_rows,
            "col_widths": {
                "A": 18, "B": 30, "C": 22, "D": 45, "E": 28,
                "F": 8, "G": 12, "H": 12, "I": 12, "J": 24,
            },
        },
        {
            "title": "Stage",
            "headers": [
                "MusicId", "曲目名", "StageType", "SIDE", "难度",
                "StageFileName", "PreviewMusicCueId",
                "RelationLotteryRateIncreaseRate",
                "GrooveAchievementRewardId", "GrooveCommonRewardId",
                "ExtraAchievementIds",
            ],
            "rows": stage_rows_out,
            "col_widths": {
                "A": 10, "B": 28, "C": 12, "D": 8, "E": 8,
                "F": 22, "G": 18, "H": 32, "I": 26, "J": 24, "K": 30,
            },
        },
        {
            "title": "角色对照",
            "headers": [
                "CharacterId", "CharacterNameJpn", "CharacterNameEng",
                "CharacterGroupCode", "IconFileName", "MiniCharaIconFileName",
            ],
            "rows": character_rows,
            "col_widths": {
                "A": 14, "B": 20, "C": 24, "D": 22, "E": 28, "F": 32,
            },
        },
        {
            "title": "携带饮料",
            "headers": [
                "BoostSlot", "来源字段", "ItemId", "道具名",
                "ItemTypeCode", "ItemRarityCode", "官方说明", "资源文件名",
            ],
            "rows": boost_item_rows,
            "col_widths": {
                "A": 12, "B": 24, "C": 10, "D": 22,
                "E": 16, "F": 18, "G": 46, "H": 24,
            },
            "wrap_cols": [7],
        },
        {
            "title": "シューズ回復",
            "headers": [
                "ItemId", "道具名", "RecoveryAmount",
                "ItemTypeCode", "官方说明", "资源文件名",
            ],
            "rows": stamina_recovery_rows_out,
            "col_widths": {
                "A": 10, "B": 22, "C": 18, "D": 16, "E": 46, "F": 24,
            },
            "wrap_cols": [5],
        },
        {
            "title": "ほしいもの",
            "headers": [
                "ItemId", "道具名", "LotteryRate", "ReleaseDateTime", "EndTime",
                "SortOrder", "ItemTypeCode", "ItemRarityCode",
                "ItemRouteCode", "官方说明",
            ],
            "rows": wish_list_rows_out,
            "col_widths": {
                "A": 10, "B": 28, "C": 16, "D": 24, "E": 24,
                "F": 12, "G": 16, "H": 18, "I": 16, "J": 48,
            },
            "wrap_cols": [10],
        },
        {
            "title": "ほしいもの出やすさ阈值",
            "headers": ["LevelId", "BorderLotteryRate", "Text"],
            "rows": wish_rate_level_rows_out,
            "col_widths": {"A": 12, "B": 22, "C": 30},
        },
        {
            "title": "ChanceBox颜色参数",
            "headers": ["ChanceBoxItemRarity", "ChanceBoxColor", "LotteryRate"],
            "rows": chance_box_color_rows_out,
            "col_widths": {"A": 24, "B": 18, "C": 16},
        },
        {
            "title": "PlayQuality倍率",
            "headers": [
                "PlayQualityRewardRateId", "Rainbow", "Gold", "Silver", "Copper",
            ],
            "rows": play_quality_rows_out,
            "col_widths": {
                "A": 28, "B": 14, "C": 14, "D": 14, "E": 14,
            },
        },
        {
            "title": "掉落与消耗常量",
            "headers": [
                "ConstantKey", "RelationLotteryRateDenominator",
                "WishListItemLotteryRateDenominator",
                "ChanceBoxPinCustomItemLotteryRateMax",
                "ChanceBoxWishListItemMaxRate",
                "ConsumeGrooveStaminaRecoveryCrystal", "MaxScore",
            ],
            "rows": drop_constant_rows_out,
            "col_widths": {
                "A": 14, "B": 30, "C": 34, "D": 36,
                "E": 34, "F": 38, "G": 14,
            },
        },
        {
            "title": "未解析关联",
            "headers": [
                "Key", "Status", "Left", "Right", "Evidence", "ReferenceTables",
            ],
            "rows": unresolved_rows_out,
            "col_widths": {
                "A": 38, "B": 18, "C": 42, "D": 42, "E": 80, "F": 36,
            },
            "wrap_cols": [3, 4, 5, 6],
        },
        {
            "title": "Groove常量",
            "headers": keys,
            "rows": constant_rows,
        },
    ]

    out = xlsx_path("groove_optimizer_source.xlsx")
    write_workbook(out, sheets)
    return out


def run(session=None):
    data = extract(session=session)
    return export(data)
