# -*- coding: utf-8 -*-
"""帧 + zlib 流式解压核心（2026-09-14 逆向: 16B 帧头 + zlib 跨段数据）

服务器响应结构：
  段 = [16B 帧头 b1cb7400...][zlib 数据段]  （部分段无头，为压缩延续）
  解压采用流式（decompressobj + 自动切流），容忍帧边界残留。
"""
import zlib
from ..protocol import FRAME_MARK


class ZlibStreamDecoder:
    """把 TCP 载荷流解码为解压字节。

    用法：
        dec = ZlibStreamDecoder()
        for tcp_segment in connection_receive():
            dec.feed(payload_only(tcp_segment))
        data = dec.output
    """

    def __init__(self):
        self.output = bytearray()
        self._dobj = zlib.decompressobj()
        self._frame_buf = b""
        self._reset_count = 0

    # ponytail: 帧头剥离假设 16B；若正式协议头变长再调 FRAME_POSTFIX
    def feed(self, seg: bytes) -> None:
        """喂入一个 TCP 载荷（含帧头或纯延续）。"""
        if seg[:4] == FRAME_MARK:
            self._frame_buf += seg[16:]   # 有帧头 → 剥 16B
        else:
            self._frame_buf += seg        # 延续段全收
        self._flush_buf()

    def _flush_buf(self):
        try:
            dec = self._dobj.decompress(bytes(self._frame_buf))
            self.output += dec
            self._frame_buf = b""
            if self._dobj.eof:          # 一个 zlib 流结束 → 开新的
                self._reset_count += 1
                self._dobj = zlib.decompressobj()
        except zlib.error:
            # 帧内混入非压缩字节 → 丢弃坏帧，重新同步
            self._reset_count += 1
            self._frame_buf = b""
            self._dobj = zlib.decompressobj()

    @property
    def decoded(self) -> bytes:
        return bytes(self.output)