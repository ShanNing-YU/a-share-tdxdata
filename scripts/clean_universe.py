#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例：用 tdxdata 清洗标的池（分类 / 过滤 / 存活校验）。

背景：全市场代码池通常混着 股票 / ETF·LOF / 可转债，且会残留已退市标的。
本脚本演示三步清洗，可直接当模板改：

  1. 分类   —— 按代码段区分 股票 / ETF·LOF / 可转债 / 其他
  2. 过滤   —— 用外部「在市 / 退市」名单（如交易所或数据商的名单）剔除退市标的
  3. 存活校验 —— 用 tdxdata 实取财务，确认该代码**当前仍可取到数据**（最硬的存活证据）

用法：
    python scripts/clean_universe.py 000001 600519 510050 000016
    # 或从文件读（每行一个 6 位代码）
    python scripts/clean_universe.py --file codes.txt --out clean.csv
"""
import argparse
import csv
import sys

sys.path.insert(0, __file__.rsplit('/scripts/', 1)[0] + '/src')

from tdxdata import Pool  # noqa: E402

ETF_PREFIX = ('510', '511', '512', '513', '515', '516', '518', '588', '159',
              '560', '561', '562', '563', '501', '502', '506', '150', '160')
CB_PREFIX = ('110', '113', '118', '123', '127', '128')
STOCK_PREFIX = ('60', '68', '00', '30', '90', '20')


def classify(code: str) -> str:
    """按代码段分类（A 股常见段；特殊段自行补充）"""
    if code[:3] in ETF_PREFIX:
        return 'ETF/LOF'
    if code[:3] in CB_PREFIX:
        return '可转债'
    if code[:2] in STOCK_PREFIX:
        return '股票'
    return '其他'


def alive_codes(codes, n_conn: int = 5):
    """用财务接口做存活校验：能取到 40 字段即为存活。

    注意：并发数请克制（默认 5），对方每请求有固定延迟；43 是库的上限不是建议值。
    """
    rows = Pool(n_conn=n_conn).finance_all(list(codes))
    return {r['code'] for r in rows if r.get('ok')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('codes', nargs='*', help='6 位代码')
    ap.add_argument('--file', help='每行一个代码的文件')
    ap.add_argument('--delisted', help='退市代码文件（每行一个），提供则做退市过滤')
    ap.add_argument('--out', help='输出 CSV 路径')
    ap.add_argument('--no-alive-check', action='store_true', help='跳过 tdxdata 存活校验')
    a = ap.parse_args()

    codes = list(a.codes)
    if a.file:
        with open(a.file) as f:
            codes += [l.strip() for l in f if l.strip()]
    codes = sorted(set(codes))
    delisted = set()
    if a.delisted:
        with open(a.delisted) as f:
            delisted = {l.strip() for l in f if l.strip()}

    alive = set(codes) if a.no_alive_check else alive_codes(codes)

    out = []
    for c in codes:
        out.append({'code': c, 'kind': classify(c),
                    'is_delisted': c in delisted, 'alive': c in alive,
                    'keep': (classify(c) == '股票') and (c not in delisted) and (c in alive)})
    print(f'   输入 {len(codes)} 只｜退市名单 {len(delisted)}｜存活 {len(alive)}')
    print(f'   分类: ' + ', '.join(f'{k}={sum(1 for r in out if r["kind"]==k)}'
                                for k in ('股票', 'ETF/LOF', '可转债', '其他')))
    print(f'   ✅ 清洗后可用股票池: {sum(1 for r in out if r["keep"])} 只')

    if a.out:
        with open(a.out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['code', 'kind', 'is_delisted', 'alive', 'keep'])
            w.writeheader()
            w.writerows(out)
        print(f'   → 已写 {a.out}')


if __name__ == '__main__':
    main()
