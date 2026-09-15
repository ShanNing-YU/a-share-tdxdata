# -*- coding: utf-8 -*-
"""GetSecurityQuotes 报价接口 — 旧 pytdx 格式在新服务器原样可用（2026-09-15 实测）

变长整数解码 (get_price) 参考 pytdx (MIT License) rainx/pytdx — https://github.com/rainx/pytdx
请求/响应框架为 tdxdata 独立实现。

响应(1只,100B): 帧头18B + count(2) + market(1) + code(6) + active1(2)
  + price_base(变长) + last_close_diff + open_diff + high_diff + low_diff (相对base的差分)
  + 时间 + (-price) + vol + cur_vol + amount(u32) + s_vol + b_vol
  + bid1/ask1/bv1/av1 ... bid5/ask5/bv5/av5
价格单位: 变长整数 / 100 (分->元)
"""
import struct

def get_price(data, pos):
    """pytdx 变长整数编码(带符号)"""
    pos_byte = 6
    bdata = data[pos]
    intdata = bdata & 0x3f
    sign = bool(bdata & 0x40)
    if bdata & 0x80:
        while True:
            pos += 1
            bdata = data[pos]
            intdata += (bdata & 0x7f) << pos_byte
            pos_byte += 7
            if not (bdata & 0x80):
                break
    pos += 1
    return (-intdata if sign else intdata), pos

def build_quotes_req(items):
    """items: [(market, code), ...]"""
    n = len(items)
    pkgdatalen = n * 7 + 12
    hdr = struct.pack("<HIHHIIHH", 0x10c, 0x02006320, pkgdatalen, pkgdatalen, 0x5053e, 0, 0, n)
    body = b''.join(struct.pack("<B6s", m, c.encode()) for m, c in items)
    return hdr + body

def parse_quotes(resp: bytes):
    """返回 [dict...]"""
    out = []
    # 找帧头偏移: b1cb7400 后 18B(0c01 报价帧), 或直接从 num_stock=1 处
    for head_len in (16, 18, 20):
        b = resp[head_len:]
        if len(b) < 12:
            continue
        (num_stock,) = struct.unpack("<H", b[0:2])
        if num_stock not in (1, 2, 5):
            continue
        pos = 2
        for _ in range(num_stock):
            if pos + 9 > len(b):
                break
            market, code, active1 = struct.unpack("<B6sH", b[pos:pos+9]); pos += 9
            price_base, pos = get_price(b, pos)
            lc_diff, pos = get_price(b, pos)
            op_diff, pos = get_price(b, pos)
            hi_diff, pos = get_price(b, pos)
            lo_diff, pos = get_price(b, pos)
            rev0, pos = get_price(b, pos)
            rev1, pos = get_price(b, pos)
            vol, pos = get_price(b, pos)
            cur_vol, pos = get_price(b, pos)
            if pos + 4 > len(b):
                break
            (amount_raw,) = struct.unpack("<I", b[pos:pos+4]); pos += 4
            s_vol, pos = get_price(b, pos)
            b_vol, pos = get_price(b, pos)
            # ⚠️ 关键: pytdx 在 b_vol 后还有 reversed_bytes2/3 两个变长字段，
            # 不跳过会导致 pos 偏移 → 多只错位、单只五档全错（曾漏此 2 字段）
            _, pos = get_price(b, pos)
            _, pos = get_price(b, pos)
            bids, asks, bvs, avs = [], [], [], []
            for _ in range(5):
                bd, pos = get_price(b, pos); aq, pos = get_price(b, pos)
                bv, pos = get_price(b, pos); av, pos = get_price(b, pos)
                bids.append(bd); asks.append(aq); bvs.append(bv); avs.append(av)
            # 每只记录尾部（pytdx 对齐）: rev4(H) + rev5-8(4×变长) + rev9(h)+active2(H)
            pos += 2
            for _ in range(4):
                _, pos = get_price(b, pos)
            pos += 4
            base = price_base
            out.append({
                'market': market, 'code': code.decode(errors='ignore'),
                'price': base/100, 'last_close': (base+lc_diff)/100,
                'open': (base+op_diff)/100, 'high': (base+hi_diff)/100,
                'low': (base+lo_diff)/100,
                'vol': vol, 'cur_vol': cur_vol, 'amount': amount_raw,
                'bid': [(base + b) / 100 for b in bids], 'ask': [(base + a) / 100 for a in asks],
                'bid_vol': bvs, 'ask_vol': avs,
            })
        if out:
            return out
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
    s.sendall(build_quotes_req([(0, '000059'), (1, '600519')]))
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
    for q in parse_quotes(buf):
        print(f"{q['code']}: 现价={q['price']} 昨收={q['last_close']} 高={q['high']} 低={q['low']} 量={q['vol']} bid1={q['bid'][0]}")
    s.close()