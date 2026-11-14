# -*- coding: utf-8 -*-
"""market_of / pool2._market_for 离线回归 —— 880xxx 板块指数属沪市(market=1)。

回归 issue #5 剩下一半：880xxx 之前被 market_of 判成深市(market=0)，
导致 snap() 恒 ok=False。纯离线，无 socket/网络。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.client import TdxClient, market_of      # noqa: E402
from tdxdata.pool2 import _market_for                 # noqa: E402

SH_CASES = ['880867', '880556', '880860', '600519', '510300', '900901']
SZ_CASES = ['000001', '002905', '300750', '159915']


def test_market_of_sh():
    for code in SH_CASES:
        assert market_of(code) == 1, code


def test_market_of_sz():
    for code in SZ_CASES:
        assert market_of(code) == 0, code


def test_pool_market_for():
    assert _market_for('880867') == 1
    assert _market_for('000001') == 0
    assert _market_for('880860') == 1


def test_snap_request_market_byte(monkeypatch):
    """snap('880867') 请求里 market 字节必须=1（SNAP_PREFIX 12 字节，payload[12]=market）。"""
    captured = {}

    def fake_req(self, payload, secs=3.0):
        captured['payload'] = payload
        return b''

    monkeypatch.setattr(TdxClient, '_req', fake_req)
    c = TdxClient()
    c.snap('880867')                      # market=None → market_of('880867')=1
    assert captured['payload'][12] == 1

    c.snap('000001')                      # 深市对照 → 0
    assert captured['payload'][12] == 0


if __name__ == '__main__':
    test_market_of_sh()
    test_market_of_sz()
    test_pool_market_for()
    print('test_market_of: 全部通过 ✅')
