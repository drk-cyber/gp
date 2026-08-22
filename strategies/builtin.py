# -*- coding: utf-8 -*-
"""
内置策略库：双均线 / MACD / RSI / 布林带 / KDJ / 量价配合
"""
import pandas as pd

from strategies.base import BaseStrategy, crossover, crossunder
from utils import indicators as ind


class MACrossStrategy(BaseStrategy):
    name = "ma_cross"
    description = "双均线策略：短周期均线上穿长周期均线买入，下穿卖出"
    params = {"fast": 5, "slow": 20}

    def generate_signals(self, df):
        fast = self.get_param("fast", 5)
        slow = self.get_param("slow", 20)
        d = ind.add_indicators(df)
        ma_fast = d["close"].rolling(fast, min_periods=1).mean()
        ma_slow = d["close"].rolling(slow, min_periods=1).mean()
        buy = crossover(ma_fast, ma_slow)
        sell = crossunder(ma_fast, ma_slow)
        return buy, sell

    def describe(self):
        return f"双均线：{self.get_param('fast',5)}日均线上穿{self.get_param('slow',20)}日均线买入，下穿卖出"


class MACDStrategy(BaseStrategy):
    name = "macd"
    description = "MACD策略：DIF上穿DEA金叉买入，下穿死叉卖出"
    params = {"fast": 12, "slow": 26, "signal": 9}

    def generate_signals(self, df):
        d = ind.add_indicators(df)
        buy = crossover(d["dif"], d["dea"])
        sell = crossunder(d["dif"], d["dea"])
        return buy, sell

    def describe(self):
        return "MACD金叉买入，死叉卖出"


class RSIStrategy(BaseStrategy):
    name = "rsi"
    description = "RSI策略：超卖（低于阈值）买入，超买（高于阈值）卖出"
    params = {"period": 14, "oversold": 30, "overbought": 70}

    def generate_signals(self, df):
        period = self.get_param("period", 14)
        oversold = self.get_param("oversold", 30)
        overbought = self.get_param("overbought", 70)
        d = ind.add_indicators(df)
        rsi = ind.rsi(d["close"], period)
        buy = (rsi.shift(1) <= oversold) & (rsi > oversold)  # 从超卖区回升
        sell = (rsi.shift(1) >= overbought) & (rsi < overbought)
        return buy, sell

    def describe(self):
        return f"RSI({self.get_param('period',14)})低于{self.get_param('oversold',30)}回升买入，高于{self.get_param('overbought',70)}回落卖出"


class BollingerStrategy(BaseStrategy):
    name = "bollinger"
    description = "布林带策略：触及下轨回升买入，触及上轨回落卖出"
    params = {"period": 20, "k": 2}

    def generate_signals(self, df):
        period = self.get_param("period", 20)
        k = self.get_param("k", 2)
        d = ind.add_indicators(df)
        upper, mid, lower = ind.boll(d["close"], period, k)
        buy = (d["close"].shift(1) <= lower.shift(1)) & (d["close"] > lower)
        sell = (d["close"].shift(1) >= upper.shift(1)) & (d["close"] < upper)
        return buy, sell

    def describe(self):
        return f"布林带({self.get_param('period',20)})下轨回升买入，上轨回落卖出"


class KDJStrategy(BaseStrategy):
    name = "kdj"
    description = "KDJ策略：K线上穿D线金叉买入，下穿死叉卖出"
    params = {"n": 9, "m1": 3, "m2": 3}

    def generate_signals(self, df):
        d = ind.add_indicators(df)
        buy = crossover(d["k"], d["d"]) & (d["k"] < 50)
        sell = crossunder(d["k"], d["d"])
        return buy, sell

    def describe(self):
        return "KDJ低位金叉买入，死叉卖出"


class VolumePriceStrategy(BaseStrategy):
    name = "volume_price"
    description = "量价配合策略：放量突破20日高点买入，缩量跌破20日低点卖出"
    params = {"period": 20, "vol_ratio": 1.5}

    def generate_signals(self, df):
        period = self.get_param("period", 20)
        vol_ratio = self.get_param("vol_ratio", 1.5)
        d = ind.add_indicators(df)
        high20 = d["high"].rolling(period, min_periods=1).max().shift(1)
        low20 = d["low"].rolling(period, min_periods=1).min().shift(1)
        vol_ma = d["volume"].rolling(period, min_periods=1).mean()
        # 放量突破前20日高点
        buy = (d["close"] > high20) & (d["volume"] > vol_ma * vol_ratio)
        # 跌破前20日低点
        sell = d["close"] < low20
        return buy, sell

    def describe(self):
        return f"放量{self.get_param('vol_ratio',1.5)}倍突破20日高点买入，跌破20日低点卖出"


class GridStrategy(BaseStrategy):
    name = "grid"
    description = "网格交易：价格相对均线中枢跌一格买入，涨一格卖出，赚震荡差价"
    params = {"center": 20, "grid_pct": 0.05}

    def generate_signals(self, df):
        center = self.get_param("center", 20)
        grid_pct = self.get_param("grid_pct", 0.05)
        d = ind.add_indicators(df)
        mid = d["close"].rolling(center, min_periods=1).mean()
        lower = mid * (1 - grid_pct)
        upper = mid * (1 + grid_pct)
        # 收盘价下穿下轨 → 买入；上穿上轨 → 卖出
        buy = crossunder(d["close"], lower)
        sell = crossover(d["close"], upper)
        return buy, sell

    def describe(self):
        center = self.get_param("center", 20)
        grid_pct = self.get_param("grid_pct", 0.05)
        return f"网格：以{center}日均线为中枢，跌{grid_pct*100:.0f}%买入，涨{grid_pct*100:.0f}%卖出"


class DCAStrategy(BaseStrategy):
    name = "dca"
    description = "定投：每隔固定交易日买入固定金额，长期持有"
    params = {"interval": 22, "amount": 10000}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 定投每笔固定金额买入（而非全仓）
        self.buy_amount = self.get_param("amount", 10000)

    def generate_signals(self, df):
        interval = self.get_param("interval", 22)
        n = len(df)
        buy = pd.Series([i % interval == 0 for i in range(n)])
        sell = pd.Series([False] * n)
        return buy, sell

    def describe(self):
        interval = self.get_param("interval", 22)
        amount = self.get_param("amount", 10000)
        return f"定投：每{interval}个交易日投{amount:,.0f}元，长期持有"


class TurtleStrategy(BaseStrategy):
    name = "turtle"
    description = "海龟法则：突破N日最高价买入，跌破M日最低价卖出（趋势跟踪）"
    params = {"entry": 20, "exit": 10}

    def generate_signals(self, df):
        entry = self.get_param("entry", 20)
        exit_ = self.get_param("exit", 10)
        d = ind.add_indicators(df)
        # 用前 N 日（不含当日）的高低点判断突破
        high_entry = d["high"].rolling(entry, min_periods=1).max().shift(1)
        low_exit = d["low"].rolling(exit_, min_periods=1).min().shift(1)
        buy = d["close"] > high_entry
        sell = d["close"] < low_exit
        return buy, sell

    def describe(self):
        entry = self.get_param("entry", 20)
        exit_ = self.get_param("exit", 10)
        return f"海龟：突破{entry}日最高买入，跌破{exit_}日最低卖出"


# 策略注册表
STRATEGIES = {
    MACrossStrategy.name: MACrossStrategy,
    MACDStrategy.name: MACDStrategy,
    RSIStrategy.name: RSIStrategy,
    BollingerStrategy.name: BollingerStrategy,
    KDJStrategy.name: KDJStrategy,
    VolumePriceStrategy.name: VolumePriceStrategy,
    GridStrategy.name: GridStrategy,
    DCAStrategy.name: DCAStrategy,
    TurtleStrategy.name: TurtleStrategy,
}


def get_strategy(name, **params):
    if name not in STRATEGIES:
        raise ValueError(f"未知策略 {name}，可选：{list(STRATEGIES.keys())}")
    return STRATEGIES[name](**params)


def list_strategies():
    return [
        {"name": name, "desc": cls().describe()}
        for name, cls in STRATEGIES.items()
    ]
