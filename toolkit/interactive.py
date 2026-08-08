"""BMC Toolkit — 交互式入口（双击 exe 使用）

流程:
  1. 显示功能菜单，选择要拆包的部分
  2. 若选择了 master_data 数据域，则弹出文件选择窗口选 .s2b 文件
  3. 自动解密 s2b → master_data.json → 执行选定域
  4. 若选择了 s2b 文件解析，则弹出窗口选择文件或目录
  5. 输出文件生成在所选输入文件/目录旁边
"""
import sys
import os

# ---- 预检查依赖（避免闪退） ----
try:
    import msgpack
    import lz4.block
except ImportError:
    print("[!] 缺少必要组件，请重新下载完整版工具包")
    input("按回车键退出...")
    sys.exit(1)

MASTERDATA_DOMAINS = {'1', '2', '3', '4', '5', '6', '7', '11', '13'}
S2B_FILE_DOMAINS = {'8', '9', '10'}
AUDIO_DOMAINS = {'12', '13'}

DOMAIN_MAP = {
    '1': ('cards', '卡牌数据'),
    '2': ('music', '乐曲数据'),
    '3': ('snap', '拍立得/Snap'),
    '4': ('birthday', '生日台词'),
    '5': ('recipes', '酒保配方'),
    '6': ('missions', '隐藏任务'),
    '7': ('items', '道具图鉴'),
    '11': ('events', '活动总档案'),
    '8': ('lyrics', '歌词解析 (.s2blyrics)'),
    '9': ('scripts', '脚本解析 (.s2bscript)'),
    '10': ('charts', 'OJT表解析 (.s2bchart)'),
    '12': ('audio', 'ACB音频/语音索引'),
    '13': ('home_voices', '主页/季节/生日 ACB 语音表'),
}


S2B_EXT_MAP = {
    '8': ('lyrics', '.s2blyrics', [("歌词文件", "*.s2blyrics")]),
    '9': ('scripts', '.s2bscript', [("脚本文件", "*.s2bscript")]),
    '10': ('charts', '.s2bchart', [("谱面文件", "*.s2bchart")]),
}


def select_s2b_file():
    """获取 s2b 文件路径（拖拽 或 文件选择窗口）"""
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path):
            return os.path.abspath(path)
        print(f"[!] 无效文件: {path}")

    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="请选择 master_data.s2b 文件",
            filetypes=[("s2b 文件", "*.s2b"), ("所有文件", "*.*")]
        )
        root.destroy()
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    except Exception:
        pass

    print("未选择文件。你也可以把 .s2b 文件拖到 exe 图标上运行。")
    path = input("请输入 .s2b 文件路径: ").strip().strip('"')
    if path and os.path.isfile(path):
        return os.path.abspath(path)

    return None


def select_s2b_input(ext_label, filetypes):
    """选择目录或单个文件（优先选目录，取消则选单文件）。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        # 优先：选目录
        path = filedialog.askdirectory(
            title=f"请选择存放 {ext_label} 的目录"
        )
        if path:
            root.destroy()
            return os.path.abspath(path)

        # 取消：改选单个文件
        path = filedialog.askopenfilename(
            title=f"请选择 {ext_label} 文件",
            filetypes=filetypes + [("所有文件", "*.*")]
        )
        root.destroy()
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    except Exception:
        pass

    return None


def select_audio_directory(required=False):
    """选择包含 ACB/AWB 的目录；卡牌关联时允许取消跳过。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askdirectory(
            title="请选择包含 ACB/AWB 的 Musics 目录" + ("" if required else "（可取消以跳过语音关联）")
        )
        root.destroy()
        if path and os.path.isdir(path):
            return os.path.abspath(path)
    except Exception:
        pass
    return None


def show_menu():
    print()
    print("=" * 50)
    print("  BMC Toolkit — Break My Case Wiki 拆包工具")
    print("=" * 50)
    print()
    print("  你想拆哪些部分？（可多选，用空格分隔，如: 1 2 3）")
    print()
    print("  --- master_data 数据域（需 .s2b 文件） ---")
    print("  [1] 卡牌数据")
    print("  [2] 乐曲数据")
    print("  [3] 拍立得/Snap")
    print("  [4] 生日台词")
    print("  [5] 酒保配方")
    print("  [6] 隐藏任务")
    print("  [7] 道具图鉴")
    print("  [11] 活动总档案")
    print("  [A] 全选以上 8 项")
    print()
    print("  --- s2b 文件解析（选择文件或包含目录） ---")
    print("  [8] 歌词解析 (.s2blyrics)")
    print("  [9] 脚本解析 (.s2bscript)")
    print("  [10] OJT表解析 (.s2bchart)")
    print()
    print("  --- CRI 音频资源（选择包含 ACB/AWB 的目录） ---")
    print("  [12] ACB音频清单、语音文本与卡面语音索引")
    print("  [13] 主页/季节/生日 ACB 语音 Wiki 表（同时需要 masterdata）")
    print()
    print("  [Q] 退出")
    print("-" * 50)
    print("  输出: 在所选文件/目录旁边生成 json_output/ 和 xlsx_output/")


def decrypt_s2b(s2b_path, out_dir):
    """解密 s2b → master_data.json"""
    import zlib
    import lzma
    import json
    from datetime import datetime

    master_json = os.path.join(out_dir, "master_data.json")

    if os.path.exists(master_json):
        print("[*] master_data.json 已存在，跳过解密")
        return master_json

    print("[*] 正在解密 s2b ...")

    def try_decompress(data, tag="unknown"):
        try:
            size = msgpack.unpackb(data[:5])
            return lz4.block.decompress(data[5:], uncompressed_size=size)
        except Exception:
            pass
        try:
            return lz4.block.decompress(data)
        except Exception:
            pass
        try:
            return zlib.decompress(data)
        except Exception:
            pass
        try:
            return zlib.decompress(data, wbits=-15)
        except Exception:
            pass
        try:
            return lzma.decompress(data)
        except Exception:
            pass
        try:
            return lzma.decompress(data[5:])
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
                    return f"<Binary: {len(decompressed)} bytes>"
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
    objs = [obj for obj in unpacker]

    print(f"[*] 解码对象数: {len(objs)}")

    with open(master_json, "w", encoding="utf-8") as out:
        json.dump(objs, out, default=json_serial, ensure_ascii=False, indent=2)

    print(f"[+] master_data.json 已生成")
    return master_json


def run():
    # Step 1: 先出菜单，再决定流程
    show_menu()

    while True:
        print()
        choice = input(">>> 请输入数字选择: ").strip().upper()
        if choice == 'Q':
            print("再见！")
            break

        if choice == 'A':
            selected = ['1', '2', '3', '4', '5', '6', '7', '11']
        else:
            selected = choice.split()

        valid = [s for s in selected if s in DOMAIN_MAP]
        if not valid:
            print("[!] 无效选择，请重试")
            continue

        needs_masterdata = any(v in MASTERDATA_DOMAINS for v in valid)

        output_dirs = set()
        out_dir = os.getcwd()
        audio_input = None

        # Step 2: 如果需要 masterdata，先选 .s2b 文件并解密
        if needs_masterdata:
            print()
            print("[*] 需要 master_data.s2b 来提取数据域...")
            s2b_path = select_s2b_file()
            if not s2b_path:
                print("[!] 未选择 .s2b 文件，无法处理 master_data 数据域")
                # 仅保留 s2b 文件域的选项
                s2b_only = [v for v in valid if v in S2B_FILE_DOMAINS]
                if not s2b_only:
                    input("按回车键退出...")
                    return
                print("[*] 跳过后台数据域，只解析 s2b 文件")
                valid = s2b_only
                needs_masterdata = False

            if needs_masterdata:
                out_dir = os.path.dirname(s2b_path) or "."
                output_dirs.add(os.path.abspath(out_dir))
                os.chdir(out_dir)
                try:
                    decrypt_s2b(s2b_path, out_dir)
                except Exception as e:
                    print(f"[!] 解密失败: {e}")
                    input("按回车键退出...")
                    return

        # 卡牌可选关联 ACB；独立音频域则必须选择音频目录。
        if '12' in valid or '13' in valid or '1' in valid or '2' in valid:
            print()
            if '12' in valid or '13' in valid:
                print("[*] ACB 音频索引需要选择 Musics 目录...")
            else:
                print("[*] 可选择 Musics 目录填充卡面日文语音；取消则保持语音列为空...")
            audio_input = select_audio_directory(required='12' in valid or '13' in valid)
            if audio_input:
                print(f"[*] 音频输入: {audio_input}")
            elif '12' in valid or '13' in valid:
                print("[!] 未选择音频目录，跳过 ACB 音频索引")
                valid = [key for key in valid if key not in {'12', '13'}]

        # Step 3: 执行
        from .domains import DOMAINS

        for key in valid:
            name, desc = DOMAIN_MAP[key]
            mod = DOMAINS.get(name)
            if not mod:
                print(f"  [!] 模块不存在: {name}")
                continue

            print(f"\n{'=' * 40}")
            print(f"  [{key}] {desc}")
            print(f"{'=' * 40}")

            # s2b 文件解析类：弹出文件或目录选择器
            if key in S2B_FILE_DOMAINS:
                name, ext, filetypes = S2B_EXT_MAP[key]
                print(f"  [*] 请选择 {ext} 文件或所在目录...")
                input_path = select_s2b_input(ext, filetypes)
                if not input_path:
                    print(f"  [!] 未选择，跳过")
                    continue
                print(f"  [*] 输入: {input_path}")
                try:
                    result_dir = mod.run(input_path)
                    if result_dir:
                        output_dirs.add(os.path.abspath(result_dir))
                except Exception as e:
                    print(f"  [!] {desc} 失败: {e}")
                continue  # 已执行，跳到下一项

            if key in AUDIO_DOMAINS:
                try:
                    result_dir = mod.run(audio_input)
                    if isinstance(result_dir, dict):
                        for path in result_dir.values():
                            output_dirs.add(os.path.dirname(os.path.abspath(path)))
                    elif result_dir:
                        output_dirs.add(os.path.abspath(result_dir))
                    print(f"  [+] {desc} — 完成")
                except Exception as e:
                    print(f"  [!] {desc} 失败: {e}")
                continue

            try:
                if hasattr(mod, 'run'):
                    if key in {'1', '2'}:
                        mod.run(audio_input)
                    else:
                        mod.run()
                else:
                    if hasattr(mod, 'extract'):
                        mod.extract()
                    if hasattr(mod, 'export'):
                        mod.export()
                print(f"  [+] {desc} — 完成")
                output_dirs.add(os.path.abspath(os.getcwd()))
            except Exception as e:
                print(f"  [!] {desc} 失败: {e}")

        print("\n[√] 全部处理完成")
        for path in sorted(output_dirs or {os.path.abspath(out_dir)}):
            print(f"  输出目录: {path}")
        break

    print()
    input("按回车键退出...")


if __name__ == '__main__':
    run()
