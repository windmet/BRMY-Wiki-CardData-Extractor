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


_NOTE_ON = 0x07D0
_DELAY = 0x07D1
_REFERENCE_SEQUENCE = 3
_REFERENCE_SYNTH = 2
_REFERENCE_WAVEFORM = 1


def _commands(blob):
    """Split a TrackEvent command stream into ``(code, payload)`` pairs."""
    offset, commands = 0, []
    while offset + 3 <= len(blob):
        code, size = struct.unpack(">HB", blob[offset:offset + 3])
        payload = blob[offset + 3:offset + 3 + size]
        if len(payload) != size:
            raise CriUtfError("truncated ACB track command")
        commands.append((code, payload))
        offset += 3 + size
    return commands


def _subtable(header, name):
    blob = header.get(name)
    if not isinstance(blob, bytes) or blob[:4] != b"@UTF":
        return []
    return parse_utf(blob)[1]


def extract_acb_cue_clips(data):
    """Return each named cue with the waveforms its sequence actually plays.

    Most card cues play one waveform. Some cues chain several note-on events
    separated by delays, so one cue name can hold several spoken clips.
    Unsupported reference shapes raise instead of silently dropping clips.
    """
    _, header_rows = parse_utf(data)
    if not header_rows:
        return []
    header = header_rows[0]
    cues = _subtable(header, "CueTable")
    names = _subtable(header, "CueNameTable")
    sequences = _subtable(header, "SequenceTable")
    tracks = _subtable(header, "TrackTable")
    events = _subtable(header, "TrackEventTable")
    synths = _subtable(header, "SynthTable")
    waveforms = _subtable(header, "WaveformTable")

    def waveform_for_synth(index):
        items = synths[index].get("ReferenceItems") or b""
        refs = [struct.unpack(">HH", items[i:i + 4]) for i in range(0, len(items), 4)]
        if len(refs) != 1 or refs[0][0] != _REFERENCE_WAVEFORM:
            raise CriUtfError(f"unsupported synth reference {refs} at synth {index}")
        return refs[0][1]

    result = []
    for name_row in names:
        cue_index = name_row.get("CueIndex")
        cue = cues[cue_index]
        if cue.get("ReferenceType") != _REFERENCE_SEQUENCE:
            raise CriUtfError(f"unsupported cue reference type {cue.get('ReferenceType')}")
        track_blob = sequences[cue["ReferenceIndex"]].get("TrackIndex") or b""
        clips, unknown = [], []
        for offset in range(0, len(track_blob), 2):
            track = tracks[struct.unpack(">H", track_blob[offset:offset + 2])[0]]
            position_ms = 0
            for code, payload in _commands(events[track["EventIndex"]]["Command"]):
                if code == _NOTE_ON:
                    kind, index = struct.unpack(">HH", payload[:4])
                    if kind != _REFERENCE_SYNTH:
                        raise CriUtfError(f"unsupported note-on reference type {kind}")
                    waveform_index = waveform_for_synth(index)
                    waveform = waveforms[waveform_index]
                    rate = waveform.get("SamplingRate") or 0
                    clips.append({
                        "SynthIndex": index,
                        "WaveformIndex": waveform_index,
                        "MemoryAwbId": waveform.get("MemoryAwbId"),
                        "StreamAwbId": waveform.get("StreamAwbId"),
                        "Streaming": waveform.get("Streaming"),
                        "StartSeconds": position_ms / 1000,
                        "DurationSeconds": round(waveform.get("NumSamples", 0) / rate, 3) if rate else None,
                    })
                elif code == _DELAY:
                    position_ms += struct.unpack(">I", payload[:4])[0]
                elif code:
                    unknown.append({"Code": code, "Payload": payload.hex()})
        result.append({
            "CueName": name_row.get("CueName", ""),
            "CueIndex": cue_index,
            "UserData": cue.get("UserData", ""),
            "Clips": clips,
            "UnknownCommands": unknown,
        })
    return result


def read_memory_awb(data):
    """Return ``{awb_id: bytes}`` from the AFS2 archive embedded in an ACB."""
    _, header_rows = parse_utf(data)
    blob = header_rows[0].get("AwbFile") if header_rows else None
    if not isinstance(blob, bytes) or not blob:
        return {}
    if blob[:4] != b"AFS2":
        raise CriUtfError("embedded AWB is not AFS2")
    offset_size = blob[5]
    id_size = struct.unpack("<H", blob[6:8])[0]
    count, alignment = struct.unpack("<II", blob[8:16])
    alignment &= 0xFFFF
    ids = [int.from_bytes(blob[16 + id_size * i:16 + id_size * (i + 1)], "little") for i in range(count)]
    base = 16 + id_size * count
    offsets = [int.from_bytes(blob[base + offset_size * i:base + offset_size * (i + 1)], "little")
               for i in range(count + 1)]
    entries = {}
    for i, awb_id in enumerate(ids):
        start = -(-offsets[i] // alignment) * alignment if alignment else offsets[i]
        if offsets[i + 1] > len(blob) or start > offsets[i + 1]:
            raise CriUtfError(f"invalid AFS2 entry {awb_id}")
        entries[awb_id] = blob[start:offsets[i + 1]]
    return entries
