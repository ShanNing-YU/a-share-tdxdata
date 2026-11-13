# -*- coding: utf-8 -*-
"""协议帧构造与响应拆分（2026-11-13 新增）

请求帧（12B 头 + Data，实测自活服务器）:
    0c | MsgID(u32 LE) | Control(1) | len(u16 LE) | len(u16 LE) | Type(u16 LE) | Data
    其中 len = len(Data) + 2；Control 目前观察到恒为 0x01（含义未知）

响应帧（16B 头 + Data，Data 可能 zlib 压缩）:
    b1cb7400 | Control(1) | MsgID(4) | ?(1) | Type(u16 LE) | ZipLen(u16 LE) | Len(u16 LE) | Data
    ZipLen == Len → 未压缩；否则 Data 为 zlib（ZipLen 为压缩长度）

帧格式来源：injoyai/tdx（MIT）protocol/frame.go，本实现独立重写并逐字节实测核对
（`0c02`/`0c03`/`0f 00` 请求均可原样构造，服务端正常响应）。
"""
import struct
import zlib

PREFIX = 0x0C                 # 请求帧头
RESP_MARK = bytes.fromhex('b1cb7400')   # 响应帧头
CONTROL_DEFAULT = 0x01

# 常用请求类型（Type 字段，u16 LE）
TYPE_CONNECT = 0x000D
TYPE_HEART = 0x0004
TYPE_GBBQ = 0x000F            # 股本变迁（除权除息）
TYPE_COUNT = 0x044E
TYPE_CODE = 0x0450
TYPE_KLINE = 0x052D
TYPE_QUOTE = 0x053E


def build_frame(type_: int, data: bytes, msg_id: int = 0,
                control: int = CONTROL_DEFAULT, prefix: int = PREFIX) -> bytes:
    """构造请求帧；len 字段 = len(data) + 2（与实测一致）"""
    ln = len(data) + 2
    return (bytes([prefix]) + struct.pack('<I', msg_id) + bytes([control])
            + struct.pack('<HH', ln, ln) + struct.pack('<H', type_) + data)


def split_response(raw: bytes):
    """拆响应帧 → (Type, Data)；Data 若为 zlib 则已解压。

    返回 (None, raw) 当 raw 不是标准响应帧（例如部分老命令的明文响应）。
    """
    if len(raw) < 16 or raw[:4] != RESP_MARK:
        return None, raw
    typ = struct.unpack_from('<H', raw, 10)[0]
    zip_len, ln = struct.unpack_from('<HH', raw, 12)
    body = raw[16:16 + zip_len]
    if zip_len != ln:
        try:
            body = zlib.decompress(body)
        except Exception:
            pass
    return typ, body
