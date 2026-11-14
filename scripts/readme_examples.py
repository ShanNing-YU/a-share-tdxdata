#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""readme_examples.py — 把 README 里的 python 代码块**逐块原样执行**（发版清单一项）

对外使用者第一步就是照抄 README，所以示例必须真能跑。**每个块都独立执行**
（若某块依赖上一块的变量，说明用户单独复制会 NameError → 应改成自包含）。

用法（跑在装好待发布 wheel 的干净 venv 里）：
    <venv>/bin/python scripts/readme_examples.py README.md
"""

import re
import sys
import traceback
from pathlib import Path

readme = Path(sys.argv[1] if len(sys.argv) > 1 else 'README.md').read_text()
blocks = re.findall(r'```python\n(.*?)```', readme, re.S)
print(f'README 里 python 代码块 {len(blocks)} 个')

ok = fail = 0
for i, code in enumerate(blocks, 1):
    head = code.strip().split('\n')[0][:60]
    ns = {}
    try:
        exec(compile(code, f'README-block-{i}', 'exec'), ns)
        print(f'  ✅ 块 {i}: {head}')
        ok += 1
    except Exception:
        print(f'  ❌ 块 {i}: {head}')
        traceback.print_exc(limit=2)
        fail += 1

print(f'\n=== README 示例：通过 {ok} / 失败 {fail} ===')
sys.exit(1 if fail else 0)
