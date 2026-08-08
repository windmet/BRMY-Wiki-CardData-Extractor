---
name: bmc-toolkit
description: "Break My Case wiki data extraction toolkit — exe build, domain structure, data sources, story/ASS converter"
metadata: 
  node_type: memory
  type: project
  originSessionId: c2a73b49-ffac-41c0-a940-4b4d8a2f1d35
---

# BMC Toolkit Project

> 历史重构记录：本文中的目录、菜单和 EXE 状态停留在早期版本。当前状态请以 [BMC 数据提取工具箱开发现状](DEVELOPMENT_STATUS.md) 为准。

## Overview

Reverse-engineering Break My Case (コリー社/Coly) game data for wiki building.
Master data comes from `master_data.s2b` (MsgPack + LZ4 compressed).
Additional data from S3 bucket: `https://coly-s2b-client-stg.s3.ap-northeast-1.amazonaws.com/`

## Key Directory Layout

```
D:\Files\Downloads\Compressed\masterdata\
  run.py                    # CLI entry (double-click = interactive, args = CLI)
  build.bat                 # Nuitka one-click build
  bmc_toolkit/              # Main package
    core/
      scanner.py            # walk(), load_json(), save_json()
      exporter.py           # write_xlsx(), json_path(), xlsx_path() → json_output/ + xlsx_output/
      data.py               # Shared constants (CHAR_MAP, RARITY_MAP, translate_scene, clean_text, etc.)
      s2b_parser.py         # MsgPack+LZ4 ext type 99 parser for .s2b* files
    domains/
      cards.py              # Card extraction (extract from master_data + export to xlsx)
      music.py              # Music extraction (with local MP3 duration via mutagen)
      snap.py               # Snap/Polaroid extraction + dedup export
      birthday.py           # Birthday lines extraction (cycle 3, horizontal table)
      recipes.py            # Bar recipes + ingredients + shift menus
      missions.py           # Hidden missions → xlsx
      lyrics.py             # .s2blyrics → JSON + LRC
      scripts.py            # .s2bscript → JSON
      charts.py             # .s2bchart (OJT表) → JSON
      snap_wiki.py          # Spin-based wiki format (experimental, not in menu)
    interactive.py          # tkinter file dialog + numbered menu
  dist/
    bmc_toolkit.exe         # Nuitka-built exe (~23MB with tk-inter plugin)
  final/                    # OLD 50MB PyInstaller exe source (reference only)
  新建文件夹/                # Original scattered scripts (UNCHANGED, reference only)
```

## Data Flow

1. `master_data.s2b` → decrypt (MsgPack+LZ4+lzma) → `master_data.json` (50MB)
2. `master_data.json` → domain extractors → `json_output/*.json`
3. `json_output/*.json` → domain exporters → `xlsx_output/*.xlsx`

## Nuitka Build

```cmd
python -m nuitka --standalone --onefile --enable-plugin=tk-inter --output-dir=dist --output-filename=bmc_toolkit.exe run.py
```

Critical: MUST use `--enable-plugin=tk-inter` for the file dialog to work.

## Bug Fixes Applied

1. **cards.py gacha linking**: Gacha objects have no `CharacterCardId`, so `if not cid: continue` skipped them. Fixed by adding a separate walk() for gacha linking after card extraction.
2. **music.py audio_dir**: Old script hardcoded a local Jukebox path. The monorepo version accepts it as an optional parameter.
3. **snap.py comments shift**: Extract phase was padding empty comments, which sorted before real data in export phase. Fixed by only storing real comments.
4. **music.py sorting**: String-sorted MusicId keys ("1","10","100"...) → fixed with `key=int`.

## Exe Menu (current)

```
[1] Cards  [2] Music  [3] Snap  [4] Birthday  [5] Recipes  [6] Missions
[7] Lyrics (.s2blyrics)  [8] Scripts (.s2bscript)  [9] OJT (.s2bchart)
[A] All (1-6)  [Q] Quit
```
