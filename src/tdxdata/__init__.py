# -*- coding: utf-8 -*-
"""tdxdata — 通达信 2026-09 新版行情协议客户端

核心能力（全实测）:
- snap: 分时快照（最新价 + 32-51 点当日分时，深沪深+指数）
- bars: 历史K线（日/5min/15/30/60/1min/周/月）  — 旧命令+新版本标识 18 7b 00 01
- quotes: 盘口报价（现价/昨收/高低/量/额/五档） — 旧格式原样可用
- finance: 财务（流通/总股本/净利润/每股净资产） — 0c1f
- xdxr: 除权除息（股本变迁）事件 — 0f 00，2026-11-13 新增，**无需 0c01 身份**
- bars_adjusted: K 线复权（仿射口径，与通达信桌面端对齐） — 2026-11-13 新增
- gbbq: 整表权息表（HTTP 下载 + 解密解析） — 2026-11-13 新增，**无需通达信客户端**
- 0c02/0c03 打底连接，无需 0c01 身份（批量接口需 0c01，已放弃）

权息 / 复权用法::

    from tdxdata import TdxClient, read_gbbq, events_of

    c = TdxClient('101.33.225.16'); c.connect()
    c.xdxr('001225')                                    # 协议查除权除息（免客户端）
    c.bars_adjusted('600519', count=20, adjust='qfq')   # 前复权日线
    recs = read_gbbq()                                  # HTTP 拉整表权息表（免客户端）
    events_of(recs, '600519')                           # 该股全部除权除息事件
    c.close()
"""
from .adjust import adjust_bars, adjust_prices, affine_coeffs, factors, round_half_up
from .client import TdxClient, market_of, parse_snap
from .gbbq import (GBBQ_URL, decrypt_record, decrypt_records,  # noqa: F401
                   download_gbbq, events_of, read_gbbq, to_map)
from .pool2 import Pool  # 0.2.0: 顶层导出并发池（含 finance_all），否则 import tdxdata; tdxdata.Pool 不可见

__version__ = "0.2.7"  # ponytail: 与 pyproject.toml 手工同步；tests 里有漂移断言兜底
__all__ = ["TdxClient", "Pool", "market_of", "parse_snap", "__version__",
           # 权息 / 复权（2026-11-13 新增）
           "GBBQ_URL", "download_gbbq", "read_gbbq", "decrypt_record", "decrypt_records",
           "events_of", "to_map", "adjust_bars", "adjust_prices", "factors",
           "affine_coeffs", "round_half_up"]
