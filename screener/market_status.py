# -*- coding: utf-8 -*-
"""
大盘行情判断：判断当前牛/熊/震荡市，识别热点板块
"""
import pandas as pd

from utils import indicators as ind
from data import fetcher


def judge_market():
    """
    判断大盘状态
    :return: dict，包含状态、指数趋势、涨跌家数、热点等
    """
    result = {
        "state": "未知",
        "style": "balanced",
        "index_trend": {},
        "breadth": {},
        "hot_sectors": [],
        "summary": "",
    }

    # 1. 指数趋势判断
    indices = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
    }
    bullish_count = 0
    bearish_count = 0
    index_details = []
    for name, symbol in indices.items():
        try:
            df = fetcher.get_index_daily(symbol)
            close = df["close"]
            ma5 = ind.ma(close, 5)
            ma10 = ind.ma(close, 10)
            ma20 = ind.ma(close, 20)
            ma60 = ind.ma(close, 60)
            last = -1
            trend = "纠缠"
            if ma5.iloc[last] > ma10.iloc[last] > ma20.iloc[last] > ma60.iloc[last]:
                trend = "多头排列"
                bullish_count += 1
            elif ma5.iloc[last] < ma10.iloc[last] < ma20.iloc[last] < ma60.iloc[last]:
                trend = "空头排列"
                bearish_count += 1
            # 近5日涨跌
            chg5 = (close.iloc[last] / close.iloc[-6] - 1) if len(close) > 6 else 0
            index_details.append({
                "name": name,
                "close": round(float(close.iloc[last]), 2),
                "trend": trend,
                "chg5d": round(float(chg5 * 100), 2),
            })
        except Exception as e:
            index_details.append({"name": name, "close": None, "trend": "获取失败", "chg5d": 0})
    result["index_trend"] = index_details

    # 2. 市场宽度（涨跌家数）
    try:
        spot = fetcher.get_all_spot()
        up_count = int((spot["pct_chg"] > 0).sum())
        down_count = int((spot["pct_chg"] < 0).sum())
        flat_count = int((spot["pct_chg"] == 0).sum())
        # 涨停/跌停家数（按代码判断幅度）
        def _limit(row):
            c = str(row["code"])
            return 0.20 if c.startswith(("300", "301", "688")) else 0.10
        spot["_limit"] = spot.apply(_limit, axis=1)
        limit_up = int(((spot["pct_chg"] >= spot["_limit"] * 100 - 0.5)).sum())
        limit_down = int(((spot["pct_chg"] <= -(spot["_limit"] * 100 - 0.5))).sum())
        result["breadth"] = {
            "上涨": up_count, "下跌": down_count, "平盘": flat_count,
            "涨停": limit_up, "跌停": limit_down,
        }
    except Exception:
        result["breadth"] = {"上涨": 0, "下跌": 0, "平盘": 0, "涨停": 0, "跌停": 0}

    # 3. 综合判断状态
    if bullish_count >= 2:
        state = "牛市（偏多）"
        style = "aggressive"
    elif bearish_count >= 2:
        state = "熊市（偏空）"
        style = "defensive"
    else:
        state = "震荡市"
        style = "balanced"
    result["state"] = state
    result["style"] = style

    # 4. 生成摘要
    trend_txt = "、".join(
        f"{d['name']}{d['trend']}" for d in index_details if d["close"] is not None)
    breadth = result["breadth"]
    result["summary"] = (
        f"当前市场状态：{state}\n"
        f"指数趋势：{trend_txt}\n"
        f"市场宽度：上涨 {breadth['上涨']} 家 / 下跌 {breadth['下跌']} 家，"
        f"涨停 {breadth['涨停']} 家 / 跌停 {breadth['跌停']} 家"
    )
    return result
