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

    # 1. 大盘判断
    log("正在判断大盘状态...")
    market = market_status.judge_market()
    log(f"  => {market['state']}")

    # 2. 全市场扫描
    log("正在获取全市场行情快照...")
    spot = fetcher.get_all_spot()
    log(f"  => 共 {len(spot)} 只股票")

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
    for i, (_, row) in enumerate(pool.iterrows(), 1):
        code = row["code"]
        name = row.get("name", code)
        try:
            df = fetcher.get_stock_daily(code, start_date=hist_start)
            sigs = signals.detect_signals(df)
            chg60 = row.get("60日涨跌幅")
            score, reasons, risks = scorer.fine_score(
                sigs, row.get("pe"), row.get("turnover"), chg60)

            # 根据风格微调打分
            if style == "aggressive" and any(s["name"] in ("放量突破", "均线多头排列", "MACD金叉") for s in sigs):
                score += 3
            elif style == "defensive" and row.get("pe") is not None and row.get("pe") < 20:
                score += 3

            results.append({
                "code": code, "name": name,
                "price": _f(row.get("price")),
                "pct_chg": _f(row.get("pct_chg")),
                "pe": _f(row.get("pe")),
                "pb": _f(row.get("pb")),
                "turnover": _f(row.get("turnover")),
                "score": round(score, 1),
                "reasons": reasons,
                "risks": risks,
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
