from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from .common import MasterData, window, write_json

RANKS = ("SS", "S", "A", "B", "C", "D", "E")


def extract(md: MasterData) -> dict[str, Any]:
    items = md.by_id("mst_item", "ItemId")
    direct_by_group = md.group_by("mst_direct_reward", "DirectRewardGroupId")
    events = md.by_id("mst_event", "EventId")
    exchange_by_id = md.by_id("mst_exchange", "ExchangeId")
    mission_by_id = md.by_id("mst_mission", "MissionId")

    def item_reward_rows(group_id: int | None) -> list[dict[str, Any]]:
        if not group_id:
            return []
        return [r for r in direct_by_group.get(group_id, []) if r.get("RewardTypeCode") == 2 and r.get("RewardTargetId") in items]

    # ---- Explicit acquisition/use sources ---------------------------------
    acquisitions: dict[int, list[dict[str, Any]]] = defaultdict(list)
    uses: dict[int, list[dict[str, Any]]] = defaultdict(list)

    # Exchange products: reward side is acquisition; exchange cost side is use.
    for p in md.rows("mst_exchange_product"):
        ex = exchange_by_id.get(p.get("ExchangeId"), {})
        avail = window(p.get("StartTime") or ex.get("StartTime"), p.get("EndTime") or ex.get("EndTime"))
        slot = p.get('CostItemIdNumber') or 1
        if slot not in (1,2): raise ValueError('Unknown exchange cost slot')
        cost_id = ex.get(f'CostItemId{slot}')
        for r in item_reward_rows(p.get("DirectRewardGroupId")):
            acquisitions[r["RewardTargetId"]].append({
                "Kind": "exchange_reward",
                "SourceKey": f"exchange:{p.get('ExchangeId')}:{p.get('ExchangeProductNo')}",
                "ExchangeId": p.get("ExchangeId"),
                "ExchangeName": ex.get("ExchangeName", ""),
                "RewardCount": r.get("RewardCount"),
                "CostItemId": cost_id,
                "CostItemIdNumber": slot,
                "CostItemCount": p.get("CostItemCount"),
                "Availability": avail,
                "Evidence": "mst_exchange_product.DirectRewardGroupId -> mst_direct_reward",
            })
        for field in (f"CostItemId{slot}",):
            item_id = ex.get(field)
            if item_id in items:
                uses[item_id].append({
                    "Kind": "exchange_currency",
                    "SourceKey": f"exchange:{p.get('ExchangeId')}:{p.get('ExchangeProductNo')}",
                    "ExchangeId": p.get("ExchangeId"),
                    "ExchangeName": ex.get("ExchangeName", ""),
                    "CostItemCount": p.get("CostItemCount"),
                "CostItemIdNumber": slot,
                    "ProductRewardGroupId": p.get("DirectRewardGroupId"),
                    "Availability": avail,
                    "Evidence": f"mst_exchange.{field}",
                })

    # Mission sequence rewards, normalized rather than embedded in item records.
    for seq in md.rows("mst_mission_sequence"):
        mission = mission_by_id.get(seq.get("MissionId"), {})
        for r in item_reward_rows(seq.get("DirectRewardGroupId")):
            acquisitions[r["RewardTargetId"]].append({
                "Kind": "mission_reward",
                "SourceKey": f"mission:{seq.get('MissionId')}:{seq.get('MissionSequenceNo')}",
                "MissionId": seq.get("MissionId"),
                "Description": mission.get("Description", ""),
                "Border": seq.get("Border"),
                "RewardCount": r.get("RewardCount"),
                "Availability": window(mission.get("StartTime"), mission.get("EndTime")),
                "Evidence": "mst_mission_sequence.DirectRewardGroupId -> mst_direct_reward",
            })

    # Bind event-specific currencies/items to their event without pretending that
    # this binding is itself an acquisition route.
    event_item_bindings: dict[int, list[dict[str, Any]]] = defaultdict(list)
    event_field_specs = {
        "mst_event_a": ("EventItemId", "TravelCoinItemId", "EventStaminaItemId"),
        "mst_event_accumulate_item": ("EventItemId",),
        "mst_event_c": ("PrizeMedalItemId", "ChartStampItemId"),
    }
    for table, fields in event_field_specs.items():
        for row in md.rows(table):
            eid = row.get("EventId")
            ev = events.get(eid, {})
            for field in fields:
                iid = row.get(field)
                if iid in items:
                    event_item_bindings[iid].append({
                        "EventId": eid,
                        "EventTitle": ev.get("EventTitle", ""),
                        "Field": field,
                        "Table": table,
                    })

    item_rows = []
    for iid, row in sorted(items.items()):
        item_rows.append({
            "ItemId": iid,
            "ItemName": row.get("ItemName", ""),
            "ItemNameMultiLine": row.get("ItemNameMultiLine", ""),
            "ItemTypeCode": row.get("ItemTypeCode"),
            "ItemRarityCode": row.get("ItemRarityCode"),
            "ItemAttributeCode": row.get("ItemAttributeCode"),
            "ItemGroupCode": row.get("ItemGroupCode"),
            "ItemRouteCode": row.get("ItemRouteCode"),
            "ItemDescription1": row.get("ItemDescription1", ""),
            "ItemDescription2": row.get("ItemDescription2", ""),
            "ItemDescription3": row.get("ItemDescription3", ""),
            "ItemFileName": row.get("ItemFileName", ""),
            "ItemDisplayTab": row.get("ItemDisplayTab"),
            "SortOrder": row.get("SortOrder"),
            "AcquisitionSourceCount": len(acquisitions.get(iid, [])),
            "UseSourceCount": len(uses.get(iid, [])),
            "EventBindings": event_item_bindings.get(iid, []),
        })

    return {
        "Meta": {
            "Domain": "items_catalog",
            "Notes": [
                "Items are identity/description records; acquisition/use relations live in separate arrays.",
                "Puzzle pool usage count is descriptive and intended for common-pool UI grouping.",
                "LotteryRateRaw is kept raw and is not converted to probability.",
            ],
        },
        "Items": item_rows,
        "Acquisitions": {str(k): v for k, v in sorted(acquisitions.items())},
        "Uses": {str(k): v for k, v in sorted(uses.items())},
        "Audit": {
            "ItemCount": len(item_rows),
            "ItemsWithAcquisitionSources": len(acquisitions),
            "ItemsWithUseSources": len(uses),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("masterdata")
    ap.add_argument("--output", default="Items_Catalog_Source.json")
    args = ap.parse_args()
    result = extract(MasterData.load(args.masterdata))
    write_json(args.output, result)
    print(f"wrote {args.output}: {result['Audit']['ItemCount']} items")


if __name__ == "__main__":
    main()
