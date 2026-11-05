# -*- coding: utf-8 -*-
"""tdxdata 统一客户端入口

用法:
    c = TdxClient('101.35.121.35')
    c.connect()                       # 0c02 init + 0c03 tdxlevel（无需 0c01）
    c.snap('600519')                  # 分时快照（最新价 + 32-51 点当日分时）
    c.bars(9, '000059', 0, 10)        # 历史K线（9=日线 0=5min 3=60min 5=周 6=月 7/8=1min，4=日线变体）
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
    """0=深市 1=沪市 2=京市/北交所（2026-11-06 实测: 北交所须 market=2，
    0/1 服务器回 ret_count=0 空帧）
    - 京市: 920xxx 股票（北交所 2025 年起统一 920 号段，存量老代码 83/87/43
      已停用、m2 同样回空）、899xxx 指数（899050 北证50）、82xxxx（实测 821001
      有数据，解析自洽）
    - 沪市: 5/6 开头股票基金、88 板块指数、9 开头（999 上证指数别名/900 B股）
    ⚠️ 000001 双义: market=1 是上证指数，market=0 是平安银行"""
    if code.startswith(('82', '92', '899')):
        return 2
    if code.startswith(('5', '6', '88', '9')):
        return 1
    return 0


def is_index_code(market: int, code: str) -> bool:
    """指数代码判定（决定 K线记录是否带涨跌家数 4B 尾部）:
    沪市 000xxx 指数系列（000001 上证指数/000300 沪深300/000905 中证500）、
    88xxxx 板块指数全系（880/881/885/886 段）、999xxx；深市 399xxx
    （399001 深证成指/399006 创业板指）；京市 899xxx（899050 北证50，
    与沪指同款 12B 尾部布局，东货行情逐字段验证）。
    ⚠️ 000001 双义: market=1 是上证指数（指数布局），market=0 是平安银行（个股布局）"""
    if market == 1:
        return code.startswith(('000', '88', '999'))
    if market == 2:
        return code.startswith('899')
    return code.startswith('399')


def maybe_decompress(resp: bytes) -> bytes:
    """服务器对大数据量响应返回 zlib 压缩（小数据量明文），统一解压"""
    import zlib
    i = resp.find(b'\x78\x9c')
    if i >= 0:
        try:
            return resp[:i] + zlib.decompress(resp[i:])
        except Exception:
            pass
    return resp


class TdxClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = PORT, timeout: float = 4.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None
        self._eof = False

    def connect(self):
        """建立连接并完成 0c02/0c03 认证（幂等: 旧连接先关）。
        实测认证回包 ~70ms 单包收完，静默窗口 0.8s 足够，全程 ~1.3s"""
        self.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))
        self._eof = False
        self._send_wait(C02, 0.8)
        self._send_wait(build_auth(), 0.8)

    def close(self):
        """关闭连接；之后再调用 bars/snap 等会自动重连"""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def _send_wait(self, payload: bytes, secs: float = 0.8):
        self.sock.sendall(payload)
        time.sleep(0.08)
        self._recv(secs)

    def _recv(self, secs: float = 3.0) -> bytes:
        buf = b''
        end = time.time() + secs
        got = None
        while time.time() < end:
            # 每次 recv 的阻塞时长对齐静默窗口——旧实现固定 4s socket 超时,
            # 回包收完后最后一只 recv 干等满 4s,connect 因此慢 ~7s
            self.sock.settimeout(max(0.02, end - time.time()))
            try:
                ch = self.sock.recv(65536)
            except socket.timeout:
                break
            if not ch:
                self._eof = True   # 服务器已断连(空闲超时/网络断开)
                self.close()
                break
            buf += ch
            if got is None:
                got = time.time()
                end = min(end, got + 0.5)  # 首个数据后多等 0.5s 收残余 TCP 段（防半帧错位）
        return buf

    def _req(self, payload: bytes, secs: float = 3.0) -> bytes:
        """发送并接收响应；连接被服务器断开（空闲超时/网络抖动）时自动重连重试一次"""
        err = None
        for _ in (1, 2):
            if self.sock is None:
                self.connect()
            try:
                self.sock.settimeout(self.timeout)
                self.sock.sendall(payload)
                r = self._recv(secs)
            except OSError as e:    # 断管/被重置/发送超时: 连接已死
                err, r = e, b''
            else:
                err = None
            if err is None and (r or not self._eof):
                return r            # 拿到数据；或连接健在只是暂时无包
            self.close()            # 死连接: 重建后再试一次
        if err is not None:
            raise ConnectionError(f'{self.host}:{self.port} 请求失败(已自动重试一次): {err}') from err
        return r

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
        r = maybe_decompress(r)
        if len(r) <= 18:
            return []
        return parse_bars_response(r[16:], category, is_index=is_index_code(m, code))

    # ---- 盘口报价 ----
    def quotes(self, items):
        r = self._req(build_quotes_req(items))
        return parse_quotes(maybe_decompress(r))

    # ---- 财务 ----
    def finance(self, code: str, market: int = None):
        m = market if market is not None else market_of(code)
        r = self._req(build_finance_req(m, code))
        return parse_finance(maybe_decompress(r))

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