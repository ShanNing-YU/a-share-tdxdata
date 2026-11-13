# tdxdata

[![PyPI version](https://img.shields.io/pypi/v/tdxdata.svg)](https://pypi.org/project/tdxdata/)
[![Python versions](https://img.shields.io/pypi/pyversions/tdxdata.svg)](https://pypi.org/project/tdxdata/)
[![License](https://img.shields.io/github/license/ShanNing-YU/a-share-tdxdata.svg)](LICENSE)
[![PyPI downloads](https://img.shields.io/pypi/dm/tdxdata.svg)](https://pypi.org/project/tdxdata/)

通达信（TDX）新版行情协议 Python 客户端 — 2026-09 协议逆向适配。

老 pytdx / mootdx / xmtdx 的协议 2026-09-10 起被通达信服务器拒绝（服务端协议改动：版本标识 + 命令族 + zlib 流式压缩）。tdxdata 是逆向新协议后的独立实现。

**A-share (CN) realtime quote client for TDX's 2026-09 protocol.**

## 快速开始

```bash
pip install tdxdata
```

开发者从源码安装：克隆本仓库后 `pip install -e .`。

```python
from tdxdata import TdxClient

c = TdxClient()              # 默认连 101.35.121.35（43 主站之一，见 servers.txt）
c.connect()                  # 0c02 init + 0c03 tdxlevel 认证
c.snap('600519')             # 分时快照: 最新价 + 当日分时点
c.bars(9, '000059', 0, 100)  # 历史K线: 9=日线 0=5min 8=1min 6=周 7=月
c.quotes([(0, '000059')])    # 盘口报价: 现价/昨收/高低/量/额/五档
c.finance('000059')          # 财务: 流通/总股本/净利润/每股净资产
c.close()
```

全市场并发快照（多主站摊掉每请求 ~3s 延迟）：

```python
from tdxdata.pool2 import Pool

p = Pool()                   # 43 个主站 IP × 并发连接
r = p.snap('600519')         # 单只: {'last': 1277.56, 'prices': [32点分时...]}
rows = p.snap_all(['000001', '600519'])  # 并发全列表 → [(code, last, ok)]
```

支持深市 / 沪市 / 指数（market 自动推断，也可显式传）：

```python
p.snap('000001')                 # 平安银行（深 market=0）
p.snap('000001', market=1)       # 上证指数（沪 market=1）
p.snap('688981', market=1)       # 中芯国际（科创板）
```

权息（除权除息）与复权 —— 两条通道都**不需要通达信客户端**：

```python
from tdxdata import TdxClient, read_gbbq, events_of

c = TdxClient('101.33.225.16'); c.connect()
c.xdxr('600519')                                     # 协议查除权除息：分红/送转/配股事件
c.bars_adjusted('600519', count=20, adjust='qfq')     # 前复权日线（adjust 也可 'hfq'）
recs = read_gbbq()                                   # HTTP 拉整表权息表（20.8 万条 / 7417 只）
events_of(recs, '600519')                            # 该股全部除权除息事件
c.close()
```

复权为**仿射口径**（复权价 = A × 原始价 + B），与通达信桌面端对齐；成交量 / 成交额不复权。

CLI：

```bash
tdxdata-probe                        # 连通性自检（snap/bars/quotes/finance）
tdxdata-probe --codes 000001,600519 --host 101.35.121.35

tdxdata-qx xdxr 001225               # 按个股查除权除息（协议，免客户端）
tdxdata-qx gbbq --code 600519        # 下载整表权息表 + 列出该股事件（HTTP，免客户端）
tdxdata-qx adjust 600519 -n 20       # 近 20 根日线：原始 / 前复权 / 后复权对照
```

## 功能

| 接口 | 命令 | 状态 |
|---|---|---|
| 分时快照（最新价+32-51点分时） | 0c09 | ✅ 深沪深+指数 |
| 历史K线（日/5min/15/30/60/1min/周/月） | 0x010c (GetSecurityBars) | ✅ 单只任意历史段 |
| 盘口报价（现价/昨收/高低/量/额/五档） | 0x010c (GetSecurityQuotes) | ✅ |
| 财务（流通/总股本/净利润/每股净资产） | 0c1f | ✅ |
| **除权除息（股本变迁）** | 0f 00 | ✅ 按个股，无需客户端（2026-11-13 新增） |
| **前/后复权 K 线** | — | ✅ 仿射口径，与通达信桌面端对齐（2026-11-13 新增） |
| **整表权息表（20.8 万条/7417 只）** | HTTP dbf 包 | ✅ 官方数据站直下，无需客户端（2026-11-13 新增） |
| 多主站并发（43 IP 轮询、坏 IP 剔除） | — | ✅ 全市场快照 ~12-15 分钟 |
| 批量快照（单包多只） | 0c01 身份会话 | ⚠️ 服务端需 0c01 会话，已放弃（单只循环+并发替代） |
| 全量历史K线（单请求批量全市场） | — | ❌ 新版客户端用本地文件+增量，服务器无此接口（单只循环可拉任意股票） |

## 已知限制

- **每连接每请求固定 ~3s 延迟**（服务器行为）→ 用多连接并发摊掉，勿压单连接频率
- 单出口并发 >60 会触发出口级限流（热状态，需长冷却）→ 默认 43 连接
- 3 个主站 IP 连接即 reset（已从 servers.txt 剔除）
- 大数据量响应为 zlib 压缩流（小数据量明文），客户端已统一处理（`client.maybe_decompress`）
- 少数股票 5min 含 13:00 一根 bar（服务器行为，与旧 pytdx 主库一致）
- 无效代码（不存在的股票代码）返回未定义数据（bars 可能含乱码日期、quotes 可能重定向到其他代码），调用方需保证传入有效代码
- quotes 对基金（ETF）价格精度为 0.001 元 → 返回价 ×10（510300 实际 4.523 会显示 45.23，pytdx 同款行为）；基金行情请用 snap/bars（float32 直读，精度正确）
- 市场自动判断规则：5/6/9 开头=沪（5 基金/6 A/9 B），0/1/2/3 开头=深（0 A/1 基金/2 B/3 创业板）；北交所(4/8/92)暂不支持

## 协议要点（完整版见 docs/protocol.md）

```
TCP 7709 → 0c02(init) → 0c03(tdxlevel) → 数据请求
单只快照 = 0c09 0041 0300 2700 2700 d10f [market] [code6] + 29B 后缀
market: 0=深市 1=沪市（同 code 不同 market = 不同标的！）
历史K线 = 0x010c + 版本标识 18 7b 00 01（老 pytdx 命令仅改此标识即复用）
```

## 借用与版权

- 解码逻辑参考/移植自 **pytdx**（MIT, rainx）—— 见 `NOTICE.md`（含许可证全文）
- 权息/复权部分参考 **injoyai/tdx**（MIT）的帧布局、除权除息请求布局与仿射复权口径；
  整表权息表的 HTTP 数据源地址来自 **jing2uo/tdx2db** —— 实现均为本项目独立重写，见 `NOTICE.md`
- gbbq 解密密钥表（客户端常量）与格式分析来自公开社区资料 —— 见 `NOTICE.md`

## License

MIT — 详见 [LICENSE](LICENSE)。

> ⚠️ 仅供学习研究。行情数据版权归交易所所有；请遵守通达信服务条款，控制请求频率。
