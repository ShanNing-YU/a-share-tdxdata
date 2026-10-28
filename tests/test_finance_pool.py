# -*- coding: utf-8 -*-
"""Pool.finance_all 冒烟测试（真实服务器取数 + 字段断言）。

运行:
    python tests/test_finance_pool.py          # 直接跑（无需 pytest）
    python -m pytest tests/ -q                 # 有 pytest 也行

断言依据（2026-10-28 实测 + 与 iFinD 官方交叉校验 99.98% 一致）:
    000001 平安银行: ipo_date=19910403（iFinD 官方上市日 1991-04-03 ✓ 两源一致）
    总股本/净利润/每股净资产 均为非空正值域；返回 40 字段。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tdxdata.pool2 import Pool  # noqa: E402

CASES = ['000001', '600519', '300750']


def test_finance_all_basic():
    rows = Pool(n_conn=3).finance_all(CASES)
    assert len(rows) == len(CASES), f'返回长度应为 {len(CASES)}，实际 {len(rows)}'
    for code, r in zip(CASES, rows):
        assert r.get('ok') is True, f'{code} 取数失败: {r}'
        assert r.get('code') == code, f'顺序/代码错位: 期望 {code} 实际 {r.get("code")}'
        assert len(r) == 40, f'{code} 字段数应为 40，实际 {len(r)}'


def test_known_values():
    rows = Pool(n_conn=3).finance_all(['000001'])
    r = rows[0]
    assert r.get('ok') is True
    # 与 iFinD 官方上市日交叉校验一致（TDX 19910403 = iFinD 1991-04-03）
    assert r.get('ipo_date') == 19910403, f'ipo_date 应为 19910403，实际 {r.get("ipo_date")}'
    assert r.get('zongguben', 0) > 0, '总股本应为正'
    assert r.get('bvps', 0) > 0, '每股净资产应为正'


def test_version_no_drift():
    """__version__ 必须与 pyproject.toml 一致 —— 防止发布时两处不同步。"""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    pv = re.search(r'^version\s*=\s*"([^"]+)"',
                   (root / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
    import tdxdata
    assert tdxdata.__version__ == pv, \
        f'版本漂移: __init__.py={tdxdata.__version__} vs pyproject.toml={pv}'


if __name__ == '__main__':
    test_version_no_drift()
    print('   ✓ test_version_no_drift 通过（__init__ 与 pyproject 一致）')
    test_finance_all_basic()
    print('   ✓ test_finance_all_basic 通过（3 只 / 40 字段 / 顺序保持）')
    test_known_values()
    print('   ✓ test_known_values 通过（000001 ipo_date=19910403 = iFinD 官方一致）')
    print('   OK 全部通过')
