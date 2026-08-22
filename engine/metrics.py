# -*- coding: utf-8 -*-
"""
绩效指标计算
"""
import numpy as np
import pandas as pd

import config


def calc_metrics(equity_curve, trades=None, initial_cash=None):
    """计算回测绩效指标"""
    if equity_curve is None or equity_curve.empty:
        return {}

    eq = equity_curve["equity"].astype(float)
    initial_cash = initial_cash or config.INITIAL_CASH

    total_return = eq.iloc[-1] / initial_cash - 1

    # 年化收益率（按交易日 252 天）
    days = len(eq)
    years = days / 252
    if years > 0 and eq.iloc[-1] > 0:
        annual_return = (eq.iloc[-1] / initial_cash) ** (1 / years) - 1
    else:
        annual_return = 0.0

    # 最大回撤
    cummax = eq.cummax()
    drawdown = eq / cummax - 1
    max_drawdown = drawdown.min()

    # 日收益序列
    daily_ret = eq.pct_change().dropna()

    # 夏普比率
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = (daily_ret.mean() * 252 - config.RISK_FREE_RATE) / (daily_ret.std() * np.sqrt(252))
    else:
        sharpe = 0.0

    # 索提诺比率（下行风险）
    downside = daily_ret[daily_ret < 0]
    if len(downside) > 1 and downside.std() > 0:
        sortino = (daily_ret.mean() * 252 - config.RISK_FREE_RATE) / (downside.std() * np.sqrt(252))
    else:
        sortino = 0.0

    # 卡玛比率
    calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

    # 胜率 / 盈亏比
    win_rate = 0.0
    profit_loss_ratio = 0.0
    trade_count = 0
    if trades is not None and not trades.empty:
        sells = trades[trades["type"] == "卖出"]
        if "profit" in sells.columns and not sells.empty:
            trade_count = len(sells)
            wins = sells[sells["profit"] > 0]
            losses = sells[sells["profit"] <= 0]
            win_rate = len(wins) / len(sells) if len(sells) > 0 else 0.0
            avg_win = wins["profit"].mean() if len(wins) > 0 else 0.0
            avg_loss = abs(losses["profit"].mean()) if len(losses) > 0 else 0.0
            profit_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    # 波动率（年化）
    volatility = daily_ret.std() * np.sqrt(252) if len(daily_ret) > 1 else 0.0

    return {
        "总收益率": total_return,
        "年化收益率": annual_return,
        "最大回撤": max_drawdown,
        "夏普比率": sharpe,
        "索提诺比率": sortino,
        "卡玛比率": calmar,
        "年化波动率": volatility,
        "交易次数": int(trade_count),
        "胜率": win_rate,
        "盈亏比": profit_loss_ratio,
        "期末权益": float(eq.iloc[-1]),
        "回测天数": days,
    }


def fmt_metrics(metrics):
    """把指标格式化为可读字符串"""
    mapping = {
        "总收益率": lambda v: f"{v*100:.2f}%",
        "年化收益率": lambda v: f"{v*100:.2f}%",
        "最大回撤": lambda v: f"{v*100:.2f}%",
        "夏普比率": lambda v: f"{v:.2f}",
        "索提诺比率": lambda v: f"{v:.2f}",
        "卡玛比率": lambda v: f"{v:.2f}",
        "年化波动率": lambda v: f"{v*100:.2f}%",
        "交易次数": lambda v: f"{int(v)}",
        "胜率": lambda v: f"{v*100:.2f}%",
        "盈亏比": lambda v: f"{v:.2f}",
        "期末权益": lambda v: f"{v:,.0f}",
        "回测天数": lambda v: f"{int(v)}",
    }
    out = {}
    for k, v in metrics.items():
        out[k] = mapping.get(k, lambda x: str(x))(v)
    return out
