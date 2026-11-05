# -*- coding: utf-8 -*-
"""bars 指数/周期回归测试（真实服务器取数 + 东方财富行情锚点断言）。

运行:
    python tests/test_bars_index.py          # 直接跑（无需 pytest）
    python -m pytest tests/test_bars_index.py -q

断言依据（2026-11-06 实测，与东方财富 push2his 行情接口逐字段交叉校验）:
    根因: 指数 K 线记录比个股多 4B 尾部 [上涨家数 u16][下跌家数 u16]，
          且 vol 单位不对称（指数日线=万股、个股日线=手，cat4 又相反）。
          旧版按个股 8B 尾部切指数响应 → 999999 首根对、其余全错。
锚点（东方财富，历史数据静态不变）:
    上证指数 2026-10-30: O3605.65 C3599.02 H3660.21 L3595.26
                         vol 497,973,940手 amt 764,227,190,864.5 涨455/跌1855
    上证指数 2026-11-05: O3646.57 C3689.91 H3701.59 L3646.57
                         vol 571,291,638手 amt 979,711,778,222 涨1965/跌347
    贵州茅台 2026-10-30: O1363.00 C1392.05 H1393.37 L1352.98 vol 59927手 amt 8,257,381,778
    深证成指 2026-11-05: O11216.81 C11471.09 H11613.40 L11215.48 vol 672,558,794手
    茅台 2026-10-30 当周周线: O1325.40 C1392.05 H1393.37 L1322.60 vol 221,993手
    茅台 2026-09 月线收盘: 1258.62（=9-30 日线收盘，东财周线接口同值）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tdxdata.client import TdxClient, is_index_code

HOST = os.environ.get('TDX_HOST', '101.35.121.35')

SZ_SH_1030 = {'open': 3605.65, 'close': 3599.02, 'high': 3660.21, 'low': 3595.26,
              'vol': 497973940, 'amount': 764227190864.5}
SZ_SH_1105 = {'open': 3646.57, 'close': 3689.91, 'high': 3701.59, 'low': 3646.57,
              'vol': 571291638, 'amount': 979711778222.0}
MT_1030 = {'open': 1363.00, 'close': 1392.05, 'high': 1393.37, 'low': 1352.98,
           'vol': 59927, 'amount': 8257381778.0}
SZCZ_1105 = {'open': 11216.81, 'close': 11471.09, 'high': 11613.40, 'low': 11215.48,
             'vol': 672558794, 'amount': 1138241322280.09}
MT_WEEK_1030 = {'open': 1325.40, 'close': 1392.05, 'high': 1393.37, 'low': 1322.60,
                'vol': 221993, 'amount': 30043773039.0}


def _client():
    c = TdxClient(HOST)
    c.connect()
    return c


def _find(bars, date, label):
    for b in bars:
        if b['datetime'].startswith(date):
            return b
    raise AssertionError(f'{label}: 未找到 {date} 的K线（共 {len(bars)} 根）')


def _assert_bar(b, ref, label):
    for k, want in ref.items():
        got = b[k]
        tol = 0.011 if k in ('open', 'close', 'high', 'low') else max(300.0, abs(want) * 2e-6)
        assert abs(got - want) <= tol, f'{label}.{k}: got={got} want={want}'


def test_is_index_code():
    assert is_index_code(1, '999999') is True
    assert is_index_code(1, '000001') is True    # 上证指数
    assert is_index_code(0, '000001') is False   # 平安银行
    assert is_index_code(0, '399001') is True
    assert is_index_code(1, '000300') is True
    assert is_index_code(1, '880001') is True
    assert is_index_code(1, '881101') is True    # 板块指数 881 段
    assert is_index_code(1, '600519') is False
    assert is_index_code(1, '510300') is False


def test_market_of_plate_index():
    """板块指数 88 段自动路由沪市（market_of 曾只认 5/6/9 前缀）"""
    from tdxdata.client import market_of
    assert market_of('880823') == 1
    assert market_of('881101') == 1
    assert market_of('600519') == 1
    assert market_of('510300') == 1
    assert market_of('000001') == 0
    assert market_of('399001') == 0


def test_market_of_bj():
    """北交所路由 market=2（2026-11-06 实测: 0/1 回空帧，m2 有数据）"""
    from tdxdata.client import market_of
    assert market_of('920021') == 2
    assert market_of('821001') == 2
    assert market_of('899050') == 2
    assert market_of('999999') == 1   # 9 开头其余归沪: 上证指数别名/B股
    assert market_of('900901') == 1
    assert is_index_code(2, '899050') is True
    assert is_index_code(2, '920021') is False


def test_bj_bars_920021_899050():
    """北交所日线: 920 股票走个股布局、899 指数走 12B 尾部，均不带 market 自动路由
    锚点: 东方财富 2026-11-06 逐字段交叉验证（历史静态）"""
    c = _client()
    try:
        bars = c.bars(9, '920021', 0, 10)   # 不带 market
        b = _find(bars, '2026-10-30', '920021日线')
        _assert_bar(b, {'open': 7.60, 'close': 7.31, 'high': 7.88, 'low': 7.27,
                        'vol': 221179, 'amount': 167887264.0}, '920021 10-30')
        b = _find(bars, '2026-11-05', '920021日线')
        _assert_bar(b, {'open': 8.52, 'close': 8.96, 'high': 9.34, 'low': 8.50,
                        'vol': 590308, 'amount': 527396224.0}, '920021 11-05')
        bars = c.bars(9, '899050', 0, 10)   # 北证50, 不带 market
        b = _find(bars, '2026-11-05', '899050日线')
        _assert_bar(b, {'open': 880.47, 'close': 910.07, 'high': 922.84, 'low': 880.47,
                        'vol': 9463300, 'amount': 17372520448.0}, '899050 11-05')
        assert (b['up_count'], b['down_count']) == (331, 21)   # 全北交所涨跌家数
    finally:
        c.close()


def test_plate_index_880823():
    """板块指数: 不带 market 自动路由（修复前返回空列表）
    锚点: 2026-11-06 实测,历史数据静态;amt/vol/100≈板块平均股价(元/股)交叉验证"""
    c = _client()
    try:
        bars = c.bars(9, '880823', 0, 10)   # 不带 market —— market_of 须识别为沪市
        assert len(bars) == 10, f'应返回10根, got {len(bars)}'
        for b in bars:
            assert b['high'] >= max(b['open'], b['close']), b['datetime']
            assert b['low'] <= min(b['open'], b['close']), b['datetime']
            assert b['up_count'] >= 0 and b['down_count'] >= 0
        b = _find(bars, '2026-10-30', '880823日线')
        assert abs(b['close'] - 6233.16) <= 0.011, f'10-30收盘 got={b["close"]}'
        assert (b['up_count'], b['down_count']) == (15, 385)
        b = _find(bars, '2026-11-05', '880823日线')
        assert abs(b['close'] - 6602.76) <= 0.011, f'11-05收盘 got={b["close"]}'
        assert (b['up_count'], b['down_count']) == (392, 7)
    finally:
        c.close()


def test_index_daily_999999():
    """用户报错场景: 指数日线 100 根全链解析 + 涨跌家数"""
    c = _client()
    try:
        bars = c.bars(9, '999999', 0, 100)
        assert len(bars) == 100, f'应返回100根, got {len(bars)}'
        b = _find(bars, '2026-10-30', '999999日线')
        _assert_bar(b, SZ_SH_1030, '999999 10-30')
        assert (b['up_count'], b['down_count']) == (455, 1855)
        b = _find(bars, '2026-11-05', '999999日线')
        _assert_bar(b, SZ_SH_1105, '999999 11-05')
        assert (b['up_count'], b['down_count']) == (1965, 347)
    finally:
        c.close()


def test_index_daily_000001_sh():
    """上证指数真代码（market=1 的 000001, 与平安银行区分）"""
    c = _client()
    try:
        bars = c.bars(9, '000001', 0, 50, market=1)
        b = _find(bars, '2026-11-05', '000001+1日线')
        _assert_bar(b, SZ_SH_1105, '000001+1 11-05')
    finally:
        c.close()


def test_index_daily_399001_sz():
    """深市指数路径: 399001 深证成指"""
    c = _client()
    try:
        bars = c.bars(9, '399001', 0, 100)
        b = _find(bars, '2026-11-05', '399001日线')
        _assert_bar(b, SZCZ_1105, '399001 11-05')
        assert 1000 <= b['up_count'] + b['down_count'] <= 8000
    finally:
        c.close()


def test_stock_daily_regression_600519():
    """个股日线回归: 布局/单位不受指数修复影响"""
    c = _client()
    try:
        bars = c.bars(9, '600519', 0, 100)
        b = _find(bars, '2026-10-30', '600519日线')
        _assert_bar(b, MT_1030, '600519 10-30')
    finally:
        c.close()


def test_weekly_monthly_600519():
    """周期映射实测: 5=周线 6=月线（旧文档 6=周/7=月 有误）"""
    c = _client()
    try:
        week = c.bars(5, '600519', 0, 10)
        _assert_bar(_find(week, '2026-10-30', '600519周线'), MT_WEEK_1030, '茅台周线 10-30当周')
        month = c.bars(6, '600519', 0, 10)
        b = _find(month, '2026-09-30', '600519月线')
        assert abs(b['close'] - 1258.62) <= 0.011, f'9月月线收盘 got={b["close"]}'
    finally:
        c.close()


def test_cat4_vol_unit():
    """cat4 日线变体的不对称 vol 单位: 个股=股(÷100), 指数=手(原样)"""
    c = _client()
    try:
        b = _find(c.bars(4, '600519', 0, 30), '2026-10-30', '600519 cat4')
        _assert_bar(b, MT_1030, '600519 cat4 10-30')
        b = _find(c.bars(4, '999999', 0, 30), '2026-10-30', '999999 cat4')
        _assert_bar(b, SZ_SH_1030, '999999 cat4 10-30')
    finally:
        c.close()


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f'PASS {fn.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL {fn.__name__}: {e}')
    sys.exit(1 if failed else 0)
