#!/usr/bin/env python3
"""BMC Toolkit —— Break My Case Wiki 数据解包统一工具

[master_data 数据域] — 需先解密 master_data.s2b
    decrypt                                   解密 s2b → master_data.json
    run cards|music|snap|birthday|recipes|... 提取 + 导出一条龙
    all                                       全量跑所有 masterdata 域
    update cards <旧cards_data.xlsx> [Musics目录]
                                              保留人工列并生成增删改清单

[s2b 文件解析] — 可指定文件或目录；不指定则扫描当前目录
    run lyrics [文件或目录]                    歌词解析 (.s2blyrics → JSON+LRC)
    run scripts [文件或目录]                   脚本解析 (.s2bscript → JSON)
    run charts [文件或目录]                    谱面解析 (.s2bchart → JSON)

[CRI 音频]
    run audio <Musics目录>                     ACB清单、语音文本与卡面语音索引
    run cards [Musics目录]                     提取卡表，并可选填入卡面日文语音
    run birthday [--year 周期起始年] [--cycle 周期号]
                                              自动选择最新生日周期，或显式覆盖
    run home_voices <Musics目录> [master_data.json] [--subject 主体]
                    [--reference-acb 旧ACB目录] [--recent-year YYYY-MM-DD]
                                              主页/季节/生日语音 Wiki 表

[通用]
    resources catalog|masterdata|download --cache <目录> [--offline]
                                              正式服资源清单与按需下载
    generate <域...> --output <目录> --masterdata <文件>
                                              显式输入输出，生成本次产物清单
    list                                      列出所有可用域
    doctor [--json]                           检查依赖、Tkinter 和域注册
"""

import json
import sys
import os
import time

from .domains import DOMAINS
from .core.console import configure_console
from .core.session import MasterDataSession, utc_now

# 确保工作目录正确（通常放在 master_data.json 同级）
MASTER_DIR = os.getcwd()
MASTERDATA_DOMAIN_NAMES = {
    'cards', 'music', 'snap', 'birthday', 'recipes', 'missions', 'items', 'events'
}


def prepare_masterdata():
    """Verify or build master_data.json when the canonical S2B is available."""
    from .core.masterdata import ensure_masterdata_json

    s2b_path = os.path.join(MASTER_DIR, "master_data.s2b")
    json_path = os.path.join(MASTER_DIR, "master_data.json")
    if os.path.isfile(s2b_path):
        return ensure_masterdata_json(s2b_path, MASTER_DIR).json_path
    if os.path.isfile(json_path):
        return json_path
    print("[!] 未找到 master_data.s2b 或 master_data.json")
    return False


def print_usage():
    print(__doc__)


def cmd_doctor(as_json=False):
    from .core.doctor import build_doctor_report

    report = build_doctor_report(DOMAINS)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"运行环境检查: {report['status']}")
        print(f"  Python: {report['python_version']}")
        print(f"  Frozen EXE: {'yes' if report['frozen'] else 'no'}")
        for check in report["dependencies"]:
            detail = check.get("version") or check.get("error", "")
            print(f"  {check['status']:4s} {check['name']}: {detail}")
        print(f"  Domains: {len(report['domains'])}")
        if report["missing_domains"]:
            print("  Missing domains: " + ", ".join(report["missing_domains"]))
    return report["status"] == "PASS"


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
    print("\n  --- 增量更新 ---")
    print("    update cards <旧XLSX> [Musics目录] — 保留卡牌人工列并生成差分")


def cmd_decrypt():
    """严格解码 master_data.s2b，并按源文件哈希管理 JSON 缓存。"""
    configure_console()
    from .core.masterdata import ensure_masterdata_json

    s2b_path = os.path.join(MASTER_DIR, "master_data.s2b")
    if not os.path.exists(s2b_path):
        print(f"[!] 未找到 master_data.s2b，请将文件放在当前目录")
        return False
    return ensure_masterdata_json(s2b_path, MASTER_DIR).json_path


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
    configure_console()
    mod = DOMAINS.get(domain_name)
    if not mod:
        print(f"[!] 未知域: {domain_name}")
        return False
    session = None
    started_at = utc_now()
    if domain_name in MASTERDATA_DOMAIN_NAMES:
        masterdata_path = prepare_masterdata()
        if not masterdata_path:
            return False
        session = MasterDataSession.open(masterdata_path)
        if session.assessment.errors:
            for error in session.assessment.errors:
                print(f"[!] Schema: {error}")
            session.write_audit([], started_at=started_at, success=False)
            return False
    started = time.perf_counter()
    if hasattr(mod, 'run'):
        input_paths = input_paths or []
        if domain_name == 'home_voices':
            if not input_paths:
                print("[!] home_voices 需要 Musics 目录")
                return False
            positional = []
            options = {}
            index = 0
            while index < len(input_paths):
                value = input_paths[index]
                if value in {"--subject", "--reference-acb", "--recent-year"}:
                    if index + 1 >= len(input_paths):
                        print(f"[!] {value} 缺少参数")
                        return False
                    options[value] = input_paths[index + 1]
                    index += 2
                    continue
                positional.append(value)
                index += 1
            if not positional:
                print("[!] home_voices 需要 Musics 目录")
                return False
            mod.run(
                positional[0],
                positional[1] if len(positional) >= 2 else None,
                options.get("--subject") or (positional[2] if len(positional) >= 3 else None),
                options.get("--reference-acb"),
                options.get("--recent-year"),
            )
        elif domain_name == 'birthday':
            options = {}
            index = 0
            while index < len(input_paths):
                value = input_paths[index]
                if value not in {"--year", "--cycle"}:
                    print(f"[!] birthday 未知参数: {value}")
                    return False
                if index + 1 >= len(input_paths):
                    print(f"[!] {value} 缺少参数")
                    return False
                try:
                    options[value] = int(input_paths[index + 1])
                except ValueError:
                    print(f"[!] {value} 必须是整数: {input_paths[index + 1]}")
                    return False
                index += 2
            try:
                mod.run(
                    session=session,
                    target_year=options.get("--year"),
                    target_cycle=options.get("--cycle"),
                )
            except ValueError as error:
                print(f"[!] birthday 参数错误: {error}")
                if session:
                    session.write_audit(
                        [{
                            "name": domain_name,
                            "status": "FAIL",
                            "duration_seconds": round(time.perf_counter() - started, 3),
                            "error": str(error),
                        }],
                        started_at=started_at,
                        success=False,
                    )
                return False
        elif input_paths:
            if session:
                mod.run(input_paths[0], session=session)
            else:
                mod.run(input_paths[0])
        else:
            if session:
                mod.run(session=session)
            else:
                mod.run()
    else:
        print(f"[!] {domain_name} 没有 run() 方法")
        return False
    if session:
        session.write_audit(
            [{
                "name": domain_name,
                "status": "PASS",
                "duration_seconds": round(time.perf_counter() - started, 3),
            }],
            started_at=started_at,
            success=True,
        )
    return True


def cmd_all():
    configure_console()
    print("=" * 50)
    print("  BMC Toolkit — 全量解包")
    print("=" * 50)
    masterdata_path = prepare_masterdata()
    if not masterdata_path:
        return False
    started_at = utc_now()
    session = MasterDataSession.open(masterdata_path)
    if session.assessment.errors:
        for error in session.assessment.errors:
            print(f"[!] Schema: {error}")
        session.write_audit([], started_at=started_at, success=False)
        return False
    failures = []
    domain_results = []
    for name in ['cards', 'music', 'snap', 'birthday', 'recipes', 'missions', 'items', 'events']:
        mod = DOMAINS.get(name)
        if not mod:
            continue
        print(f"\n--- [{name}] ---")
        started = time.perf_counter()
        try:
            if hasattr(mod, 'run'):
                mod.run(session=session)
            elif hasattr(mod, 'extract'):
                mod.extract(session=session)
                if hasattr(mod, 'export'):
                    mod.export()
            domain_results.append({
                "name": name,
                "status": "PASS",
                "duration_seconds": round(time.perf_counter() - started, 3),
            })
        except Exception as e:
            print(f"[!] {name} 失败: {e}")
            failures.append((name, str(e)))
            domain_results.append({
                "name": name,
                "status": "FAIL",
                "duration_seconds": round(time.perf_counter() - started, 3),
                "error": str(e),
            })
    session.write_audit(
        domain_results, started_at=started_at, success=not failures
    )
    if failures:
        print(f"\n[!] 全量解包失败：{len(failures)} 个域未完成")
        for name, message in failures:
            print(f"    - {name}: {message}")
        return False
    print("\n[+] 全量解包完成")
    return True


def cmd_update_cards(old_workbook, audio_dir=None):
    configure_console()
    if not os.path.isfile(old_workbook):
        print(f"[!] 旧卡牌工作簿不存在: {old_workbook}")
        return False
    if audio_dir and not os.path.isdir(audio_dir):
        print(f"[!] Musics 目录不存在: {audio_dir}")
        return False
    masterdata_path = prepare_masterdata()
    if not masterdata_path:
        return False
    started_at = utc_now()
    session = MasterDataSession.open(masterdata_path)
    if session.assessment.errors:
        for error in session.assessment.errors:
            print(f"[!] Schema: {error}")
        session.write_audit([], started_at=started_at, success=False)
        return False

    started = time.perf_counter()
    try:
        DOMAINS['card_update'].run(
            old_workbook,
            audio_dir=audio_dir,
            session=session,
        )
    except Exception as error:
        print(f"[!] 卡牌增量更新失败: {error}")
        session.write_audit(
            [{
                "name": "card_update",
                "status": "FAIL",
                "duration_seconds": round(time.perf_counter() - started, 3),
                "error": str(error),
            }],
            started_at=started_at,
            success=False,
        )
        return False
    session.write_audit(
        [{
            "name": "card_update",
            "status": "PASS",
            "duration_seconds": round(time.perf_counter() - started, 3),
        }],
        started_at=started_at,
        success=True,
    )
    return True


def main():
    configure_console()
    args = sys.argv[1:]

    if not args:
        print_usage()
        return

    cmd = args[0].lower()

    if cmd == 'resources':
        from .resources import main as resources_main
        if not resources_main(args[1:]):
            raise SystemExit(1)
    elif cmd == 'generate':
        from .generate import main as generate_main
        if not generate_main(args[1:]):
            raise SystemExit(1)
    elif cmd == 'list':
        cmd_list()
    elif cmd == 'doctor' and len(args) <= 2:
        if len(args) == 2 and args[1] != '--json':
            print_usage()
            raise SystemExit(1)
        if not cmd_doctor(as_json=len(args) == 2):
            raise SystemExit(1)
    elif cmd == 'decrypt':
        if not cmd_decrypt():
            raise SystemExit(1)
    elif cmd == 'all':
        if not cmd_all():
            raise SystemExit(1)
    elif cmd == 'extract' and len(args) >= 2:
        cmd_extract(args[1])
    elif cmd == 'export' and len(args) >= 2:
        cmd_export(args[1])
    elif cmd == 'run' and len(args) >= 2:
        if not cmd_run(args[1], args[2:]):
            raise SystemExit(1)
    elif cmd == 'update' and len(args) in {3, 4} and args[1].lower() == 'cards':
        if not cmd_update_cards(args[2], args[3] if len(args) == 4 else None):
            raise SystemExit(1)
    else:
        print_usage()


if __name__ == '__main__':
    main()
