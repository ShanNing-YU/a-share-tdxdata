# -*- coding: utf-8 -*-
"""GetSecurityBars 历史K线接口 — 旧 pytdx 请求 + 新版本标识(18 7b 00 01)

2026-09-15 实测: 日线/5min/15min/30min/60min/1min 全周期可用（000059 数据正确）
关键: 老格式请求需把版本标识 0x01016408(字节 08 64 01 01) 换成 0x01007b18(字节 18 7b 00 01)
解码逻辑参考 pytdx (MIT) rainx/pytdx — get_datetime/get_price/差分价格；请求构造 tdxdata 独立实现。

category: 0=5min 1=15min 2=30min 3=60min 4=日线(后复权) 5=? 6=周 7=月 8=1min 9=日线 10=季 11=年
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
        d = struct.unpack("<I", body[pos:pos+4])[0]; pos += 4
        if category in (0, 1, 2, 3, 8):
            d1, t1 = d >> 16, d & 0xffff
            year, month, day = d1 // 10000, d1 // 100 % 100, d1 % 100
            hour, minute = t1 // 100, t1 % 100
        else:
            year, month, day = d // 10000, d // 100 % 100, d % 100
            hour = minute = 0
        od, pos = get_price(body, pos); cd, pos = get_price(body, pos)
        hd, pos = get_price(body, pos); ld, pos = get_price(body, pos)
        (vol_raw,) = struct.unpack("<I", body[pos:pos+4]); pos += 4
        (amt_raw,) = struct.unpack("<I", body[pos:pos+4]); pos += 4
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