# -*- coding: utf-8 -*-
"""gbbq（权息表）离线测试 —— 加密记录夹具取自 2026-11-12 官方 dbf 包（HTTP 源）

跑法：python tests/test_gbbq.py   或   pytest tests/test_gbbq.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.gbbq import (GBBQ_URL, RECORD_SIZE, decrypt_record,          # noqa: E402
                          events_of, to_map)

# 001225 三条 category=1 加密记录（29B hex）+ 期望解密结果
CASES = [
    ('1f8299cce874c2ea85569cc3454c912950940abb96412e270000000000',
     0, '001225', 20230522, 1, 12.5, 0.0, 0.0, 0.0),
    ('1f8299cce874c2ea2c9288533983b59350940abb96412e270000000000',
     0, '001225', 20240422, 1, 12.5, 0.0, 0.0, 0.0),
    ('1f8299cce874c2ea973d98914eeae91250940abb96412e270000000000',
     0, '001225', 20250522, 1, 12.22, 0.0, 0.0, 0.0),
]


def test_url_and_size():
    assert GBBQ_URL.startswith('http://www.tdx.com.cn/')
    assert RECORD_SIZE == 29


def test_decrypt_record_fixtures():
    import struct
    for hexrec, market, code, date, cat, f1, f2, f3, f4 in CASES:
        rec = bytes.fromhex(hexrec)
        assert len(rec) == RECORD_SIZE
        clear = decrypt_record(rec)
        m, code_b, d, c, a1, a2, a3, a4 = struct.unpack('<B7sIBffff', clear)
        assert m == market, (m, market)
        assert code_b.rstrip(b'\x00').decode() == code
        assert d == date, (d, date)
        assert c == cat
        assert abs(a1 - f1) < 0.01, (a1, f1)
        assert abs(a2 - f2) < 1e-6 and abs(a3 - f3) < 1e-6 and abs(a4 - f4) < 1e-6


def test_selection_helpers():
    recs = [
        {'market': 0, 'code': 'A', 'date': 20250101, 'category': 1, 'fenhong': 1.0,
         'peigujia': 0, 'songzhuangu': 0, 'peigu': 0},
        {'market': 0, 'code': 'A', 'date': 20240101, 'category': 1, 'fenhong': 0.5,
         'peigujia': 0, 'songzhuangu': 0, 'peigu': 0},
        {'market': 0, 'code': 'A', 'date': 20240601, 'category': 5, 'fenhong': 0,
         'peigujia': 0, 'songzhuangu': 0, 'peigu': 0},
        {'market': 1, 'code': 'B', 'date': 20250101, 'category': 1, 'fenhong': 2.0,
         'peigujia': 0, 'songzhuangu': 0, 'peigu': 0},
    ]
    ev = events_of(recs, 'A')
    assert [r['date'] for r in ev] == [20240101, 20250101]      # 升序 + 只取 category=1
    assert len(events_of(recs, 'A', category=5)) == 1
    m = to_map(recs)
    assert set(m) == {'A', 'B'} and [r['date'] for r in m['A']] == [20240101, 20250101]


if __name__ == '__main__':
    test_url_and_size()
    test_decrypt_record_fixtures()
    test_selection_helpers()
    print('test_gbbq: 全部通过 ✅')
