"""Named-table access for decoded master_data.json payloads."""
from __future__ import annotations

from collections import defaultdict


class TableCatalog:
    """Expose masterdata tables by name and keep schema failures explicit."""

    def __init__(self, data):
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise ValueError("masterdata root must be a list whose first item is the table directory")

        names = list(data[0].keys())
        if len(data) - 1 < len(names):
            raise ValueError(
                f"masterdata declares {len(names)} tables but only contains {len(data) - 1} payloads"
            )

        self._tables = {}
        for index, name in enumerate(names, start=1):
            rows = data[index]
            if not isinstance(rows, list):
                raise ValueError(f"masterdata table {name!r} is not a list")
            self._tables[name] = rows

    @property
    def names(self):
        return tuple(self._tables)

    def rows(self, name, *, active_only=False):
        rows = self._tables.get(name, [])
        if not active_only:
            return rows
        return [row for row in rows if isinstance(row, dict) and row.get("IsActive", True)]

    def require(self, name, *, active_only=False):
        if name not in self._tables:
            raise KeyError(f"required masterdata table is missing: {name}")
        return self.rows(name, active_only=active_only)

    def by_id(self, name, key, *, active_only=True, required=True):
        rows = (
            self.require(name, active_only=active_only)
            if required else self.rows(name, active_only=active_only)
        )
        return {
            row[key]: row
            for row in rows
            if isinstance(row, dict) and key in row
        }

    def group_by(self, name, key, *, active_only=True, required=True):
        grouped = defaultdict(list)
        rows = (
            self.require(name, active_only=active_only)
            if required else self.rows(name, active_only=active_only)
        )
        for row in rows:
            if isinstance(row, dict) and key in row:
                grouped[row[key]].append(row)
        return dict(grouped)
