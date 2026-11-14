# -*- coding: utf-8 -*-
"""GetGbbq(0x000f) 股本变迁 / 除权除息 —— 2026-11-13 实测可用（无需 0c01 身份）

请求（21B）: 12B 帧头(Type=0x000f, len=0x000B) + Data(9B) = 01 00 + market(1) + code(6)
响应: 16B 帧头 + count(u16 LE)@[9:11] + 记录 × count
  每条 29B: market(1) + code(6) + 保留(1) + date(u32 LE, YYYYMMDD) + category(1) + 16B
  - category == 1（除权除息）: 4 × float32 LE = 分红(每10股派n元) / 配股价 / 送转(每10股) / 配股(每10股)
  - category 11/12（缩股）: 第 3 个 float32 为缩股比例
  - category 13/14（送权证）: 第 1、3 个 float32 有效
  - 其他（股本变化/增发等）: 4 × float32 = 股本（万股）——前流通/前总/后流通/后总

与客户端本地 `gbbq` 文件的记录**格式完全一致**（同 29B 布局），实测 001225 / 001285 /
001309 / 600519 四只与本地 gbbq 逐条一致（2026-11-13）。

category 取值（官网口径）: 1 除权除息 · 2 送配股上市 · 3 非流通股上市 · 4 未知股本变动
· 5 股本变化 · 6 增发新股 · 7 股份回购 · 8 增发新股上市 · 9 转配股上市 · 10 可转债上市
· 11 扩缩股 · 12 非流通股缩股 · 13 送认购权证 · 14 送认沽权证

协议帧格式参考 injoyai/tdx（MIT, protocol/model_gbbq.go），本实现独立重写 + 实测核对。
"""
import struct

from ..frame import TYPE_GBBQ, build_frame

CATEGORY_NAMES = {
    1: '除权除息', 2: '送配股上市', 3: '非流通股上市', 4: '未知股本变动', 5: '股本变化',
    6: '增发新股', 7: '股份回购', 8: '增发新股上市', 9: '转配股上市', 10: '可转债上市',
    11: '扩缩股', 12: '非流通股缩股', 13: '送认购权证', 14: '送认沽权证',
}


def build_xdxr_req(market: int, code: str, msg_id: int = 0) -> bytes:
    """构造除权除息请求帧（market: 0=深 1=沪）"""
    data = bytes([0x01, 0x00, market]) + code.encode()
    return build_frame(TYPE_GBBQ, data, msg_id=msg_id)


def parse_xdxr(body: bytes) -> list:
    """解析响应 body（已剥离 16B 帧头）→ [{'market','code','date','category','category_name','fenhong','peigujia','songzhuangu','peigu','shares'}]

    `date` 为 int（YYYYMMDD）；`fenhong`/`songzhuangu`/`peigu` 单位为「每 10 股」；
    `peigujia` 为配股价（元）。非除权除息类别的股本字段放 `shares`（万股）。
    """
    if len(body) < 11:
        return []
    count = struct.unpack_from('<H', body, 9)[0]
    bs = body[11:]
    out = []
    for _ in range(count):
        if len(bs) < 29:
            break
        market = bs[0]
        code = bs[1:7].decode('ascii', 'ignore')
        date = struct.unpack_from('<I', bs, 8)[0]
        cat = bs[12]
        rec = {
            'market': market,
            'code': code,
            'date': date,
            'category': cat,
            'category_name': CATEGORY_NAMES.get(cat, '未知'),
            'fenhong': 0.0,        # 分红（每10股派 n 元）
            'peigujia': 0.0,       # 配股价（元）
            'songzhuangu': 0.0,    # 送转股（每10股）
            'peigu': 0.0,          # 配股（每10股）
            'shares': None,        # 股本类类别才有：前流通/前总/后流通/后总（万股）
        }
        # ⚠️ 4 个字段一律 float32（2026-11-13 实测更正）：与 gbbq 文件同一编码；
        #    早期版本误按「uint32 + 自研 volume 解码」处理非除权除息类 → 股本恒为 0.0（0.2.6~0.2.9 的 bug）。
        #    实测对照：301233 20261112 cat=5 → (3937.61, 7176.68, 3937.61, 7231.82) 万股，
        #    与同股实时 finance 流通A股（39,376,101 股 = 3937.61 万股）一致。
        f1, f2, f3, f4 = struct.unpack_from('<ffff', bs, 13)
        if cat == 1:
            rec.update(fenhong=round(f1, 6), peigujia=round(f2, 6),
                       songzhuangu=round(f3, 6), peigu=round(f4, 6))
        elif cat in (11, 12):
            rec['songzhuangu'] = round(f3, 6)      # 缩股比例
        elif cat in (13, 14):
            rec['peigujia'] = round(f1, 6)         # 行权价
            rec['peigu'] = round(f3, 6)            # 份数
        else:
            rec['shares'] = (round(f1, 6), round(f2, 6), round(f3, 6), round(f4, 6))
        out.append(rec)
        bs = bs[29:]
    return out


def xdxr_of(body: bytes, category: int = 1) -> list:
    """只要某一类别的记录（默认除权除息），按日期升序"""
    return sorted([r for r in parse_xdxr(body) if r['category'] == category],
                  key=lambda r: r['date'])
