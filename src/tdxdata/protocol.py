# -*- coding: utf-8 -*-
"""协议常量与命令码（2026-09-14 抓包逆向）"""

# TCP 端口（通达信标准行情服务器）
DEFAULT_PORT = 7709

# 版本标识（服务器校验关键字段，老库 0x01016408 已被拒）
# 抓包新客户端: 18 7b 00 01（小端 0x01007b18）
VERSION_FLAG = 0x01007B18
# 老库值（存档对照）
VERSION_FLAG_OLD = 0x01016408

# 帧/长度字段（抓包: 1a 01 1a 01；子类型 0b 00）
FRAME_LEN = 0x011A
SUBTYPE = 0x000B

# 命令族（抓包观察）
CMD_HEARTBEAT = 0x0C00       # 12B 心跳: 0c00...
CMD_INIT = 0x0C01            # 74B 加密初始化（会话上下文，用途待定）
CMD_AUTH = 0x0C03            # tdxlevel 认证
CMD_FILE_REQ = 0x0C04        # 文件下载请求（infoharbor_spec.cfg 等）
CMD_BARS = 0x0C07            # 数据请求（带明文 code）— ⚠️ 实际 bars 走 0x010c 命令族，此常量仅为抓包观察存档
CMD_SNAPSHOT = 0x0000        # 明文批量快照请求（00...c002 + code 列表）

# 认证负载见 commands/auth.py build_auth()（42B 正确版；此处不再存档防漂移）

# 帧头标记（响应）
FRAME_MARK = b"\xb1\xcb\x74\x00"