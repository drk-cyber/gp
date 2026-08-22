# -*- coding: utf-8 -*-
"""
打分模型：综合技术面 + 估值面 + 资金面 + 动量，输出 0-100 综合得分
"""
import pandas as pd


def rough_score(row):
    """
    初筛粗打分（只用实时快照，无需历史数据），用于从全市场快速缩小候选范围
    """
    score = 50.0
    reasons = []

    # 估值
    pe = row.get("pe")
    if pd.notna(pe) and pe > 0:
        if pe < 15:
            score += 12; reasons.append("低估值(PE<15)")
        elif pe < 30:
            score += 7; reasons.append("估值合理(PE<30)")
        elif pe < 50:
            score += 3
        else:
            score -= 3
    pb = row.get("pb")
    if pd.notna(pb) and pb > 0 and pb < 2:
        score += 5; reasons.append("低市净率(PB<2)")

    # 换手率（资金活跃度）
    turnover = row.get("turnover")
    if pd.notna(turnover):
        if 2 <= turnover <= 10:
            score += 8; reasons.append("换手活跃")
        elif turnover > 20:
            score -= 5; reasons.append("换手过高")

    # 近期动量（60日涨跌幅）
    chg60 = row.get("60日涨跌幅", None)
    if pd.notna(chg60):
        if 5 <= chg60 <= 40:
            score += 8; reasons.append("中期趋势向上")
        elif chg60 > 60:
            score -= 3; reasons.append("短期涨幅过大")

    return score, reasons


def fine_score(signals, pe, turnover, chg60=None):
    """
    精细打分（结合历史技术信号 + 估值 + 资金）
    """
    score = 50.0
    reasons = []
    risks = []

    # 技术信号
    for s in signals:
        if s["direction"] == "bullish":
            score += s["strength"] * 10
            reasons.append(s["name"])
        else:
            score -= s["strength"] * 8
            risks.append(s["name"])

    # 估值
    if pd.notna(pe) and pe > 0:
        if pe < 15:
            score += 10; reasons.append("低估值")
        elif pe < 30:
            score += 6
        elif pe > 60:
            score -= 4; risks.append("估值偏高")

    # 换手率
    if pd.notna(turnover):
        if 2 <= turnover <= 10:
            score += 5
        elif turnover > 20:
            score -= 6; risks.append("换手过高")

    # 动量
    if chg60 is not None and pd.notna(chg60):
        if 5 <= chg60 <= 40:
            score += 4
        elif chg60 > 60:
            score -= 3; risks.append("涨幅过大")

    score = max(0.0, min(100.0, score))
    return score, reasons, risks
