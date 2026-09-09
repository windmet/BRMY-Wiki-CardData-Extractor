""".s2blyrics 歌词文件解析 → JSON + LRC 字幕。"""
import os
from ..core.output import output_directory, record_output, record_error

from ..core.s2b_parser import parse_s2b_file, save_json


def format_lrc_time(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds == 100:
        secs += 1
        centiseconds = 0
    if secs >= 60:
        minutes += 1
        secs -= 60
    return f"[{minutes:02d}:{secs:02d}.{centiseconds:02d}]"


def convert_to_lrc(data, path):
    try:
        lyrics_list = data[0][0]
        lines = []
        for item in lyrics_list:
            if isinstance(item, list) and len(item) >= 3:
                lines.append(f"{format_lrc_time(item[1])}{str(item[2]).strip()}")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))
        record_output(path)
        return True
    except Exception as e:
        print(f"  [!] LRC convert error: {e}")
        record_error(f"LRC: {e}")
        return False


def run(input_path=None):
    if input_path and os.path.isfile(input_path):
        files = [os.path.basename(input_path)]
        input_dir = os.path.abspath(os.path.dirname(input_path) or ".")
    else:
        input_dir = os.path.abspath(input_path or os.getcwd())
        files = [f for f in os.listdir(input_dir) if f.endswith(".s2blyrics")]

    if not files:
        print("[!] 未找到 .s2blyrics 文件")
        record_error("未找到可解析的输入文件")
        return

    json_dir = output_directory("audit", os.path.join(input_dir, "json_output"))
    xlsx_dir = output_directory("wiki", os.path.join(input_dir, "xlsx_output"))
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(xlsx_dir, exist_ok=True)

    print(f"[*] 处理 {len(files)} 个 .s2blyrics 文件")
    for fn in files:
        fp = os.path.join(input_dir, fn)
        try:
            data = parse_s2b_file(fp)
            base = os.path.splitext(fn)[0]
            save_json(data, os.path.join(json_dir, f"{fn}.json"))
            convert_to_lrc(data, os.path.join(xlsx_dir, f"{base}.lrc"))
            print(f"  [+] {fn} → JSON + LRC")
        except Exception as e:
            print(f"  [!] {fn}: {e}")
            record_error(f"{fn}: {e}")
    return input_dir
