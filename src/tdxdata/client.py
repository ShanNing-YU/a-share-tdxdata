# -*- coding: utf-8 -*-
"""tdxdata 统一客户端入口

用法:
    c = TdxClient('101.35.121.35')
    c.connect()                       # 0c02 init + 0c03 tdxlevel（无需 0c01）
    c.snap('600519')                  # 分时快照（最新价 + 32-51 点当日分时）
    c.bars(9, '000059', 0, 10)        # 历史K线（9=日线 0=5min 3=60min 6=周 7=月 8=1min）
    c.quotes([(0, '000059')])         # 盘口报价（现价/昨收/高低/量/额/五档）
    c.finance(0, '000059')            # 财务（流通股本/总股本/净利润/每股净资产）
    c.close()

协议要点（2026-09 逆向）:
- 服务器认 0c02/0c03 即可用普通命令；批量接口需 0c01 身份（放弃，用单只循环+多IP并发）
- 老 pytdx 命令（bars/quotes/finance）只改版本标识 18 7b 00 01 即可用
"""
import socket, time

from .commands.auth import build_auth
from .commands.bars import build_bars_req, parse_bars_response
from .commands.finance import build_finance_req, parse_finance
from .commands.quotes import build_quotes_req, parse_quotes

DEFAULT_HOST = '101.35.121.35'
PORT = 7709
C02 = bytes.fromhex("0c0218940001030003000d0001")

SNAP_PREFIX = bytes.fromhex("0c090041030027002700d10f")
SNAP_SUFFIX = bytes.fromhex("0000000000000000000000000000000001001400000000010000000000")


def market_of(code: str) -> int:
    """0=深市 1=沪市（000001+1=上证指数）"""
    return 1 if code.startswith(('6', '9')) else 0


class TdxClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = PORT):
        self.host, self.port = host, port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(4)
        self.sock.connect((self.host, self.port))
        self._send_wait(C02)
        self._send_wait(build_auth())

    def _send_wait(self, payload: bytes, secs: float = 1.2):
        self.sock.sendall(payload)
        time.sleep(0.08)
        self._recv(secs)

    def _recv(self, secs: float = 3.0) -> bytes:
        buf = b''
        end = time.time() + secs
        got = None
        while time.time() < end:
            try:
                ch = self.sock.recv(65536)
            except socket.timeout:
                break
            if not ch:
                break
            buf += ch
            if got is None:
                got = time.time()
                end = min(end, got + 0.15)
        return buf

    def _req(self, payload: bytes, secs: float = 3.0) -> bytes:
        self.sock.sendall(payload)
        return self._recv(secs)

    # ---- 分时快照 ----
    def snap(self, code: str, market: int = None):
        import struct
        m = market if market is not None else market_of(code)
        req = SNAP_PREFIX + bytes([m, 0]) + code.encode() + SNAP_SUFFIX
        r = self._req(req)
        return parse_snap(r)

    # ---- 历史 K 线 ----
    def bars(self, category: int, code: str, start: int = 0, count: int = 100, market: int = None):
        m = market if market is not None else market_of(code)
        r = self._req(build_bars_req(category, m, code, start, count))
        if len(r) <= 18:
            return []
        return parse_bars_response(r[16:], category)

    # ---- 盘口报价 ----
    def quotes(self, items):
        r = self._req(build_quotes_req(items))
        return parse_quotes(r)

    # ---- 财务 ----
    def finance(self, code: str, market: int = None):
        m = market if market is not None else market_of(code)
        r = self._req(build_finance_req(m, code))
        return parse_finance(r)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


def parse_snap(resp: bytes) -> dict:
    import struct, zlib
    if len(resp) < 60:
        return {'ok': False, 'raw_len': len(resp)}
    data = resp
    compressed = False
    i789 = resp.find(b'\x78\x9c')
    if i789 >= 0:
        try:
            data = resp[:i789] + zlib.decompress(resp[i789:])
            compressed = True
        except Exception:
            pass
    if len(data) < 60:
        return {'ok': False, 'raw_len': len(resp), 'compressed': compressed}
    code = data[18:24].decode(errors='ignore')
    market = data[17]
    prices = []
    i = 50
    while i + 4 <= len(data):
        v = struct.unpack('<f', data[i:i+4])[0]
        if 0.1 < v < 100000:
            prices.append(round(v, 3))
            i += 4
        else:
            i += 2
    return {'ok': True, 'code': code, 'market': market, 'prices': prices,
            'last': prices[-1] if prices else None, 'compressed': compressed}


if __name__ == '__main__':
    c = TdxClient()
    c.connect()
    for code in ['000059', '600519']:
        m = market_of(code)
        s = c.snap(code)
        q = c.quotes([(m, code)])
        f = c.finance(code)
        b = c.bars(9, code, 0, 3)
        print(f'{code}: 分时最新={s.get("last")} 报价昨收={q[0]["last_close"] if q else "?"} '
              f'财务流通={f.get("liutongguben", 0)/1e8:.2f}亿 日线{len(b)}根(最新c={b[-1]["close"] if b else "?"})')
    c.close()