#!/usr/bin/env python3
"""Helpers around Il2CppDumper's script.json for headless Ghidra decompiles.

    index    script.json -> methods.tsv (for DecompileRvas.java) + names.tsv
    find     print RVAs of methods whose name contains a substring
    annotate add method names and string literals to Ghidra C output

Ghidra loads libil2cpp.so at image base 0x100000; RVAs in dump.cs and
script.json are relative to 0. See docs/CARD_PIPELINE.md for the workflow.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GHIDRA_IMAGE_BASE = 0x100000


def build_index(script_json, out_dir):
    data = json.loads(Path(script_json).read_text(encoding="utf-8"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = lambda text: text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    with open(out_dir / "methods.tsv", "w", encoding="utf-8") as methods, \
            open(out_dir / "names.tsv", "w", encoding="utf-8") as names:
        for item in data["ScriptMethod"]:
            methods.write(f"{item['Address']:x}\t{clean(item['Name'])}\n")
            names.write(f"{item['Address']:x}\t{clean(item['Name'])}\n")
        for item in data.get("ScriptString", []):
            names.write(f"{item['Address']:x}\tSTR\"{clean(item['Value'])[:80]}\"\n")
        for item in data.get("ScriptMetadata", []) + data.get("ScriptMetadataMethod", []):
            names.write(f"{item['Address']:x}\t{clean(item['Name'])}\n")


def load_names(path):
    names = {}
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            address, _, name = line.rstrip("\n").partition("\t")
            names.setdefault(int(address, 16), name)
    return names


def annotate(names_tsv, source, target):
    names = load_names(names_tsv)

    def label(hex_address):
        return names.get(int(hex_address, 16) - GHIDRA_IMAGE_BASE)

    text = Path(source).read_text(encoding="utf-8")
    text = re.sub(
        r"\b(?:FUN|DAT|LAB|thunk_FUN)_([0-9a-fA-F]{6,})",
        lambda m: f"{m.group(0)}/*{label(m.group(1))}*/" if label(m.group(1)) else m.group(0),
        text,
    )
    text = re.sub(
        r"/\*->([0-9a-f]+)\*/",
        lambda m: f"/*->{m.group(1)} {label(m.group(1))}*/" if label(m.group(1)) else m.group(0),
        text,
    )
    Path(target).write_text(text, encoding="utf-8")


def find(methods_tsv, needle):
    with open(methods_tsv, encoding="utf-8") as stream:
        for line in stream:
            address, _, name = line.rstrip("\n").partition("\t")
            if needle in name:
                print(f"0x{int(address, 16):X}\t{name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index")
    index.add_argument("script_json")
    index.add_argument("out_dir")
    lookup = commands.add_parser("find")
    lookup.add_argument("methods_tsv")
    lookup.add_argument("needle")
    note = commands.add_parser("annotate")
    note.add_argument("names_tsv")
    note.add_argument("source")
    note.add_argument("target")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.command == "index":
        build_index(args.script_json, args.out_dir)
    elif args.command == "find":
        find(args.methods_tsv, args.needle)
    else:
        annotate(args.names_tsv, args.source, args.target)


if __name__ == "__main__":
    main()
