# tdxdata

通达信（TDX）新版行情协议 Python 客户端 — 2026-09 协议逆向适配。

老 pytdx / mootdx / xmtdx 的协议 2026-09-10 起被通达信服务器拒绝（服务端协议改动：版本标识 + 命令族 + zlib 流式压缩）。tdxdata 是逆向新协议后的独立实现。

**A-share (CN) realtime quote client for TDX's 2026-09 protocol. Drop-in replacement path after pytdx stopped working.**

## 快速开始

```bash
pip install -e .
```

```python
from tdxdata.pool2 import Pool

p = Pool()              # 43 个主站 IP × 并发连接，自动避开坏 IP
r = p.snap('600519')    # 贵州茅台
print(r['last'])        # 最新价 1277.56
print(r['prices'])      # 当日 32 个分时价格点
```

支持深市 / 沪市 / 指数：
```python
p.snap('000001')                 # 平安银行（深）
p.snap('000001', market=1)       # 上证指数（沪 market=1）
p.snap('688981', market=1)       # 中芯国际（科创板）
```

## 功能

- ✅ 单只快照（分时 32 点 + 最新价）— 深沪深 + 指数全部可用
- ✅ 多主站并发（43 IP 自动轮询、坏 IP 剔除），全市场 ~12-15 分钟
- ✅ tdxlevel 认证（0c03）自动完成
- ⚠️ 批量快照（704 只/批）— 逆向中（疑似依赖 0c01 身份会话，见 docs/protocol.md）
- ❌ 全量历史 K 线 — 新版客户端用本地文件+增量，服务器无此接口

## 已知限制

- **每连接每请求固定 ~3s 延迟**（服务器行为）→ 用多连接并发摊掉，勿压单连接频率
- 单出口并发 >60 会触发出口级限流（热状态，需长冷却）→ 默认 43 连接
- 3 个主站 IP 连接即 reset（已从 servers.txt 剔除）

详见 [docs/protocol.md](docs/protocol.md)。

## 协议要点（完整版见 docs/protocol.md）

```
TCP 7709 → 0c02(init) → 0c03(tdxlevel) → 数据请求
单只快照 = 0c09 0041 0300 2700 2700 d10f [market] [code6] + 29B 后缀
market: 0=深市 1=沪市（同 code 不同 market = 不同标的！）
响应 = 16B 帧头 + 32 × float32 分时价格
```

## 逆向过程

逆向研究日志（抓包分析、踩坑、限流实测）在 [docs/](docs/)：
- `protocol.md` — 定稿协议文档
- `batch_daily_reverse_guide.md` — 批量日线接口逆向指南
- `analysis_round1~3.md` — 三轮逆向过程记录

## License

MIT

> ⚠️ 仅供学习研究。行情数据版权归交易所所有；请遵守通达信服务条款，控制请求频率。