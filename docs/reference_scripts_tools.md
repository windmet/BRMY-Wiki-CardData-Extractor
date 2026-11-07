# Scripts & Tools Reference

## ASS Subtitle Converter

**Location**: `<workspace>\Scripts\s2bscript_to_ass.py`

Usage:
```cmd
cd <workspace>\Scripts
python s2bscript_to_ass.py json_output\card_357_7_1.s2bscript.json
python s2bscript_to_ass.py json_output\          # batch all scripts in dir
```

Features:
- Replaces `<SelfFirstName>` → 衣都, `<SelfLastName>` → 弥代
- Character name colors from `char_colors.json` (birthday card hex codes)
- `<b>` tags → character-colored bold highlight
- Voiced lines: green ♪Voice marker + slower timing (0.15s/char)
- Unvoiced lines: 0.07s/char timing
- Narration (ト書き): gray, top-aligned
- Scene transitions: extra wait time accumulated

## Character Colors

**Location**: `<workspace>\Scripts\char_colors.json`

22 entries: 21 characters + 主人公(#FF99BB).
Source: first birthday card `CharacterCardName` field from master_data.json.

## s2b File Parsers

**Shared core**: `bmc_toolkit/core/s2b_parser.py`
- `ext_hook(code, data)` — handles MsgPack ext type 99 (LZ4)
- `clean_data(obj)` — recursive JSON-compatible cleaning
- `parse_s2b_file(path)` — full parse pipeline

Supported formats: `.s2blyrics` (→ JSON + LRC), `.s2bscript` (→ JSON), `.s2bchart` (→ JSON)

## DevMaster Decoder

Quick decode: MsgPack with ext type 99 LZ4 blocks.
156 tables. Already decoded to `DevMaster.json` (1.9MB).

## External Tools

| Tool | Status | Notes |
|------|--------|-------|
| Il2CppDumper | Used once to generate dump.cs | Need re-run with field defaults flag |
| Cpp2IL 2022.1.0 | DOESN'T WORK | Too old for metadata v31 |
| Nuitka 4.1.2 | Working | `--enable-plugin=tk-inter` required |
| AssetRipper | Not yet used | For Unity asset bundle extraction |
