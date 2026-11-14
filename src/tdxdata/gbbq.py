# -*- coding: utf-8 -*-
"""gbbq（股本变迁 / 权息表）—— HTTP 获取 + 解密 + 解析（2026-11-13 实测）

两条口径统一：本模块输出的记录字段与 `commands/xdxr.py`（协议按个股查询）**完全一致**，
两条通道可互换（实测 001225 / 001285 / 001309 / 600519 逐条相同）。

来源
----
- HTTP(S) 源：`https://www.tdx.com.cn/products/data/data/dbf/gbbq.zip`（通达信官方数据站；
  同路径 `http://` 也可用且内容字节一致，0.2.11 起默认走 https）
  包内含 `gbbq`（全市场权息表，6.0MB / 20.8 万条）、`gbbq.map`、`zhb.zip`（板块总包）、
  `infoharbor_*.txt` 等。**无需通达信客户端、无需协议身份**。
  该地址来自 jing2uo/tdx2db（其 lib/gbbq 被 injoyai/tdx 引用），本实现独立重写。
- 文件格式：4 字节记录数(u32) + N × 29 字节；每条 **前 24B 加密（3DES 族查表）+ 后 5B 明文**；
  解密后 = market(1) + code(7 补 0) + date(u32 YYYYMMDD) + category(1) + 4 × float32。
- 密钥表见 `gbbq_keys.py`（源自 pytdx，MIT）。

实测对比（2026-11-13）：HTTP 版 **207,882 条 / 7,417 只**，客户端本地版 194,553 条 / 6,342 只
→ **本地版是 HTTP 版的严格子集**（少约 1.3 万条，多为退市/老股票），两者共有股票的事件逐条一致。
（官方数据站每日滚动更新，条数会变；客户端本地版只在客户端运行时更新，因此差值会浮动。）
"""
import hashlib
import io
import struct
import urllib.request
import zipfile
from pathlib import Path

from .commands.xdxr import CATEGORY_NAMES
from .gbbq_keys import KEYS_HEX

# 默认走 https（数据会喂复权、间接影响交易决策，明文有被中间人篡改的风险；
# 实测同路径 http:// 也可用且**内容字节完全一致**，如需可自行传 url= 覆盖）
GBBQ_URL = 'https://www.tdx.com.cn/products/data/data/dbf/gbbq.zip'
RECORD_SIZE = 29
KEYS = bytes.fromhex(KEYS_HEX)

__all__ = ['GBBQ_URL', 'download_gbbq', 'decrypt_records', 'read_gbbq',
           'events_of', 'to_map']


# ---------------------------------------------------------------- 解密

def decrypt_record(rec: bytes) -> bytes:
    """解密一条 29 字节记录：前 24B（3×8B 块，16 轮查表）+ 后 5B 明文照抄"""
    out = bytearray()
    off = 0
    for _ in range(3):
        a = struct.unpack_from('<I', KEYS, 0x44)[0] ^ struct.unpack_from('<I', rec, off)[0]
        b = struct.unpack_from('<I', rec, off + 4)[0]
        num, numold = a & 0xFFFFFFFF, b
        # 轮常量索引 = [0x40, 0x3C, …, 0x04]（共 16 轮）
        # ⚠️ 写成 range(0x44, 0, -4) 会多一轮且错位 → 解出乱码（2026-11-12 踩坑）
        for j in range(0x40, 0, -4):
            eax = struct.unpack_from('<I', KEYS, ((num & 0xFF0000) >> 16) * 4 + 0x448)[0]
            eax = (eax + struct.unpack_from('<I', KEYS, (num >> 24) * 4 + 0x48)[0]) & 0xFFFFFFFF
            eax ^= struct.unpack_from('<I', KEYS, ((num & 0xFF00) >> 8) * 4 + 0x848)[0]
            eax = (eax + struct.unpack_from('<I', KEYS, (num & 0xFF) * 4 + 0xC48)[0]) & 0xFFFFFFFF
            eax ^= struct.unpack_from('<I', KEYS, j)[0]
            num, numold = (numold ^ eax) & 0xFFFFFFFF, num
        numold ^= struct.unpack_from('<I', KEYS, 0)[0]
        out += struct.pack('<II', numold & 0xFFFFFFFF, num)
        off += 8
    out += rec[off:off + 5]
    return bytes(out)


def decrypt_records(raw: bytes) -> list:
    """解密整个 gbbq 文件 → 记录列表（dict，字段与 xdxr 一致）

    文件损坏/为空时抛 `ValueError`（不是裸 struct.error），便于调用方识别。
    """
    if len(raw) < 4:
        raise ValueError(f'gbbq 数据过短（{len(raw)} 字节，至少需要 4 字节的记录数）——不是有效的 gbbq')
    count = struct.unpack_from('<I', raw, 0)[0]
    body = raw[4:]
    n = min(count, len(body) // RECORD_SIZE)
    out = []
    for i in range(n):
        clear = decrypt_record(body[i * RECORD_SIZE:(i + 1) * RECORD_SIZE])
        market, code_b, date, cat, f1, f2, f3, f4 = struct.unpack('<B7sIBffff', clear)
        code = code_b.rstrip(b'\x00').decode('ascii', 'ignore')
        out.append({
            'market': market,
            'code': code,
            'date': date,
            'category': cat,
            'category_name': CATEGORY_NAMES.get(cat, '未知'),
            'fenhong': round(f1, 6) if cat == 1 else 0.0,
            'peigujia': round(f2, 6) if cat == 1 else 0.0,
            'songzhuangu': round(f3, 6) if cat == 1 else 0.0,
            'peigu': round(f4, 6) if cat == 1 else 0.0,
            'raw': (f1, f2, f3, f4) if cat != 1 else None,
        })
    return out


# ---------------------------------------------------------------- 获取

def _extract_members(blob: bytes, members=('gbbq', 'gbbq.map')) -> dict:
    """从官方 zip 里解出指定成员；缺 gbbq 时抛可读的 ValueError（不是裸 KeyError）"""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = set(z.namelist())
            out = {m: z.read(m) for m in members if m in names}
    except zipfile.BadZipFile as e:
        raise ValueError(f'官方数据包不是有效 zip：{e}') from e
    if 'gbbq' not in out:
        raise ValueError(f'官方数据包内没有 gbbq（包内文件：{sorted(names)[:8]}）—— 数据源可能已改版')
    return out


def download_gbbq(dest=None, url=GBBQ_URL, timeout=90, members=('gbbq', 'gbbq.map')):
    """下载 gbbq.zip 并解出指定成员 → {成员名: bytes}；`dest` 传目录时同时落盘

    实测（2026-11-13）：6,344,573 B / 约 23s；zip 内 gbbq 为 6,027,654 B。
    """
    req = urllib.request.Request(url, headers={'User-Agent': 'tdxdata/0.2.6'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        blob = r.read()
    out = _extract_members(blob, members)
    if dest is not None:
        d = Path(dest)
        d.mkdir(parents=True, exist_ok=True)
        for m, data in out.items():
            (d / m).write_bytes(data)
    return out


def read_gbbq(path=None, url=GBBQ_URL, cache_dir=None, use_cache=True, verbose=False):
    """读 gbbq（本地文件路径，或 None=从 url 下载）→ 记录列表

    `use_cache` 时把解密结果缓存到 `cache_dir/gbbq_<源md5前8>.bin`（固定 24B/条），
    二次读取免解密（20 万条解密约 20-40s，缓存后 <1s）。
    """
    if path is None:
        data = download_gbbq()['gbbq']
        tag = 'http'
    else:
        data = Path(path).read_bytes()
        tag = Path(path).name
    if use_cache:
        cache_dir = Path(cache_dir or Path.home() / '.cache' / 'tdxdata')
        # 缓存键用源文件 md5——只按长度会撞（不同版本 gbbq 长度可能相同 → 读到过期数据）
        key = f'gbbq_{tag}_{hashlib.md5(data).hexdigest()[:12]}.bin'
        cf = cache_dir / key
        if cf.exists():
            try:
                return _load_cache(cf)
            except Exception:
                pass          # 缓存损坏 → 忽略，走完整解密
        recs = decrypt_records(data)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            _save_cache(cf, recs)
            _prune_cache(cache_dir, tag, keep=3)
        except Exception:
            pass
        return recs
    return decrypt_records(data)


# ---------------------------------------------------------------- 缓存（魔数 + 24B/条，纯 stdlib）

CACHE_MAGIC = b'TXG1'


def _save_cache(cf: Path, recs: list):
    buf = bytearray(CACHE_MAGIC)
    for r in recs:
        code = r['code'].encode()[:7].ljust(7, b'\x00')
        f = r['raw'] or (r['fenhong'], r['peigujia'], r['songzhuangu'], r['peigu'])
        buf += struct.pack('<B7sIBffff', r['market'], code, r['date'],
                           r['category'], *[float(x) for x in f])
    cf.write_bytes(bytes(buf))


def _load_cache(cf: Path) -> list:
    """读缓存；格式不符/被截断/损坏 → 抛 ValueError（调用方回退完整解密，不静默给空数据）"""
    raw = cf.read_bytes()
    if not raw.startswith(CACHE_MAGIC):
        raise ValueError('缓存文件魔数不符')
    body = raw[len(CACHE_MAGIC):]
    if not body or len(body) % 24:
        raise ValueError(f'缓存文件长度异常（{len(body)} 字节，应为 24 的倍数）')
    raw = body
    out = []
    for i in range(len(raw) // 24):
        market, code_b, date, cat, f1, f2, f3, f4 = struct.unpack_from('<B7sIBffff', raw, i * 24)
        code = code_b.rstrip(b'\x00').decode('ascii', 'ignore')
        out.append({
            'market': market, 'code': code, 'date': date, 'category': cat,
            'category_name': CATEGORY_NAMES.get(cat, '未知'),
            'fenhong': round(f1, 6) if cat == 1 else 0.0,
            'peigujia': round(f2, 6) if cat == 1 else 0.0,
            'songzhuangu': round(f3, 6) if cat == 1 else 0.0,
            'peigu': round(f4, 6) if cat == 1 else 0.0,
            'raw': (f1, f2, f3, f4) if cat != 1 else None,
        })
    return out


# ---------------------------------------------------------------- 提取

def events_of(recs, code=None, category=1):
    """筛出某只股票的某类别事件，按日期升序（默认 category=1 除权除息）"""
    out = [r for r in recs if r['category'] == category and (code is None or r['code'] == code)]
    return sorted(out, key=lambda r: r['date'])


def to_map(recs, category=1):
    """{代码: [事件…]}（按日期升序）"""
    m = {}
    for r in recs:
        if r['category'] == category:
            m.setdefault(r['code'], []).append(r)
    for v in m.values():
        v.sort(key=lambda r: r['date'])
    return m


def _prune_cache(cache_dir: Path, tag: str, keep: int = 3):
    """同一来源只保留最近 keep 份缓存（权息表每版约 5MB，不清理会持续累积）"""
    try:
        files = sorted(cache_dir.glob(f'gbbq_{tag}_*.bin'), key=lambda p: p.stat().st_mtime)
        for p in files[:-keep] if len(files) > keep else []:
            p.unlink()
    except Exception:
        pass
