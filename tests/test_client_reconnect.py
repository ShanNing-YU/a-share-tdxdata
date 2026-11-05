# -*- coding: utf-8 -*-
"""客户端连接层回归: 快速认证 + 断线自动重连。

运行:
    python tests/test_client_reconnect.py     # 直接跑（无需 pytest）
    python -m pytest tests/test_client_reconnect.py -q

断言依据（2026-11-06 实测）:
    - 认证回包 ~70ms 单包收完，connect 全程 ~1.3s
      （旧版每次 _recv 尾等固定 4s socket 超时，connect ~8.2s）
    - 服务器会断开空闲连接；连接死后 bars 曾静默返回 [] —— 现自动重连重试一次，
      重试仍失败则抛 ConnectionError（不再静默吞掉）
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tdxdata.client import TdxClient

HOST = os.environ.get('TDX_HOST', '101.35.121.35')


def test_connect_fast():
    """connect 全程 < 5s（旧实现 ~8.2s: 回包收完后尾等满 4s socket 超时）"""
    c = TdxClient(HOST)
    t0 = time.time()
    c.connect()
    dt = time.time() - t0
    c.close()
    assert dt < 5.0, f'connect 耗时 {dt:.2f}s，应 < 5s'


def test_reconnect_after_server_drop():
    """模拟服务器断连（直接关掉底层 socket）: bars 自动重连返回数据，而非静默空列表"""
    c = TdxClient(HOST)
    c.connect()
    try:
        assert c.bars(9, '600519', 0, 3)      # 预热
        c.sock.close()                        # 背后杀连接
        bars = c.bars(9, '600519', 0, 3)
        assert len(bars) == 3, f'断连后应自动重连取到数据, got {len(bars)}'
    finally:
        c.close()


def test_request_after_close():
    """close() 后再请求 → 自动重连（幂等）"""
    c = TdxClient(HOST)
    c.connect()
    c.close()
    bars = c.bars(9, '000059', 0, 3)
    assert len(bars) == 3
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
