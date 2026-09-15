# -*- coding: utf-8 -*-
"""tdxdata — 通达信新版行情协议客户端（2026-09 协议逆向成果）

协议要点（逆向自 2026-09-14 抓包）:
- TCP 7709，老框架 + 新版本标识
- 认证: tdxlevel (0c03) + 版本 float
- 响应: 16B 帧头 + zlib 流式数据（跨段），解压后为行情文本
- 请求 code 明文 ASCII
"""
from .client import TdxNovaClient, TdxNovaError

__version__ = "0.1.0"
__all__ = ["TdxNovaClient", "TdxNovaError", "__version__"]