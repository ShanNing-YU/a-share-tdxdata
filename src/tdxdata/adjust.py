# -*- coding: utf-8 -*-
"""前/后复权（与通达信桌面端对齐口径，2026-11-13）

数学口径
--------
单个 `category=1`（除权除息）事件的**仿射系数**：
    m = (10 + 送转 + 配股) / 10          乘法因子（送股/转增/配股）
    c = (分红 − 配股 × 配股价) / 10       每股净现金流出
复权价（不是纯比例缩放，**带加法项**）：
    复权价 = round_half_up(A × 原始价 + B)

前复权（锚定最新交易日 A=1, B=0，自今向过去回溯；遇 ex-day **严格晚于**当日则施加）：
    a = a / m ;  b = b − a × c
后复权（由最早交易日的 QFQ 系数 (a0,b0) 锚定）：
    hfq = (a / a0) × raw + (b − b0) / a0

三个已记录的口径坑（照抄结论，勿再踩）
--------------------------------------
1. **纯比例口径在有现金分红时会系统性偏离通达信** → 必须用仿射（带加法项）；
2. 事件按**日期位置**施加，不能按「ex-day 是否命中交易日」——停牌（股改/大比例转增连续
   停牌）会让该日不在 K 线里，按命中判断会整体跳过事件，污染该日及之前全部因子；
3. **必须丢弃 ex-day 严格晚于最新交易日的「已公告未生效」分红**——否则最新日 B≠0，
   整条历史被平移一个尚未发生的分红额（实例：600887 含未来 20260626 派 9 元）。

算法口径参考 injoyai/tdx（MIT, protocol/model_gbbq.go，其结论为「与桌面端逐分对齐」），
本实现独立重写 + 单测断言（见 tests/test_adjust.py）。
"""
__all__ = ['affine_coeffs', 'round_half_up', 'factors', 'adjust_prices', 'adjust_bars']


def _as_int_date(d):
    """YYYYMMDD int / 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM' → int YYYYMMDD"""
    if isinstance(d, int):
        return d
    s = str(d).strip()
    return int(s[:10].replace('-', ''))


def round_half_up(x: float, ndigits: int = 2) -> float:
    """四舍五入（Python 内置 round 是银行家舍入，与通达信口径不同）

    用 Decimal 走**十进制**半进位：价格的二进制浮点表示会骗人
    （`1.005` 实际是 `1.00499999…`，用 floor(x*100+0.5) 会得到 1.00）。
    """
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-ndigits)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))


def affine_coeffs(event) -> tuple:
    """单个除权除息事件 → (m, c)。event 需含 fenhong / peigujia / songzhuangu / peigu"""
    fh = float(event.get('fenhong', 0) or 0)
    pgj = float(event.get('peigujia', 0) or 0)
    sg = float(event.get('songzhuangu', 0) or 0)
    pg = float(event.get('peigu', 0) or 0)
    m = (10.0 + sg + pg) / 10.0
    c = (fh - pg * pgj) / 10.0
    return (m if m else 1.0, c)


def factors(events, dates) -> list:
    """计算每个交易日的仿射复权系数

    :param events: 除权除息事件列表（`gbbq.events_of` / `commands.xdxr.xdxr_of` 的输出）
    :param dates:  交易日序列（int YYYYMMDD 或 'YYYY-MM-DD'），**需按时间升序**
    :return: [{'date','qfq_mul','qfq_add','hfq_mul','hfq_add'}]（与 dates 等长、同序）
    """
    ds = [_as_int_date(d) for d in dates]
    if not ds:
        return []
    if any(ds[i] > ds[i + 1] for i in range(len(ds) - 1)):
        raise ValueError('dates 必须按时间升序')

    latest = ds[-1]
    evs = []
    for e in events:
        if e.get('category', 1) != 1:
            continue
        d = _as_int_date(e['date'])
        if d > latest:          # 坑 3：已公告未生效，不施加
            continue
        m, c = affine_coeffs(e)
        evs.append((d, m, c))
    evs.sort(key=lambda x: x[0])            # 按 ex-day 升序

    out = [None] * len(ds)
    a, b = 1.0, 0.0
    ei = len(evs) - 1
    for i in range(len(ds) - 1, -1, -1):
        for j in range(ei, -1, -1):
            if evs[j][0] > ds[i]:          # 坑 2：按日期位置施加（不要求命中交易日）
                m, c = evs[j][1], evs[j][2]
                a = a / m
                b = b - a * c
                ei = j - 1
            else:
                break
        out[i] = {'date': ds[i], 'qfq_mul': a, 'qfq_add': b}
    # 后复权：锚定最早交易日
    a0, b0 = out[0]['qfq_mul'], out[0]['qfq_add']
    for r in out:
        if a0:
            r['hfq_mul'] = r['qfq_mul'] / a0
            r['hfq_add'] = (r['qfq_add'] - b0) / a0
        else:
            r['hfq_mul'], r['hfq_add'] = 1.0, 0.0
    return out


def adjust_prices(prices, dates, events, mode='qfq', ndigits=2) -> list:
    """按仿射系数复权一组价格（与 dates 一一对应，升序）"""
    if mode not in ('qfq', 'hfq', 'none'):
        raise ValueError("mode 只能是 'qfq' / 'hfq' / 'none'")
    if mode == 'none':
        return list(prices)
    fs = factors(events, dates)
    out = []
    for p, f in zip(prices, fs, strict=True):
        if p is None:
            out.append(None)
            continue
        mul, add = (f['qfq_mul'], f['qfq_add']) if mode == 'qfq' else (f['hfq_mul'], f['hfq_add'])
        out.append(round_half_up(mul * float(p) + add, ndigits))
    return out


def adjust_bars(bars, events, mode='qfq', price_keys=('open', 'close', 'high', 'low'),
                ndigits=2) -> list:
    """复权 K 线：bars = client.bars() 的输出（需含 datetime）→ 新列表（不改原列表）

    成交量/额**不复权**（与桌面端一致）。
    """
    if not bars:
        return []
    dates = [_as_int_date(bar.get('datetime') or bar.get('date')) for bar in bars]
    fs = factors(events, dates)
    out = []
    for bar, f in zip(bars, fs, strict=True):
        nb = dict(bar)
        if mode == 'qfq':
            mul, add = f['qfq_mul'], f['qfq_add']
        elif mode == 'hfq':
            mul, add = f['hfq_mul'], f['hfq_add']
        else:
            mul, add = 1.0, 0.0
        if mode in ('qfq', 'hfq'):
            for k in price_keys:
                if nb.get(k) is not None:
                    nb[k] = round_half_up(mul * float(nb[k]) + add, ndigits)
        nb['adjust'] = mode
        out.append(nb)
    return out
