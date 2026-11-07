"""Puzzle stage / challenge / drop-route source extraction.

Designed for BRMY-Wiki-CardData-Extractor on codex/migrate-masterdata-toolkit-v2.
The module follows the current Toolkit boundary: masterdata joins upstream,
product decisions and route ranking downstream.

Important contracts:
- A playable stage instance is keyed by (PuzzleMapId, PuzzleStageNo, PuzzleType).
- MusicPuzzleStageId is a relation, NOT a unique stage identity.
- Campaign rows are overlays; Bartending owns ingredient tables.
- Unlock condition codes remain raw until their enum semantics are independently verified.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from toolkit.core.exporter import audit_path, json_path
from toolkit.core.output import record_warning
from toolkit.core.rewards import RewardResolver
from toolkit.core.scanner import load_json, save_json
from toolkit.core.tables import TableCatalog

INPUT_JSON = "master_data.json"
RANKS = ("SS", "S", "A", "B", "C", "D", "E")


def _by_id(tables, name, key):
    return tables.by_id(name, key, required=False, active_only=False)


def _group(tables, name, key):
    return tables.group_by(name, key, required=False, active_only=False)


def _window(start, end):
    return {"StartTime": start or "", "EndTime": end or ""}


def _event_items(tables):
    result = defaultdict(dict)
    for table, fields in (
        ("mst_event_a", ("EventItemId", "TravelCoinItemId", "EventStaminaItemId")),
        ("mst_event_accumulate_item", ("EventItemId",)),
        ("mst_event_c", ("PrizeMedalItemId", "ChartStampItemId")),
    ):
        for row in tables.rows(table, active_only=False):
            event_id = row.get("EventId")
            if not event_id:
                continue
            for field in fields:
                if row.get(field):
                    result[event_id][field] = row[field]
    return dict(result)


def _render_achievement(group, row):
    text = (group or {}).get("Description", "")
    # Snapshot audit: descriptions use {1} only. Keep other placeholders untouched.
    if row and "{1}" in text:
        text = text.replace("{1}", str(row.get("ClearRequireCount", "")))
    return text


def extract(session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))

    maps = _by_id(tables, "mst_puzzle_map", "PuzzleMapId")
    characters = _by_id(tables, "mst_character", "CharacterId")
    events = _by_id(tables, "mst_event", "EventId")
    campaigns = _by_id(tables, "mst_campaign", "CampaignId")
    items = _by_id(tables, "mst_item", "ItemId")
    music_stages = _by_id(tables, "mst_music_puzzle_stage", "MusicPuzzleStageId")
    music = _by_id(tables, "mst_music", "MusicId")
    unlock_conditions = _by_id(tables, "mst_puzzle_stage_unlock_condition", "PuzzleStageUnlockConditionId")
    achievement_groups = _by_id(tables, "mst_puzzle_achievement_group", "PuzzleAchievementGroupId")
    achievements = _by_id(tables, "mst_puzzle_achievement", "PuzzleAchievementGroupId")
    achievement_rewards = _by_id(tables, "mst_puzzle_achievement_reward", "PuzzleAchievementRewardId")
    drop_rows = _group(tables, "mst_puzzle_drop_reward", "PuzzleDropRewardGroupId")
    basic_rows = _group(tables, "mst_puzzle_drop_reward_basic", "PuzzleDropRewardBasicGroupId")
    lottery_counts = _by_id(tables, "mst_puzzle_drop_reward_lottery_count", "PuzzleDropRewardLotteryCountId")
    event_reward_profiles = _by_id(tables, "mst_puzzle_event_reward", "PuzzleEventRewardId")
    reward_rates = _by_id(tables, "mst_puzzle_reward_rate", "PuzzleRewardRateId")
    direct_groups = _group(tables, "mst_direct_reward", "DirectRewardGroupId")
    resolver = RewardResolver(tables)
    event_item_ids = _event_items(tables)

    issues = []

    def owner(map_row):
        if not map_row:
            return {"Kind": "unknown"}
        if map_row.get("CharacterId"):
            cid = map_row["CharacterId"]
            return {
                "Kind": "character", "CharacterId": cid,
                "CharacterName": characters.get(cid, {}).get("CharacterNameJpn", ""),
            }
        if map_row.get("EventId"):
            eid = map_row["EventId"]
            event = events.get(eid, {})
            return {
                "Kind": "event", "EventId": eid, "EventTitle": event.get("EventTitle", ""),
                "Availability": _window(event.get("OpenStartTime") or event.get("StartTime"), event.get("EndTime")),
            }
        if map_row.get("CampaignId"):
            cid = map_row["CampaignId"]
            campaign = campaigns.get(cid, {})
            return {
                "Kind": "campaign", "CampaignId": cid, "CampaignTitle": campaign.get("CampaignTitle", ""),
                "CampaignSequenceNo": map_row.get("CampaignSequenceNo", 0),
                "Availability": _window(campaign.get("StartTime"), campaign.get("EndTime")),
            }
        return {"Kind": "other"}

    def music_info(stage):
        relation = music_stages.get(stage.get("MusicPuzzleStageId"), {})
        master = music.get(relation.get("MusicId"), {})
        return {
            "MusicPuzzleStageId": stage.get("MusicPuzzleStageId"),
            "MusicId": relation.get("MusicId"),
            "DisplayName": master.get("DisplayName", ""),
            "ArtistName": master.get("ArtistName", ""),
            "ArtistNameInformal": master.get("ArtistNameInformal", ""),
            "MusicType": master.get("MusicType"),
            "CharacterId": master.get("CharacterId"),
        }

    def unlocks(stage):
        result = []
        for slot in ("A", "B"):
            condition_id = stage.get(f"PuzzleStageUnlockConditionId{slot}")
            if not condition_id:
                continue
            row = unlock_conditions.get(condition_id)
            if not row:
                issues.append({"Status": "missing_unlock_condition", "ConditionId": condition_id,
                               "StageKey": [stage.get("PuzzleMapId"), stage.get("PuzzleStageNo"), stage.get("PuzzleType")]})
                result.append({"Slot": slot, "ConditionId": condition_id, "Resolution": "missing"})
            else:
                result.append({
                    "Slot": slot, "ConditionId": condition_id,
                    "ConditionCode": row.get("PuzzleStageUnlockConditionCode"),
                    "Value1": row.get("Value1"), "Value2": row.get("Value2"),
                    "Value3": row.get("Value3"), "Value4": row.get("Value4"),
                    "Resolution": "raw_semantics_unresolved",
                })
        return result

    def challenges(stage):
        profile = achievement_rewards.get(stage.get("PuzzleAchievementRewardId"), {})
        result = []
        for slot in range(1, 5):
            group_id = stage.get(f"PuzzleExtraNo{slot}")
            if not group_id:
                continue
            group = achievement_groups.get(group_id)
            achievement = achievements.get(group_id)
            reward_group_id = profile.get(f"RewardPuzzleExtraNo{slot}") if profile else None
            rewards = [resolver.resolve(row) for row in direct_groups.get(reward_group_id, [])]
            resolution = "resolved" if group and achievement and reward_group_id and rewards else "unresolved"
            if resolution != "resolved":
                issues.append({"Status": "unresolved_stage_challenge", "GroupId": group_id,
                               "RewardGroupId": reward_group_id, "Slot": slot,
                               "StageKey": [stage.get("PuzzleMapId"), stage.get("PuzzleStageNo"), stage.get("PuzzleType")]})
            result.append({
                "Slot": slot,
                "PuzzleAchievementGroupId": group_id,
                "AchievementTypeCode": group.get("PuzzleAchievementTypeCode") if group else None,
                "DescriptionTemplate": group.get("Description", "") if group else "",
                "Description": _render_achievement(group, achievement),
                "ClearRequireCount": achievement.get("ClearRequireCount") if achievement else None,
                "PuzzleAchievementTargetId": achievement.get("PuzzleAchievementTargetId") if achievement else None,
                "Value1": achievement.get("Value1") if achievement else None,
                "Value2": achievement.get("Value2") if achievement else None,
                "DirectRewardGroupId": reward_group_id,
                "Rewards": [{k: reward.get(k) for k in (
                    "RewardTypeCode", "RewardTargetId", "RewardName", "RewardCount", "Resolution"
                )} for reward in rewards],
                "Resolution": resolution,
            })
        return result

    # Descriptive navigation ordinal only. It is deliberately NOT named prerequisite depth.
    navigation_ordinal = {}
    nav_groups = defaultdict(list)
    for row in tables.rows("mst_puzzle_stage", active_only=False):
        nav_groups[(row.get("PuzzleMapId"), row.get("PageNo"), row.get("PuzzleType"))].append(row)
    for key, rows in nav_groups.items():
        ordered = sorted(rows, key=lambda r: (r.get("PuzzleStageNo", 0), r.get("ReleaseDateTime", ""), r.get("MusicPuzzleStageId", 0)))
        for index, row in enumerate(ordered, 1):
            navigation_ordinal[(row.get("PuzzleMapId"), row.get("PuzzleStageNo"), row.get("PuzzleType"))] = index

    stage_rows = []
    for row in sorted(tables.rows("mst_puzzle_stage", active_only=False), key=lambda r: (r.get("PuzzleMapId", 0), r.get("PuzzleStageNo", 0), r.get("PuzzleType", 0))):
        key = (row.get("PuzzleMapId"), row.get("PuzzleStageNo"), row.get("PuzzleType"))
        map_row = maps.get(row.get("PuzzleMapId"), {})
        reward_profile = achievement_rewards.get(row.get("PuzzleAchievementRewardId"), {})
        stage_rows.append({
            "PuzzleMapId": key[0], "PuzzleStageNo": key[1], "PuzzleType": key[2],
            "Owner": owner(map_row), "Music": music_info(row),
            "PageNo": row.get("PageNo"), "PuzzleStageType": row.get("PuzzleStageType"),
            "IsHidden": row.get("IsHidden", False),
            "IsCoinStage": row.get("IsCoinStage"),
            "MarvelousChallengeId": row.get("MarvelousChallengeId"),
            "Availability": _window(row.get("ReleaseDateTime") or row.get("DisplayStartTime"), row.get("EndTime")),
            "NavigationOrdinal": navigation_ordinal.get(key),
            "UnlockConditions": unlocks(row),
            "Challenges": challenges(row),
            "Score": {"SSRankScore": row.get("SSRankScore"), "AverageCombo": row.get("AverageCombo")},
            "ComboBorders": [row.get("ComboBorderValue1"), row.get("ComboBorderValue2"), row.get("ComboBorderValue3")],
            "ScoreRewardGroupIds": {rank: reward_profile.get(f"RewardScoreRank{rank}") for rank in ("D", "C", "B", "A", "S", "SS")},
            "ComboRewardGroupIds": [reward_profile.get(f"RewardComboBorderValue{i}") for i in range(1, 4)],
            "ConsumeStamina": row.get("ConsumeStamina"), "ConsumeEventStamina": row.get("ConsumeEventStamina"),
            "PuzzleAchievementRewardId": row.get("PuzzleAchievementRewardId"),
            "PuzzleDropRewardLotteryCountId": row.get("PuzzleDropRewardLotteryCountId"),
            "DropGroupIds": {rank: row.get(f"PuzzleDropRewardGroupId{rank}", 0) for rank in RANKS},
            "BasicDropGroupIds": {rank: row.get(f"PuzzleDropRewardBasicGroupId{rank}", 0) for rank in RANKS},
            "PickUpItemIds": list(row.get("PickUpItemIds") or []),
            "DisplayGetRouteItemIds": list(row.get("DisplayGetRouteItemIds") or []),
            "PuzzleEventRewardId": row.get("PuzzleEventRewardId"),
            "RawEventId": row.get("EventId", 0),
        })

    campaign_rows = []
    for row in tables.rows("mst_puzzle_stage_campaign", active_only=False):
        cid = row.get("CampaignId")
        campaign = campaigns.get(cid, {})
        campaign_rows.append({
            "PuzzleMapId": row.get("PuzzleMapId"), "PuzzleStageNo": row.get("PuzzleStageNo"), "PuzzleType": row.get("PuzzleType"),
            "CampaignId": cid, "CampaignTitle": campaign.get("CampaignTitle", ""),
            "Availability": _window(campaign.get("StartTime"), campaign.get("EndTime")),
            "DropGroupIds": {rank: row.get(f"PuzzleDropRewardGroupId{rank}", 0) for rank in RANKS},
            "BasicDropGroupIds": {rank: row.get(f"PuzzleDropRewardBasicGroupId{rank}", 0) for rank in RANKS},
            "PuzzleDropRewardLotteryCountId": row.get("PuzzleDropRewardLotteryCountId"),
            "PickUpItemIds": list(row.get("PickUpItemIds") or []),
            "DisplayGetRouteItemIds": list(row.get("DisplayGetRouteItemIds") or []),
        })

    referenced_drop_groups = {gid for row in stage_rows + campaign_rows for gid in row["DropGroupIds"].values() if gid}
    referenced_basic_groups = {gid for row in stage_rows + campaign_rows for gid in row["BasicDropGroupIds"].values() if gid}

    drop_groups = []
    for gid in sorted(drop_rows):
        rewards = []
        for row in sorted(drop_rows.get(gid, []), key=lambda r: r.get("PuzzleDropRewardSequenceNo", 0)):
            resolved = ({"RewardName": "无掉落", "Resolution": "no_drop"}
                        if row.get("RewardTypeCode") == 0 and row.get("RewardTargetId") == 0
                        else resolver.resolve(row))
            rewards.append({
                "SequenceNo": row.get("PuzzleDropRewardSequenceNo"), "LotteryRateRaw": row.get("LotteryRate"),
                "IsEventFlag": row.get("IsEvent"), "RewardTypeCode": row.get("RewardTypeCode"),
                "RewardTargetId": row.get("RewardTargetId"), "RewardCount": row.get("RewardCount"),
                "RewardName": resolved.get("RewardName"), "Resolution": resolved.get("Resolution"),
            })
        drop_groups.append({"PuzzleDropRewardGroupId": gid, "Rewards": rewards})

    basic_groups = []
    for gid in sorted(referenced_basic_groups):
        basic_groups.append({
            "PuzzleDropRewardBasicGroupId": gid,
            "Rewards": [{k: resolved.get(k) for k in (
                "RewardTypeCode", "RewardTargetId", "RewardName", "RewardCount", "Resolution"
            )} for row in sorted(basic_rows.get(gid, []), key=lambda r: r.get("PuzzleDropRewardBasicSequenceNo", 0))
                for resolved in [({**row, "RewardName": "旅行币（依活动而定）", "Resolution": "context_required"}
                    if row.get("RewardTypeCode") == 102 and row.get("RewardTargetId") == 0
                    else resolver.resolve(row))]],
        })

    # Event currencies are a separate clear-reward pipeline, not mst_puzzle_drop_reward targets.
    event_clear_rewards = []
    for event_id, target_ids in sorted(event_item_ids.items()):
        event = events.get(event_id, {})
        event_clear_rewards.append({
            "EventId": event_id, "EventTitle": event.get("EventTitle", ""),
            "Availability": _window(event.get("OpenStartTime") or event.get("StartTime"), event.get("EndTime")),
            "TargetItemIds": target_ids,
            "TargetItems": {field: {"ItemId": iid, "ItemName": items.get(iid, {}).get("ItemName", "")} for field, iid in target_ids.items()},
        })

    source = {
        "Meta": {"SchemaVersion": 3, "Domain": "puzzle_stages"},
        "Maps": [{**row, "Owner": owner(row)} for row in tables.rows("mst_puzzle_map", active_only=False)],
        "Stages": stage_rows,
        "CampaignOverlays": campaign_rows,
        "DropGroups": drop_groups,
        "BasicDropGroups": basic_groups,
        "DropLotteryCountProfiles": list(lottery_counts.values()),
        "PuzzleEventRewardProfiles": list(event_reward_profiles.values()),
        "PuzzleRewardRateProfiles": list(reward_rates.values()),
        "EventClearRewardTargets": event_clear_rewards,
        "Items": [{k: row.get(k) for k in ("ItemId", "ItemName", "ItemTypeCode", "ItemRarityCode", "ItemRouteCode", "ItemFileName")} for row in tables.rows("mst_item", active_only=False)],
        "Characters": [{k: row.get(k) for k in ("CharacterId", "CharacterNameJpn", "CharacterNameEng", "CharacterGroupCode")} for row in tables.rows("mst_character", active_only=False)],
        "Issues": issues + resolver.issues,
        "UnresolvedSemantics": [
            "PuzzleStageUnlockConditionCode enum meanings are not named in masterdata; keep ConditionCode/Value1..4 raw.",
            "LotteryRate is a raw weight; this export does not infer a denominator/probability.",
            "NavigationOrdinal is UI depth only, not a proven mandatory-clear chain.",
        ],
    }
    return source


def _same_music_audit(tables):
    rows = [row for row in tables.rows("mst_puzzle_stage", active_only=False)
            if 1 <= row.get("PuzzleMapId", 0) <= 21 and row.get("PageNo") == 1]
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("MusicPuzzleStageId"), row.get("PuzzleType"))].append(row)
    repeated = {key: value for key, value in groups.items() if len(value) > 1}
    fields = [
        *(f"PuzzleDropRewardGroupId{rank}" for rank in RANKS),
        *(f"PuzzleDropRewardBasicGroupId{rank}" for rank in RANKS),
        "PuzzleDropRewardLotteryCountId", "PuzzleAchievementRewardId", "SSRankScore", "AverageCombo",
        "PuzzleExtraNo1", "PuzzleExtraNo2", "PuzzleExtraNo3", "PuzzleExtraNo4", "PickUpItemIds", "DisplayGetRouteItemIds",
    ]
    def signature(row):
        result = []
        for field in fields:
            value = row.get(field)
            result.append((field, tuple(value) if isinstance(value, list) else value))
        return tuple(result)
    return {
        "CharacterPage1StageRows": len(rows),
        "MusicPuzzleStageAndTypeGroups": len(groups),
        "RepeatedAcrossCharacterMaps": len(repeated),
        "RepeatedWithDifferentDropChallengeScoreConfig": sum(1 for group in repeated.values() if len({signature(row) for row in group}) > 1),
    }


def run(session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    source = extract(session=session)
    save_json(source, json_path("Puzzle_Stage_Source.json"))
    audit = {
        "Counts": {key: len(value) for key, value in source.items() if isinstance(value, list)},
        "SameMusicAudit": _same_music_audit(tables),
        "UnlockConditionCodes": dict(Counter(
            row.get("PuzzleStageUnlockConditionCode")
            for row in tables.rows("mst_puzzle_stage_unlock_condition", active_only=False)
        )),
        "UnresolvedSemantics": source["UnresolvedSemantics"],
    }
    save_json(audit, audit_path("puzzle_stage_audit.json"))
    if source["Issues"]:
        record_warning(f"Puzzle stage export has {len(source['Issues'])} unresolved relations; inspect puzzle_stage_audit.json")
    print(f"[+] Puzzle stages: {len(source['Stages'])} stage instances / {len(source['CampaignOverlays'])} campaign overlays")
    return source
