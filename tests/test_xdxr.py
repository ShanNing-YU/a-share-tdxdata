# -*- coding: utf-8 -*-
"""xdxr（除权除息，Type=0x000f）离线测试 —— 夹具为 2026-11-13 活服务器实录

跑法：python tests/test_xdxr.py   或   pytest tests/test_xdxr.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.commands.xdxr import build_xdxr_req, parse_xdxr, xdxr_of   # noqa: E402
from tdxdata.frame import TYPE_GBBQ, split_response                     # noqa: E402

# 001225 实录响应（2026-11-13，主站 101.33.225.16）：178B 原始帧
FIXTURE_HEX = (
    'b1cb74001c00000000000f00a2006701789c636460303030343232e5813118fc369830b23240c161d1532e85'
    'a2a75c6192551b4d181919183c1c1990015432ee3a50274cc73291c7283ad56ee0d1b9ed2650274c07671db3'
    '2bb2ce59ff813ae55b9db1ea946334656485e900d357cfc2756e528349020541f4921767e0920ceaa68c8c22'
    'ebdc1db0197b431daa13a4a3f0f109149dd61aa620afc0408303b24e9024274c87e97c1eb765f9fc6e00538f'
    '4ce4'
)
# 实录原始帧 178B（已核对长度）
assert len(FIXTURE_HEX) == 356


def test_build_req_shape():
    f = build_xdxr_req(0, '001225')
    assert len(f) == 21, len(f)
    assert f[0] == 0x0C
    assert f[5] == 0x01
    assert f[6:10] == b'\x0b\x00\x0b\x00'
    assert f[10:12] == (TYPE_GBBQ).to_bytes(2, 'little')
    assert f[12:] == b'\x01\x00\x00' + b'001225'
    # 沪市 market=1
    assert build_xdxr_req(1, '600519')[12:] == b'\x01\x00\x01' + b'600519'


def test_parse_from_fixture():
    raw = bytes.fromhex(FIXTURE_HEX)
    typ, body = split_response(raw)
    assert typ == TYPE_GBBQ, typ
    recs = parse_xdxr(body)
    assert len(recs) == 12, len(recs)
    ev = xdxr_of(body, 1)
    assert [r['date'] for r in ev] == [20230522, 20240422, 20250522, 20260608, 20260923]
    last = ev[-1]
    assert last['code'] == '001225' and last['market'] == 0
    assert abs(last['songzhuangu'] - 4.0) < 1e-6
    assert abs(last['fenhong']) < 1e-9
    assert last['category_name'] == '除权除息'
    # 2026-06-08 是纯派现 3.12 元/10 股
    d2026 = next(r for r in ev if r['date'] == 20260608)
    assert abs(d2026['fenhong'] - 3.12) < 0.01


def test_parse_edge_cases():
    assert parse_xdxr(b'') == []
    assert parse_xdxr(b'\x00' * 8) == []
    assert xdxr_of(b'\x00' * 20, 1) == []


if __name__ == '__main__':
    test_build_req_shape()
    test_parse_from_fixture()
    test_parse_edge_cases()
    print('test_xdxr: 全部通过 ✅')
