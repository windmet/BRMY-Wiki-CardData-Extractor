"""Minimal reader for CRI @UTF tables used by ACB cue metadata."""
from __future__ import annotations

import struct


_TYPE_FORMATS = {
    0: ">B",
    1: ">b",
    2: ">H",
    3: ">h",
    4: ">I",
    5: ">i",
    6: ">Q",
    7: ">q",
    8: ">f",
    9: ">d",
}
_TYPE_SIZES = {key: struct.calcsize(value) for key, value in _TYPE_FORMATS.items()}
_TYPE_SIZES.update({10: 4, 11: 8})


class CriUtfError(ValueError):
    pass


def _unpack(fmt, data, offset):
    try:
        return struct.unpack_from(fmt, data, offset)[0]
    except struct.error as exc:
        raise CriUtfError(f"truncated @UTF value at offset {offset}") from exc


def parse_utf(data):
    """Return ``(table_name, rows)`` for one unencrypted CRI @UTF table."""
    if not isinstance(data, (bytes, bytearray, memoryview)) or bytes(data[:4]) != b"@UTF":
        raise CriUtfError("missing @UTF signature")
    data = bytes(data)

    u16 = lambda offset: _unpack(">H", data, offset)
    u32 = lambda offset: _unpack(">I", data, offset)
    base = 8
    rows_offset = base + u16(10)
    strings_offset = base + u32(12)
    data_offset = base + u32(16)
    table_name_offset = u32(20)
    column_count = u16(24)
    row_width = u16(26)
    row_count = u32(28)

    def read_string(relative_offset):
        start = strings_offset + relative_offset
        end = data.find(b"\x00", start)
        if start < 0 or start >= len(data) or end < 0:
            raise CriUtfError(f"invalid @UTF string offset {relative_offset}")
        return data[start:end].decode("utf-8", errors="replace")

    def read_value(value_type, offset):
        if value_type in _TYPE_FORMATS:
            return _unpack(_TYPE_FORMATS[value_type], data, offset)
        if value_type == 10:
            return read_string(u32(offset))
        if value_type == 11:
            relative_offset = u32(offset)
            size = u32(offset + 4)
            start = data_offset + relative_offset
            end = start + size
            if start < 0 or end > len(data):
                raise CriUtfError(f"invalid @UTF data range {start}:{end}")
            return data[start:end]
        raise CriUtfError(f"unsupported @UTF value type {value_type}")

    columns = []
    offset = 32
    for _ in range(column_count):
        if offset + 5 > len(data):
            raise CriUtfError("truncated @UTF column definition")
        flags = data[offset]
        name = read_string(u32(offset + 1))
        offset += 5
        storage = flags & 0xF0
        value_type = flags & 0x0F
        if value_type not in _TYPE_SIZES:
            raise CriUtfError(f"unsupported @UTF column type {value_type} for {name}")
        constant = None
        if storage == 0x30:
            constant = read_value(value_type, offset)
            offset += _TYPE_SIZES[value_type]
        elif storage not in (0x10, 0x50):
            raise CriUtfError(f"unsupported @UTF storage 0x{storage:02x} for {name}")
        columns.append((name, storage, value_type, constant))

    rows = []
    for row_index in range(row_count):
        offset = rows_offset + row_index * row_width
        row = {}
        for name, storage, value_type, constant in columns:
            if storage == 0x50:
                row[name] = read_value(value_type, offset)
                offset += _TYPE_SIZES[value_type]
            elif storage == 0x30:
                row[name] = constant
            else:
                row[name] = 0
        rows.append(row)

    return read_string(table_name_offset), rows


def extract_acb_cue_rows(data):
    """Join ACB CueNameTable rows to CueTable.UserData by CueIndex."""
    _, header_rows = parse_utf(data)
    if not header_rows:
        return []
    header = header_rows[0]
    cue_blob = header.get("CueTable")
    name_blob = header.get("CueNameTable")
    if not isinstance(cue_blob, bytes) or not isinstance(name_blob, bytes):
        raise CriUtfError("ACB header has no CueTable/CueNameTable")

    _, cue_rows = parse_utf(cue_blob)
    _, name_rows = parse_utf(name_blob)
    joined = []
    for name_row in name_rows:
        cue_index = name_row.get("CueIndex")
        if not isinstance(cue_index, int) or cue_index < 0 or cue_index >= len(cue_rows):
            continue
        cue = cue_rows[cue_index]
        joined.append({
            "CueName": name_row.get("CueName", ""),
            "CueIndex": cue_index,
            "CueId": cue.get("CueId"),
            "UserData": cue.get("UserData", ""),
        })
    return joined
