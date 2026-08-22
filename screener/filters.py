# -*- coding: utf-8 -*-
"""
股票池过滤：排除 ST、停牌、次新、流动性不足、涨跌停等
"""
import pandas as pd


def filter_spot(spot, min_turnover=None):
    """
    对全市场快照进行过滤
    :return: 过滤后的 DataFrame
    """
    if spot is None or spot.empty:
        return spot

    df = spot.copy()

    # 1. 排除 ST / *ST（名称含 ST）
    df = df[~df["name"].astype(str).str.contains("ST", case=False, na=False)]

    # 2. 排除停牌（价格或成交量为 0/NaN）
    df = df[df["price"] > 0]
    df = df[df["volume"] > 0]

    # 3. 排除涨跌停（无法买入）
    def _limit(row):
        c = str(row["code"])
        return 0.20 if c.startswith(("300", "301", "688")) else 0.10
    if "_limit" not in df.columns:
        df["_limit"] = df.apply(_limit, axis=1)
    df = df[df["pct_chg"] < df["_limit"] * 100 - 0.5]   # 排除涨停
    df = df[df["pct_chg"] > -(df["_limit"] * 100 - 0.5)]  # 排除跌停

    # 4. 排除流动性不足（成交额过小）
    if "amount" in df.columns:
        min_turnover = min_turnover or 5000 * 10000
        df = df[df["amount"] >= min_turnover]

    # 5. 排除 PE/PB 为负或异常的（亏损股、估值异常，可选保留）
    if "pe" in df.columns:
        df = df[(df["pe"] > 0) | (df["pe"].isna())]

    # 6. 排除北交所（代码 8 开头 / 4 开头）和 B股
    df = df[df["code"].str.startswith(("60", "00", "30", "68"))]

    return df.reset_index(drop=True)
