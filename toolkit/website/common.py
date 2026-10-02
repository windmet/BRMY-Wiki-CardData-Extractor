from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


class MasterData:
    """Small standalone reader for BRMY decoded master_data.json.

    The current dump is a list where element 0 is an ordered table-name index and
    each following element is the row array for the corresponding table name.
    The API intentionally resembles the Toolkit TableCatalog subset used by the
    project so these parsers are easy to port upstream later.
    """

    def __init__(self, payload: Any):
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise ValueError("Unexpected masterdata shape: expected [table_index, table_rows...]")
        self._names = list(payload[0].keys())
        if len(payload) - 1 != len(self._names):
            raise ValueError(f"Table count mismatch: index={len(self._names)} arrays={len(payload)-1}")
        self._tables = {name: payload[i + 1] for i, name in enumerate(self._names)}

    @classmethod
    def load(cls, path: str | Path) -> "MasterData":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._names)

    def rows(self, name: str, *, active_only: bool = False) -> list[dict[str, Any]]:
        rows = self._tables.get(name)
        if rows is None:
            raise ValueError(f"Missing required table {name}")
        if not isinstance(rows, list):
            raise ValueError(f"Table {name} is not a row array")
        if not active_only:
            return rows
        return [r for r in rows if not isinstance(r, dict) or r.get("IsActive", True)]

    def by_id(self, name: str, key: str, *, active_only: bool = False) -> dict[Any, dict[str, Any]]:
        result: dict[Any, dict[str, Any]] = {}
        for row in self.rows(name, active_only=active_only):
            value = row.get(key)
            if value is not None:
                if value in result:
                    raise ValueError(f"Duplicate {name}.{key}={value}")
                result[value] = row
        return result

    def group_by(self, name: str, key: str, *, active_only: bool = False) -> dict[Any, list[dict[str, Any]]]:
        result: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows(name, active_only=active_only):
            result[row.get(key)].append(row)
        return dict(result)


def stage_key(row: dict[str, Any]) -> str:
    return f"{row.get('PuzzleMapId')}:{row.get('PuzzleStageNo')}:{row.get('PuzzleType')}"


def window(start: Any, end: Any) -> dict[str, str]:
    return {"StartTime": str(start or ""), "EndTime": str(end or "")}


def write_json(path: str | Path, value: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sorted_unique(values: Iterable[Any]) -> list[Any]:
    return sorted(set(values))


def reward_name_maps(md: MasterData) -> dict[int, dict[int, str]]:
    """Names for only the reward types needed by this parser pack.

    RewardTypeCode=2  -> mst_item
    RewardTypeCode=101 -> mst_event_ingredient
    Unknown types remain unresolved instead of being guessed.
    """
    return {
        2: {r["ItemId"]: r.get("ItemName", "") for r in md.rows("mst_item") if r.get("ItemId") is not None},
        101: {r["IngredientId"]: r.get("IngredientName", "") for r in md.rows("mst_event_ingredient") if r.get("IngredientId") is not None},
    }


def resolve_direct_reward_group(md: MasterData, group_id: int | None) -> list[dict[str, Any]]:
    if not group_id:
        return []
    names = reward_name_maps(md)
    rows = [r for r in md.rows("mst_direct_reward") if r.get("DirectRewardGroupId") == group_id]
    rows.sort(key=lambda r: r.get("DirectRewardSequenceNo", 0))
    out = []
    for r in rows:
        code = int(r.get("RewardTypeCode") or 0)
        target = int(r.get("RewardTargetId") or 0)
        out.append({
            "RewardTypeCode": code,
            "RewardTargetId": target,
            "RewardName": names.get(code, {}).get(target, ""),
            "RewardCount": r.get("RewardCount"),
            "Resolution": "resolved_name" if target in names.get(code, {}) else "raw_only",
        })
    return out
