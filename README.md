# tdxdata

通达信（TDX）新版行情协议 Python 客户端 — 2026-09 协议逆向适配。

老 pytdx / mootdx / xmtdx 的协议 2026-09-10 起被通达信服务器拒绝（服务端协议改动：版本标识 + 命令族 + zlib 流式压缩）。tdxdata 是逆向新协议后的独立实现。

**A-share (CN) realtime quote client for TDX's 2026-09 protocol. Drop-in replacement path after pytdx stopped working.**

## 快速开始

```bash
pip install -e .
```

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

CLI 连通性自检：

```bash
tdxdata-probe                        # 探测 600519 的 snap/bars/quotes/finance
tdxdata-probe --codes 000001,600519 --host 101.35.121.35
```

## 功能

| 接口 | 命令 | 状态 |
|---|---|---|
| 分时快照（最新价+32-51点分时） | 0c09 | ✅ 深沪深+指数 |
| 历史K线（日/5min/15/30/60/1min/周/月） | 0x010c (GetSecurityBars) | ✅ 单只任意历史段 |
| 盘口报价（现价/昨收/高低/量/额/五档） | 0x010c (GetSecurityQuotes) | ✅ |
| 财务（流通/总股本/净利润/每股净资产） | 0c1f | ✅ |
| 多主站并发（43 IP 轮询、坏 IP 剔除） | — | ✅ 全市场快照 ~12-15 分钟 |
| 批量快照（单包多只） | 0c01 身份会话 | ⚠️ 服务端需 0c01 会话，已放弃（单只循环+并发替代） |
| 全量历史K线（单请求批量全市场） | — | ❌ 新版客户端用本地文件+增量，服务器无此接口（单只循环可拉任意股票） |

## 已知限制

- **每连接每请求固定 ~3s 延迟**（服务器行为）→ 用多连接并发摊掉，勿压单连接频率
- 单出口并发 >60 会触发出口级限流（热状态，需长冷却）→ 默认 43 连接
- 3 个主站 IP 连接即 reset（已从 servers.txt 剔除）
- 大数据量响应为 zlib 压缩流（小数据量明文），客户端已统一处理（`client.maybe_decompress`）
- 少数股票 5min 含 13:00 一根 bar（服务器行为，与旧 pytdx 主库一致）

## 协议要点（完整版见 docs/protocol.md）

```
TCP 7709 → 0c02(init) → 0c03(tdxlevel) → 数据请求
单只快照 = 0c09 0041 0300 2700 2700 d10f [market] [code6] + 29B 后缀
market: 0=深市 1=沪市（同 code 不同 market = 不同标的！）
历史K线 = 0x010c + 版本标识 18 7b 00 01（老 pytdx 命令仅改此标识即复用）
```

## 借用与版权

解码层部分逻辑参考 pytdx（MIT, rainx）——详见 [NOTICE.md](NOTICE.md)。协议逆向过程见 [docs/](docs/)（protocol.md / extractable.md / analysis_round1~3.md）。

## License

MIT — 详见 [LICENSE](LICENSE)。

> ⚠️ 仅供学习研究。行情数据版权归交易所所有；请遵守通达信服务条款，控制请求频率。
