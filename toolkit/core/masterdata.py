"""Strict master_data.s2b decoding and content-addressed JSON caching."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .s2b_parser import parse_s2b_file
from .tables import TableCatalog


PARSER_VERSION = 1
CACHE_DIRECTORY = ".bmc_toolkit"
CACHE_MANIFEST = "master_data_cache.json"


@dataclass(frozen=True)
class MasterDataResult:
    json_path: str
    manifest_path: str
    source_sha256: str
    reused: bool
    table_count: int


def _tool_version():
    try:
        return version("brmy-masterdata-toolkit")
    except PackageNotFoundError:
        return "development"


def _log(message):
    """Write user-facing status without crashing on legacy Windows code pages."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe_message = message.encode(encoding, errors="replace").decode(encoding)
    print(safe_message)


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_masterdata(data):
    catalog = TableCatalog(data)
    if not catalog.names:
        raise ValueError("masterdata contains no named tables")
    return catalog


def decode_masterdata(s2b_path):
    data = parse_s2b_file(s2b_path, strict_extensions=True)
    validate_masterdata(data)
    return data


def _read_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _atomic_json_dump(value, path, *, indent):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=indent)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def ensure_masterdata_json(s2b_path, out_dir=None):
    """Return a verified JSON cache, rebuilding whenever source or parser changes."""
    source = Path(s2b_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"master_data.s2b not found: {source}")

    output_directory = Path(out_dir).resolve() if out_dir else source.parent
    json_path = output_directory / "master_data.json"
    manifest_path = output_directory / CACHE_DIRECTORY / CACHE_MANIFEST
    source_hash = sha256_file(source)
    manifest = _read_manifest(manifest_path)

    reusable = (
        json_path.is_file()
        and manifest is not None
        and manifest.get("parser_version") == PARSER_VERSION
        and manifest.get("source", {}).get("sha256") == source_hash
        and manifest.get("output", {}).get("sha256") == sha256_file(json_path)
    )
    if reusable:
        table_count = manifest.get("output", {}).get("table_count", 0)
        _log(f"[*] 已验证 master_data.json 缓存（{table_count} 张表）")
        return MasterDataResult(
            str(json_path), str(manifest_path), source_hash, True, table_count
        )

    _log("[*] 正在严格解码 master_data.s2b ...")
    data = decode_masterdata(source)
    catalog = validate_masterdata(data)
    _atomic_json_dump(data, json_path, indent=2)
    output_hash = sha256_file(json_path)
    manifest = {
        "manifest_version": 1,
        "parser_version": PARSER_VERSION,
        "tool_version": _tool_version(),
        "source": {
            "name": source.name,
            "size": source.stat().st_size,
            "sha256": source_hash,
        },
        "output": {
            "name": json_path.name,
            "size": json_path.stat().st_size,
            "sha256": output_hash,
            "table_count": len(catalog.names),
        },
    }
    _atomic_json_dump(manifest, manifest_path, indent=2)
    _log(f"[+] master_data.json 已生成并校验（{len(catalog.names)} 张表）")
    return MasterDataResult(
        str(json_path), str(manifest_path), source_hash, False, len(catalog.names)
    )
