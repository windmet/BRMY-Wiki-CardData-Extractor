#!/usr/bin/env python3
"""BMC Toolkit

用法:
    - 双击 exe / python run.py              → GUI
    - 拖拽 .s2b 文件到 exe 图标             → GUI（自动选中文件）
    - python run.py sync|generate ...       → 维护者 / CI 命令行
"""
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 确保能找到同级包模块
HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PARENT = os.path.dirname(HERE)
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)

if len(sys.argv) <= 1:
    from toolkit.gui import main
    main()
elif len(sys.argv) == 2 and os.path.isfile(sys.argv[1]) and sys.argv[1].lower().endswith(('.s2b', '.json')):
    from toolkit.gui import main
    main(sys.argv[1])
else:
    from toolkit.cli import main
    main()
