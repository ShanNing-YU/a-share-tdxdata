# -*- coding: utf-8 -*-
"""tdxdata-probe CLI — 连通性自检 + 快速行情探测

用法:
    tdxdata-probe                    # 默认 101.35.121.35, 探测 600519
    tdxdata-probe --host 1.2.3.4 --codes 000001,600519
    tdxdata-probe --snap-only        # 只测分时快照（不测 bars/quotes/finance）
"""
import argparse, sys

from .client import TdxClient, market_of


def probe(host: str, codes, snap_only: bool) -> int:
    c = TdxClient(host)
    try:
        c.connect()
    except Exception as e:
        print(f'[connect] FAIL {host}: {e}')
        return 1
    print(f'[connect] OK {host}')
    for code in codes:
        m = market_of(code)
        s = c.snap(code, m)
        print(f'[snap] {code} (m{m}): last={s.get("last")} ok={s.get("ok")} pts={len(s.get("prices") or [])}')
        if snap_only:
            continue
        q = c.quotes([(m, code)])
        q0 = q[0] if q else {}
        print(f'[quote] {code}: 现价={q0.get("price")} 昨收={q0.get("last_close")} 高={q0.get("high")} 低={q0.get("low")}')
        f = c.finance(code, m)
        print(f'[fin] {code}: 流通={f.get("liutongguben", 0)/1e8:.2f}亿 净利={f.get("net_profit")}')
        b = c.bars(9, code, 0, 2, m)
        print(f'[bars] {code}: 日线{len(b)}根 最新={b[-1]["datetime"]} c={b[-1]["close"]}' if b else f'[bars] {code}: 无')
    c.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description='tdxdata 连通性自检')
    ap.add_argument('--host', default='101.35.121.35')
    ap.add_argument('--codes', default='600519', help='逗号分隔代码列表')
    ap.add_argument('--snap-only', action='store_true')
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    sys.exit(probe(args.host, codes, args.snap_only))


if __name__ == '__main__':
    main()
