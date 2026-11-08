#!/usr/bin/env python3
"""Compare masterdata with the client's own schema from an Il2CppDumper dump.cs.

dump.cs declares every masterdata table as ``[MemoryTable("mst_...")]`` with typed
fields, and the code enums (``CardRarityCode``, ``RewardTypeCode`` ...) under
``Coly.S2BShared.Enums``. This script reports:

- fields present in masterdata but unknown to the client, and the reverse;
- values of code-like enum fields (``*Code``/``*Type``/``*Category``) that the
  client enum does not define, i.e. masterdata ahead of the dumped client.
  Empty tables and the unset value 0 are not reported.

Usage:
    python scripts/dump_schema.py DUMP_CS --masterdata master_data.json [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ENUM_RE = re.compile(r"^public enum (\w+) ")
CONST_RE = re.compile(r"^\tpublic const \w+ (\w+) = (-?\d+);")
TABLE_RE = re.compile(r'^\[MemoryTable\("(\w+)"\)\]')
CLASS_RE = re.compile(r"^public (?:sealed )?class (\w+)")
FIELD_RE = re.compile(r"^\tprivate (?:readonly )?([\w<>\[\], .]+?) <(\w+)>k__BackingField;")
CLOSED_ENUM_SUFFIXES = ("Code", "Type", "Category")


def parse_dump(path):
    """Return (enums, tables) from dump.cs: {enum: {member: value}}, {table: {field: type}}."""
    enums, tables = {}, {}
    namespace = ""
    pending_table = None
    current_enum = current_table = None
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            line = line.rstrip("\n")
            if line.startswith("// Namespace: "):
                namespace = line[len("// Namespace: "):]
                continue
            if current_enum is not None:
                if line == "}":
                    current_enum = None
                elif match := CONST_RE.match(line):
                    enums[current_enum][match.group(1)] = int(match.group(2))
                continue
            if current_table is not None:
                if line == "}" or line == "\t// Properties":
                    current_table = None
                elif match := FIELD_RE.match(line):
                    tables[current_table][match.group(2)] = match.group(1)
                continue
            if match := TABLE_RE.match(line):
                pending_table = match.group(1)
            elif match := ENUM_RE.match(line):
                if namespace == "Coly.S2BShared.Enums":
                    current_enum = match.group(1)
                    enums[current_enum] = {}
            elif CLASS_RE.match(line):
                if pending_table:
                    current_table = pending_table
                    tables[current_table] = {}
                pending_table = None
    return enums, tables


def _element_type(type_name):
    match = re.fullmatch(r"(?:List<|IReadOnlyList<)?(\w+)(?:>|\[\])?", type_name)
    return match.group(1) if match else type_name


def _values(value):
    return value if isinstance(value, list) else [value]


def compare(enums, client_tables, masterdata):
    names = list(masterdata[0].keys())
    data_tables = {name: masterdata[index] for index, name in enumerate(names, start=1)}
    report = {"MissingTables": [], "NewTables": [], "Fields": {}, "UnknownEnumValues": {}}
    report["NewTables"] = sorted(set(data_tables) - set(client_tables))
    report["MissingTables"] = sorted(set(client_tables) - set(data_tables))

    for table, rows in data_tables.items():
        client_fields = client_tables.get(table)
        if client_fields is None or not rows:
            continue
        data_fields = set()
        for row in rows:
            if isinstance(row, dict):
                data_fields.update(row)
        only_data = sorted(data_fields - set(client_fields))
        only_client = sorted(set(client_fields) - data_fields)
        if only_data or only_client:
            report["Fields"][table] = {"OnlyInMasterdata": only_data, "OnlyInClient": only_client}

        for field, type_name in client_fields.items():
            enum_name = _element_type(type_name)
            members = enums.get(enum_name)
            if not members or not enum_name.endswith(CLOSED_ENUM_SUFFIXES):
                continue
            known = set(members.values())
            unknown = sorted({
                value for row in rows if isinstance(row, dict) and field in row
                for value in _values(row[field])
                # 0 is the C# default for an unset enum field.
                if isinstance(value, int) and value != 0 and value not in known
            })
            if unknown:
                report["UnknownEnumValues"][f"{table}.{field}"] = {"Enum": enum_name, "Values": unknown}
    return report


def render(report, enum_count, table_count):
    lines = [f"client: {table_count} tables, {enum_count} enums"]
    for key, label in (("NewTables", "tables only in masterdata"), ("MissingTables", "tables only in client")):
        if report[key]:
            lines.append(f"{label} ({len(report[key])}): {', '.join(report[key])}")
    for table, diff in sorted(report["Fields"].items()):
        parts = []
        if diff["OnlyInMasterdata"]:
            parts.append(f"+masterdata {diff['OnlyInMasterdata']}")
        if diff["OnlyInClient"]:
            parts.append(f"+client {diff['OnlyInClient']}")
        lines.append(f"{table}: {'; '.join(parts)}")
    for field, item in sorted(report["UnknownEnumValues"].items()):
        lines.append(f"UNKNOWN {field} ({item['Enum']}): {item['Values']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dump", type=Path)
    parser.add_argument("--masterdata", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="write enums, client tables and the report as JSON")
    args = parser.parse_args(argv)

    enums, client_tables = parse_dump(args.dump)
    masterdata = json.loads(args.masterdata.read_text(encoding="utf-8"))
    report = compare(enums, client_tables, masterdata)
    if args.json:
        args.json.write_text(
            json.dumps({"Enums": enums, "Tables": client_tables, "Report": report},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(render(report, len(enums), len(client_tables)))
    return 1 if report["UnknownEnumValues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
