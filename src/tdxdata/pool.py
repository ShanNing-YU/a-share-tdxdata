# -*- coding: utf-8 -*-
"""tdxdata 多 IP 轮询客户端（不限流：单 IP ~30-50 只后限流，46 主站轮询分散）"""
import socket, time, struct, random, os

HOST_DEFAULT = '101.33.225.16'
PORT = 7709
C02 = bytes.fromhex("0c0218940001030003000d0001")
C03 = bytes.fromhex("0c031899000120002000db0f7464786c6576656c000000295cf740110000000000000000000000000005")
SN_PREFIX = bytes.fromhex("0c090041030027002700d10f")
SN_SUFFIX = bytes.fromhex("0000000000000000000000000000000001001400000000010000000000")
_SERVERS = None

def load_servers():
    global _SERVERS
    if _SERVERS is None:
        p = os.path.join(os.path.dirname(__file__), 'servers.txt')
        with open(p) as f:
            _SERVERS = [l.strip() for l in f if l.strip()]
    return _SERVERS

def market_of(code: str) -> int:
    return 1 if code.startswith(('6', '9')) else 0

def build_snap(code: str, market: int) -> bytes:
    return SN_PREFIX + bytes([market, 0]) + code.encode() + SN_SUFFIX

def parse_snap(resp: bytes) -> dict:
    if len(resp) < 60:
        return {'ok': False, 'raw_len': len(resp)}
    code = resp[18:24].decode(errors='ignore')
    market = resp[17]
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
            'last': prices[-1] if prices else None}


class _Conn:
    def __init__(self, host, timeout=3.0):
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((host, PORT))
        self._recv()
        self.sock.sendall(C02)
        self._recv()
        self.sock.sendall(C03)
        self._recv()
        self.count = 0

    def _recv(self, secs=0.8):
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
                end = min(end, got + 0.15)  # 首个数据后最多再等 0.15s 收残余 TCP 段
        return buf

    def snap(self, code, market):
        self.sock.sendall(build_snap(code, market))
        r = self._recv(2.0)
        self.count += 1
        return parse_snap(r)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class Pool:
    """46 主站轮询：每连接 N 只后换 IP。ponytail: 简单轮询; 若要优先健康IP再加重试队列"""

    def __init__(self, max_per_conn=30, interval=0.2):
        self.servers = load_servers()
        random.shuffle(self.servers)
        self.max_per_conn = max_per_conn
        self.interval = interval
        self.conn = None
        self.si = 0
        self.dead = set()

    def _next_conn(self):
        for _ in range(len(self.servers)):
            host = self.servers[self.si % len(self.servers)]
            self.si += 1
            if host in self.dead:
                continue
            try:
                c = _Conn(host)
                print(f'  [pool] conn {host} ok')
                return c
            except Exception as e:
                print(f'  [pool] {host} dead: {e}')
                self.dead.add(host)
        raise RuntimeError('no alive server')

    def snap(self, code, market=None):
        if market is None:
            market = market_of(code)
        if self.conn is None or self.conn.count >= self.max_per_conn:
            if self.conn:
                self.conn.close()
            self.conn = self._next_conn()
        try:
            r = self.conn.snap(code, market)
        except (socket.timeout, ConnectionError, OSError):
            self.dead.add(self.conn.host)
            self.conn.close()
            self.conn = self._next_conn()
            r = self.conn.snap(code, market)
        time.sleep(self.interval)
        return r

    def close(self):
        if self.conn:
            self.conn.close()


if __name__ == '__main__':
    tests = ['000001', '000002', '600519', '688981', '601319']
    p = Pool(max_per_conn=10)
    t0 = time.time()
    for code in tests:
        r = p.snap(code)
        print(f'{code}: ok={r["ok"]} last={r.get("last")}')
    print(f'5 只耗时 {time.time()-t0:.1f}s, servers={len(p.servers)}')
    p.close()