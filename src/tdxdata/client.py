# -*- coding: utf-8 -*-
"""客户端入口"""
from .transport.sync import SyncTransport
from .commands.auth import build_auth, parse_auth_response
from .commands.bars import build_bars_req


class TdxNovaError(Exception):
    pass


class TdxNovaClient:
    """通达信新版行情协议客户端（骨架版，明天盘中验证后定稿）"""

    def __init__(self, host: str, port: int = 7709, timeout: float = 8.0):
        self.transport = SyncTransport(host, port, timeout)

    def authenticate(self) -> dict:
        """tdxlevel 认证（0c03）"""
        self.transport.connect()
        self.transport.send(build_auth())
        resp = self.transport.recv()
        return parse_auth_response(resp)

    def request_code(self, code: str) -> bytes:
        """日线 K 线请求（0c01+新版本位）——响应格式见 commands/bars.py"""
        raw = b""
        try:
            while True:
                chunk = self.transport.recv()
                if not chunk:
                    break
                raw += chunk
        except TimeoutError:
            pass
        return self.transport.decoded

    def close(self) -> None:
        self.transport.close()