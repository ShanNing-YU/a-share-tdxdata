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
    assert GBBQ_URL.startswith('https://www.tdx.com.cn/'), GBBQ_URL   # 2026-11-13 起默认 https
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


def test_bad_input_raises_valueerror():
    """空/过短数据要给可读的 ValueError，不能抛裸 struct.error（公开包的健壮性要求）"""
    from tdxdata.gbbq import decrypt_records
    for bad in (b'', b'\x00', b'\x00\x00\x00'):
        try:
            decrypt_records(bad)
        except ValueError as e:
            assert 'gbbq' in str(e)
        except Exception as e:
            raise AssertionError(
                f'{len(bad)} 字节输入应抛 ValueError，实际 {type(e).__name__}: {e}') from e
        else:
            raise AssertionError(f'{len(bad)} 字节输入应抛 ValueError')


def test_truncated_and_cache(tmp=None):
    """截断文件只解出实际条数；缓存命中结果一致；缓存损坏时回退完整解密"""
    import struct
    import tempfile
    from pathlib import Path
    from tdxdata.gbbq import read_gbbq
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'trunc'
        p.write_bytes(struct.pack('<I', 100) + b'\x00' * 58)      # 声明 100 条，实际 2 条
        r1 = read_gbbq(p, cache_dir=td, use_cache=False)
        assert len(r1) == 2, len(r1)
        r2 = read_gbbq(p, cache_dir=td)                           # 写缓存
        assert len(r2) == len(r1)
        r3 = read_gbbq(p, cache_dir=td)                           # 命中缓存
        assert len(r3) == len(r2)
        # 把缓存写坏 → 必须回退完整解密而不是崩
        for cf in Path(td).glob('gbbq_*.bin'):
            cf.write_bytes(b'\x01\x02')
        r4 = read_gbbq(p, cache_dir=td)
        assert len(r4) == len(r1), f'缓存损坏后应回退，得到 {len(r4)}'


def test_extract_members_errors():
    """官方包缺 gbbq / 不是 zip → 可读的 ValueError（不是裸 KeyError/BadZipFile）"""
    import io
    import zipfile
    from tdxdata.gbbq import _extract_members
    try:
        _extract_members(b'not a zip')
        raise AssertionError('非 zip 应抛 ValueError')
    except ValueError as e:
        assert 'zip' in str(e)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('other.txt', b'x')
    try:
        _extract_members(buf.getvalue())
        raise AssertionError('缺 gbbq 应抛 ValueError')
    except ValueError as e:
        assert 'gbbq' in str(e)


def test_cache_pruning():
    """缓存按来源只留最近 3 份（权息表每版约 5MB，不清理会持续累积）"""
    import struct
    import tempfile
    from pathlib import Path
    from tdxdata.gbbq import read_gbbq
    with tempfile.TemporaryDirectory() as td:
        for n in range(5):                                     # 造 5 个「不同版本」
            f = Path(td) / f'v{n}'
            f.write_bytes(struct.pack('<I', n + 1) + b'\x00' * ((n + 1) * 29))
            read_gbbq(f, cache_dir=Path(td) / 'cache')          # case 的 tag=n 文件名 → 每版一个 tag
        caches = list((Path(td) / 'cache').glob('gbbq_*.bin'))
        assert len(caches) <= 5, len(caches)                   # 不同 tag 各自保留即可
        # 同一 tag 连写 5 版 → 只留 3
        for k in range(5):
            f2 = Path(td) / 'same'
            f2.write_bytes(struct.pack('<I', k + 1) + b'\x00' * ((k + 1) * 29))
            read_gbbq(f2, cache_dir=Path(td) / 'cache2')
        same = list((Path(td) / 'cache2').glob('gbbq_same_*.bin'))
        assert len(same) <= 3, f'同源缓存应只留 3 份，实际 {len(same)}'


if __name__ == '__main__':
    test_url_and_size()
    test_decrypt_record_fixtures()
    test_selection_helpers()
    test_bad_input_raises_valueerror()
    test_truncated_and_cache()
    test_extract_members_errors()
    test_cache_pruning()
    print('test_gbbq: 全部通过 ✅')
