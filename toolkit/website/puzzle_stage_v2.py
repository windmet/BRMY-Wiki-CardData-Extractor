from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .common import MasterData, stage_key, window, write_json

RANKS = ("SS", "S", "A", "B", "C", "D", "E")
BASIC_PIECE_IDS = (1, 2, 3, 4, 5, 6)
ATTRIBUTE_PIECES = {
    "SUN": (1, 2),
    "MOON": (3, 4),
    "STAR": (5, 6),
}


def extract(md: MasterData) -> dict[str, Any]:
    maps = md.by_id("mst_puzzle_map", "PuzzleMapId")
    characters = md.by_id("mst_character", "CharacterId")
    events = md.by_id("mst_event", "EventId")
    campaigns = md.by_id("mst_campaign", "CampaignId")
    music_stage = md.by_id("mst_music_puzzle_stage", "MusicPuzzleStageId")
    music = md.by_id("mst_music", "MusicId")
    pieces = md.by_id("mst_piece_info", "PieceInfoId")
    regulations = md.by_id("mst_puzzle_regulation", "PuzzleRegulationId")

    tutorials_by_piece: dict[int, list[dict[str, Any]]] = defaultdict(list)
    global_rule_tutorials: list[dict[str, Any]] = []
    for row in md.rows("mst_gimmick_tutorial"):
        projected = {
            "TutorialId": row.get("TutorialId"),
            "GimmickSlideNo": row.get("GimmickSlideNo"),
            "GimmickName": row.get("GimmickName", ""),
            "Description": row.get("GimmickDescription", ""),
            "PieceInfoIds": list(row.get("PieceInfoIds") or []),
        }
        pids = projected["PieceInfoIds"]
        # Only direct piece links are safe stage-level evidence. Tutorials whose
        # PieceInfoIds are just generic piece 1 are kept as global rules instead.
        linked_special = [pid for pid in pids if isinstance(pid, int) and abs(pid) >= 1000]
        if linked_special:
            for pid in linked_special:
                tutorials_by_piece[pid].append(projected)
        else:
            global_rule_tutorials.append(projected)

    quiz_by_stage = {stage_key(r): r for r in md.rows("mst_puzzle_stage_quiz_question")}
    preset_by_stage = {stage_key(r): r for r in md.rows("mst_puzzle_stage_preset")}

    # Drop-group reuse is useful for UI summarization. It is descriptive only;
    # do not turn it into a probability claim.
    group_usage = Counter()
    basic_group_usage = Counter()
    for row in md.rows("mst_puzzle_stage"):
        for rank in RANKS:
            gid = int(row.get(f"PuzzleDropRewardGroupId{rank}") or 0)
            if gid:
                group_usage[gid] += 1
            bgid = int(row.get(f"PuzzleDropRewardBasicGroupId{rank}") or 0)
            if bgid:
                basic_group_usage[bgid] += 1
    for row in md.rows("mst_puzzle_stage_campaign"):
        for rank in RANKS:
            gid = int(row.get(f"PuzzleDropRewardGroupId{rank}") or 0)
            if gid:
                group_usage[gid] += 1
            bgid = int(row.get(f"PuzzleDropRewardBasicGroupId{rank}") or 0)
            if bgid:
                basic_group_usage[bgid] += 1

    def owner(map_id: int) -> dict[str, Any]:
        row = maps.get(map_id, {})
        if row.get("CharacterId"):
            cid = row["CharacterId"]
            return {"Kind": "character", "CharacterId": cid, "CharacterName": characters.get(cid, {}).get("CharacterNameJpn", "")}
        if row.get("EventId"):
            eid = row["EventId"]
            ev = events.get(eid, {})
            return {"Kind": "event", "EventId": eid, "EventTitle": ev.get("EventTitle", ""), "Availability": window(ev.get("OpenStartTime") or ev.get("StartTime"), ev.get("EndTime"))}
        if row.get("CampaignId"):
            cid = row["CampaignId"]
            cp = campaigns.get(cid, {})
            return {"Kind": "campaign", "CampaignId": cid, "CampaignTitle": cp.get("CampaignTitle", ""), "Availability": window(cp.get("StartTime"), cp.get("EndTime"))}
        return {"Kind": "other"}

    def music_info(row: dict[str, Any]) -> dict[str, Any]:
        rel = music_stage.get(row.get("MusicPuzzleStageId"), {})
        master = music.get(rel.get("MusicId"), {})
        return {
            "MusicPuzzleStageId": row.get("MusicPuzzleStageId"),
            "MusicId": rel.get("MusicId"),
            "DisplayName": master.get("DisplayName", ""),
            "ArtistName": master.get("ArtistName", ""),
            "ArtistNameInformal": master.get("ArtistNameInformal", ""),
            "MusicType": master.get("MusicType"),
            "CharacterId": master.get("CharacterId"),
        }

    def regulation(reg_id: int | None) -> dict[str, Any] | None:
        if not reg_id:
            return None
        row = regulations.get(reg_id)
        if not row:
            return {"PuzzleRegulationId": reg_id, "Resolution": "missing"}
        return {
            "PuzzleRegulationId": reg_id,
            "CharacterCardIds": list(row.get("CharacterCardIds") or []),
            "CharacterIds": list(row.get("CharacterIds") or []),
            "CardRarityCodes": list(row.get("CardRarityCodes") or []),
            "CardAttributeCodes": list(row.get("CardAttributeCodes") or []),
            "Resolution": "masterdata",
        }

    stages: list[dict[str, Any]] = []
    for row in sorted(md.rows("mst_puzzle_stage"), key=lambda x: (x.get("PuzzleMapId", 0), x.get("PuzzleStageNo", 0), x.get("PuzzleType", 0))):
        pids = list(row.get("PieceInfoIds") or [])
        basic_ids = [pid for pid in pids if pid in BASIC_PIECE_IDS]
        special_ids = [pid for pid in pids if pid not in BASIC_PIECE_IDS]
        basic = [{"PieceInfoId": pid, "Name": pieces.get(pid, {}).get("Name", ""), "PieceColor": pieces.get(pid, {}).get("PieceColor")} for pid in basic_ids]
        special = []
        for pid in special_ids:
            prow = pieces.get(pid, {})
            special.append({
                "PieceInfoId": pid,
                "Name": prow.get("Name", ""),
                "Race": prow.get("Race"),
                "Hp": prow.get("Hp"),
                "PieceColor": prow.get("PieceColor"),
                "IsSwap": prow.get("IsSwap"),
                "IsMatch": prow.get("IsMatch"),
                "IsGravity": prow.get("IsGravity"),
                "GimmickTutorials": tutorials_by_piece.get(pid, []),
            })
        attrs = {
            name: {
                "PieceIds": list(pair),
                "PresentPieceIds": [pid for pid in pair if pid in basic_ids],
                "Complete": all(pid in basic_ids for pid in pair),
                "Partial": any(pid in basic_ids for pid in pair),
            }
            for name, pair in ATTRIBUTE_PIECES.items()
        }
        q = quiz_by_stage.get(stage_key(row))
        preset = preset_by_stage.get(stage_key(row))
        stages.append({
            "StageKey": stage_key(row),
            "PuzzleMapId": row.get("PuzzleMapId"),
            "PuzzleStageNo": row.get("PuzzleStageNo"),
            "PuzzleType": row.get("PuzzleType"),
            "PuzzleStageType": row.get("PuzzleStageType"),
            "MarvelousChallengeId": row.get("MarvelousChallengeId", 0),
            "Owner": owner(row.get("PuzzleMapId")),
            "Music": music_info(row),
            "PageNo": row.get("PageNo"),
            "Availability": window(row.get("ReleaseDateTime") or row.get("DisplayStartTime"), row.get("EndTime")),
            "IsHidden": bool(row.get("IsHidden")),
            "IsCoinStage": bool(row.get("IsCoinStage")),
            "CardAttributeCode": row.get("CardAttributeCode"),
            "ConsumeStamina": row.get("ConsumeStamina"),
            "ConsumeEventStamina": row.get("ConsumeEventStamina"),
            "SpCost": row.get("SpCost"),
            "SSRankScore": row.get("SSRankScore"),
            "AverageCombo": row.get("AverageCombo"),
            "PieceProfile": {
                "PieceInfoIds": pids,
                "BasicPieces": basic,
                "SpecialPieces": special,
                "Attributes": attrs,
            },
            "Regulations": {
                "Leader": regulation(row.get("LeaderPuzzleRegulationId")),
                "Member": regulation(row.get("MemberPuzzleRegulationId")),
            },
            "Quiz": None if not q else {"QuestionIds": list(q.get("QuestionIds") or [])},
            "Preset": None if not preset else {
                "TitleName": preset.get("TitleName", ""),
                "ScriptFileNameA": preset.get("ScriptFileNameA", ""),
                "ScriptFileNameB": preset.get("ScriptFileNameB", ""),
                "LeaderCharacterCardId": preset.get("LeaderCharacterCardId"),
                "MemberCharacterCardIds": list(preset.get("MemberCharacterCardIds") or []),
            },
            "DropRefs": {
                "PickUpItemIds": list(row.get("PickUpItemIds") or []),
                "DisplayGetRouteItemIds": list(row.get("DisplayGetRouteItemIds") or []),
                "DropGroupIds": {rank: int(row.get(f"PuzzleDropRewardGroupId{rank}") or 0) for rank in RANKS},
                "BasicDropGroupIds": {rank: int(row.get(f"PuzzleDropRewardBasicGroupId{rank}") or 0) for rank in RANKS},
            },
        })

    # Safe grouping for card-style character playlist UI. PuzzleType itself is
    # a variant only when the rest of this identity agrees.
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for stage in stages:
        m = stage["Music"]
        group_key = (
            stage["PuzzleMapId"], stage["PuzzleStageNo"], m.get("MusicPuzzleStageId"),
            stage.get("PuzzleStageType"), stage.get("MarvelousChallengeId", 0),
        )
        grouped[group_key].append(stage)

    stage_groups = []
    for key, rows in sorted(grouped.items(), key=lambda kv: tuple(x or 0 for x in kv[0])):
        first = rows[0]
        stage_groups.append({
            "GroupKey": ":".join(str(x) for x in key),
            "PuzzleMapId": first["PuzzleMapId"],
            "PuzzleStageNo": first["PuzzleStageNo"],
            "Owner": first["Owner"],
            "Music": first["Music"],
            "PuzzleStageType": first["PuzzleStageType"],
            "MarvelousChallengeId": first["MarvelousChallengeId"],
            "Variants": [
                {
                    "StageKey": r["StageKey"],
                    "PuzzleType": r["PuzzleType"],
                    "PieceProfile": r["PieceProfile"],
                    "IsCoinStage": r["IsCoinStage"],
                    "CardAttributeCode": r["CardAttributeCode"],
                    "SSRankScore": r["SSRankScore"],
                    "DropRefs": r["DropRefs"],
                }
                for r in sorted(rows, key=lambda x: x["PuzzleType"])
            ],
        })

    reverse_piece = defaultdict(list)
    for stage in stages:
        for pid in stage["PieceProfile"]["PieceInfoIds"]:
            reverse_piece[str(pid)].append(stage["StageKey"])

    piece_catalog = []
    for pid, row in sorted(pieces.items(), key=lambda kv: kv[0]):
        piece_catalog.append({
            "PieceInfoId": pid,
            "Name": row.get("Name", ""),
            "Race": row.get("Race"),
            "Hp": row.get("Hp"),
            "PieceColor": row.get("PieceColor"),
            "IsSwap": row.get("IsSwap"),
            "IsMatch": row.get("IsMatch"),
            "IsGravity": row.get("IsGravity"),
            "Tutorials": tutorials_by_piece.get(pid, []),
        })

    return {
        "Meta": {
            "Domain": "puzzle_stage_v2",
            "Notes": [
                "PieceInfoIds is native stage data and is safe for piece-presence filtering.",
                "Global rules such as GRAVITY/MOVE LIMIT/NO SEEK BAR are not assigned to stages without a verified FK.",
                "StageGroup is a presentation grouping; StageKey remains the canonical instance identity.",
            ],
        },
        "Stages": stages,
        "StageGroups": stage_groups,
        "PieceCatalog": piece_catalog,
        "ReversePieceIndex": dict(reverse_piece),
        "DropGroupUsage": {
            "Random": {str(k): v for k, v in sorted(group_usage.items())},
            "Basic": {str(k): v for k, v in sorted(basic_group_usage.items())},
        },
        "UnboundRuleCatalog": global_rule_tutorials,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("masterdata")
    ap.add_argument("--output", default="Puzzle_Stage_V2_Source.json")
    args = ap.parse_args()
    md = MasterData.load(args.masterdata)
    result = extract(md)
    write_json(args.output, result)
    print(f"wrote {args.output}: {len(result['Stages'])} stages / {len(result['StageGroups'])} groups / {len(result['PieceCatalog'])} pieces")


if __name__ == "__main__":
    main()
