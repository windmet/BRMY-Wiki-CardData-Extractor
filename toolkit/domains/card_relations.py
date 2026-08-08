"""Relationship and acquisition evidence for character cards."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime


CARD_ROUTE_MAP = {1: "Gacha", 2: "EventReward"}
EVENT_EXTENSION_TABLES = (
    "mst_event_a",
    "mst_event_b",
    "mst_event_c",
    "mst_event_accumulate_item",
)


def _active(rows):
    return [row for row in rows if isinstance(row, dict) and row.get("IsActive", True)]


def _as_ids(value):
    if isinstance(value, list):
        return [item for item in value if item]
    return [value] if value else []


def _timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _event_matches_release(event, release):
    released = _timestamp(release)
    start = _timestamp(event.get("StartTime"))
    end = _timestamp(event.get("EndTime"))
    return bool(released and start and end and start <= released <= end)


def _clean_exchange_name(name):
    match = re.search(r"\[(.*?)\]", name or "")
    return match.group(1).strip() if match else (name or "").strip()


def _representative_gacha_name(names):
    unique = list(dict.fromkeys(name for name in names if name))
    birthday = [name for name in unique if "バースデー" in name]
    if birthday:
        return birthday[0]

    for name in unique:
        match = re.search(r"\[(.*?)\]", name)
        if match:
            return match.group(1).strip()

    candidates = [
        name for name in unique
        if "Spotlights" not in name and "PU" not in name and "確定" not in name and "有償" not in name
    ]
    chosen = min(candidates or unique, key=len, default="")
    chosen = re.sub(r"\s*Spotlights.*", "", chosen).strip()
    return re.sub(r"\s*PU.*", "", chosen).strip()


def _event_relations(tables):
    events = {
        row["EventId"]: row
        for row in _active(tables.require("mst_event"))
        if "EventId" in row
    }
    by_card = defaultdict(list)

    for table_name in EVENT_EXTENSION_TABLES:
        for row in _active(tables.rows(table_name)):
            event_id = row.get("EventId")
            event = events.get(event_id, {})
            common = {
                "EventId": event_id,
                "EventTitle": event.get("EventTitle", ""),
                "EventFormat": event.get("EventFormat"),
                "StartTime": event.get("StartTime", ""),
                "OpenStartTime": event.get("OpenStartTime", ""),
                "EndTime": event.get("EndTime", ""),
                "SourceTable": table_name,
            }
            pickup_ids = set(_as_ids(row.get("PickUpCharacterCardId")))
            pickup_ids.update(_as_ids(row.get("PickUpCharacterCardIds")))
            featured_ids = set(_as_ids(row.get("CharacterCardIds")))
            for card_id in sorted(pickup_ids | featured_ids):
                relation = dict(common)
                roles = []
                if card_id in pickup_ids:
                    roles.append("pickup_reward")
                if card_id in featured_ids:
                    roles.append("event_featured")
                relation["Roles"] = roles
                by_card[card_id].append(relation)
    return by_card


def _gacha_relations(tables):
    names_by_group = defaultdict(list)
    for row in _active(tables.require("mst_gacha")):
        names_by_group[row.get("GachaGroupId")].append(row.get("GachaName", ""))

    by_card = defaultdict(list)
    for row in _active(tables.rows("mst_gacha_arrival")):
        group_id = row.get("GachaGroupId")
        names = list(dict.fromkeys(name for name in names_by_group.get(group_id, []) if name))
        relation = {
            "GachaGroupId": group_id,
            "GachaNames": names,
            "GachaArrivalType": row.get("GachaArrivalType"),
            "IsNew": row.get("IsNew"),
            "SourceTable": "mst_gacha_arrival",
        }
        for card_id in _as_ids(row.get("CharacterCardIds")):
            by_card[card_id].append(dict(relation))

    # Older data sometimes has no arrival row but still lists the card on a gacha.
    for row in _active(tables.require("mst_gacha")):
        for card_id in _as_ids(row.get("CostumeIntroductionCharacterCardIds")):
            existing_names = {
                name
                for relation in by_card[card_id]
                for name in relation.get("GachaNames", [])
            }
            name = row.get("GachaName", "")
            if name and name not in existing_names:
                by_card[card_id].append({
                    "GachaGroupId": row.get("GachaGroupId"),
                    "GachaNames": [name],
                    "GachaArrivalType": None,
                    "IsNew": None,
                    "SourceTable": "mst_gacha.CostumeIntroductionCharacterCardIds",
                })
    return by_card


def _reward_and_exchange_relations(tables):
    reward_groups = defaultdict(list)
    card_groups = defaultdict(list)
    for row in _active(tables.require("mst_direct_reward")):
        group_id = row.get("DirectRewardGroupId")
        reward_groups[group_id].append(dict(row))
        if row.get("RewardTypeCode") == 1 and row.get("RewardTargetId"):
            card_groups[row["RewardTargetId"]].append(group_id)

    exchanges = {
        row.get("ExchangeId"): row
        for row in _active(tables.rows("mst_exchange"))
        if row.get("ExchangeId")
    }
    products_by_group = defaultdict(list)
    for row in _active(tables.rows("mst_exchange_product")):
        products_by_group[row.get("DirectRewardGroupId")].append(row)

    exchange_by_card = defaultdict(list)
    for card_id, group_ids in card_groups.items():
        for group_id in group_ids:
            for product in products_by_group.get(group_id, []):
                exchange = exchanges.get(product.get("ExchangeId"), {})
                exchange_by_card[card_id].append({
                    "ExchangeId": product.get("ExchangeId"),
                    "ExchangeName": exchange.get("ExchangeName", ""),
                    "StartTime": exchange.get("StartTime", product.get("StartTime", "")),
                    "EndTime": exchange.get("EndTime", product.get("EndTime", "")),
                    "DirectRewardGroupId": group_id,
                    "ExchangeProductNo": product.get("ExchangeProductNo"),
                    "SourceTable": "mst_exchange_product",
                })
    return card_groups, reward_groups, exchange_by_card


def _select_event(relations, release, *, reward_only=False):
    candidates = relations
    if reward_only:
        pickup = [item for item in candidates if "pickup_reward" in item.get("Roles", [])]
        if pickup:
            candidates = pickup
    in_period = [item for item in candidates if _event_matches_release(item, release)]
    candidates = in_period or candidates
    return max(candidates, key=lambda item: item.get("EventId") or 0, default=None)


def _select_exchange(relations, release):
    released = _timestamp(release)
    in_period = []
    for item in relations:
        start = _timestamp(item.get("StartTime"))
        end = _timestamp(item.get("EndTime"))
        if released and start and end and start <= released <= end:
            in_period.append(item)
    return (in_period or relations)[-1] if relations else None


def _derive_acquisition(card_id, raw, events, gachas, exchanges, reward_groups):
    route_code = raw.get("CardRouteCode")
    release = raw.get("ReleaseDateTime", "")
    route = CARD_ROUTE_MAP.get(route_code, f"Unknown({route_code})")
    evidence = [{"Kind": "card_route", "Code": route_code, "Value": route}]
    method = ""
    source_name = ""
    confidence = "low"

    event = _select_event(events, release, reward_only=route_code == 2)
    exchange = _select_exchange(exchanges, release)
    gacha_names = [name for item in gachas for name in item.get("GachaNames", []) if name]
    gacha_name = _representative_gacha_name(gacha_names)

    if events:
        evidence.extend({"Kind": "event", **item} for item in events)
    if gachas:
        evidence.extend({"Kind": "gacha", **item} for item in gachas)
    if exchanges:
        evidence.extend({"Kind": "exchange", **item} for item in exchanges)
    if reward_groups:
        evidence.extend(
            {"Kind": "direct_reward", "DirectRewardGroupId": group_id, "RewardTypeCode": 1}
            for group_id in reward_groups
        )

    if route_code == 2:
        method = "活动报酬"
        if event:
            source_name = event.get("EventTitle", "")
            confidence = "high" if "pickup_reward" in event.get("Roles", []) else "medium"
        elif exchange:
            source_name = _clean_exchange_name(exchange.get("ExchangeName"))
            confidence = "high"
    elif route_code == 1:
        # Cards 1-63 are the initial permanent roster. Later Megamix/reissue
        # gachas reference some of them, but that is availability rather than
        # their original acquisition source.
        if card_id <= 63:
            method = "常驻"
            confidence = "high"
        elif "バースデー" in gacha_name:
            method = "生日限定"
            source_name = gacha_name
            confidence = "high"
        elif event and _event_matches_release(event, release):
            source_name = event.get("EventTitle", "")
            method = "周年卡池" if "Anniversary" in source_name else "活动卡池"
            confidence = "high" if gachas else "medium"
        elif gacha_name:
            source_name = gacha_name
            method = "周年卡池" if "Anniversary" in source_name else "活动卡池"
            confidence = "high"

    warnings = []
    if not method:
        warnings.append(f"unresolved acquisition route for card {card_id}")
    if method != "常驻" and not source_name:
        warnings.append(f"unresolved acquisition source for card {card_id}")

    return {
        "RouteCode": route_code,
        "Route": route,
        "Method": method,
        "SourceName": source_name,
        "Confidence": confidence,
        "Evidence": evidence,
        "Warnings": warnings,
    }


def enrich_card_relations(cards, tables, character_names):
    """Attach relationship evidence and derived acquisition to every card."""
    events_by_card = _event_relations(tables)
    gachas_by_card = _gacha_relations(tables)
    card_groups, reward_rows, exchanges_by_card = _reward_and_exchange_relations(tables)
    multi_by_card = defaultdict(list)
    for row in _active(tables.rows("mst_character_card_multi_character")):
        character_id = row.get("CharacterId")
        multi_by_card[row.get("CharacterCardId")].append({
            "CharacterId": character_id,
            "CharacterName": character_names.get(character_id, f"Char_{character_id}"),
        })

    duo_by_card = defaultdict(list)
    for row in _active(tables.rows("mst_home_voice_character_card_duo")):
        duo_by_card[row.get("CharacterCardId")].append(dict(row))

    unresolved = []
    for card_id, card in cards.items():
        raw = card.get("Raw", {})
        group_ids = list(dict.fromkeys(card_groups.get(card_id, [])))
        card["Relations"] = {
            "AdditionalCharacters": multi_by_card.get(card_id, []),
            "EventAssociations": events_by_card.get(card_id, []),
            "GachaAssociations": gachas_by_card.get(card_id, []),
            "DirectRewardGroupIds": group_ids,
            "DirectRewards": [row for group_id in group_ids for row in reward_rows.get(group_id, [])],
            "ExchangeAssociations": exchanges_by_card.get(card_id, []),
            "HomeVoiceDuo": duo_by_card.get(card_id, []),
        }
        card["Acquisition"] = _derive_acquisition(
            card_id,
            raw,
            card["Relations"]["EventAssociations"],
            card["Relations"]["GachaAssociations"],
            card["Relations"]["ExchangeAssociations"],
            group_ids,
        )
        unresolved.extend(card["Acquisition"]["Warnings"])
    return unresolved
