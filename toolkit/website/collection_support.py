"""Strict local masterdata reader. No network, credentials, or Library mutation."""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

class MasterData:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise ValueError('Expected [ordered table index, table arrays ...]')
        names = list(payload[0])
        if len(names) != len(payload) - 1:
            raise ValueError('Index/table count mismatch')
        self.tables = dict(zip(names, payload[1:]))
        if any(not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) for rows in self.tables.values()):
            raise ValueError('Expected arrays of objects for all tables')
    def rows(self, table: str, active_only: bool = False, required: bool = True):
        if table not in self.tables:
            if required:
                raise ValueError(f'Missing table: {table}')
            return []
        rows = self.tables[table]
        return [r for r in rows if r.get('IsActive', True)] if active_only else rows
    def by_id(self, table: str, field: str):
        out = {}
        for r in self.rows(table):
            key = r[field]
            if key in out:
                raise ValueError(f'Duplicate {table}.{field}={key}')
            out[key] = r
        return out
    def group(self, table: str, field: str, active_only: bool = True):
        out = defaultdict(list)
        for r in self.rows(table, active_only):
            out[r[field]].append(r)
        return dict(out)

def stage_key(row):
    return ':'.join(str(row[k]) for k in ('PuzzleMapId','PuzzleStageNo','PuzzleType'))

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def verify_bundle(path: str | None, expected: str):
    if not path:
        return {'status': 'not_supplied'}
    p = Path(path); data = json.loads(p.read_text(encoding='utf-8'))
    candidates = [data.get('manifest',{}).get('masterdataSha256'),
                  data.get('Meta',{}).get('MasterdataSha256'),
                  data.get('data',{}).get('Meta',{}).get('MasterdataSha256')]
    hashes = {v for v in candidates if v}
    if hashes != {expected}:
        raise ValueError(f'Canonical bundle masterdata hash mismatch: {p.name}')
    return {'status': 'matched', 'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
