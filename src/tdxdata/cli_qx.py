# -*- coding: utf-8 -*-
"""tdxdata-qx — 权息（除权除息）与复权命令行

两个**免客户端**通道 + 复权：
    tdxdata-qx xdxr 001225              按个股查除权除息（协议 Type=0x000f）
    tdxdata-qx xdxr 001225 --all        全部类别（含股本变化/送配股上市等）
    tdxdata-qx gbbq                     下载整表权息表（HTTP）+ 摘要
    tdxdata-qx gbbq --path ./gbbq --code 600519     读本地文件并列出该股事件
    tdxdata-qx adjust 600519 -n 20      近 20 根日线：原始 / 前复权 / 后复权对照

注意：复权用**仿射口径**（复权价 = A×原始价 + B，与通达信桌面端逐分对齐），
成交量额不复权。
"""
import argparse
import json
import sys

from .adjust import factors, round_half_up
from .client import TdxClient


def _print_events(events, code):
    if not events:
        print(f'{code}: 无记录')
        return
    print(f'{code}: {len(events)} 条')
    print('  日期        类别        分红(每10股)  配股价     送转(每10股) 配股(每10股)')
    for e in events:
        print(f"  {e['date']}  {e.get('category_name', ''):<10s} "
              f"{e.get('fenhong', 0):>10.4f}  {e.get('peigujia', 0):>8.4f}  "
              f"{e.get('songzhuangu', 0):>10.4f}  {e.get('peigu', 0):>10.4f}")


def cmd_xdxr(a):
    c = TdxClient(a.host)
    c.connect()
    try:
        ev = c.xdxr(a.code, None if a.market is None else a.market,
                    None if a.all else 1)
    finally:
        c.close()
    if a.json:
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 0
    _print_events(ev, a.code)
    return 0


def cmd_gbbq(a):
    from .gbbq import decrypt_records, download_gbbq, events_of, read_gbbq
    if a.path:
        recs = read_gbbq(a.path, cache_dir=a.cache_dir)
        src = a.path
    else:
        data = download_gbbq(dest=a.out, url=a.url)['gbbq']
        recs = decrypt_records(data)
        src = f'{a.url}（{len(data):,d} B）'
    ev = [r for r in recs if r['category'] == 1]
    print(f'来源: {src}')
    print(f'记录 {len(recs):,d} · 除权除息 {len(ev):,d} · 股票 {len({r["code"] for r in recs}):,d} '
          f'· 最新事件日 {max(r["date"] for r in ev) if ev else "-"}')
    if a.code:
        _print_events(events_of(recs, a.code), a.code)
    if a.out and not a.path:
        print(f'已解出到 {a.out}/gbbq')
    return 0


def cmd_adjust(a):
    c = TdxClient(a.host)
    c.connect()
    try:
        bars = c.bars(9, a.code, 0, a.count, None if a.market is None else a.market)
        ev = c.xdxr(a.code, None if a.market is None else a.market)
    finally:
        c.close()
    if not bars:
        print(f'{a.code}: 无 K 线')
        return 1
    dates = [int(b['datetime'][:10].replace('-', '')) for b in bars]
    fs = factors(ev, dates)
    print(f'{a.code} 近 {len(bars)} 根日线（复权=仿射口径，成交量不复权）'
          f'｜可用事件 {len(ev)} 条')
    print('  日期        原始收盘   前复权    后复权   QFQ(A,B)                 HFQ(A,B)')
    for b, f in zip(bars, fs, strict=True):
        raw = b['close']
        q = round_half_up(f['qfq_mul'] * raw + f['qfq_add'])
        h = round_half_up(f['hfq_mul'] * raw + f['hfq_add'])
        print(f"  {b['datetime'][:10]}  {raw:>9.3f}  {q:>8.2f}  {h:>8.2f}   "
              f"({f['qfq_mul']:.6f},{f['qfq_add']:+.4f})      "
              f"({f['hfq_mul']:.6f},{f['hfq_add']:+.4f})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='tdxdata-qx', description='权息（除权除息）与复权')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('xdxr', help='按个股查除权除息（协议，免客户端）')
    p1.add_argument('code')
    p1.add_argument('--host', default=None)
    p1.add_argument('--market', type=int, default=None, help='0=深 1=沪（默认自动）')
    p1.add_argument('--all', action='store_true', help='全部类别（默认只除权除息）')
    p1.add_argument('--json', action='store_true')
    p1.set_defaults(func=cmd_xdxr)

    p2 = sub.add_parser('gbbq', help='整表权息表：HTTP 下载 / 读本地文件')
    p2.add_argument('--url', default=None)
    p2.add_argument('--path', default=None, help='本地 gbbq 文件（不填=HTTP 下载）')
    p2.add_argument('--out', default=None, help='解出目录（HTTP 模式）')
    p2.add_argument('--cache-dir', default=None)
    p2.add_argument('--code', default=None, help='顺带列出该股事件')
    p2.set_defaults(func=cmd_gbbq)

    p3 = sub.add_parser('adjust', help='K 线复权（前/后，仿射口径）')
    p3.add_argument('code')
    p3.add_argument('-n', '--count', type=int, default=20)
    p3.add_argument('--host', default=None)
    p3.add_argument('--market', type=int, default=None)
    p3.set_defaults(func=cmd_adjust)

    a = ap.parse_args(argv)
    if getattr(a, 'host', None) is None:
        a.host = '101.35.121.35'
    if getattr(a, 'url', None) is None and hasattr(a, 'url'):
        from .gbbq import GBBQ_URL
        a.url = GBBQ_URL
    try:
        return a.func(a)
    except (OSError, ValueError) as e:
        # 网络不通 / 数据源改版 / 参数问题 → 一行可读错误（原来是裸 traceback，像崩了）。
        # 其他异常照旧抛出（真 bug 要看得见）。
        print(f'错误: {type(e).__name__}: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
