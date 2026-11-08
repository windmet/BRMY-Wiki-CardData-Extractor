#!/usr/bin/env python3
"""BMC Toolkit —— Break My Case Wiki 数据解包统一工具

组员请直接双击 exe 打开桌面工具箱。以下命令供维护者和 CI 使用：

    gui                                       打开桌面工具箱
    sync <任务...> --cache <目录> --output <目录> [--offline] [--plan-only]
                                              按任务同步正式资源并生成
    generate <任务...> --output <目录> --masterdata <文件> [--audio <Musics目录>]
             [--source <文件或目录>] [--old-workbook <旧XLSX>]
             [--cycle N] [--year YYYY] [--subject 主体] [--recent-year YYYY-MM-DD]
                                              用本地文件生成，并输出本次产物清单
    resources catalog|masterdata|download --cache <目录> [--offline]
    website check|prepare --cache <目录> --output <目录> [--offline]
                                              正式服资源清单与按需下载
    list                                      列出所有任务
    doctor [--json]                           检查依赖、Tkinter 和任务注册

旧的 decrypt / all / run / update / extract / export 已停用，请改用 generate 或 sync。
"""

import json
import sys

from .domains import DOMAINS
from .core.console import configure_console

RETIRED = {
    'decrypt': 'generate 直接接受 master_data.s2b',
    'all': 'generate <任务...> 或 sync <任务...>',
    'run': 'generate <任务> --masterdata/--audio/--source …',
    'update': 'generate card_update --old-workbook <旧XLSX> --audio <Musics目录>',
    'extract': 'generate <任务>',
    'export': 'generate <任务>',
}


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
    print("可用任务:")
    for name in sorted(DOMAINS):
        doc = (DOMAINS[name].__doc__ or "").strip().split('\n')[0]
        print(f"    {name:18s} — {doc}")


def main():
    configure_console()
    args = sys.argv[1:]

    if not args:
        print_usage()
        return

    cmd = args[0].lower()

    if cmd == 'gui':
        if args[1:] == ['--self-test']:
            from .gui import self_test
            print(json.dumps(self_test(), ensure_ascii=False))
        elif len(args) == 1:
            from .gui import main as gui_main
            gui_main()
        else:
            raise SystemExit('gui 仅支持 --self-test 或无参数启动')
    elif cmd == 'website':
        from .website.service import main as website_main
        if not website_main(args[1:]):
            raise SystemExit(1)
    elif cmd == 'sync':
        from .resolve import main as sync_main
        if not sync_main(args[1:]):
            raise SystemExit(1)
    elif cmd == 'resources':
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
    elif cmd in RETIRED:
        raise SystemExit(f'{cmd} 命令已停用，请改用：{RETIRED[cmd]}')
    else:
        print_usage()


if __name__ == '__main__':
    main()
