# -*- coding: utf-8 -*-
"""tdxlevel 认证命令（0c03，抓包格式）"""
import struct
from ..protocol import AUTH_LOAD


def build_auth(version_float: float = 7.92) -> bytes:
    """构造 tdxlevel 认证请求。

    抓包原样: 0c03 1899 0001 2000 2000 db0f 'tdxlevel' 000000 <float> 110000...
    version_float 为客户端版本号（抓包 0x40f75c29 ≈ 7.918）
    """
    return struct.pack("!I", 0) and AUTH_LOAD  # 先用抓包原样，明天按需参数化

def parse_auth_response(buf: bytes) -> dict:
    """解析认证响应（b1cb7400 0c03... 195B）。"""
    if len(buf) < 8 or buf[4:6] != b"\x0c\x03":
        return {"ok": False, "raw": buf[:16].hex()}
    # b300 b300 = 行情级别数量？（179）
    level = struct.unpack("<H", buf[16:18])[0] if len(buf) >= 18 else 0
    return {"ok": True, "level_hint": level, "raw_len": len(buf)}