""".s2bscript 脚本文件解析 → JSON。"""
import os
from ..core.output import output_directory, record_output, record_error

from ..core.s2b_parser import parse_s2b_file, save_json


def run(input_path=None):
    if input_path and os.path.isfile(input_path):
        files = [os.path.basename(input_path)]
        input_dir = os.path.abspath(os.path.dirname(input_path) or ".")
    else:
        input_dir = os.path.abspath(input_path or os.getcwd())
        files = [f for f in os.listdir(input_dir) if f.endswith(".s2bscript")]

    if not files:
        print("[!] 未找到 .s2bscript 文件")
        record_error("未找到可解析的输入文件")
        return

    json_dir = output_directory("audit", os.path.join(input_dir, "json_output"))
    os.makedirs(json_dir, exist_ok=True)
    print(f"[*] 处理 {len(files)} 个 .s2bscript 文件")
    for fn in files:
        fp = os.path.join(input_dir, fn)
        try:
            data = parse_s2b_file(fp)
            save_json(data, os.path.join(json_dir, f"{fn}.json"))
            print(f"  [+] {fn} → JSON")
        except Exception as e:
            print(f"  [!] {fn}: {e}")
            record_error(f"{fn}: {e}")
    return input_dir
