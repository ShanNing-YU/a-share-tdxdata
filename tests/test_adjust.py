# -*- coding: utf-8 -*-
"""复权（仿射）离线测试 —— 场景取自真实事件（001225 送转 / 600519 派现）

跑法：python tests/test_adjust.py   或   pytest tests/test_adjust.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.adjust import (adjust_bars, adjust_prices, affine_coeffs,   # noqa: E402
                            factors, round_half_up)


def ev(date, fh=0.0, pgj=0.0, sg=0.0, pg=0.0, cat=1):
    return {'date': date, 'category': cat, 'fenhong': fh, 'peigujia': pgj,
            'songzhuangu': sg, 'peigu': pg}


def test_round_half_up():
    assert round_half_up(1.005) == 1.01          # 银行家舍入会给 1.0
    assert round_half_up(2.675) == 2.68
    assert round_half_up(-1.005) == -1.01
    assert round_half_up(33.5643) == 33.56


def test_affine_coeffs():
    m, c = affine_coeffs(ev(20260626, fh=280.2423))          # 纯派现
    assert abs(m - 1.0) < 1e-12 and abs(c - 28.02423) < 1e-6
    m, c = affine_coeffs(ev(20260923, sg=4.0))               # 纯送转
    assert abs(m - 1.4) < 1e-12 and abs(c) < 1e-12
    m, c = affine_coeffs(ev(20261013, fh=15.0, sg=4.0))      # 分红 + 送转
    assert abs(m - 1.4) < 1e-12 and abs(c - 1.5) < 1e-12
    m, c = affine_coeffs(ev(20250101, sg=2.0, pg=3.0, pgj=5.0))   # 送转 + 配股（现金流入）
    assert abs(m - 1.5) < 1e-12 and abs(c + 1.5) < 1e-12


def test_qfq_songzhuan():
    """001225：2026-09-23 送转 4.0（比值 1.4）→ 之前的价格整体 ÷1.4"""
    events = [ev(20260923, sg=4.0)]
    dates = [20260922, 20260923, 20260924]
    px = adjust_prices([46.99, 50.92, 33.01], dates, events, 'qfq')
    assert px == [33.56, 50.92, 33.01], px
    fs = factors(events, dates)
    assert abs(fs[0]['qfq_mul'] - 1 / 1.4) < 1e-12
    assert abs(fs[1]['qfq_add']) < 1e-12        # 纯送转无加法项


def test_qfq_cash_dividend_is_affine():
    """600519：2026-06-26 派 28.02423 元/股 → 之前的价格**减去**该金额（不是按比例缩放）"""
    events = [ev(20260626, fh=280.2423)]
    dates = [20260625, 20260626]
    px = adjust_prices([1450.0, 1400.0], dates, events, 'qfq')
    assert px[0] == 1421.98, px                  # 1450 − 28.02423
    assert px[1] == 1400.0, px
    fs = factors(events, dates)
    assert abs(fs[0]['qfq_mul'] - 1.0) < 1e-12 and abs(fs[0]['qfq_add'] + 28.02423) < 1e-6


def test_future_event_dropped():
    """已公告未生效（ex-day 晚于最新交易日）必须丢弃，否则全历史被平移"""
    events = [ev(20261231, fh=10.0)]
    dates = [20261112, 20261113]
    fs = factors(events, dates)
    assert all(abs(f['qfq_add']) < 1e-12 and abs(f['qfq_mul'] - 1) < 1e-12 for f in fs), fs


def test_suspension_gap_applies_both_events():
    """停牌缺口内的多个事件必须**全部**复合（按日期位置施加，不要求命中交易日）"""
    events = [ev(20260601, sg=1.0), ev(20260602, sg=1.0)]     # 两天都不在交易日序列里
    dates = [20260530, 20260603]
    fs = factors(events, dates)
    assert abs(fs[0]['qfq_mul'] - 1 / 1.21) < 1e-12, fs[0]
    assert abs(fs[1]['qfq_mul'] - 1.0) < 1e-12, fs[1]


def test_hfq_anchor():
    """后复权锚定最早交易日：最早日 = 原价，其余按比例放大"""
    events = [ev(20260923, sg=4.0)]
    dates = [20260922, 20260923, 20260924]
    px = adjust_prices([46.99, 50.92, 33.01], dates, events, 'hfq')
    assert px[0] == 46.99, px
    assert px[1] == 71.29, px                    # 50.92 × 1.4
    assert px[2] == 46.21, px                    # 33.01 × 1.4


def test_adjust_bars_and_none():
    bars = [
        {'datetime': '2026-09-22 00:00', 'open': 46.0, 'close': 46.99,
         'high': 47.5, 'low': 45.8, 'vol': 12345.0},
        {'datetime': '2026-09-23 00:00', 'open': 33.0, 'close': 33.01,
         'high': 33.5, 'low': 32.8, 'vol': 999.0},
    ]
    out = adjust_bars(bars, [ev(20260923, sg=4.0)], 'qfq')
    assert out[0]['close'] == 33.56 and out[0]['open'] == round(46.0 / 1.4, 2)
    assert out[1]['close'] == 33.01
    assert out[0]['vol'] == 12345.0              # 成交量不复权
    assert bars[0]['close'] == 46.99             # 原列表不被修改
    same = adjust_bars(bars, [ev(20260923, sg=4.0)], 'none')
    assert [b['close'] for b in same] == [46.99, 33.01]


def test_input_validation():
    try:
        factors([], [20260102, 20260101])
    except ValueError:
        pass
    else:
        raise AssertionError('未按升序应报错')
    try:
        adjust_prices([1.0], [20260101], [], 'bad-mode')
    except ValueError:
        pass
    else:
        raise AssertionError('非法 mode 应报错')
    assert factors([], []) == []


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
    print('test_adjust: 全部通过 ✅')
