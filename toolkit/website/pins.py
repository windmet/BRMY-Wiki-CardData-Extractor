#!/usr/bin/env python3
"""Export the BREAK MY CASE Pins effect system from decoded master_data.json.

Maintainer-only source adapter. Website runtime consumes only the emitted JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIER_BY_LV2_POLISH = {1: 1, 2: 2, 5: 3, 10: 4, 20: 5}

BASE_EFFECTS = {
    "全てのステータスを{0}％上げる": ("all_stats", "全属性提升", "%", 100),
    "オーラのステータスを{0}％上げる": ("aura", "Aura提升", "%", 100),
    "ビジュアルのステータスを{0}％上げる": ("visual", "Visual提升", "%", 100),
    "カリスマのステータスを{0}％上げる": ("charisma", "Charisma提升", "%", 100),
    "SPスキルコストを{0}％ダウン": ("sp_cost", "SP技能COST降低", "%", 100),
    "オートスキルの効果時間を{0}秒伸ばす": ("auto_duration", "自动技能持续时间延长", "秒", 100),
    "コンビネーションスキルの効果を{0}％上乗せ": ("combination_bonus", "协作技能效果追加", "%", 1),
}


def load_master(path: Path) -> tuple[dict[str, Any], list[Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        raise ValueError("Unsupported master_data.json layout")
    return raw[0], raw


def table(index: dict[str, Any], raw: list[Any], name: str) -> list[dict[str, Any]]:
    names = list(index.keys())
    if name not in index:
        raise KeyError(f"Missing required table: {name}")
    rows = raw[names.index(name) + 1]
    if not isinstance(rows, list):
        raise TypeError(f"Table {name} is not an array")
    return rows


def active(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("IsActive", True)]


def base_description(description: str) -> str:
    return description.split("\n")[-1]


def display_value(raw_value: int | float, scale: int) -> float:
    return raw_value / scale


def format_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def material_rows(cost_row: dict[str, Any], item_by_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for slot in range(1, 7):
        item_id = int(cost_row.get(f"CostItemId{slot}", 0) or 0)
        count = int(cost_row.get(f"CostItemCount{slot}", 0) or 0)
        if not item_id:
            continue
        item = item_by_id.get(item_id)
        result.append({
            "ItemId": item_id,
            "ItemName": item.get("ItemName", "") if item else "",
            "Count": count,
        })
    return result


def export(input_path: Path) -> dict[str, Any]:
    index, raw = load_master(input_path)
    required = [
        "mst_pin_effect",
        "mst_pin_effect_activate_condition",
        "mst_pin_effect_category",
        "mst_pin_effect_level",
        "mst_pin_effect_lottery",
        "mst_pin_effect_lottery_item",
        "mst_item_pin_effect_level",
        "mst_item",
        "mst_character",
        "mst_campaign_pin_effect_lottery",
    ]
    tables = {name: active(table(index, raw, name)) for name in required}

    issues: list[dict[str, Any]] = []
    items = {int(x["ItemId"]): x for x in tables["mst_item"]}
    characters = {int(x["CharacterId"]): x for x in tables["mst_character"]}
    effect_rows = tables["mst_pin_effect"]
    effect_by_id = {int(x["PinEffectId"]): x for x in effect_rows}
    levels = defaultdict(dict)
    for row in tables["mst_pin_effect_level"]:
        levels[int(row["PinEffectId"])][int(row["PinEffectLevel"])] = row
    costs = defaultdict(dict)
    for row in tables["mst_item_pin_effect_level"]:
        costs[int(row["PinEffectId"])][int(row["PinEffectLevel"])] = row

    category_by_type: dict[int, dict[str, Any]] = {}
    for row in tables["mst_pin_effect_category"]:
        for effect_type in row.get("PinEffectTypes", []):
            category_by_type[int(effect_type)] = row

    conditions: list[dict[str, Any]] = [{
        "ConditionId": 0,
        "Kind": "none",
        "Description": "无条件",
        "CharacterId": None,
        "CardRarityCode": None,
    }]
    for row in tables["mst_pin_effect_activate_condition"]:
        cid = int(row["PinEffectActivateConditionId"])
        kind_code = int(row.get("PinEffectActivateCondition", 0) or 0)
        value1 = int(row.get("Value1", 0) or 0)
        if kind_code == 2:
            kind = "character_in_team"
            character_id = value1
            rarity = None
        elif kind_code == 1:
            kind = "card_rarity"
            character_id = None
            rarity = value1
        else:
            kind = f"unknown_{kind_code}"
            character_id = None
            rarity = None
            issues.append({"Type": "unknown_condition_kind", "ConditionId": cid, "Value": kind_code})
        conditions.append({
            "ConditionId": cid,
            "Kind": kind,
            "Description": row.get("Description", ""),
            "CharacterId": character_id,
            "CardRarityCode": rarity,
        })
    condition_by_id = {int(x["ConditionId"]): x for x in conditions}

    # Tier is not inferred from PinEffectId arithmetic. It is derived from the
    # actual Lv1->Lv2 Pins Polish cost, which currently forms five stable groups.
    tier_by_effect: dict[int, int] = {}
    for pid in effect_by_id:
        cost = costs.get(pid, {}).get(2)
        if not cost:
            issues.append({"Type": "missing_level2_cost", "PinEffectId": pid})
            continue
        if int(cost.get("CostItemId1", 0) or 0) != 566:
            issues.append({"Type": "unexpected_tier_item", "PinEffectId": pid, "Cost": cost})
            continue
        polish = int(cost.get("CostItemCount1", 0) or 0)
        tier = TIER_BY_LV2_POLISH.get(polish)
        if tier is None:
            issues.append({"Type": "unknown_tier_polish_cost", "PinEffectId": pid, "Polish": polish})
            continue
        tier_by_effect[pid] = tier

    effects: list[dict[str, Any]] = []
    referenced_materials: set[int] = set()
    group_members = defaultdict(list)
    for row in effect_rows:
        pid = int(row["PinEffectId"])
        description = str(row.get("Description", ""))
        base = base_description(description)
        if base not in BASE_EFFECTS:
            issues.append({"Type": "unknown_effect_description", "PinEffectId": pid, "Description": description})
            continue
        effect_key, effect_name_zh, unit, scale = BASE_EFFECTS[base]
        effect_type = int(row.get("PinEffectType", 0) or 0)
        category = category_by_type.get(effect_type)
        condition_id = int(row.get("PinEffectActivateConditionId", 0) or 0)
        condition = condition_by_id.get(condition_id)
        if not condition:
            issues.append({"Type": "missing_condition", "PinEffectId": pid, "ConditionId": condition_id})
            continue
        tier = tier_by_effect.get(pid)
        if tier is None:
            continue

        value_rows = []
        if set(levels.get(pid, {})) != {1, 2, 3, 4, 5}:
            issues.append({"Type": "invalid_level_set", "PinEffectId": pid, "Levels": sorted(levels.get(pid, {}))})
        for level in range(1, 6):
            level_row = levels.get(pid, {}).get(level)
            if not level_row:
                continue
            raw_value = level_row.get("EffectValue1", 0)
            shown = display_value(raw_value, scale)
            value_rows.append({
                "Level": level,
                "RawValue1": raw_value,
                "DisplayValue": shown,
                "DisplayUnit": unit,
                "DisplayText": description.replace("{0}", format_value(shown)),
            })

        upgrade_rows = []
        if set(costs.get(pid, {})) != {2, 3, 4, 5}:
            issues.append({"Type": "invalid_upgrade_level_set", "PinEffectId": pid, "Levels": sorted(costs.get(pid, {}))})
        for target_level in range(2, 6):
            cost_row = costs.get(pid, {}).get(target_level)
            if not cost_row:
                continue
            materials = material_rows(cost_row, items)
            referenced_materials.update(m["ItemId"] for m in materials)
            upgrade_rows.append({"TargetLevel": target_level, "Items": materials})

        effect = {
            "PinEffectId": pid,
            "EffectKey": effect_key,
            "EffectNameZh": effect_name_zh,
            "PinEffectType": effect_type,
            "CategoryName": category.get("CategoryName", "") if category else "",
            "DescriptionTemplate": description,
            "BaseDescription": base,
            "ConditionId": condition_id,
            "ConditionKind": condition["Kind"],
            "ConditionDescription": condition["Description"],
            "CharacterId": condition["CharacterId"],
            "CardRarityCode": condition["CardRarityCode"],
            "Tier": tier,
            "PolishCostToLevel2": int(costs[pid][2].get("CostItemCount1", 0) or 0),
            "DisplayScale": scale,
            "DisplayUnit": unit,
            "Levels": value_rows,
            "UpgradeCosts": upgrade_rows,
        }
        effects.append(effect)
        group_members[(effect_key, condition_id)].append(effect)

    # Each effect + condition should currently have exactly five tiers.
    for key, rows in group_members.items():
        tiers = sorted(x["Tier"] for x in rows)
        if tiers != [1, 2, 3, 4, 5]:
            issues.append({"Type": "tier_group_mismatch", "Group": key, "Tiers": tiers})

    base_effects = []
    for description, (effect_key, zh, unit, scale) in BASE_EFFECTS.items():
        matching = [x for x in effects if x["EffectKey"] == effect_key]
        types = sorted({x["PinEffectType"] for x in matching})
        categories = sorted({x["CategoryName"] for x in matching})
        base_effects.append({
            "EffectKey": effect_key,
            "EffectNameZh": zh,
            "BaseDescription": description,
            "PinEffectType": types[0] if len(types) == 1 else None,
            "CategoryName": categories[0] if len(categories) == 1 else "",
            "DisplayUnit": unit,
            "DisplayScale": scale,
        })

    chemical_group_by_item: dict[int, int] = {}
    for row in tables["mst_pin_effect_lottery_item"]:
        item_id = int(row["ItemId"])
        chemical_group_by_item[item_id] = int(row["PinEffectLotteryGroupId"])
        referenced_materials.add(item_id)

    lottery_entries = []
    totals = Counter()
    tier_totals = defaultdict(Counter)
    for row in tables["mst_pin_effect_lottery"]:
        group_id = int(row["PinEffectLotteryGroupId"])
        pid = int(row["PinEffectId"])
        rate = int(row.get("LotteryRate", 0) or 0)
        if pid not in effect_by_id:
            issues.append({"Type": "lottery_missing_effect", "PinEffectId": pid, "GroupId": group_id})
            continue
        if pid not in tier_by_effect:
            continue
        totals[group_id] += rate
        tier_totals[group_id][tier_by_effect[pid]] += rate
        lottery_entries.append({
            "LotteryGroupId": group_id,
            "PinEffectId": pid,
            "LotteryRate": rate,
        })

    chemicals = []
    for item_id, group_id in sorted(chemical_group_by_item.items(), key=lambda x: x[1]):
        item = items.get(item_id)
        total = totals[group_id]
        chemical_entries = [x for x in lottery_entries if x["LotteryGroupId"] == group_id]
        chemicals.append({
            "ItemId": item_id,
            "ItemName": item.get("ItemName", "") if item else "",
            "ItemDescription": item.get("ItemDescription1", "") if item else "",
            "ItemRarityCode": item.get("ItemRarityCode") if item else None,
            "LotteryGroupId": group_id,
            "TotalWeight": total,
            "CandidateCount": len(chemical_entries),
            "TierDistribution": [
                {
                    "Tier": tier,
                    "Weight": tier_totals[group_id][tier],
                    "Probability": (tier_totals[group_id][tier] / total) if total else 0,
                }
                for tier in range(1, 6)
                if tier_totals[group_id][tier]
            ],
        })

    # Campaign override table is currently empty. Refuse to silently guess its
    # semantics when the game starts populating it in a later update.
    campaign_rows = tables["mst_campaign_pin_effect_lottery"]
    if campaign_rows:
        issues.append({
            "Type": "campaign_pin_effect_lottery_requires_review",
            "Count": len(campaign_rows),
            "Evidence": "mst_campaign_pin_effect_lottery became non-empty; add an explicit schema before publication",
        })

    materials = []
    for item_id in sorted(referenced_materials):
        item = items.get(item_id)
        if not item:
            issues.append({"Type": "missing_material_item", "ItemId": item_id})
            continue
        materials.append({
            "ItemId": item_id,
            "ItemName": item.get("ItemName", ""),
            "ItemDescription": item.get("ItemDescription1", ""),
            "ItemTypeCode": item.get("ItemTypeCode"),
            "ItemRarityCode": item.get("ItemRarityCode"),
        })

    character_rows = [
        {
            "CharacterId": cid,
            "CharacterNameJpn": row.get("CharacterNameJpn", ""),
            "CharacterNameEng": row.get("CharacterNameEng", ""),
            "CharacterGroupCode": row.get("CharacterGroupCode"),
        }
        for cid, row in sorted(characters.items())
        if cid <= 21
    ]

    source_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    return {
        "Meta": {
            "SchemaVersion": 1,
            "Domain": "pins",
            "GeneratedAt": datetime.now(timezone.utc).isoformat(),
            "SourceFile": input_path.name,
            "SourceSha256": source_sha,
            "TierPolishCosts": [1, 2, 5, 10, 20],
            "Counts": {
                "Effects": len(effects),
                "BaseEffects": len(base_effects),
                "Conditions": len(conditions),
                "Chemicals": len(chemicals),
                "LotteryEntries": len(lottery_entries),
                "Materials": len(materials),
                "Characters": len(character_rows),
            },
        },
        "Characters": character_rows,
        "EffectCategories": [
            {
                "PinEffectCategory": row.get("PinEffectCategory"),
                "CategoryName": row.get("CategoryName", ""),
                "PinEffectTypes": row.get("PinEffectTypes", []),
                "SortOrder": row.get("SortOrder", 0),
            }
            for row in tables["mst_pin_effect_category"]
        ],
        "Conditions": conditions,
        "BaseEffects": base_effects,
        "Effects": sorted(effects, key=lambda x: x["PinEffectId"]),
        "Chemicals": chemicals,
        "LotteryEntries": sorted(lottery_entries, key=lambda x: (x["LotteryGroupId"], x["PinEffectId"])),
        "Materials": materials,
        "Issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="decoded master_data.json")
    parser.add_argument("-o", "--output", type=Path, default=Path("Pins_Optimizer_Source.json"))
    args = parser.parse_args()
    payload = export(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "counts": payload["Meta"]["Counts"], "issues": len(payload["Issues"])}, ensure_ascii=False))
    if payload['Issues']:
        raise SystemExit('Unresolved PINS source issues; candidate rejected')


if __name__ == "__main__":
    main()
