# -*- coding: utf-8 -*-
"""
超跌反弹选股扫描
找「中长期趋势向上 + 近期短期超跌」的股票，适合博短期反弹
"""
import time

import pandas as pd

import config
from data import fetcher
from screener import filters, market_status


def _f(v):
    """安全转 float，None/NaN 返回 None"""
    try:
        if v is None:
            return None
        fv = float(v)
        if pd.isna(fv):
            return None
        return round(fv, 2)
    except (TypeError, ValueError):
        return None


def scan_dip(top_n=None, candidate_limit=None, verbose=True, progress=None,
             trend_ma=60, dip_days=5, dip_threshold=-0.10,
             take_profit=0.08, stop_loss=0.05):
    """
    超跌反弹选股扫描
    :param top_n: 最终推荐数量
    :param candidate_limit: 深度分析的候选数量
    :param trend_ma: 判断趋势的均线周期（默认60日）
    :param dip_days: 短期超跌的回看天数（默认5日）
    :param dip_threshold: 短期跌幅阈值（默认-10%）
    :param take_profit: 止盈比例（默认+8%）
    :param stop_loss: 止损比例（默认-5%）
    :return: dict，含 market、recommendations 列表
    """
    top_n = top_n or config.TOP_N
    candidate_limit = candidate_limit or config.CANDIDATE_LIMIT

    def log(msg):
        if verbose:
            print(msg)
        if progress:
            progress(msg)

    # 1. 大盘判断
    log("正在判断大盘状态...")
    market = market_status.judge_market()
    log(f"  => {market['state']}")

    # 2. 全市场扫描
    log("正在获取全市场行情快照...")
    spot = fetcher.get_all_spot()
    log(f"  => 共 {len(spot)} 只股票")

    # 3. 基础过滤
    log("正在过滤股票池（排除ST/停牌/涨跌停/流动性不足）...")
    pool = filters.filter_spot(spot)
    log(f"  => 过滤后剩余 {len(pool)} 只")

    if pool.empty:
        return {"market": market, "recommendations": []}

    # 4. 粗筛：按成交额取前 N 只（保证流动性，控制拉历史数据的数量）
    pool = pool.sort_values("amount", ascending=False).head(candidate_limit * 4)
    log(f"  => 初筛候选（按成交额）：{len(pool)} 只")

    # 5. 深度筛选（拉历史数据，精确判断趋势 + 超跌）
    log(f"正在深度分析：趋势向上({trend_ma}日) + 超跌(近{dip_days}日跌{dip_threshold*100:.0f}%)...")
    results = []
    hist_start = (pd.Timestamp.today() - pd.Timedelta(days=config.HISTORY_DAYS)).strftime("%Y%m%d")
    for i, (_, row) in enumerate(pool.iterrows(), 1):
        code = row["code"]
        name = row.get("name", code)
        try:
            df = fetcher.get_stock_daily(code, start_date=hist_start)
            r = _analyze(df, row, trend_ma, dip_days, dip_threshold,
                         take_profit, stop_loss)
            if r is not None:
                results.append(r)
        except Exception as e:
            if verbose:
                print(f"  [跳过] {code} {name}: {e}")
        if i % 20 == 0:
            log(f"  已分析 {i}/{len(pool)} 只，命中 {len(results)} 只...")
        time.sleep(0.03)

    # 6. 排序输出
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_n]

    return {"market": market, "recommendations": results, "trend_ma": trend_ma}


def _analyze(df, row, trend_ma, dip_days, dip_threshold, take_profit, stop_loss):
    """分析单只股票是否满足超跌反弹条件，满足则返回结果 dict，否则返回 None"""
    if df is None or len(df) < trend_ma + 10:
        return None

    close = df["close"].astype(float)
    price = _f(row.get("price"))
    if price is None:
        price = float(close.iloc[-1])

    # 1. 趋势向上：均线最新值 > 约5个交易日前（均线持续上行）
    ma = close.rolling(trend_ma, min_periods=1).mean()
    if len(ma) < 10:
        return None
    ma_now = float(ma.iloc[-1])
    ma_prev = float(ma.iloc[-6])
    if not ma_now > ma_prev:
        return None

    # 2. 短期超跌：近 dip_days 日累计跌幅 <= 阈值
    if len(close) < dip_days + 1:
        return None
    dip = float(close.iloc[-1] / close.iloc[-(dip_days + 1)] - 1)
    if dip > dip_threshold:
        return None

    # 3. 打分：趋势强度 + 超跌质量
    ma_chg = ma_now / ma_prev - 1
    trend_score = min(20.0, max(0.0, ma_chg * 200))  # 均线近5日涨幅映射 0-20

    if -0.20 <= dip <= dip_threshold:
        dip_score = 20.0   # 适度超跌，反弹概率高
    elif -0.30 <= dip < -0.20:
        dip_score = 15.0   # 较深超跌
    else:
        dip_score = 8.0    # 过深，趋势可能已破坏

    score = 50.0 + trend_score + dip_score

    # 4. 输出
    reasons = [
        f"{trend_ma}日均线向上",
        f"近{dip_days}日跌 {dip*100:.1f}%",
    ]
    risks = []
    if dip < -0.25:
        risks.append("短期跌幅过深，反弹可能只是反抽")

    return {
        "code": str(row["code"]).zfill(6),
        "name": row.get("name", row["code"]),
        "price": round(price, 2),
        "pct_chg": _f(row.get("pct_chg")),
        "dip_pct": round(dip * 100, 2),
        "trend": f"{trend_ma}日均线向上",
        "take_profit": round(price * (1 + take_profit), 2),
        "stop_loss": round(price * (1 - stop_loss), 2),
        "score": round(score, 1),
        "reasons": reasons,
        "risks": risks,
    }
