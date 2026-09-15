# -*- coding: utf-8 -*-
"""tdxlevel 认证命令（0c03，抓包格式）"""
import struct
from ..protocol import AUTH_LOAD


def build_auth() -> bytes:
    """构造 tdxlevel 认证请求（抓包原样 42B，实测才能过认证）。

    0c03 1899 0001 2000 2000 db0f 'tdxlevel' 00000000 <float 7.918> 11 00...00 05
    ⚠️ 注意必须 42B（AUTH_LOAD 曾少 1B 导致服务器不响应）
    """
    return bytes.fromhex(
        "0c031899000120002000db0f7464786c6576656c"
        "000000295cf740110000000000000000000000000005"
    )

def parse_auth_response(buf: bytes) -> dict:
    """解析认证响应（b1cb7400 0c03... 195B）。"""
    if len(buf) < 8 or buf[4:6] != b"\x0c\x03":
        return {"ok": False, "raw": buf[:16].hex()}
    # b300 b300 = 行情级别数量？（179）
    level = struct.unpack("<H", buf[16:18])[0] if len(buf) >= 18 else 0
    return {"ok": True, "level_hint": level, "raw_len": len(buf)}