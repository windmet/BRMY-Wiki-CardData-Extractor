#!/usr/bin/env python3
"""BMC Toolkit —— Break My Case Wiki 数据解包统一工具

[master_data 数据域] — 需先解密 master_data.s2b
    decrypt                                   解密 s2b → master_data.json
    run cards|music|snap|birthday|recipes|... 提取 + 导出一条龙
    all                                       全量跑所有 masterdata 域

[s2b 文件解析] — 可指定文件或目录；不指定则扫描当前目录
    run lyrics [文件或目录]                    歌词解析 (.s2blyrics → JSON+LRC)
    run scripts [文件或目录]                   脚本解析 (.s2bscript → JSON)
    run charts [文件或目录]                    谱面解析 (.s2bchart → JSON)

[CRI 音频]
    run audio <Musics目录>                     ACB清单、语音文本与卡面语音索引
    run cards [Musics目录]                     提取卡表，并可选填入卡面日文语音
    run home_voices <Musics目录> [master_data.json] [--subject 主体]
                    [--reference-acb 旧ACB目录]
                                              主页/季节/生日语音 Wiki 表

[通用]
    list                                      列出所有可用域
"""

import sys
import os

from .domains import DOMAINS

# 确保工作目录正确（通常放在 master_data.json 同级）
MASTER_DIR = os.getcwd()


def print_usage():
    print(__doc__)


def cmd_list():
    print("可用域:")
    print("\n  --- master_data 数据域（需 decrypt 前置） ---")
    for name in ['cards', 'music', 'snap', 'birthday', 'recipes', 'missions', 'items', 'events']:
        mod = DOMAINS.get(name)
        doc = (mod.__doc__ or "").strip().split('\n')[0]
        print(f"    {name:15s} — {doc}")
    print("\n  --- s2b 文件解析（可指定文件或目录） ---")
    for name in ['lyrics', 'scripts', 'charts']:
        mod = DOMAINS.get(name)
        doc = (mod.__doc__ or "").strip().split('\n')[0]
        print(f"    {name:15s} — {doc}")
    print("\n  --- CRI 音频资源（指定 ACB/AWB 目录） ---")
    mod = DOMAINS.get('audio')
    doc = (mod.__doc__ or "").strip().split('\n')[0]
    print(f"    {'audio':15s} — {doc}")
    mod = DOMAINS.get('home_voices')
    doc = (mod.__doc__ or "").strip().split('\n')[0]
    print(f"    {'home_voices':15s} — {doc}")


def cmd_decrypt():
    """调用内嵌的 s2b 解密脚本。"""
    import msgpack
    import lz4.block
    import zlib
    import lzma
    from datetime import datetime

    s2b_path = os.path.join(MASTER_DIR, "master_data.s2b")
    json_path = os.path.join(MASTER_DIR, "master_data.json")

    if not os.path.exists(s2b_path):
        print(f"[!] 未找到 master_data.s2b，请将文件放在当前目录")
        return

    print("[*] 解密 master_data.s2b ...")

    def try_decompress(data, tag="unknown"):
        try:
            size = msgpack.unpackb(data[:5])
            decompressed = lz4.block.decompress(data[5:], uncompressed_size=size)
            print(f"[+] {tag}: lz4(带size) 解压成功, size={size}")
            return decompressed
        except Exception:
            pass
        try:
            decompressed = lz4.block.decompress(data)
            print(f"[+] {tag}: lz4(无size) 解压成功, len={len(decompressed)}")
            return decompressed
        except Exception:
            pass
        try:
            decompressed = zlib.decompress(data)
            print(f"[+] {tag}: zlib 解压成功, len={len(decompressed)}")
            return decompressed
        except Exception:
            pass
        try:
            decompressed = zlib.decompress(data, wbits=-15)
            print(f"[+] {tag}: raw inflate 解压成功, len={len(decompressed)}")
            return decompressed
        except Exception:
            pass
        try:
            decompressed = lzma.decompress(data)
            print(f"[+] {tag}: 标准 LZMA 解压成功, len={len(decompressed)}")
            return decompressed
        except Exception:
            pass
        try:
            decompressed = lzma.decompress(data[5:])
            print(f"[+] {tag}: 偏移5字节 LZMA 解压成功, len={len(decompressed)}")
            return decompressed
        except Exception:
            pass
        print(f"[!] {tag}: 所有解压方式都失败")
        return data

    def ext_hook(code, data):
        if code == 99:
            decompressed = try_decompress(data, tag="ext99")
            try:
                return msgpack.unpackb(decompressed, raw=False)
            except Exception:
                try:
                    return decompressed.decode('utf-8')
                except Exception:
                    return f"<Binary Data: {len(decompressed)} bytes>"
        return msgpack.ExtType(code, data)

    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, msgpack.ext.Timestamp):
            return obj.to_datetime().isoformat()
        raise TypeError(f"Unsupported type: {type(obj)}")

    with open(s2b_path, "rb") as f:
        raw = f.read()

    unpacker = msgpack.Unpacker(ext_hook=ext_hook, raw=False)
    unpacker.feed(raw)

    objs = []
    for obj in unpacker:
        objs.append(obj)

    print(f"[*] 解码总对象数: {len(objs)}")

    import json
    with open(json_path, "w", encoding="utf-8") as out:
        json.dump(objs, out, default=json_serial, ensure_ascii=False, indent=2)

    print(f"[+] 已保存 → {json_path}")


def cmd_extract(domain_name):
    mod = DOMAINS.get(domain_name)
    if not mod:
        print(f"[!] 未知域: {domain_name}，用 'list' 查看可用域")
        return
    if hasattr(mod, 'extract'):
        mod.extract()
    elif hasattr(mod, 'run'):
        mod.run()
    else:
        print(f"[!] {domain_name} 不支持单独提取，请用 'run'")


def cmd_export(domain_name):
    mod = DOMAINS.get(domain_name)
    if not mod:
        print(f"[!] 未知域: {domain_name}")
        return
    if hasattr(mod, 'export'):
        mod.export()
    else:
        print(f"[!] {domain_name} 没有导出步骤")


def cmd_run(domain_name, input_paths=None):
    mod = DOMAINS.get(domain_name)
    if not mod:
        print(f"[!] 未知域: {domain_name}")
        return
    if hasattr(mod, 'run'):
        input_paths = input_paths or []
        if domain_name == 'home_voices':
            if not input_paths:
                print("[!] home_voices 需要 Musics 目录")
                return
            positional = []
            options = {}
            index = 0
            while index < len(input_paths):
                value = input_paths[index]
                if value in {"--subject", "--reference-acb"}:
                    if index + 1 >= len(input_paths):
                        print(f"[!] {value} 缺少参数")
                        return
                    options[value] = input_paths[index + 1]
                    index += 2
                    continue
                positional.append(value)
                index += 1
            if not positional:
                print("[!] home_voices 需要 Musics 目录")
                return
            mod.run(
                positional[0],
                positional[1] if len(positional) >= 2 else None,
                options.get("--subject") or (positional[2] if len(positional) >= 3 else None),
                options.get("--reference-acb"),
            )
        elif input_paths:
            mod.run(input_paths[0])
        else:
            mod.run()
    else:
        print(f"[!] {domain_name} 没有 run() 方法")


def cmd_all():
    print("=" * 50)
    print("  BMC Toolkit — 全量解包")
    print("=" * 50)
    for name in ['cards', 'music', 'snap', 'birthday', 'recipes', 'missions', 'items', 'events']:
        mod = DOMAINS.get(name)
        if not mod:
            continue
        print(f"\n--- [{name}] ---")
        try:
            if hasattr(mod, 'run'):
                mod.run()
            elif hasattr(mod, 'extract'):
                mod.extract()
                if hasattr(mod, 'export'):
                    mod.export()
        except Exception as e:
            print(f"[!] {name} 失败: {e}")


def main():
    args = sys.argv[1:]

    if not args:
        print_usage()
        return

    cmd = args[0].lower()

    if cmd == 'list':
        cmd_list()
    elif cmd == 'decrypt':
        cmd_decrypt()
    elif cmd == 'all':
        cmd_all()
    elif cmd == 'extract' and len(args) >= 2:
        cmd_extract(args[1])
    elif cmd == 'export' and len(args) >= 2:
        cmd_export(args[1])
    elif cmd == 'run' and len(args) >= 2:
        cmd_run(args[1], args[2:])
    else:
        print_usage()


if __name__ == '__main__':
    main()
