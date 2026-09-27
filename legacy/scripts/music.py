import json
import os
import re

try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None
    print("[!] 未安装 mutagen 库，将无法读取本地 mp3 的真实长度。请执行: pip install mutagen")

# 配置文件名与路径
INPUT_JSON = 'master_data.json'
OUTPUT_JSON = 'Music_Database.json'
# 如果你想直接读取本地 mp3 长度，请填写本机 Jukebox 目录。
# 留空则跳过读取本地时长
AUDIO_DIR = ""

def format_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

def main():
    print(f"[*] 正在加载数据库 {INPUT_JSON} ...")
    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[+] 数据库加载成功！")
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    music_db = {}

    def scan_obj(obj):
        if isinstance(obj, dict):
            # 识别音乐数据块的特征字段
            if 'MusicId' in obj and 'DisplayName' in obj:
                mid = obj['MusicId']
                
                # 处理文件名（加上后缀），如果是空字符串则保持为空
                audio_raw = obj.get('AudioFileName', "")
                audio_file = f"{audio_raw}.mp3" if audio_raw else ""
                
                jacket_raw = obj.get('JacketFileName', "")
                jacket_file = f"{jacket_raw}.png" if jacket_raw else ""

                # 处理作者名 (优先用非正式名称，通常带有 CV 信息更全)
                artist = obj.get('ArtistNameInformal', "")
                if not artist:
                    artist = obj.get('ArtistName', "")

                music_db[mid] = {
                    "MusicId": mid,
                    "DisplayName": obj.get('DisplayName', ''),
                    "ArtistName": artist,
                    "AudioFileName": audio_file,
                    "JacketFileName": jacket_file,
                    # 防御性读取：如果masterdata意外包含了长度信息，先作为兜底
                    "DurationStr": "",
                    "_raw_duration_sec": obj.get('Duration', obj.get('PlayTime', 0)) 
                }

            # 递归深搜
            for v in obj.values():
                scan_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                scan_obj(item)

    print("[*] 正在执行深度扫描与数据缝合...")
    scan_obj(data)

    # 如果提供了本地音频目录，尝试读取真实长度
    if AUDIO_DIR and os.path.exists(AUDIO_DIR) and MP3:
        print(f"[*] 正在扫描本地音频目录获取时长: {AUDIO_DIR}")
        for mid, m_data in music_db.items():
            if m_data["AudioFileName"]:
                file_path = os.path.join(AUDIO_DIR, m_data["AudioFileName"])
                if os.path.exists(file_path):
                    try:
                        audio = MP3(file_path)
                        m_data["_raw_duration_sec"] = audio.info.length
                    except Exception as e:
                        print(f"[!] 无法读取文件时长 {m_data['AudioFileName']}: {e}")

    # 格式化所有时长
    for mid, m_data in music_db.items():
        if m_data["_raw_duration_sec"]:
            m_data["DurationStr"] = format_duration(m_data["_raw_duration_sec"])
        else:
            m_data["DurationStr"] = "未知"
        
        # 移除临时数据以免污染输出
        m_data.pop("_raw_duration_sec", None)

    # 按 MusicId 排序
    sorted_music_db = {k: music_db[k] for k in sorted(music_db.keys())}

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(sorted_music_db, f, ensure_ascii=False, indent=4)
    print(f"[+] 歌曲信息已保存至: {OUTPUT_JSON}，共提取 {len(sorted_music_db)} 首曲目！")

if __name__ == "__main__":
    main()
