# -*- coding: utf-8 -*-
"""并发池正式版: 46 IP 并发，每连接顺序拉 N 只（3s/只），全市场 ~5.5 分钟"""
import socket, time, struct, os, threading, random, sys

PORT = 7709
C02 = bytes.fromhex("0c0218940001030003000d0001")
C03 = bytes.fromhex("0c031899000120002000db0f7464786c6576656c000000295cf740110000000000000000000000000005")
SN_PREFIX = bytes.fromhex("0c090041030027002700d10f")
SN_SUFFIX = bytes.fromhex("0000000000000000000000000000000001001400000000010000000000")

def load_servers():
    p = os.path.join(os.path.dirname(__file__), 'servers.txt')
    with open(p) as f:
        return [l.strip() for l in f if l.strip()]

def snap_req(code: str, market: int) -> bytes:
    return SN_PREFIX + bytes([market, 0]) + code.encode() + SN_SUFFIX

def parse_snap(resp: bytes) -> dict:
    if len(resp) < 60:
        return {'ok': False, 'raw_len': len(resp)}
    data = resp
    compressed = False
    i789 = resp.find(b'\x78\x9c')
    if i789 >= 0:
        try:
            import zlib
            data = resp[:i789] + zlib.decompress(resp[i789:])
            compressed = True
        except Exception:
            pass
    if len(data) < 60:
        return {'ok': False, 'raw_len': len(resp), 'compressed': compressed}
    prices = []
    i = 50
    while i + 4 <= len(data):
        v = struct.unpack('<f', data[i:i+4])[0]
        if 0.1 < v < 100000:
            prices.append(round(v, 3)); i += 4
        else:
            i += 2
    return {'ok': True, 'last': prices[-1] if prices else None, 'prices': prices,
            'compressed': compressed, 'raw_len': len(resp)}

class Conn:
    def __init__(self, host):
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(4)
        self.sock.connect((host, PORT))
        for payload, wait in ((C02, 1.5), (C03, 1.5)):
            self.sock.sendall(payload)
            time.sleep(0.05)
            self._recv(wait)
    def _recv(self, secs):
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
    def snap(self, code, market):
        self.sock.sendall(snap_req(code, market))
        r = self._recv(3.5)
        return parse_snap(r)
    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

def worker(host, codes, results, idx):
    c = Conn(host)
    mine = []
    for code in codes:
        m = 1 if code.startswith(('6', '9')) else 0
        try:
            r = c.snap(code, m)
            mine.append((code, r.get('last'), r['ok']))
        except Exception as e:
            mine.append((code, None, False))
    results[idx] = mine
    c.close()


class Pool:
    """多主站并发快照池 — 每连接一个服务器，顺序拉取分配到的代码。

    服务器每连接每请求固定 ~3s → 多连接并发摊掉延迟。
    用法:
        p = Pool()              # 默认 43 主站并发
        p.snap('600519')        # 单只（走第一台服务器）
        rows = p.snap_all(codes)   # 全列表并发，返回 [(code, last, ok)]
    """

    def __init__(self, n_conn: int = 43):
        self.n_conn = n_conn
        self.servers = load_servers()
        if len(self.servers) < n_conn:
            self.servers = (self.servers * (n_conn // len(self.servers) + 1))[:n_conn]

    def snap(self, code: str, market: int = None) -> dict:
        """单只快照（走第一台服务器；失败自动换下一台）"""
        if market is None:
            market = 1 if code.startswith(('6', '9')) else 0
        for host in self.servers[:3]:
            try:
                c = Conn(host)
                r = c.snap(code, market)
                c.close()
                if r.get('ok') and r.get('last'):
                    return r
            except Exception:
                continue
        return {'ok': False, 'code': code}

    def snap_all(self, codes):
        """并发拉整个代码列表。返回 [(code, last, ok), ...] 保持输入顺序。"""
        results = {}
        chunk = len(codes) // self.n_conn + 1
        threads = []
        for i in range(self.n_conn):
            seg = codes[i * chunk:(i + 1) * chunk]
            if not seg:
                continue
            t = threading.Thread(target=worker, args=(self.servers[i], seg, results, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        flat = [v for sub in results.values() for v in sub]
        by_code = {c: (last, ok) for c, last, ok in flat}
        return [(c, *by_code.get(c, (None, False))) for c in codes]

if __name__ == '__main__':
    servers = load_servers()
    # 确定存在的代码（深沪白马混合）
    codes = ['000001', '000002', '000063', '000066', '000333', '000338', '000425', '000538', '000568', '000651',
             '000661', '000725', '000768', '000776', '000783', '000792', '000858', '000876', '000895', '000963',
             '002001', '002007', '002008', '002027', '002044', '002050', '002064', '002074', '002080', '002085',
             '002110', '002129', '002142', '002153', '002179', '002202', '002230', '002236', '002241', '002271',
             '002304', '002311', '002352', '002371', '002415', '300003', '300014', '300015', '300033', '300059',
             '600000', '600004', '600009', '600010', '600011', '600015', '600016', '600018', '600019', '600028',
             '600029', '600030', '600031', '600036', '600048', '600050', '600061', '600085', '600089', '600104',
             '600109', '600111', '600115', '600150', '600153', '600160', '600176', '600183', '600196', '600201',
             '600219', '600233', '600276', '600309', '600332', '600346', '600352', '600362', '600372', '600383',
             '600390', '600406', '600426', '600438', '600519', '600547', '600570', '600585', '600588', '600690']
    random.seed(1)
    random.shuffle(codes)
    n_threads = 12
    chunk = len(codes) // n_threads + 1
    results = {}
    t0 = time.time()
    threads = []
    for i in range(n_threads):
        seg = codes[i*chunk:(i+1)*chunk]
        if not seg:
            continue
        t = threading.Thread(target=worker, args=(servers[i], seg, results, i))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    el = time.time() - t0
    flat = [v for sub in results.values() for v in sub]
    ok = sum(1 for _, last, okk in flat if okk and last)
    fail = [(c, l) for c, l, okk in flat if not (okk and l)]
    print(f'{len(flat)} 只 / {len(results)} 连接并发: {el:.0f}s, 成功 {ok}/{len(flat)}')
    if fail:
        print(f'失败 {len(fail)} 只: {[c for c, _ in fail[:10]]}')
    print(f'吞吐: {ok/el:.2f} 只/s → 全市场 5000 只(46 连接) ≈ {5000/(ok/el)/60:.1f} 分钟')