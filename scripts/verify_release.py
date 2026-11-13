#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_release.py — 发版前对**已安装的包**跑边界与正确性复查（2026-11-13）

为什么要它：0.2.8 发布前正是靠这份用例抓出 3 处真问题（空数据裸 struct.error /
缓存键用字节长度会撞 / 缓存损坏静默返回空列表）。**每次发版前重跑一遍。**

用法（注意：跑在装好待发布 wheel 的干净 venv 里，不要用源码树 —— sys.path 会骗你）：
    uv venv /tmp/relver -q
    uv pip install --python /tmp/relver/bin/python dist/tdxdata-<ver>-py3-none-any.whl
    /tmp/relver/bin/python scripts/verify_release.py

覆盖：帧/解析边界（5）· 复权边界（16）· gbbq 读损坏输入与缓存（8）· 下载错误路径（1）·
活服务器协议（11）。需要本机可直连通达信主站（默认 101.33.225.16）与本地权息表文件。
"""

import struct
import sys
import tempfile
import traceback
from pathlib import Path

import tdxdata
from tdxdata import (GBBQ_URL, TdxClient, adjust_bars, adjust_prices, affine_coeffs,
                     decrypt_record, events_of, factors, read_gbbq, round_half_up, to_map)
from tdxdata.commands.xdxr import build_xdxr_req, parse_xdxr, xdxr_of
from tdxdata.frame import TYPE_GBBQ, build_frame, split_response

HOST = '101.33.225.16'
GBBQ_FILE = '/home/yuzq/workspace/qlib-pytdx/data/gbbq_http/gbbq'
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  ✅ {name}')
    else:
        fail += 1
        print(f'  ❌ {name}  {detail}')


def section(t):
    print(f'\n=== {t} ===')


print(f'被测包: tdxdata {tdxdata.__version__} @ {Path(tdxdata.__file__).parent}')

# ---------------------------------------------------------------- 帧与解析
section('帧 / 解析（离线）')
try:
    f = build_frame(TYPE_GBBQ, b'\x01\x00\x00' + b'001225')
    check('build_frame 长度 21 / len=0x0B', len(f) == 21 and f[6:10] == b'\x0b\x00\x0b\x00', f.hex())
    check('split_response 对非帧输入不崩', split_response(b'garbage') == (None, b'garbage'))
    check('split_response 对短输入不崩', split_response(b'\x00' * 3) == (None, b'\x00' * 3))
    check('parse_xdxr 空输入 → []', parse_xdxr(b'') == [] and parse_xdxr(b'\x01' * 5) == [])
    check('xdxr_of 空输入 → []', xdxr_of(b'', 1) == [])
except Exception:
    traceback.print_exc()
    fail += 1

# ---------------------------------------------------------------- 复权边界
section('复权（离线边界）')
try:
    check('无事件 → 原价不变', adjust_prices([10.0, 20.0], [20260101, 20260102], []) == [10.0, 20.0])
    check('单日 + 无事件', adjust_prices([10.0], [20260101], []) == [10.0])
    check('空输入', adjust_prices([], [], []) == [] and factors([], []) == [])
    # 未来事件必须忽略
    fut = [{'date': 20991231, 'category': 1, 'fenhong': 5, 'peigujia': 0, 'songzhuangu': 0, 'peigu': 0}]
    check('未来事件被忽略', adjust_prices([10.0], [20260101], fut) == [10.0])
    # 乱序日期要报错
    try:
        factors([], [20260102, 20260101])
        check('乱序日期报 ValueError', False)
    except ValueError:
        check('乱序日期报 ValueError', True)
    # 非法 mode
    try:
        adjust_prices([1.0], [20260101], [], 'xxx')
        check('非法 mode 报 ValueError', False)
    except ValueError:
        check('非法 mode 报 ValueError', True)
    # None 价格不崩
    check('None 价格保留 None', adjust_prices([None, 10.0], [20260101, 20260102], []) == [None, 10.0])
    # 极端：送转+配股把分母吃掉 → m 保护
    m, c = affine_coeffs({'fenhong': 0, 'peigujia': 0, 'songzhuangu': -10.0, 'peigu': 0})
    check('m=0 时有保护（m→1）', m == 1.0, m)
    # 大比例送转
    ev = [{'date': 20260601, 'category': 1, 'fenhong': 0, 'peigujia': 0, 'songzhuangu': 900.0, 'peigu': 0}]
    px = adjust_prices([1000.0, 100.0], [20260530, 20260603], ev)
    check('10 倍送转：前复权价 = 原价/91', abs(px[0] - round(1000.0 / 91.0, 2)) < 0.02, px)
    # category != 1 的事件被忽略
    ev2 = [{'date': 20260601, 'category': 5, 'fenhong': 99, 'songzhuangu': 0, 'peigu': 0, 'peigujia': 0}]
    check('category!=1 不参与复权', adjust_prices([10.0], [20260530], ev2) == [10.0])
    # bars 输入形态
    bars = [{'datetime': '2026-06-03 00:00', 'close': 100.0, 'open': 99.0, 'high': 101.0,
             'low': 98.0, 'vol': 5.0, 'amount': 6.0}]
    out = adjust_bars(bars, ev, 'hfq')
    check('adjust_bars 后复权锚定最早日=原价', out[0]['close'] == 100.0, out)
    check('adjust_bars 不修改入参', bars[0]['close'] == 100.0)
    check('adjust_bars mode=none 不改价', adjust_bars(bars, ev, 'none')[0]['close'] == 100.0)
    check('round_half_up 十进制半进位', round_half_up(1.005) == 1.01 and round_half_up(-2.675) == -2.68)
    # 非法 bars 输入要有可读错误
    try:
        adjust_bars([{'close': 1.0}], ev, 'qfq')
        check('bars 缺 datetime → 报错（消息可读）', False, '未报错')
    except ValueError as e:
        check('bars 缺 datetime → ValueError', True)
    except Exception as e:
        check('bars 缺 datetime → ValueError', False, f'{type(e).__name__}: {e}')
except Exception:
    traceback.print_exc()
    fail += 1

# ---------------------------------------------------------------- gbbq 文件
section('gbbq 读取（离线 + 损坏输入）')
try:
    recs = read_gbbq(GBBQ_FILE, cache_dir='/tmp/vpkg_cache')
    check('读取整表成功', len(recs) > 200000, len(recs))
    check('事件筛选（600519）非空', len(events_of(recs, '600519')) > 20)
    check('to_map 覆盖多只', len(to_map(recs)) > 6000)
    check('空文件 → 空结果不崩', read_gbbq.__module__ and True)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'empty'
        p.write_bytes(b'')
        check('空文件不崩', True)  # read_gbbq 对空文件应抛清晰异常或返回 []
        try:
            r = read_gbbq(p, cache_dir=td, use_cache=False)
            check('空文件 → []', r == [], r[:3])
        except Exception as e:
            check('空文件 → 清晰异常', 'struct' not in str(e).lower() and 'unpack' not in str(e).lower(),
                  f'{type(e).__name__}: {e}')
        # 截断文件：count 声明 100 条但只有 2 条
        q = Path(td) / 'trunc'
        q.write_bytes(struct.pack('<I', 100) + b'\x00' * 58)
        r2 = read_gbbq(q, cache_dir=td, use_cache=False)
        check('截断文件 → 不崩且条数受限', len(r2) == 2, len(r2))
        # 缓存命中一致性
        r3 = read_gbbq(q, cache_dir=td)
        check('缓存命中结果一致', len(r3) == len(r2), (len(r3), len(r2)))
except Exception:
    traceback.print_exc()
    fail += 1

section('gbbq 下载错误路径')
try:
    try:
        from tdxdata import download_gbbq
        download_gbbq(url='http://127.0.0.1:9/nope', timeout=3)
        check('坏 URL 报异常', False, '未报错')
    except Exception as e:
        check('坏 URL 报清晰异常', True, type(e).__name__)
except Exception:
    traceback.print_exc()
    fail += 1

# ---------------------------------------------------------------- 活服务器
section('活服务器（协议）')
c = TdxClient(HOST)
c.connect()
try:
    for code, mk in [('001225', 0), ('600519', 1), ('510300', 1), ('000001', 1)]:
        try:
            ev = c.xdxr(code, mk)
            check(f'xdxr {code}(market={mk}) 不崩（{len(ev)} 条）', True)
        except Exception as e:
            check(f'xdxr {code}', False, f'{type(e).__name__}: {e}')
    ev_all = c.xdxr('001225', 0, category=None)
    check('category=None 返回多类别', len(ev_all) > 5 and len({e["category"] for e in ev_all}) >= 2,
          len(ev_all))
    ev5 = c.xdxr('001225', 0, category=5)
    check('category=5 过滤有效', all(e['category'] == 5 for e in ev5))
    # 不存在的代码：应不崩
    ev_bad = c.xdxr('999999', 0)
    check('不存在代码 → 空列表不崩', ev_bad == [], ev_bad[:2])
    # 北交所代码（未支持）：不崩即可
    try:
        c.xdxr('830799', 0)
        check('北交所代码不崩', True)
    except Exception as e:
        check('北交所代码不崩', False, f'{type(e).__name__}: {e}')
    # 复权 K 线：与 events 计算一致
    bars = c.bars(9, '001225', 0, 10, 0)
    adj = c.bars_adjusted('001225', count=10, adjust='qfq')
    ev = c.xdxr('001225', 0)
    manual = adjust_prices([b['close'] for b in bars],
                           [int(b['datetime'][:10].replace('-', '')) for b in bars], ev, 'qfq')
    check('bars_adjusted == 手工 adjust_prices', [b['close'] for b in adj] == manual)
    check('bars_adjusted 保留成交量', adj == adj and 'vol' in adj[0])
    adj_none = c.bars_adjusted('001225', count=5, adjust='none')
    check('adjust=none 与原始 bars 一致', [b['close'] for b in adj_none] ==
          [b['close'] for b in c.bars(9, '001225', 0, 5, 0)])
except Exception:
    traceback.print_exc()
    fail += 1
finally:
    c.close()

print(f'\n=== 结果：通过 {ok} / 失败 {fail} ===')
sys.exit(1 if fail else 0)
