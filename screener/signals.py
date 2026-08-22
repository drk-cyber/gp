# -*- coding: utf-8 -*-
"""
技术信号检测：对单只股票的历史数据检测当前触发的技术信号
每个信号包含：name(名称), description(大白话描述), direction(方向), strength(强度0-1)
"""
import numpy as np

from utils import indicators as ind
from strategies.base import crossover, crossunder


def detect_signals(df):
    """
    检测单只股票当前触发的所有技术信号
    :param df: 日线数据（含 open/high/low/close/volume）
    :return: list[dict]
    """
    if df is None or len(df) < 60:
        return []

    d = ind.add_indicators(df)
    signals = []
    close = d["close"]
    last = len(d) - 1

    # 1. 均线多头排列
    if (d["ma5"].iloc[last] > d["ma10"].iloc[last] > d["ma20"].iloc[last] > d["ma60"].iloc[last]):
        signals.append({
            "name": "均线多头排列", "direction": "bullish", "strength": 0.9,
            "description": "5日/10日/20日/60日均线呈多头排列，趋势向上",
        })
    elif (d["ma5"].iloc[last] < d["ma10"].iloc[last] < d["ma20"].iloc[last]):
        signals.append({
            "name": "均线空头排列", "direction": "bearish", "strength": 0.8,
            "description": "均线呈空头排列，趋势向下",
        })

    # 2. MACD 金叉/死叉（近5日内）
    dif, dea = d["dif"], d["dea"]
    recent_golden = crossover(dif, dea).iloc[-6:]
    recent_dead = crossunder(dif, dea).iloc[-6:]
    if recent_golden.any():
        signals.append({
            "name": "MACD金叉", "direction": "bullish", "strength": 0.8,
            "description": "MACD的DIF线上穿DEA线，短期看涨信号",
        })
    if recent_dead.any():
        signals.append({
            "name": "MACD死叉", "direction": "bearish", "strength": 0.6,
            "description": "MACD的DIF线下穿DEA线，短期看跌信号",
        })

    # 3. KDJ 金叉（低位）
    if crossover(d["k"], d["d"]).iloc[-1] and d["k"].iloc[last] < 50:
        signals.append({
            "name": "KDJ低位金叉", "direction": "bullish", "strength": 0.7,
            "description": "KDJ在低位金叉，超卖反弹信号",
        })

    # 4. RSI 超卖回升
    rsi = d["rsi"]
    if rsi.iloc[last - 1] <= 30 and rsi.iloc[last] > 30:
        signals.append({
            "name": "RSI超卖回升", "direction": "bullish", "strength": 0.7,
            "description": "RSI从超卖区（<30）回升，反弹概率增大",
        })
    elif rsi.iloc[last] > 75:
        signals.append({
            "name": "RSI超买", "direction": "bearish", "strength": 0.5,
            "description": "RSI处于超买区（>75），短期回调风险",
        })

    # 5. 放量突破20日高点
    high20 = d["high"].rolling(20, min_periods=1).max().shift(1)
    vol_ratio = d["volume"] / d["vol_ma20"]
    if close.iloc[last] > high20.iloc[last] and vol_ratio.iloc[last] > 1.5:
        signals.append({
            "name": "放量突破", "direction": "bullish", "strength": 0.9,
            "description": f"放量{vol_ratio.iloc[last]:.1f}倍突破20日新高，强势信号",
        })

    # 6. 布林带下轨反弹
    if close.iloc[last - 1] <= d["boll_low"].iloc[last - 1] and close.iloc[last] > d["boll_low"].iloc[last]:
        signals.append({
            "name": "布林带下轨反弹", "direction": "bullish", "strength": 0.6,
            "description": "触及布林带下轨后回升，超跌反弹信号",
        })

    # 7. 底背离（价格创新低，MACD未创新低）
    low20 = d["low"].rolling(20).min()
    if (close.iloc[last] <= low20.iloc[last] and
            d["macd"].iloc[last] > d["macd"].iloc[-20:].min()):
        signals.append({
            "name": "底背离", "direction": "bullish", "strength": 0.7,
            "description": "价格创新低但MACD未创新低，下跌动能衰竭",
        })

    # 8. 缩量回踩20日均线
    if (abs(close.iloc[last] - d["ma20"].iloc[last]) / d["ma20"].iloc[last] < 0.02 and
            vol_ratio.iloc[last] < 1.0 and close.iloc[last] > d["ma20"].iloc[last - 1]):
        signals.append({
            "name": "缩量回踩支撑", "direction": "bullish", "strength": 0.5,
            "description": "缩量回踩20日均线获得支撑，洗盘企稳信号",
        })

    # 风险信号（减分）
    # 高位预警（乖离率过大）
    bias = (close.iloc[last] - d["ma60"].iloc[last]) / d["ma60"].iloc[last]
    if bias > 0.3:
        signals.append({
            "name": "高位预警", "direction": "bearish", "strength": 0.8,
            "description": f"价格偏离60日均线{bias*100:.0f}%，短期涨幅过大，追高风险",
        })

    return signals
