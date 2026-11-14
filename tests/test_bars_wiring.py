# -*- coding: utf-8 -*-
"""bars() 分页接线离线测试 —— count>800 自动分页、count<=800 单次、首块空帧短路。

不碰 socket / 网络：monkeypatch ``TdxClient._req`` 解码 payload 里的 (start,count)
并返回 >18 字节假帧；monkeypatch ``tdxdata.client.parse_bars_response`` 按最近一次
记录的偏移生成记录（datetime 唯一、可排序）。纯离线可跑。

跑法：
    PYTHONPATH=src python -m pytest tests/test_bars_wiring.py -q
"""
import struct
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import tdxdata.client as client_mod  # noqa: E402
from tdxdata.client import TdxClient  # noqa: E402

BASE = date(2026, 11, 13)


def dt_of(i: int) -> str:
    """第 i 根（i=0 最新）的 datetime 串；i 越大越早，保证唯一且可排序。"""
    return f'{BASE - timedelta(days=i)} 15:00'


class FakeReq:
    """monkeypatch ``TdxClient._req``：解码 payload 里的 (start,count)，记录并返回假帧。"""

    def __init__(self, empty: bool = False):
        self.calls = []          # list[(start, count)]
        self.empty = empty       # True 时返回 <=18 字节短帧

    def __call__(self, payload: bytes, secs: float = 3.0) -> bytes:
        vals = struct.unpack("<HIHHHH6sHHHHIIH", payload)
        start, count = vals[9], vals[10]
        self.calls.append((start, count))
        if self.empty:
            return b'\x00' * 16           # 短帧 → bars() 应返回 []
        return b'\x01' * 19               # >18 字节，且不含 78 9c，不触发解压


def make_fake_parse(req: FakeReq):
    """按最近一次 _req 记录的 (start,count) 生成对应条数的记录。"""

    def fake_parse(body: bytes, category: int):
        start, count = req.calls[-1]
        return [{'datetime': dt_of(start + j), 'i': start + j} for j in range(count)]

    return fake_parse


def make_client(monkeypatch, req: FakeReq) -> TdxClient:
    monkeypatch.setattr(TdxClient, '_req', req)
    monkeypatch.setattr(client_mod, 'parse_bars_response', make_fake_parse(req))
    return TdxClient()


def test_count_100_single_request_start_zero(monkeypatch):
    """count=100 <= 800：只请求 1 次 start=0，走原单次路径。"""
    req = FakeReq()
    c = make_client(monkeypatch, req)
    out = c.bars(9, '880867', 0, 100)
    assert req.calls == [(0, 100)], req.calls
    assert len(out) == 100


def test_count_2400_three_pages_ascending_unique(monkeypatch):
    """count=2400 > 800：请求 3 次 start=0/800/1600，返回 2400 条唯一且升序。"""
    req = FakeReq()
    c = make_client(monkeypatch, req)
    out = c.bars(9, '880867', 0, 2400)
    print('count=2400 记录到的 start 偏移:', [s for s, _ in req.calls])
    assert req.calls == [(0, 800), (800, 800), (1600, 800)], req.calls
    assert len(out) == 2400
    dts = [r['datetime'] for r in out]
    assert len(set(dts)) == 2400, '返回应唯一'
    assert dts == sorted(dts), '返回应升序'


def test_count_2400_first_block_empty_returns_empty(monkeypatch):
    """count>800 但首块空帧：bars() 直接返回 []，不继续翻页。"""
    req = FakeReq(empty=True)
    c = make_client(monkeypatch, req)
    out = c.bars(9, '880867', 0, 2400)
    assert out == []
    assert req.calls == [(0, 800)], req.calls


def test_count_100_empty_frame_returns_empty(monkeypatch):
    """count<=800 短帧：保持原行为，返回 []。"""
    req = FakeReq(empty=True)
    c = make_client(monkeypatch, req)
    out = c.bars(9, '880867', 0, 100)
    assert out == []
    assert req.calls == [(0, 100)], req.calls


if __name__ == '__main__':
    print('该文件用 pytest 运行：PYTHONPATH=src python -m pytest tests/test_bars_wiring.py -q')
