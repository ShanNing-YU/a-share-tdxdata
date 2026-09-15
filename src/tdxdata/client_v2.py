# -*- coding: utf-8 -*-
"""tdxdata 新版协议客户端核心验证版：认证 + 单只快照（分时）

协议要点（2026-09-15 定稿）:
- TCP 7709, 顺序: 0c02(init) -> 0c03(tdxlevel) -> 数据请求
- 单只行情: 0c09 0041 0300 2700 2700 d10f + market(1B) + code6 + 29B
  market: 0=深市 1=沪市 (000001 m=1 是上证指数!)
- 响应: 16B帧头 + 分时价格序列(float)
- 沪市/批量需要 0c01 会话(身份校验, 无法重放); 深市单只无需 0c01 也可用
"""
import socket, time, struct

HOST = '101.33.225.16'
PORT = 7709

C02 = bytes.fromhex("0c0218940001030003000d0001")
C03 = bytes.fromhex("0c031899000120002000db0f7464786c6576656c000000295cf740110000000000000000000000000005")
SN_PREFIX = bytes.fromhex("0c090041030027002700d10f")
SN_SUFFIX = bytes.fromhex("0000000000000000000000000000000001001400000000010000000000")

def market_of(code: str) -> int:
    """沪市 600/601/603/605/688/689/9xx -> 1; 其他(深市 000/002/300/301, 创业板) -> 0"""
    if code.startswith(('6', '9')):
        return 1
    return 0

def build_snap(code: str, market: int) -> bytes:
    assert len(code) == 6 and code.isdigit()
    return SN_PREFIX + bytes([market, 0]) + code.encode() + SN_SUFFIX

def parse_snap(resp: bytes) -> dict:
    """解析快照响应 -> {code, market, count, prices[]}"""
    if len(resp) < 60:
        return {'ok': False, 'raw_len': len(resp)}
    market = resp[17]
    code = resp[18:24].decode() if resp[18:24].isalnum() else ''
    # 分时价格: 从 offset 50 起 float 序列（出现非价格 uint16 时跳过）
    prices = []
    i = 50
    while i + 4 <= len(resp):
        v = struct.unpack('<f', resp[i:i+4])[0]
        if 0.1 < v < 100000:
            prices.append(round(v, 3))
            i += 4
        else:
            i += 2
    return {'ok': True, 'code': code, 'market': market, 'prices': prices,
            'last': prices[-1] if prices else None, 'raw_len': len(resp)}


class TdxClient:
    def __init__(self, host=HOST, port=PORT):
        self.host, self.port = host, port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect((self.host, self.port))
        self._recv()
        self.sock.sendall(C02)
        self._recv()
        self.sock.sendall(C03)
        self._recv()

    def _recv(self, secs=2.0):
        buf = b''
        end = time.time() + secs
        while time.time() < end:
            try:
                ch = self.sock.recv(65536)
            except socket.timeout:
                break
            if not ch:
                break
            buf += ch
        return buf

    def snap(self, code: str, market=None) -> dict:
        m = market if market is not None else market_of(code)
        self.sock.sendall(build_snap(code, m))
        r = self._recv(3.0)
        return parse_snap(r)

    def close(self):
        if self.sock:
            self.sock.close()


if __name__ == '__main__':
    c = TdxClient()
    c.connect()
    for code in ['000001', '000002', '600519', '688981']:
        r = c.snap(code)
        print(f'{code}: ok={r["ok"]} last={r.get("last")} count={len(r.get("prices", []))}')
    c.close()