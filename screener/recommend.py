# -*- coding: utf-8 -*-
"""
选股推荐：编排整个流程
大盘判断 -> 全市场扫描 -> 过滤 -> 粗筛 -> 深度技术打分 -> 排序输出
"""
import time

import pandas as pd

import config
from data import fetcher
from screener import dip_scanner, filters, market_status, scorer, signals


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


def recommend(top_n=None, candidate_limit=None, style=None, verbose=True,
              progress=None, mode="general"):
    """
    主推荐流程
    :param top_n: 最终推荐数量
    :param candidate_limit: 深度技术打分的候选数量（拉历史数据的股票数）
    :param style: 强制指定推荐风格（aggressive/defensive/balanced），None 则自动
    :param progress: 可选进度回调 progress(message)，用于 Web 端实时显示
    :param mode: 推荐模式，"general" 综合推荐 / "dip" 超跌反弹(60日) / "dip120" 超跌反弹(120日半年线)
    :return: dict，含 market、recommendations 列表
    """
    # 超跌反弹模式走独立扫描器
    if mode in ("dip", "dip120"):
        trend_ma = 120 if mode == "dip120" else 60
        return dip_scanner.scan_dip(
            top_n=top_n, candidate_limit=candidate_limit,
            verbose=verbose, progress=progress, trend_ma=trend_ma)

    top_n = top_n or config.TOP_N
    candidate_limit = candidate_limit or config.CANDIDATE_LIMIT

    def log(msg):
        if verbose:
            print(msg)
        if progress:
            progress(msg)

    # 1. 全市场扫描（同时复用给大盘宽度判断，避免重复请求）
    log("正在获取全市场行情快照...")
    spot = fetcher.get_all_spot()
    log(f"  => 共 {len(spot)} 只股票")

    # 2. 大盘判断
    log("正在判断大盘状态...")
    market = market_status.judge_market(spot=spot)
    log(f"  => {market['state']}")

    # 3. 过滤
    log("正在过滤股票池（排除ST/停牌/涨跌停/流动性不足）...")
    pool = filters.filter_spot(spot)
    log(f"  => 过滤后剩余 {len(pool)} 只")

    if pool.empty:
        return {"market": market, "recommendations": []}

    # 4. 粗筛（只用快照，快）
    log("正在粗筛（估值+动量+换手）...")
    pool["_rough_score"] = 0.0
    pool["_rough_reasons"] = None
    for idx, row in pool.iterrows():
        s, _ = scorer.rough_score(row)
        pool.at[idx, "_rough_score"] = s
    pool = pool.sort_values("_rough_score", ascending=False).head(candidate_limit)

    # 5. 深度技术打分（拉历史数据）
    log(f"正在对前 {len(pool)} 只候选做深度技术分析（拉取历史数据）...")
    results = []
    style = style or market["style"]
    hist_start = (pd.Timestamp.today() - pd.Timedelta(days=config.HISTORY_DAYS)).strftime("%Y%m%d")
    try:
        benchmark = fetcher.get_index_daily("sh000001", start_date=hist_start)
    except Exception:
        benchmark = None
    for i, (_, row) in enumerate(pool.iterrows(), 1):
        code = row["code"]
        name = row.get("name", code)
        try:
            df = fetcher.get_stock_daily(code, start_date=hist_start)
            sigs = signals.detect_signals(df)
            features = scorer.features_from_history(df, benchmark=benchmark)
            chg60 = features.get("ret60", row.get("60日涨跌幅"))
            tech_names = {s["name"] for s in sigs}
            if "放量突破" in tech_names: features["technical_score"] = min(1.0, features.get("technical_score", 0) + .18)
            if "MACD死叉" in tech_names or "均线空头排列" in tech_names: features["technical_score"] = max(0.0, features.get("technical_score", 0) - .18)
            style_multiplier = market.get("risk_multiplier", 1.0)
            score, reasons, risks, breakdown, confidence = scorer.fine_score(
                sigs, row.get("pe"), row.get("turnover"), chg60,
                features=features, market_multiplier=style_multiplier, style=style)

            price = _f(row.get("price")) or _f(df["close"].iloc[-1])
            atr = features.get("atr")
            entry_low = price
            entry_high = price
            trigger = "回踩20日均线企稳" if features.get("pullback") else "等待20日高点放量突破"
            if features.get("breakout"):
                entry_low = price
                entry_high = price + .5 * atr if atr else price
                trigger = "已放量突破20日高点"
            elif features.get("ma20") and price > features["ma20"]:
                entry_low = max(features["ma20"] - .01 * price, price - .5 * (atr or 0))
                entry_high = features["ma20"] + .02 * price
            stop = max(0.01, price - 2 * atr) if atr else price * .95
            target = price + 2 * max(price - stop, atr or price * .05)
            if features.get("overextended"):
                risks.append("当前价格偏离20日均线较远，等待回踩后再考虑")

            results.append({
                "code": code, "name": name,
                "price": price,
                "pct_chg": _f(row.get("pct_chg")),
                "pe": _f(row.get("pe")),
                "pb": _f(row.get("pb")),
                "turnover": _f(row.get("turnover")),
                "score": round(score, 1),
                "reasons": reasons,
                "risks": risks,
                "score_breakdown": breakdown,
                "confidence": confidence,
                "entry_low": round(entry_low, 2),
                "entry_high": round(entry_high, 2),
                "stop_loss": round(stop, 2),
                "take_profit": round(target, 2),
                "entry_trigger": trigger,
                "signal_valid_days": 3 if features.get("breakout") or features.get("pullback") else 1,
                "atr_pct": round((features.get("atr_pct") or 0) * 100, 2),
                "data_as_of": str(df["date"].iloc[-1].date()) if "date" in df.columns else None,
            })
        except Exception as e:
            if verbose:
                print(f"  [跳过] {code} {name}: {e}")
        if i % 10 == 0:
            log(f"已分析 {i}/{len(pool)} 只...")
        time.sleep(0.05)

    # 6. 排序输出
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_n]

    return {"market": market, "recommendations": results}


def fmt_recommendations(result):
    """把推荐结果格式化为可读文本"""
    lines = []
    m = result["market"]
    lines.append(f"当前市场状态：{m['state']}")
    lines.append(f"市场宽度：上涨 {m['breadth'].get('上涨',0)} / 下跌 {m['breadth'].get('下跌',0)}，"
                 f"涨停 {m['breadth'].get('涨停',0)} / 跌停 {m['breadth'].get('跌停',0)}")
    lines.append("")
    lines.append(f"{'排名':<4}{'代码':<8}{'名称':<10}{'现价':<10}{'涨跌幅':<8}{'得分':<8}推荐理由")
    lines.append("-" * 80)
    for i, r in enumerate(result["recommendations"], 1):
        reasons = "+".join(r["reasons"][:4]) if r["reasons"] else "-"
        risks = "、".join(r["risks"][:2]) if r["risks"] else "-"
        lines.append(
            f"{i:<4}{r['code']:<8}{r['name']:<10}{r['price']:<10}"
            f"{r['pct_chg']:<8.2f}{r['score']:<8}{reasons}")
        lines.append(f"     风险提示：{risks}")
    return "\n".join(lines)


def fmt_dip_recommendations(result):
    """把超跌反弹结果格式化为可读文本（含止盈止损位）"""
    lines = []
    m = result["market"]
    lines.append(f"当前市场状态：{m['state']}")
    lines.append(f"市场宽度：上涨 {m['breadth'].get('上涨',0)} / 下跌 {m['breadth'].get('下跌',0)}，"
                 f"涨停 {m['breadth'].get('涨停',0)} / 跌停 {m['breadth'].get('跌停',0)}")
    lines.append("")
    lines.append(f"{'排名':<4}{'代码':<8}{'名称':<10}{'现价':<10}{'近5日':<8}{'止盈':<8}{'止损':<8}{'得分':<8}理由")
    lines.append("-" * 90)
    for i, r in enumerate(result["recommendations"], 1):
        reasons = "+".join(r["reasons"][:3]) if r["reasons"] else "-"
        risks = "、".join(r["risks"][:2]) if r["risks"] else "-"
        dip = f"{r.get('dip_pct', 0):+.1f}%" if r.get("dip_pct") is not None else "-"
        lines.append(
            f"{i:<4}{r['code']:<8}{r['name']:<10}{r['price']:<10}{dip:<8}"
            f"{r.get('take_profit', '-'):<8}{r.get('stop_loss', '-'):<8}{r['score']:<8}{reasons}")
        if risks != "-":
            lines.append(f"     风险：{risks}")
    return "\n".join(lines)
