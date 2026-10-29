# -*- coding: utf-8 -*-
"""tdxdata — 通达信 2026-09 新版行情协议客户端

核心能力（全实测 2026-09-15）:
- snap: 分时快照（最新价 + 32-51 点当日分时，深沪深+指数）
- bars: 历史K线（日/5min/15/30/60/1min/周/月）  — 旧命令+新版本标识 18 7b 00 01
- quotes: 盘口报价（现价/昨收/高低/量/额/五档） — 旧格式原样可用
- finance: 财务（流通/总股本/净利润/每股净资产） — 0c1f
- 0c02/0c03 打底连接，无需 0c01 身份（批量接口需 0c01，已放弃）
"""
from .client import TdxClient, market_of, parse_snap
from .pool2 import Pool  # 0.2.0: 顶层导出并发池（含 finance_all），否则 import tdxdata; tdxdata.Pool 不可见

__version__ = "0.2.1"  # ponytail: 与 pyproject.toml 手工同步；tests 里有漂移断言兜底
__all__ = ["TdxClient", "Pool", "market_of", "parse_snap", "__version__"]