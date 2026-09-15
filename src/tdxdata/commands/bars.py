# -*- coding: utf-8 -*-
"""数据请求命令（K 线/快照）

逆向结论（2026-09-14）:
- 请求 code 明文 ASCII
- 0c07 带 code 的请求（抓包: 0c07002900010f000f004705010000 + code6 + 000000）
- 明文批量快照请求（00...c002 + code 列表）
- 完整 800 条 K 线响应格式：明天盘中抓包定稿
"""
import struct


def build_code_request(code: str) -> bytes:
    """0c07 数据请求（抓包格式，code=6 位如 '000002'）"""
    assert len(code) == 6 and code.isdigit()
    return bytes.fromhex("0c07002900010f000f004705010000") + code.encode() + b"\x00\x00\x00"


def build_snapshot_request(codes: list[str]) -> bytes:
    """明文批量快照请求（骨架：code 列表，分隔 00）"""
    body = b"".join(c.encode() + b"\x00" for c in codes)
    return struct.pack("<6sHH", b"\x00" * 6, 0x02C0, 0x02C0) + b"\x10\x00d\x00\x00" + body