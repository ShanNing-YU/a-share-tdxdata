# -*- coding: utf-8 -*-
"""GetFinanceInfo(0c1f) 财务接口 — 旧 pytdx 格式在新服务器原样可用（2026-09-15 实测）

请求 21B: 0c1f 1876 0001 0b00 0b00 1000 0100 + market + code6
响应: 帧头 + count(2) + market(1) + code(6) + 流通股本(f32) + 省份(u16) + 行业(u16)
     + 更新日期(u32 yyyymmdd) + IPO(u32) + 总股本..每股净资产(28×f32)
"""
import struct

TMPL = bytes.fromhex("0c1f187600010b000b0010000100")

FIELDS = ['总股本', '国家股', '发起人法人股', '法人股', 'B股', 'H股', '职工股', '总资产', '流动资产',
          '固定资产', '无形资产', '股东人数', '流动负债', '长期负债', '资本公积金', '净资产', '主营收入',
          '主营利润', '应收帐款', '营业利润', '投资收益', '经营现金流', '总现金流', '存货', '利润总额',
          '税后利润', '净利润', '未分利润', '每股净资产', '保留']
# 单位: 股本类 ×10000(手?)实际为股; 金额类 ×10000 元; 每股类直接
# 兼容 pytdx: liutongguben*10000 等

def build_finance_req(market: int, code: str) -> bytes:
    return TMPL + bytes([market]) + code.encode()

def parse_finance(resp: bytes) -> dict:
    if len(resp) < 40:
        return {'ok': False, 'raw_len': len(resp)}
    body = resp[16:]
    cnt = struct.unpack('<H', body[0:2])[0]
    if cnt < 1:
        return {'ok': False, 'raw_len': len(resp)}
    market = body[2]
    code = body[3:9].decode(errors='ignore')
    pos = 9
    liutong = struct.unpack('<f', body[pos:pos+4])[0] * 10000
    pos += 4
    prov, ind = struct.unpack('<HH', body[pos:pos+4]); pos += 4
    upd, ipo = struct.unpack('<II', body[pos:pos+8]); pos += 8
    pos += 4  # 总股本（单独拿）
    zongguben = struct.unpack('<f', body[pos-4:pos])[0] * 10000
    rest = {}
    for i in range(1, 30):
        if pos + 4 <= len(body):
            v = struct.unpack('<f', body[pos:pos+4])[0]
            pos += 4
            if i in (11, 28, 29):  # 股东人数/每股净资产直接值
                rest[FIELDS[i]] = round(v, 4)
            else:
                rest[FIELDS[i]] = round(v * 10000, 2)
    return {
        'ok': True, 'code': code, 'market': market,
        'liutongguben': liutong,          # 股
        'zongguben': zongguben,           # 股
        'province': prov, 'industry': ind,
        'updated_date': upd, 'ipo_date': ipo,
        'net_profit': rest.get('净利润'),    # 元
        'bvps': rest.get('每股净资产'),
        **rest,
    }


if __name__ == '__main__':
    import socket, time
    HOST = '101.35.121.35'
    C02 = bytes.fromhex("0c0218940001030003000d0001")
    C03 = bytes.fromhex("0c031899000120002000db0f7464786c6576656c000000295cf740110000000000000000000000000005")
    s = socket.socket(); s.settimeout(3)
    s.connect((HOST, 7709))
    for _ in range(3):
        s.sendall(C02 if _ == 0 else C03)
        time.sleep(0.2)
        try:
            s.recv(65536)
        except socket.timeout:
            pass
    for code, m in [('000059', 0), ('600519', 1)]:
        s.sendall(build_finance_req(m, code))
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
        r = parse_finance(buf)
        print(f'{code}: 流通={r.get("liutongguben", 0)/1e8:.2f}亿股 总股本={r.get("zongguben", 0)/1e8:.2f}亿 净利润={r.get("net_profit")} 每股净资产={r.get("bvps")} 更新={r.get("updated_date")}')
    s.close()