# -*- coding: utf-8 -*-
"""
策略基类：所有策略统一接口
"""
import pandas as pd


class BaseStrategy:
    name = "base"
    description = "策略基类"
    params = {}   # {参数名: 默认值}

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        # 每笔买入的固定金额（None = 全仓买入）。定投等策略会覆盖此值
        self.buy_amount = None

    def get_param(self, key, default):
        return self.kwargs.get(key, default)

    def generate_signals(self, df):
        """返回 (buy_signal, sell_signal) 两个布尔 Series"""
        raise NotImplementedError

    def describe(self):
        """返回策略大白话描述"""
        return self.description


def crossover(a, b):
    """a 上穿 b（前一值 <= 前一值 b，当前值 > 当前值 b）"""
    a = pd.Series(a).reset_index(drop=True)
    b = pd.Series(b).reset_index(drop=True)
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a, b):
    """a 下穿 b"""
    a = pd.Series(a).reset_index(drop=True)
    b = pd.Series(b).reset_index(drop=True)
    return (a < b) & (a.shift(1) >= b.shift(1))
