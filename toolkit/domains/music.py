"""音乐数据提取 + 导出。"""
import os

from ..core.scanner import walk, load_json, save_json
from ..core.exporter import write_xlsx, json_path, xlsx_path
from ..core.data import format_duration

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    MP3 = None
    HAS_MUTAGEN = False

INPUT_JSON = 'master_data.json'
def extract(audio_dir=None):
    data = load_json(INPUT_JSON)
    music_db = {}

    for obj in walk(data):
        if 'MusicId' in obj and 'DisplayName' in obj:
            mid = obj['MusicId']
            audio_raw = obj.get('AudioFileName', '')
            audio_file = f"{audio_raw}.mp3" if audio_raw else ''
            jacket_raw = obj.get('JacketFileName', '')
            jacket_file = f"{jacket_raw}.png" if jacket_raw else ''
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


def run(audio_dir=None):
    extract(audio_dir=audio_dir)
    export()
