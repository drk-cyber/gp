# -*- coding: utf-8 -*-
"""
技术指标计算库（全部基于 pandas，不依赖 TA-Lib）
输入一般为包含 close/open/high/low/volume 列的 DataFrame
"""
import numpy as np
import pandas as pd


def sma(series, n, m=1):
    """中国式 SMA(X, N, M) 递推：Y = (M*X + (N-M)*Y_prev) / N"""
    result = np.zeros(len(series))
    result[0] = series.iloc[0]
    for i in range(1, len(series)):
        result[i] = (m * series.iloc[i] + (n - m) * result[i - 1]) / n
    return pd.Series(result, index=series.index)


def ma(series, n):
    """简单移动平均"""
    return series.rolling(n, min_periods=1).mean()


def ema(series, n):
    """指数移动平均"""
    return series.ewm(span=n, adjust=False).mean()


def macd(close, fast=12, slow=26, signal=9):
    """MACD：返回 DIF, DEA, MACD柱"""
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def rsi(close, n=14):
    """RSI 相对强弱指标"""
    diff = close.diff()
    up = diff.clip(lower=0)
    down = -diff.clip(upper=0)
    # 使用 Wilder 平滑
    avg_up = up.ewm(alpha=1 / n, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    rsi_val = 100 - 100 / (1 + rs)
    return rsi_val.fillna(50)


def boll(close, n=20, k=2):
    """布林带：返回中轨、上轨、下轨"""
    mid = ma(close, n)
    std = close.rolling(n, min_periods=1).std()
    upper = mid + k * std
    lower = mid - k * std
    return upper, mid, lower


def kdj(high, low, close, n=9, m1=3, m2=3):
    """KDJ 指标：返回 K, D, J"""
    low_n = low.rolling(n, min_periods=1).min()
    high_n = high.rolling(n, min_periods=1).max()
    rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    rsv = rsv.fillna(50)
    k = sma(rsv, m1, 1)
    d = sma(k, m2, 1)
    j = 3 * k - 2 * d
    return k, d, j


def atr(high, low, close, n=14):
    """ATR 平均真实波幅"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df):
    """一次性计算所有常用指标，返回扩展后的 DataFrame"""
    d = df.copy()
    close = d["close"]
    d["ma5"] = ma(close, 5)
    d["ma10"] = ma(close, 10)
    d["ma20"] = ma(close, 20)
    d["ma60"] = ma(close, 60)
    d["dif"], d["dea"], d["macd"] = macd(close)
    d["rsi"] = rsi(close, 14)
    d["rsi6"] = rsi(close, 6)
    d["boll_up"], d["boll_mid"], d["boll_low"] = boll(close)
    d["k"], d["d"], d["j"] = kdj(d["high"], d["low"], close)
    d["vol_ma20"] = ma(d["volume"], 20)
    return d
