# -*- coding: utf-8 -*-
"""可解释的多因子选股评分；评分用于排序，不是收益承诺。"""
import numpy as np
import pandas as pd


def _num(value):
    try:
        value = float(value)
        return None if not np.isfinite(value) else value
    except (TypeError, ValueError):
        return None


def rough_score(row):
    score, reasons = 50.0, []
    pe, pb = _num(row.get("pe")), _num(row.get("pb"))
    turnover, chg60 = _num(row.get("turnover")), _num(row.get("60日涨跌幅"))
    if pe is not None and pe > 0:
        if pe < 15: score += 10; reasons.append("估值偏低")
        elif pe < 30: score += 5; reasons.append("估值适中")
        elif pe > 60: score -= 4
    if pb is not None and 0 < pb < 2: score += 4; reasons.append("PB较低")
    if turnover is not None:
        if 1.5 <= turnover <= 12: score += 6; reasons.append("成交活跃")
        elif turnover > 25: score -= 5; reasons.append("换手过高")
    if chg60 is not None:
        if 0 < chg60 < 50: score += 5; reasons.append("中期动量")
        elif chg60 > 70: score -= 4; reasons.append("短期涨幅过大")
    return max(0.0, min(100.0, score)), reasons


def fine_score(signals, pe, turnover, chg60=None, features=None,
               market_multiplier=1.0, style="balanced"):
    """趋势/技术35、动量25、估值20、风险20，按可用字段归一化。"""
    features = features or {}
    reasons, risks, breakdown, factors = [], [], {}, []

    def add(name, value, weight, positive=None, reason=None, risk=None):
        value = _num(value)
        if value is None: return
        value = max(0.0, min(1.0, value))
        factors.append((name, value, weight)); breakdown[name] = round(value * weight, 1)
        if positive is True and reason: reasons.append(reason)
        if positive is False and risk: risks.append(risk)

    trend = features.get("trend_score")
    add("趋势环境", trend, 35, _num(trend) is not None and trend >= .65, "均线趋势向上", "趋势未确认")
    technical = features.get("technical_score")
    add("技术确认", technical, 25, _num(technical) is not None and technical >= .62, "技术信号形成确认", "技术信号分歧")
    momentum = features.get("momentum_score")
    if momentum is None and chg60 is not None: momentum = (float(chg60) + 30) / 90
    add("相对强弱", momentum, 25, _num(momentum) is not None and momentum >= .62, "中期相对强势", "动量偏弱")
    pe_n = _num(pe)
    value_score = None if pe_n is None or pe_n <= 0 else (1.0 if pe_n <= 15 else .7 if pe_n <= 30 else .4 if pe_n <= 60 else .15)
    add("估值", value_score, 20, value_score is not None and value_score >= .7, "估值处于可接受区间", "估值偏高")
    atr_pct = _num(features.get("atr_pct")); risk_score = .8 if atr_pct is None else max(.1, min(.9, 1 - atr_pct * 3))
    if features.get("overextended"): risk_score *= .35; risks.append("距离均线过远，避免追高")
    add("风险收益", risk_score, 20, risk_score >= .65, "波动与位置可控", "波动或位置风险较高")
    total_weight = sum(x[2] for x in factors) or 1
    score = max(0.0, min(100.0, sum(x[1] * x[2] for x in factors) / total_weight * 100 * float(market_multiplier)))
    if style == "defensive" and value_score is not None: score = min(100.0, score + 2 * value_score)
    if not breakdown: risks.append("可用数据不足，评分置信度低")
    confidence = round(min(1.0, total_weight / 100), 2)
    return score, list(dict.fromkeys(reasons)), list(dict.fromkeys(risks)), breakdown, confidence


def features_from_history(df, benchmark=None):
    """从历史 OHLCV 生成趋势、动量、量价确认和 ATR 风险特征。"""
    if df is None or len(df) < 130: return {}
    d = df.copy()
    for c in ("high", "low", "close", "volume"): d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["high", "low", "close", "volume"])
    if len(d) < 130: return {}
    close, high, low, volume = d["close"], d["high"], d["low"], d["volume"]
    ma20, ma60, ma120 = close.rolling(20).mean(), close.rolling(60).mean(), close.rolling(120).mean()
    vol_ma20 = volume.rolling(20).mean(); prev = close.shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    ret60 = close.iloc[-1] / close.iloc[-61] - 1; ret120 = close.iloc[-1] / close.iloc[-121] - 1
    ret250 = close.iloc[-1] / close.iloc[-min(251, len(close))] - 1
    bench60 = None
    if benchmark is not None and len(benchmark) >= 61:
        bench = pd.to_numeric(benchmark["close"], errors="coerce").dropna()
        if len(bench) >= 61: bench60 = bench.iloc[-1] / bench.iloc[-61] - 1
    relative = ret60 - bench60 if bench60 is not None else ret60
    trend_score = np.mean([close.iloc[-1] > ma20.iloc[-1], ma20.iloc[-1] > ma60.iloc[-1], ma60.iloc[-1] > ma120.iloc[-1], ma60.iloc[-1] > ma60.iloc[-6]])
    momentum_score = .45*(ret60+.3)/.9 + .35*(ret120+.3)/.9 + .2*(relative+.2)/.6
    vol_ratio = float(volume.iloc[-1] / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] else 0
    breakout = bool(close.iloc[-1] > high.shift(1).rolling(20).max().iloc[-1] and vol_ratio >= 1.5)
    pullback = bool(abs(close.iloc[-1] / ma20.iloc[-1] - 1) <= .025 and vol_ratio < 1 and close.iloc[-1] >= close.iloc[-2])
    technical_score = .65*trend_score + .2*breakout + .15*pullback
    atr_now = float(atr.iloc[-1]); atr_pct = atr_now / float(close.iloc[-1]) if close.iloc[-1] else None
    dist_ma20 = float(close.iloc[-1] / ma20.iloc[-1] - 1)
    return {"ret60": float(ret60), "ret120": float(ret120), "ret250": float(ret250), "relative60": float(relative), "trend_score": float(trend_score), "momentum_score": float(np.clip(momentum_score, 0, 1)), "technical_score": float(np.clip(technical_score, 0, 1)), "vol_ratio": vol_ratio, "breakout": breakout, "pullback": pullback, "atr": atr_now, "atr_pct": atr_pct, "ma20": float(ma20.iloc[-1]), "ma60": float(ma60.iloc[-1]), "overextended": dist_ma20 > .08 or (close.iloc[-1] / close.iloc[-4] - 1) > .10}
