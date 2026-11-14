# -*- coding: utf-8 -*-
"""fetch_paged 离线测试 —— 分页取数 / 去重 / 排序 / 边界行为。

假 fetch_once 用生成的 datetime 串，无 socket / 网络 / sleep，纯离线可跑。

跑法：
    python tests/test_bars_paging.py           # 直接跑（无需 pytest）
    PYTHONPATH=src python -m pytest tests/test_bars_paging.py -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tdxdata.paging import fetch_paged  # noqa: E402

BASE = date(2026, 11, 13)


def dt_of(i: int) -> str:
    """第 i 根（i=0 为最新）的 datetime 串；i 越大越早，保证唯一且可排序。"""
    return f'{BASE - timedelta(days=i)} 15:00'


class FakeFetch:
    """可控假取数器：universe 共 total 根，i=0 最新；记录每次 (start, n) 调用。"""

    def __init__(self, total: int, overlap: bool = False):
        self.total = total
        self.overlap = overlap          # True 时每块开头回吐上一块边界行（制造跨块重复）
        self.calls = []

    def __call__(self, start: int, n: int):
        self.calls.append((start, n))
        begin = start - 1 if (self.overlap and start > 0) else start
        end = begin + n                  # 固定返回 n 行；overlap 时首行=上一块尾行（跨块重复）
        rows = []
        i = begin
        while i < end and i < self.total:
            rows.append({'datetime': dt_of(i), 'i': i})
            i += 1
        return rows


def test_small_count_single_call_untouched():
    """count=700 <= 800：只调一次 fetch_once(0, 700)，且原样返回（最新在前、不升序重排）。"""
    f = FakeFetch(total=5000)
    out = fetch_paged(f, 700)
    assert f.calls == [(0, 700)], f.calls
    assert len(out) == 700
    assert out[0]['datetime'] == dt_of(0)      # 原样返回：仍最新在前
    assert out[-1]['datetime'] == dt_of(699)


def test_large_count_three_calls_unique_ascending():
    """count=2400 > 800：调 3 次 (0/800/1600, 800)，返回 2400 条唯一且升序。"""
    f = FakeFetch(total=3000)
    out = fetch_paged(f, 2400)
    assert f.calls == [(0, 800), (800, 800), (1600, 800)], f.calls
    assert len(out) == 2400
    dts = [r['datetime'] for r in out]
    assert len(set(dts)) == 2400, '返回应唯一'
    assert dts == sorted(dts), '返回应升序'


def test_fewer_than_count_returns_what_exists():
    """只剩 900 条时 count=1000：返回 900 且不抛异常。"""
    f = FakeFetch(total=900)
    out = fetch_paged(f, 1000)
    assert f.calls == [(0, 800), (800, 800)], f.calls
    assert len(out) == 900


def test_cross_block_duplicate_deduped():
    """跨块重复的边界行被去重（保留首次出现）。"""
    f = FakeFetch(total=1600, overlap=True)
    out = fetch_paged(f, 1600)
    assert f.calls == [(0, 800), (800, 800)], f.calls
    dts = [r['datetime'] for r in out]
    assert len(out) == 1599, f'1600 行含 1 条边界重复，去重后应 1599，实际 {len(out)}'
    assert len(set(dts)) == len(out), '去重后不应再有重复'
    assert dts.count(dt_of(799)) == 1, '边界行 dt_of(799) 应只保留一次'
    assert dts == sorted(dts), '返回应升序'


def test_zero_count_returns_empty_without_calling():
    """count=0：返回 [] 且 fetch_once 未被调用（count<0 同理）。"""
    f = FakeFetch(total=10)
    assert fetch_paged(f, 0) == []
    assert f.calls == [], f.calls
    g = FakeFetch(total=10)
    assert fetch_paged(g, -3) == []
    assert g.calls == []


if __name__ == '__main__':
    test_small_count_single_call_untouched()
    test_large_count_three_calls_unique_ascending()
    test_fewer_than_count_returns_what_exists()
    test_cross_block_duplicate_deduped()
    test_zero_count_returns_empty_without_calling()
    print('test_bars_paging: 全部通过 ✅')
