#!/usr/bin/env python3
"""BMC Toolkit

用法:
    - 双击 exe / python run.py              → 交互模式（文件选择 + 菜单）
    - 拖拽 .s2b 文件到 exe 图标              → 交互模式（自动选中文件）
    - python run.py run cards               → CLI 模式
    - python run.py all                     → CLI 全量
    - python run.py decrypt                 → CLI 解密
"""

import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

if len(sys.argv) <= 1:
    # 无参数 → 交互模式
    from bmc_toolkit.interactive import run
    run()
else:
    # 有参数 → CLI 模式
    from bmc_toolkit.cli import main
    main()
