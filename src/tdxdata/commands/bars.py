# -*- coding: utf-8 -*-
"""GetSecurityBars 历史K线接口 — 旧 pytdx 请求 + 新版本标识(18 7b 00 01)

2026-09-15 实测: 日线/5min/15min/30min/60min/1min 全周期可用（000059 数据正确）
关键: 老格式请求需把版本标识 0x01016408(字节 08 64 01 01) 换成 0x01007b18(字节 18 7b 00 01)
解码逻辑参考 pytdx (MIT) rainx/pytdx — get_datetime/get_price/差分价格；请求构造 tdxdata 独立实现。

category（2026-11-06 逐类实测，旧文档 6=周/7=月 有误）:
    0=5min 1=15min 2=30min 3=60min 4=日线变体 5=周线 6=月线
    7=1min 8=1min(与7返回相同) 9=日线 10=季线 11=年线 12=空
    4 与 9 都是日线，差别在 vol 单位（见下）。
"""
import struct

def build_bars_req(category: int, market: int, code: str, start: int, count: int) -> bytes:
    values = (0x10c, 0x01007b18, 0x1c, 0x1c, 0x052d, market, code.encode(), category, 1, start, count, 0, 0, 0)
    return struct.pack("<HIHHHH6sHHHHIIH", *values)

# 记录布局（2026-11-06 实测 + 东方财富行情交叉验证）:
#   个股: [日期4B][od][cd][hd][ld 变长差分][vol f32][amount f32=元]      尾部 8B
#   指数: [日期4B][od][cd][hd][ld 变长差分][vol f32][amount f32=元]
#         [上涨家数 u16][下跌家数 u16]                                   尾部 12B
# 指数比个股每根多 4B（pytdx GetIndexBarsCmd 同款 up/down 家数）。按个股 8B 尾部切
# 指数响应会从第 2 根起全部错位 —— 999999 首根对、后面全错的根因。
# vol f32 单位（amt/vol ≈ 现价×100 交叉验证 + eastmoney 锚点，逐类实测）:
#   个股: 分钟类(0-3,7,8)与 cat4 =股（÷100=手）；5/6/9/10/11 =手
#   指数: cat4 =手（原样）；5/6/9/10/11 =万股（×100=手）；
#         分钟类(0-3,7,8) vol 槽位=成交额千元（=amt/1000，服务器不给真实量）
# 指数 up/down 家数: 日线=当日家数；周/月=各交易日涨跌家数累计
#   （实测 10 月月线 15177+23923=39100 ≈ 17 交易日×2303 只沪市股）；季/年服务器填 0
# 锚点: 上证指数 2026-10-30 O3605.65 C3599.02 H3660.21 L3595.26
# vol 497,973,940手 amt 764,227,190,864.50（eastmoney 逐字段一致）。
def parse_bars_response(body: bytes, category: int, is_index: bool = False):
    """轻量解码（与 pytdx parseResponse 等价）：日期 4B + 4×变长价格差分 + vol + amount"""
    from tdxdata.commands.quotes import get_price
    minute_like = category < 4 or category in (7, 8)
    (ret_count,) = struct.unpack("<H", body[0:2])
    pos = 2
    out = []
    pre = 0
    for _ in range(ret_count):
        if minute_like:
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
        up_count = down_count = None
        if is_index:
            # 指数独有: +4B 涨跌家数（上证指数日/周/月线 eastmoney 锚点验证）
            up_count, down_count = struct.unpack("<HH", body[pos:pos+4]); pos += 4
            if not minute_like and category != 4:
                vol_raw *= 100  # 指数 5/6/9/10/11: vol f32=万股 → 手
            # 指数 cat4: 服务器直接给手，原样；指数分钟类: vol 槽位=成交额千元，无真实量
        elif minute_like or category == 4:
            vol_raw /= 100  # 个股分钟类与 cat4: vol f32=股 → 手
        o = (od + pre) / 1000
        c = (od + pre + cd) / 1000
        h = (od + pre + hd) / 1000
        l = (od + pre + ld) / 1000
        pre = od + cd + pre
        rec = {
            'datetime': f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}',
            'open': round(o, 3), 'close': round(c, 3), 'high': round(h, 3), 'low': round(l, 3),
            'vol': vol_raw, 'amount': amt_raw,
        }
        if is_index:
            rec['up_count'], rec['down_count'] = up_count, down_count
        out.append(rec)
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