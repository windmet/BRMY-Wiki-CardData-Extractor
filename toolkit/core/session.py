"""One-load masterdata session with schema drift and run audit support."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import scanner
from .masterdata import (
    CACHE_DIRECTORY,
    CACHE_MANIFEST,
    PARSER_VERSION,
    sha256_file,
    tool_version,
)
from .tables import TableCatalog


SCHEMA_BASELINE = "masterdata_schema.json"
AUDIT_DIRECTORY = "audit_output"

REQUIRED_SCHEMA = {
    "mst_character": {
        "CharacterId", "CharacterNameJpn", "CharacterNameEng", "IsActive"
    },
    "mst_character_card": {
        "CharacterCardId", "CharacterId", "CharacterCardName",
        "CardRarityCode", "CardAttributeCode", "CardRouteCode", "IsActive",
    },
    "mst_item": {
        "ItemId", "ItemName", "ItemTypeCode", "ItemFileName",
        "ItemDescription1", "IsActive",
    },
    "mst_music": {"MusicId", "DisplayName", "ArtistName", "IsActive"},
    "mst_event": {"EventId", "EventTitle", "EventFormat", "IsActive"},
    "mst_home_voice": {
        "HomeVoiceTargetId", "HomeVoiceNo", "VoiceCueName", "IsActive"
    },
    "mst_mission": {"MissionId", "Description", "MissionType", "IsActive"},
    "mst_mission_sequence": {
        "MissionId", "MissionSequenceNo", "Border", "IsHidden", "IsActive"
    },
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _value_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def build_schema_snapshot(tables):
    result = {"tables": {}}
    for name in tables.names:
        rows = tables.rows(name)
        fields = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                fields.setdefault(str(key), set()).add(_value_type(value))
        result["tables"][name] = {
            "row_count": len(rows),
            "fields": {key: sorted(values) for key, values in sorted(fields.items())},
        }
    fingerprint_source = {
        name: table["fields"] for name, table in sorted(result["tables"].items())
    }
    encoded = json.dumps(
        fingerprint_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    result["schema_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    result["table_count"] = len(result["tables"])
    return result


def compare_schema(previous, current):
    if not previous:
        return [{"kind": "baseline_initialized"}]
    changes = []
    old_tables = previous.get("tables", {})
    new_tables = current.get("tables", {})
    for name in sorted(new_tables.keys() - old_tables.keys()):
        changes.append({"kind": "table_added", "table": name})
    for name in sorted(old_tables.keys() - new_tables.keys()):
        changes.append({"kind": "table_removed", "table": name})
    for name in sorted(old_tables.keys() & new_tables.keys()):
        old_fields = old_tables[name].get("fields", {})
        new_fields = new_tables[name].get("fields", {})
        for field in sorted(new_fields.keys() - old_fields.keys()):
            changes.append({"kind": "field_added", "table": name, "field": field})
        for field in sorted(old_fields.keys() - new_fields.keys()):
            changes.append({"kind": "field_removed", "table": name, "field": field})
        for field in sorted(old_fields.keys() & new_fields.keys()):
            if old_fields[field] != new_fields[field]:
                changes.append({
                    "kind": "type_changed",
                    "table": name,
                    "field": field,
                    "before": old_fields[field],
                    "after": new_fields[field],
                })
        old_count = old_tables[name].get("row_count")
        new_count = new_tables[name].get("row_count")
        if old_count != new_count:
            changes.append({
                "kind": "row_count_changed", "table": name,
                "before": old_count, "after": new_count,
            })
    return changes


def validate_required_schema(snapshot, required_schema=None):
    required_schema = REQUIRED_SCHEMA if required_schema is None else required_schema
    errors = []
    tables = snapshot.get("tables", {})
    for name, required_fields in required_schema.items():
        if name not in tables:
            errors.append(f"required table is missing: {name}")
            continue
        fields = tables[name].get("fields", {})
        for field in sorted(required_fields - fields.keys()):
            errors.append(f"required field is missing: {name}.{field}")
    return errors


def _atomic_json(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@dataclass
class SchemaAssessment:
    errors: list[str]
    changes: list[dict]

    @property
    def warnings(self):
        return list(self.changes)

    @property
    def status(self):
        if self.errors:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"


class MasterDataSession:
    def __init__(self, json_path, data, required_schema=None):
        self.json_path = str(Path(json_path).resolve())
        self.root = Path(self.json_path).parent
        self.data = data
        self.tables = TableCatalog(data)
        self.json_sha256 = sha256_file(self.json_path)
        self.schema = build_schema_snapshot(self.tables)
        self.required_schema = REQUIRED_SCHEMA if required_schema is None else required_schema
        self.schema_baseline_path = self.root / CACHE_DIRECTORY / SCHEMA_BASELINE
        self.previous_schema = self._read_previous_schema()
        self.assessment = SchemaAssessment(
            validate_required_schema(self.schema, self.required_schema),
            compare_schema(self.previous_schema, self.schema),
        )
        self.source = self._source_provenance()

    @classmethod
    def open(cls, json_path, required_schema=None):
        return cls(json_path, scanner.load_json(json_path), required_schema)

    def _read_previous_schema(self):
        try:
            return json.loads(self.schema_baseline_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _source_provenance(self):
        manifest_path = self.root / CACHE_DIRECTORY / CACHE_MANIFEST
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = None
        if manifest and manifest.get("output", {}).get("sha256") == self.json_sha256:
            return dict(manifest.get("source", {}))
        return {
            "name": Path(self.json_path).name,
            "size": Path(self.json_path).stat().st_size,
            "sha256": self.json_sha256,
        }

    def write_audit(self, domain_results, *, started_at, success):
        audit_dir = self.root / AUDIT_DIRECTORY
        audit_dir.mkdir(parents=True, exist_ok=True)
        status = "FAIL" if not success or self.assessment.errors else (
            "PASS_WITH_WARNINGS" if self.assessment.warnings else "PASS"
        )
        manifest = {
            "started_at": started_at,
            "completed_at": _utc_now(),
            "status": status,
            "tool": {
                "version": tool_version(),
                "parser_version": PARSER_VERSION,
            },
            "input": {
                "json_name": Path(self.json_path).name,
                "json_sha256": self.json_sha256,
                "source": self.source,
                "table_count": self.schema["table_count"],
                "schema_fingerprint": self.schema["schema_fingerprint"],
            },
            "schema": {
                "status": self.assessment.status,
                "errors": self.assessment.errors,
                "changes": self.assessment.changes,
            },
            "domains": domain_results,
        }
        _atomic_json(manifest, audit_dir / "run_manifest.json")
        (audit_dir / "schema_report.md").write_text(
            self.render_schema_report(), encoding="utf-8", newline="\n"
        )
        if success and not self.assessment.errors:
            _atomic_json(self.schema, self.schema_baseline_path)
        return manifest

    def render_schema_report(self):
        lines = [
            "# Masterdata Schema Report",
            "",
            f"- Status: **{self.assessment.status}**",
            f"- Tables: {self.schema['table_count']}",
            f"- Fingerprint: `{self.schema['schema_fingerprint']}`",
            "",
        ]
        if self.assessment.errors:
            lines.extend(["## Blocking Errors", ""])
            lines.extend(f"- {error}" for error in self.assessment.errors)
            lines.append("")
        lines.extend(["## Changes", ""])
        if not self.assessment.changes:
            lines.append("- No schema or row-count changes detected.")
        for change in self.assessment.changes:
            kind = change["kind"]
            if kind == "baseline_initialized":
                lines.append("- No previous local baseline; current schema initialized after success.")
            elif kind in {"table_added", "table_removed"}:
                lines.append(f"- {kind}: `{change['table']}`")
            elif kind in {"field_added", "field_removed"}:
                lines.append(f"- {kind}: `{change['table']}.{change['field']}`")
            elif kind == "type_changed":
                lines.append(
                    f"- type_changed: `{change['table']}.{change['field']}` "
                    f"{change['before']} -> {change['after']}"
                )
            elif kind == "row_count_changed":
                lines.append(
                    f"- row_count_changed: `{change['table']}` "
                    f"{change['before']} -> {change['after']}"
                )
        lines.append("")
        return "\n".join(lines)


def utc_now():
    return _utc_now()
