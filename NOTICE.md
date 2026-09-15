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
