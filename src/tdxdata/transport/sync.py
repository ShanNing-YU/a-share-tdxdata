# -*- coding: utf-8 -*-
"""同步 TCP 传输（帧接收 + 认证序列）"""
import socket
from ..codec.stream import ZlibStreamDecoder


class SyncTransport:
    def __init__(self, host: str, port: int = 7709, timeout: float = 8.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.decoder = ZlibStreamDecoder()

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def send(self, data: bytes) -> None:
        assert self.sock
        self.sock.sendall(data)

    def recv(self) -> bytes:
        """收一段 TCP 数据（帧），喂流式解码器，返回原始段。"""
        assert self.sock
        data = self.sock.recv(65536)
        if data:
            self.decoder.feed(data)
        return data

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

    @property
    def decoded(self) -> bytes:
        return self.decoder.decoded