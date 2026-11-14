# -*- coding: utf-8 -*-
"""K 线分页取数 —— 绕开服务器单请求 800 根上限。

背景（2026-11-14 实测）:
- 服务器对 bars() 单次请求最多返回 **800 根**；start 是从最新一根往前数的偏移，
  即 start=0 取最新 800 根、start=800 取再往前 800 根，以此类推。
- 现在 client.bars() 把 count 直接透传，count>800 时服务器回空帧 → 静默返回 []，
  调用方误判成「该标的历史数据为空」。日线与分钟线（category 0..8）同受此限制。

为何必须分页:
    一次请求最多 800 根，要拿超过 800 根就必须按 (0,800)、(800,800)、… 逐块拉取，
    直到凑满目标条数或某块返回不足 chunk（说明已到最早的历史）。

为何要跨块去重:
    相邻两块的边界行可能重复出现（服务器对 start 的边界包含语义不完全精确），
    直接拼接会得到重复 K 线；因此按 'datetime' 去重（保留首次出现），
    再按 datetime 升序排序，保证返回的是连续、无重复、时间递增的序列。

本模块只提供纯函数，不碰 socket / client.py 的接线（由调用方决定何时启用）。
"""


def fetch_paged(fetch_once, count: int, chunk: int = 800):
    """分页取数：把一次 ``fetch_once(start, n)`` 展开成多块请求。

    :param fetch_once: 单块取数函数，签名 ``fetch_once(start, n) -> list[dict]``，
        start 为偏移、n 为条数；每条记录必须含 'datetime' 字段。
    :param count: 目标总条数。
    :param chunk: 每块条数（默认 800，等于服务器单请求上限）。
    :return: list[dict]，见下：
        - count <= 0        → 返回 []，且**不调用** fetch_once；
        - count <= chunk    → 只调一次 ``fetch_once(0, count)`` 并**原样返回**；
        - count >  chunk    → 依次取 ``(0, chunk)``、``(chunk, chunk)``… 直到凑满
          count 或某块返回不足 chunk（服务器到底），按取值顺序拼接、按 'datetime'
          去重（保留首次出现）、按 datetime 升序排序、最多返回 count 条。
        数据不足时不抛异常，有多少返回多少。
    """
    if count <= 0:
        return []
    if count <= chunk:
        return fetch_once(0, count)

    out = []
    start = 0
    while len(out) < count:
        batch = fetch_once(start, chunk)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < chunk:          # 不足一块 → 已到历史尽头
            break
        start += chunk

    # 跨块去重（保留首次出现）→ 升序排序 → 截到 count 条
    seen = set()
    deduped = []
    for rec in out:
        key = rec.get('datetime')
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    deduped.sort(key=lambda r: r.get('datetime') or '')
    return deduped[:count]
