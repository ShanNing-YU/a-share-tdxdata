# Third-Party Notices

本项目（tdxdata）为 MIT License，但部分解码逻辑参考/移植自第三方开源项目。依据各项目许可证要求，特此声明：

## pytdx (MIT License)

- 仓库: https://github.com/rainx/pytdx （作者 rainx，已归档）
- 许可证: MIT — Copyright (c) rainx
- 借用内容:
  - `src/tdxdata/commands/quotes.py` — `get_price()` 变长整数(带符号)解码函数
  - `src/tdxdata/commands/bars.py` — 历史K线响应解码思路（日期/差分价格/vol/amount 布局与 `GetSecurityBars.parseResponse` 等价，tdxdata 独立实现请求构造）
- 用途: 旧命令（bars/quotes/finance）在 2026-09 新版协议服务器上仅需改版本标识 `08 64 01 01 → 18 7b 00 01` 即可原样复用，因此解码层沿用经过验证的 pytdx 实现，请求构造与协议适配为 tdxdata 独立逆向成果。

pytdx 的 MIT 许可证全文：

```
MIT License

Copyright (c) rainx

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 协议逆向说明

TCP 7709 协议本身的版本标识、命令族（0c02 init / 0c03 tdxlevel / 0c09 snapshot / 0c1f finance / 0x010c 行情命令）、响应 zlib 流式压缩等为 tdxdata 通过抓包逆向所得（见 `docs/analysis_round1~3.md`），不属第三方代码。

## injoyai/tdx (MIT License)

- 仓库: https://github.com/injoyai/tdx
- 许可证: MIT
- 借用内容:
  - `src/tdxdata/frame.py` — 请求/响应帧布局（`0c` 前缀 + MsgID/Control/长度/Type；响应 `b1cb7400` + 16B 头）
  - `src/tdxdata/commands/xdxr.py` — 除权除息（`Type=0x000f`）请求数据布局与响应记录解析规则
  - `src/tdxdata/adjust.py` — 前后复权的**仿射口径**（`price_adj = A × raw + B`）与三个口径坑
    （纯比例在现金分红时偏离桌面端 / 事件按日期位置施加 / 丢弃 ex-day 晚于最新交易日的未生效分红）
- 说明: 上述文件的实现为本项目独立重写（含离线单测），并逐字节/逐条实测核对；未复制其源码。

## jing2uo/tdx2db

- 仓库: https://github.com/jing2uo/tdx2db
- 借用内容: `gbbq` 权息表的 **HTTP 数据源地址**（`http://www.tdx.com.cn/products/data/data/dbf/gbbq.zip`）
- 说明: 仅使用公开数据源地址；下载、解密（密钥表源自 pytdx）、解析均为本项目实现。

## gbbq 文件格式与解密密钥表

- `src/tdxdata/gbbq_keys.py` 中的密钥表（4176 字节）为通达信客户端常量，第三方实现（pytdx `reader/gbbq_reader.py`）均直接引用；
  格式分析（29 字节/条 = 前 24 字节加密 + 后 5 字节明文，3DES 族查表）来自公开的社区分析文章。
