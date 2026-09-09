"""音乐数据提取 + 导出。"""
import os

from ..core.scanner import load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path, audit_path
from ..core.output import record_warning
from ..core.data import format_duration
from ..core.tables import TableCatalog

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    MP3 = None
    HAS_MUTAGEN = False

INPUT_JSON = 'master_data.json'

def _resource_filename(value, extension):
    """Retain existing suffixes; bare asset names use the local export convention."""
    return value + extension if value and not os.path.splitext(value)[1] else value or ''

def extract(audio_dir=None, session=None):
    tables = session.tables if session else TableCatalog(load_json(INPUT_JSON))
    music_db = {}
    out_game = tables.group_by('mst_music_out_game', 'MusicId', required=False)
    audit = {'Music': [], 'Issues': []}

    for obj in tables.require('mst_music'):
        mid = obj['MusicId']
        matches = out_game.get(mid, [])
        resource = matches[0] if len(matches) == 1 else obj
        status = 'matched' if len(matches) == 1 else 'ambiguous' if matches else 'unmatched'
        audit['Music'].append({'MusicId': mid, 'Status': status,
                               'MusicRecord': obj, 'OutGameRecords': matches})
        if len(matches) > 1:
            audit['Issues'].append({'MusicId': mid, 'Status': status})
        audio_file = _resource_filename(resource.get('AudioFileName', ''), '.mp3')
        jacket_file = _resource_filename(resource.get('JacketFileName', ''), '.png')
        artist = obj.get('ArtistNameInformal', '') or obj.get('ArtistName', '')

        music_db[mid] = {
            "MusicId": mid,
            "DisplayName": obj.get('DisplayName', ''),
            "ArtistName": artist,
            "AudioFileName": audio_file,
            "JacketFileName": jacket_file,
            "DurationStr": "",
            "_raw_duration_sec": obj.get('Duration', obj.get('PlayTime', 0)),
        }

    if audio_dir and os.path.exists(audio_dir) and HAS_MUTAGEN:
        print(f"[*] 扫描本地音频目录: {audio_dir}")
        for mid, m in music_db.items():
            if m["AudioFileName"]:
                fp = os.path.join(audio_dir, m["AudioFileName"])
                if os.path.exists(fp):
                    try:
                        m["_raw_duration_sec"] = MP3(fp).info.length
                    except Exception as e:
                        print(f"[!] 无法读取 {m['AudioFileName']}: {e}")

    for m in music_db.values():
        m["DurationStr"] = format_duration(m.get("_raw_duration_sec", 0))
        m.pop("_raw_duration_sec", None)

    sorted_db = {k: music_db[k] for k in sorted(music_db.keys(), key=int)}
    for mid, records in out_game.items():
        if mid not in music_db:
            audit['Issues'].append({'MusicId': mid, 'Status': 'missing_music',
                                    'OutGameRecords': records})
    save_json(audit, audit_path('music_relations.json'))
    if audit['Issues']:
        record_warning(f"音乐资源关系有 {len(audit['Issues'])} 条异常，详见 music_relations.json")
    out = json_path('Music_Database.json')
    save_json(sorted_db, out)
    print(f"[+] 提取 {len(sorted_db)} 首曲目 → {out}")
    return sorted_db


def export():
    data = load_json(json_path('Music_Database.json'))
    headers = ["歌曲编号", "曲目名", "作者/歌手", "音频文件名", "封面文件名", "歌曲长度"]
    rows = []
    for mid, m in sorted(data.items(), key=lambda x: int(x[0])):
        rows.append([
            m.get("MusicId", ""), m.get("DisplayName", ""), m.get("ArtistName", ""),
            m.get("AudioFileName", ""), m.get("JacketFileName", ""), m.get("DurationStr", ""),
        ])
    out = xlsx_path('music_data.xlsx')
    write_xlsx(rows, out, headers, sheet_title="Music_Data",
               col_widths={'A': 12, 'B': 35, 'C': 35, 'D': 30, 'E': 35, 'F': 12})


def run(audio_dir=None, session=None):
    extract(audio_dir=audio_dir, session=session)
    export()
