"""Bartending event / shift / ingredient-stage extraction.

This module is intentionally separate from the normal Puzzle drop domain.

Verified snapshot contract (2026-09-22 masterdata):
- Bartending events are rows in mst_event_b.
- A bartending event owns one PuzzleMap through mst_puzzle_map.EventId.
- Event-map Puzzle stages can be assigned to exactly one mst_event_shift by an
  exact interval join inside the same EventId:
      stage.ReleaseDateTime == shift.StartTime
      stage.EndTime == shift.EndTime
- The join is derived evidence, not an explicit foreign key. It is exported with
  JoinMethod so downstream code does not mistake it for a native ShiftId.
- Ingredient overlays are keyed by (EventId, PuzzleMapId, PuzzleStageNo,
  PuzzleType). Event-map overlays are the primary shift-stage drops. Overlays on
  other maps are supplemental Playlist drops for that event and are *not*
  assigned to a shift without further evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict

RANKS = ("SS", "S", "A", "B", "C", "D", "E")


def _by_id(tables, name, key):
    return tables.by_id(name, key, required=False, active_only=False)


def _group(tables, name, key):
    return tables.group_by(name, key, required=False, active_only=False)


def _window(start, end):
    return {"StartTime": start or "", "EndTime": end or ""}


def _stage_key(row):
    return f"{row.get('PuzzleMapId')}:{row.get('PuzzleStageNo')}:{row.get('PuzzleType')}"


def extract(session, puzzle):
    tables = session.tables
    events = _by_id(tables, "mst_event", "EventId")
    characters = _by_id(tables, "mst_character", "CharacterId")
    maps = {m["PuzzleMapId"]: m for m in puzzle["Maps"]}
    ingredients = _by_id(tables, "mst_event_ingredient", "IngredientId")

    bartending_ids = {
        row.get("EventId")
        for row in tables.rows("mst_event_b", active_only=False)
        if row.get("EventId")
    }
    shifts_by_event = _group(tables, "mst_event_shift", "EventId")
    maps_by_event = defaultdict(list)
    for row in puzzle['Maps']: maps_by_event[row.get('EventId')].append(row)
    stages_by_map = defaultdict(list)
    canonical_stages = [{**s, 'MusicPuzzleStageId':s['Music']['MusicPuzzleStageId'], 'ReleaseDateTime':s['Availability']['StartTime'], 'EndTime':s['Availability']['EndTime']} for s in puzzle['Stages']]
    for row in canonical_stages: stages_by_map[row['PuzzleMapId']].append(row)
    overlays_by_event = _group(tables, "mst_event_puzzle_stage_ingredient", "EventId")
    ingredient_drop_rows = _group(
        tables,
        "mst_event_puzzle_drop_reward_ingredient",
        "PuzzleDropRewardIngredientGroupId",
    )

    stage_lookup = {}
    duplicate_stage_keys = set()
    for row in canonical_stages:
        key = _stage_key(row)
        if key in stage_lookup:
            duplicate_stage_keys.add(key)
        stage_lookup[key] = row

    overlay_lookup = {}
    duplicate_overlay_keys = set()
    for row in tables.rows("mst_event_puzzle_stage_ingredient", active_only=False):
        key = (row.get("EventId"), _stage_key(row))
        if key in overlay_lookup:
            duplicate_overlay_keys.add(key)
        overlay_lookup[key] = row

    issues = []
    if duplicate_stage_keys:
        issues.append({"Status": "duplicate_stage_identity", "Keys": sorted(duplicate_stage_keys)})
    if duplicate_overlay_keys:
        issues.append({"Status": "duplicate_ingredient_overlay", "Keys": [list(x) for x in sorted(duplicate_overlay_keys)]})

    def music_info(stage):
        return stage['Music']

    def ingredient_config(event_id, stage):
        row = overlay_lookup.get((event_id, _stage_key(stage)))
        if not row:
            return None
        return {
            "PickUpIngredientIds": list(row.get("PickUpIngredientIds") or []),
            "DisplayGetRouteIngredientIds": list(row.get("DisplayGetRouteIngredientIds") or []),
            "IngredientDropGroupIds": {
                rank: row.get(f"PuzzleDropRewardIngredientGroupId{rank}", 0)
                for rank in RANKS
            },
            "PuzzleDropRewardLotteryCountId": row.get("PuzzleDropRewardLotteryCountId"),
        }

    def stage_projection(event_id, stage, *, track_role, shift_id=None):
        return {
            "StageKey": _stage_key(stage),
            "PuzzleMapId": stage.get("PuzzleMapId"),
            "PuzzleStageNo": stage.get("PuzzleStageNo"),
            "PuzzleType": stage.get("PuzzleType"),
            "PuzzleStageType": stage.get("PuzzleStageType"),
            "IsHidden": bool(stage.get("IsHidden", False)),
            "Music": music_info(stage),
            "Availability": _window(stage.get("ReleaseDateTime"), stage.get("EndTime")),
            "DerivedShiftId": shift_id,
            "ShiftJoinMethod": "exact_event_and_stage_window" if shift_id else None,
            "TrackRole": track_role,
            "IngredientConfig": ingredient_config(event_id, stage),
        }

    source_events = []
    supplemental = []
    referenced_group_ids = set()
    event_audit = []

    for event_id in sorted(bartending_ids):
        event = events.get(event_id, {})
        if not event:
            issues.append({"Status": "missing_event", "EventId": event_id})
        shifts = sorted(
            shifts_by_event.get(event_id, []),
            key=lambda row: (row.get("StartTime", ""), row.get("ShiftId", 0)),
        )
        event_maps = [row for row in maps_by_event.get(event_id, []) if row.get("PuzzleMapId")]
        event_map_ids = {row["PuzzleMapId"] for row in event_maps}
        event_stages = sorted(
            [stage for map_id in event_map_ids for stage in stages_by_map.get(map_id, [])],
            key=lambda row: (
                row.get("ReleaseDateTime", ""),
                row.get("PuzzleStageNo", 0),
                row.get("PuzzleType", 0),
            ),
        )

        shift_stage_rows = defaultdict(list)
        unmatched_stage_keys = []
        ambiguous_stage_keys = []
        for stage in event_stages:
            matches = [
                shift
                for shift in shifts
                if stage.get("ReleaseDateTime") == shift.get("StartTime")
                and stage.get("EndTime") == shift.get("EndTime")
            ]
            if len(matches) == 1:
                shift_stage_rows[matches[0]["ShiftId"]].append(stage)
            elif not matches:
                unmatched_stage_keys.append(_stage_key(stage))
            else:
                ambiguous_stage_keys.append(_stage_key(stage))

        if unmatched_stage_keys:
            issues.append({
                "Status": "unmatched_event_stage_to_shift",
                "EventId": event_id,
                "StageKeys": unmatched_stage_keys,
            })
        if ambiguous_stage_keys:
            issues.append({
                "Status": "ambiguous_event_stage_to_shift",
                "EventId": event_id,
                "StageKeys": ambiguous_stage_keys,
            })

        # A shared track is derived only when the same MusicPuzzleStageId is
        # present in every shift. No fixed assumption is made about count or sides.
        music_sets = []
        for shift in shifts:
            music_sets.append({
                stage.get("MusicPuzzleStageId")
                for stage in shift_stage_rows.get(shift.get("ShiftId"), [])
                if stage.get("MusicPuzzleStageId")
            })
        shared_music_ids = set.intersection(*music_sets) if music_sets else set()

        source_shifts = []
        primary_overlay_count = 0
        for shift in shifts:
            shift_id = shift.get("ShiftId")
            projected_stages = []
            for stage in sorted(
                shift_stage_rows.get(shift_id, []),
                key=lambda row: (row.get("PuzzleStageNo", 0), row.get("PuzzleType", 0)),
            ):
                config = ingredient_config(event_id, stage)
                if config:
                    primary_overlay_count += 1
                    referenced_group_ids.update(gid for gid in config["IngredientDropGroupIds"].values() if gid)
                role = (
                    "shared_event_track"
                    if stage.get("MusicPuzzleStageId") in shared_music_ids
                    else "shift_rotation_track"
                )
                projected_stages.append(
                    stage_projection(event_id, stage, track_role=role, shift_id=shift_id)
                )
            cid = shift.get("CharacterId")
            if cid not in characters:
                issues.append({"Status": "missing_shift_character", "ShiftId": shift_id})
            source_shifts.append({
                "ShiftId": shift_id,
                "CharacterId": cid,
                "CharacterName": characters.get(cid, {}).get("CharacterNameJpn", ""),
                "Availability": _window(shift.get("StartTime"), shift.get("EndTime")),
                "Stages": projected_stages,
            })

        event_overlays = overlays_by_event.get(event_id, [])
        supplemental_count = 0
        for overlay in event_overlays:
            if _stage_key(overlay) not in stage_lookup:
                issues.append({"Status": "overlay_missing_stage", "EventId": event_id, "StageKey": _stage_key(overlay)})
            if overlay.get("PuzzleMapId") in event_map_ids:
                continue
            supplemental_count += 1
            key = _stage_key(overlay)
            base_stage = stage_lookup.get(key)
            map_row = maps.get(overlay.get("PuzzleMapId"), {})
            config = {
                "PickUpIngredientIds": list(overlay.get("PickUpIngredientIds") or []),
                "DisplayGetRouteIngredientIds": list(overlay.get("DisplayGetRouteIngredientIds") or []),
                "IngredientDropGroupIds": {
                    rank: overlay.get(f"PuzzleDropRewardIngredientGroupId{rank}", 0)
                    for rank in RANKS
                },
                "PuzzleDropRewardLotteryCountId": overlay.get("PuzzleDropRewardLotteryCountId"),
            }
            referenced_group_ids.update(gid for gid in config["IngredientDropGroupIds"].values() if gid)
            supplemental.append({
                "EventId": event_id,
                "EventTitle": event.get("EventTitle", ""),
                "StageKey": key,
                "Owner": base_stage["Owner"],
                "ShiftAssociation": None,
                "Music": music_info(base_stage or overlay),
                "IngredientConfig": config,
            })
            if not base_stage:
                issues.append({
                    "Status": "supplemental_overlay_missing_base_stage",
                    "EventId": event_id,
                    "StageKey": key,
                })

        source_events.append({
            "EventId": event_id,
            "EventTitle": event.get("EventTitle", ""),
            "Availability": _window(
                event.get("OpenStartTime") or event.get("StartTime"),
                event.get("EndTime"),
            ),
            "EventMapIds": sorted(event_map_ids),
            "SharedMusicPuzzleStageIds": sorted(shared_music_ids),
            "Shifts": source_shifts,
        })
        event_audit.append({
            "EventId": event_id,
            "EventTitle": event.get("EventTitle", ""),
            "ShiftCount": len(shifts),
            "EventMapStageCount": len(event_stages),
            "ExactShiftStageMatchCount": sum(len(rows) for rows in shift_stage_rows.values()),
            "PrimaryIngredientOverlayCount": primary_overlay_count,
            "SupplementalIngredientOverlayCount": supplemental_count,
            "SharedMusicPuzzleStageIds": sorted(shared_music_ids),
        })

    ingredient_groups = []
    referenced_ingredient_ids = set()
    for group_id in sorted(referenced_group_ids):
        rewards = []
        for row in sorted(
            ingredient_drop_rows.get(group_id, []),
            key=lambda value: value.get("PuzzleDropRewardIngredientSequenceNo", 0),
        ):
            ingredient_id = row.get("RewardTargetId")
            if ingredient_id not in ingredients:
                issues.append({"Status": "missing_ingredient", "IngredientId": ingredient_id})
            referenced_ingredient_ids.add(ingredient_id)
            rewards.append({
                "SequenceNo": row.get("PuzzleDropRewardIngredientSequenceNo"),
                "LotteryRateRaw": row.get("LotteryRate"),
                "RewardTypeCode": row.get("RewardTypeCode"),
                "RewardTargetId": ingredient_id,
                "RewardCount": row.get("RewardCount"),
                "RewardName": ingredients.get(ingredient_id, {}).get(
                    "IngredientName", f"Ingredient({ingredient_id})"
                ),
            })
        ingredient_groups.append({
            "PuzzleDropRewardIngredientGroupId": group_id,
            "Rewards": rewards,
        })

    ingredient_catalog = []
    for ingredient_id in sorted(x for x in referenced_ingredient_ids if x):
        row = ingredients.get(ingredient_id, {})
        ingredient_catalog.append({
            "IngredientId": ingredient_id,
            "IngredientName": row.get("IngredientName", ""),
            "IngredientDescription": row.get("IngredientDescription", ""),
            "IngredientFileName": row.get("IngredientFileName", ""),
        })

    aggregate = {
        "BartendingEventCount": len(source_events),
        "ShiftCount": sum(len(event["Shifts"]) for event in source_events),
        "EventMapStageCount": sum(
            len(shift["Stages"])
            for event in source_events
            for shift in event["Shifts"]
        ),
        "PrimaryIngredientOverlayCount": sum(
            item["PrimaryIngredientOverlayCount"] for item in event_audit
        ),
        "SupplementalIngredientOverlayCount": len(supplemental),
        "UnmatchedOrAmbiguousEventMapStageCount": sum(
            1
            for issue in issues
            if issue.get("Status") in {
                "unmatched_event_stage_to_shift",
                "ambiguous_event_stage_to_shift",
            }
        ),
    }

    return {
        "Meta": {
            "SchemaVersion": 1,
            "Domain": "bartending",
            "ShiftStageJoin": {
                "Kind": "derived",
                "Method": "same EventId + exact stage ReleaseDateTime/EndTime == shift StartTime/EndTime",
                "NativeForeignKey": False,
            },
        },
        "Events": source_events,
        "SupplementalIngredientOverlays": supplemental,
        "IngredientDropGroups": ingredient_groups,
        "Ingredients": ingredient_catalog,
        "Audit": {
            "Aggregate": aggregate,
            "Events": event_audit,
            "PuzzleStageTypeCounts": dict(Counter(
                stage.get("PuzzleStageType")
                for event in source_events
                for shift in event["Shifts"]
                for stage in shift["Stages"]
            )),
        },
        "Issues": issues,
    }
