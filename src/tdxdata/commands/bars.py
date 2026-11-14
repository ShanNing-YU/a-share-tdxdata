# -*- coding: utf-8 -*-
"""GetSecurityBars 历史K线接口 — 旧 pytdx 请求 + 新版本标识(18 7b 00 01)

2026-09-15 实测: 日线/5min/15min/30min/60min/1min 全周期可用（000059 数据正确）
关键: 老格式请求需把版本标识 0x01016408(字节 08 64 01 01) 换成 0x01007b18(字节 18 7b 00 01)
解码逻辑参考 pytdx (MIT) rainx/pytdx — get_datetime/get_price/差分价格；请求构造 tdxdata 独立实现。

category: 0=5min 1=15min 2=30min 3=60min 4=日线(vol 单位=股) 5=周 6=月 7=1min(与 8 同)
          8=1min 9=日线(vol 单位=手) 10=季 11=年
# ⚠️ 2026-11-14 实测修正：旧注释/README 写「6=周 7=月」是错的 —— 6 是月线、5 是周线、
#    7 与 8 逐根相同（1 分钟线）。照旧文档调 bars(7,…) 会静默拿到 1 分钟 K 线。
# ⚠️ 4 与 9 价格逐根相同，但 vol 差整 100 倍（4=股、9=手）；成交量按 amount/close 校验后再用。
# ⚠️ 2026-11-13 实测：category 4 原注释标「后复权」有误 —— 其响应与 category 9 **逐位相同**
#    （001225 除权日前后历史价均为不复权原始价）。服务器**不提供复权价**，复权=客户端本地算；
#    本库的复权见 tdxdata/adjust.py（仿射口径）。
"""
import struct

def build_bars_req(category: int, market: int, code: str, start: int, count: int) -> bytes:
    values = (0x10c, 0x01007b18, 0x1c, 0x1c, 0x052d, market, code.encode(), category, 1, start, count, 0, 0, 0)
    return struct.pack("<HIHHHH6sHHHHIIH", *values)

# 推荐直接复用 pytdx.parser.get_security_bars.GetSecurityBarsCmd.parseResponse（响应格式未变）
def parse_bars_response(body: bytes, category: int):
    """轻量解码（与 pytdx parseResponse 等价）：日期 4B + 4×变长价格差分 + vol + amount"""
    from tdxdata.commands.quotes import get_price
    (ret_count,) = struct.unpack("<H", body[0:2])
    pos = 2
    out = []
    pre = 0
    for _ in range(ret_count):
        if category < 4 or category in (7, 8):
            # 分钟线: zipday(u16 高11位年-2004+低11位月日) + tminutes(u16 分钟)
            zipday, tminutes = struct.unpack("<HH", body[pos:pos+4]); pos += 4
            year = (zipday >> 11) + 2004
            month = int((zipday % 2048) / 100)
            day = (zipday % 2048) % 100
            hour = int(tminutes / 60)
            minute = tminutes % 60
        else:
            d = struct.unpack("<I", body[pos:pos+4])[0]; pos += 4
            year, month, day = d // 10000, d // 100 % 100, d % 100
            hour = minute = 0
        od, pos = get_price(body, pos); cd, pos = get_price(body, pos)
        hd, pos = get_price(body, pos); ld, pos = get_price(body, pos)
        # ⚠️ 2026-09 新协议 vol/amount 是 f32！pytdx 旧格式 u32 会读出垃圾大数（000001 实测 u32=12.28亿 vs f32=75.5万手）
        vol_raw, amt_raw = struct.unpack("<ff", body[pos:pos+8]); pos += 8
        o = (od + pre) / 1000
        c = (od + pre + cd) / 1000
        h = (od + pre + hd) / 1000
        l = (od + pre + ld) / 1000
        pre = od + cd + pre
        out.append({
            'datetime': f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}',
            'open': round(o, 3), 'close': round(c, 3), 'high': round(h, 3), 'low': round(l, 3),
            'vol': vol_raw, 'amount': amt_raw,
        })
    return out


if __name__ == '__main__':
    import socket, time
    HOST = '101.35.121.35'
    C02 = bytes.fromhex("0c0218940001030003000d0001")
    C03 = bytes.fromhex("0c031899000120002000db0f7464786c6576656c000000295cf740110000000000000000000000000005")
    s = socket.socket(); s.settimeout(3)
    s.connect((HOST, 7709))
    for p in (C02, C03):
        s.sendall(p); time.sleep(0.2)
        try:
            s.recv(65536)
        except socket.timeout:
            pass
    for name, cat in [('日线', 9), ('5min', 0), ('周线', 6)]:
        s.sendall(build_bars_req(cat, 0, '000059', 0, 3))
        buf = b''
        end = time.time() + 3
        while time.time() < end:
            try:
                ch = s.recv(65536)
            except socket.timeout:
                break
            if not ch:
                break
            buf += ch
        bars = parse_bars_response(buf[16:], cat) if len(buf) > 20 else []
        print(f'{name}: {len(bars)}根')
        for b in bars:
            print(f'  {b["datetime"]} o={b["open"]} c={b["close"]} h={b["high"]} l={b["low"]}')
    s.close()