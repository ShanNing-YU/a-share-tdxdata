# -*- coding: utf-8 -*-
"""quotes 批量回归测试 —— 3 只/4 只曾因 `num_stock not in (1, 2, 5)` 白名单恒返回 []

夹具为 2026-11-14 实录（主站 101.35.121.35）：一次请求 600519 + 000001 + 300750 的原始
响应 261B，服务端回声 `num_stock=3`。

跑法：python tests/test_quotes_batch.py   或   pytest tests/test_quotes_batch.py
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.client import maybe_decompress                          # noqa: E402
from tdxdata.commands.quotes import build_quotes_req, parse_quotes   # noqa: E402

# [(1,'600519'), (0,'000001'), (0,'300750')] 的真实响应（261B）
FIXTURE_3 = (
    'b1cb74000c01206300003e05f500f50001040300013630303531392f11a6c211c327f630b303de409f95ba0ee6'
    'c211b38c05ad1bc777b14f9a98029af40200a8da195a0001026e0101037a0c0106c201170109c7011801091615'
    '0000000024002f11003030303030315012b7125c5f03658aabcf0ef712b5a18b02b9d8016b6e1c4f93946fa38d'
    '9c01008efc054100a81891724201ad2580b30243029422ab89034403a91b96e00545048b17a4b0019618000000'
    '001900501200333030373530a5129af302a603a6039407e801a7cacc0e84ba0292fe24bf4b0ce5d74f9fc012'
    'b4bd120090f66500010001410201094603042d4704020b4a0515041616000000001200a512'
)


def test_build_req_shape_for_three():
    f = build_quotes_req([(1, '600519'), (0, '000001'), (0, '300750')])
    # 帧头 22B + 每只 7B
    assert len(f) == 22 + 3 * 7, len(f)
    (num,) = struct.unpack('<H', f[20:22])
    assert num == 3, num


def test_parse_three_stocks():
    raw = bytes.fromhex(FIXTURE_3)
    assert raw[18:20] == b'\x03\x00', '夹具必须回声 num_stock=3'
    recs = parse_quotes(maybe_decompress(raw))
    assert len(recs) == 3, f'3 只批量曾恒返回 []: 实际 {len(recs)}'
    assert [r['code'] for r in recs] == ['600519', '000001', '300750']
    by = {r['code']: r for r in recs}
    # 2026-11-13 收盘，已与腾讯行情 qt.gtimg.cn 逐字段核对
    assert abs(by['600519']['price'] - 1435.26) < 1e-6, by['600519']['price']
    assert abs(by['600519']['last_close'] - 1410.27) < 1e-6
    assert abs(by['600519']['open'] - 1404.0) < 1e-6
    assert abs(by['600519']['high'] - 1437.69) < 1e-6
    assert abs(by['600519']['low'] - 1394.0) < 1e-6
    assert abs(by['000001']['price'] - 12.07) < 1e-6, by['000001']['price']
    assert abs(by['300750']['price'] - 237.7) < 1e-6, by['300750']['price']
    # 五档不能因为错位而空
    for r in recs:
        assert len(r['bid']) == 5 and len(r['ask']) == 5, r['code']
        assert all(v > 0 for v in r['bid'][:1]), (r['code'], r['bid'])


def test_garbage_frame_returns_empty_without_crashing():
    """坏帧不能被顺手改成抛异常"""
    assert parse_quotes(b'') == []
    assert parse_quotes(b'\x00' * 40) == []
    assert parse_quotes(maybe_decompress(bytes.fromhex(FIXTURE_3)[:20])) == []


if __name__ == '__main__':
    test_build_req_shape_for_three()
    test_parse_three_stocks()
    test_garbage_frame_returns_empty_without_crashing()
    print('test_quotes_batch: 全部通过 ✅')
