# -*- coding: utf-8 -*-
"""snap 压缩帧回归测试 —— 夹具为 2026-11-14 收盘后活服务器实录

回归的是 0.2.13 的 bug：`parse_snap()` 在**解压前**判 `len(resp) < 60`，
把压缩后只有 50~58B、解压后 286B/62 点的正常帧全部判成 ok=False
（涨停、停牌、低波动个股最容易踩；`client.py` 与 `pool2.py` 两份拷贝都有）。

跑法：python tests/test_snap_compressed.py   或   pytest tests/test_snap_compressed.py
"""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.client import parse_snap as parse_snap_client    # noqa: E402
from tdxdata.pool2 import parse_snap as parse_snap_pool       # noqa: E402

# 002905 金逸影视（2026-11-13 涨停收 9.90）—— 压缩后仅 56B
S_002905 = (
    'b1cb74001c0900410300d10f28001e01789c6360303030b234306540038c0c6738212c5b201670b465d8212'
    '7e898962637a230001aac4a0e'
)
# 002819 东方中科（收 21.70）—— 压缩后仅 58B
S_002819 = (
    'b1cb74001c0900410300d10f2a001e01789c6360303030b230b46440038c0c6738212c5b06aeeb731d6d19'
    'ae2f5ee2386be6da118501d60a865f'
)


def test_fixture_shape():
    """夹具本身要真的是「压缩后 < 60B、解压后 286B」——否则测不到这个 bug"""
    for hexs in (S_002905, S_002819):
        raw = bytes.fromhex(hexs)
        assert len(raw) < 60, f'夹具必须是压缩小帧: {len(raw)}'
        i = raw.find(b'\x78\x9c')
        assert i >= 0, '夹具必须是 zlib 帧'
        assert i == 16, i                       # 16B 前缀 + 压缩体
        assert len(zlib.decompress(raw[i:])) == 286


def test_client_parse_compressed_small_frame():
    for hexs, code, last in ((S_002905, '002905', 9.9), (S_002819, '002819', 21.7)):
        d = parse_snap_client(bytes.fromhex(hexs))
        assert d.get('ok') is True, f'{code} 压缩帧被误判: {d}'
        assert d.get('compressed') is True
        assert d.get('code') == code
        assert len(d['prices']) == 62, len(d['prices'])
        assert abs(d['last'] - last) < 1e-6, (code, d['last'])


def test_pool_parse_compressed_small_frame():
    """Pool 走的是另一份 parse_snap 拷贝，必须同步修（这份不填 code 字段）"""
    for hexs, code, last in ((S_002905, '002905', 9.9), (S_002819, '002819', 21.7)):
        d = parse_snap_pool(bytes.fromhex(hexs))
        assert d.get('ok') is True, f'{code}（Pool 路径）压缩帧被误判: {d}'
        assert len(d['prices']) == 62, len(d['prices'])
        assert abs(d['last'] - last) < 1e-6, (code, d['last'])


def test_empty_frame_still_rejected():
    """判长保护本身不能删掉：真空帧/半帧仍要 ok=False"""
    for raw in (b'', b'\x00' * 18, bytes.fromhex('b1cb74001c0900410300d10f')):
        d = parse_snap_client(raw)
        assert d.get('ok') is False, f'空帧不该被当成有效数据: {raw[:8]!r}'
        assert d.get('last') is None


if __name__ == '__main__':
    test_fixture_shape()
    test_client_parse_compressed_small_frame()
    test_pool_parse_compressed_small_frame()
    test_empty_frame_still_rejected()
    print('test_snap_compressed: 全部通过 ✅')
