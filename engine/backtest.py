# -*- coding: utf-8 -*-
"""
回测引擎：轻量级事件驱动回测，模拟 A股真实交易规则
- T+1（当日买入次日才能卖）
- 涨跌停（涨停无法买，跌停无法卖）
- 佣金 / 印花税 / 过户费
- 次日开盘价成交（避免前视偏差）
"""
import numpy as np
import pandas as pd

import config


def _limit_pct(code):
    """根据股票代码判断涨跌停幅度"""
    code = str(code)
    if code.startswith(("300", "301", "688")):  # 创业板 / 科创板
        return 0.20
    return 0.10


def run_backtest(df, buy_signal, sell_signal, code="600000",
                 initial_cash=None, commission_rate=None,
                 stamp_tax_rate=None, min_commission=None,
                 slippage=None, lot_size=None, buy_amount=None):
    """
    执行回测
    :param df: 日线数据（含 date, open, high, low, close, volume）
    :param buy_signal: 买入信号 Series（True=当日收盘发出买入）
    :param sell_signal: 卖出信号 Series
    :param buy_amount: 每笔买入的固定金额（None=全仓买入），用于定投等策略
    :return: dict，包含 equity_curve, trades, 各类指标
    """
    initial_cash = initial_cash or config.INITIAL_CASH
    commission_rate = config.COMMISSION_RATE if commission_rate is None else commission_rate
    stamp_tax_rate = config.STAMP_TAX_RATE if stamp_tax_rate is None else stamp_tax_rate
    min_commission = config.MIN_COMMISSION if min_commission is None else min_commission
    slippage = config.SLIPPAGE if slippage is None else slippage
    lot_size = config.LOT_SIZE if lot_size is None else lot_size

    limit = _limit_pct(code)

    cash = initial_cash
    position = 0          # 持股数量
    buy_date = None       # 最近一次买入的日期（用于 T+1）
    avg_cost = 0.0        # 持仓成本

    trades = []
    equity_curve = []
    dates = df["date"].tolist()
    opens = df["open"].tolist()
    closes = df["close"].tolist()
    pre_closes = df["close"].shift(1).tolist()
    pct_chg = df["pct_chg"].tolist() if "pct_chg" in df.columns else [0] * len(df)

    buys = buy_signal.tolist() if hasattr(buy_signal, "tolist") else list(buy_signal)
    sells = sell_signal.tolist() if hasattr(sell_signal, "tolist") else list(sell_signal)

    for i in range(len(df)):
        # 当日收盘信号在次日开盘执行
        if i > 0:
            exec_price = opens[i]
            prev_close = pre_closes[i] if i > 0 and pre_closes[i] == pre_closes[i] else closes[i - 1]
            # 判断当日是否涨停/跌停（用涨跌幅近似）
            is_limit_up = pct_chg[i] >= (limit * 100 - 0.5) if pd.notna(pct_chg[i]) else False
            is_limit_down = pct_chg[i] <= -(limit * 100 - 0.5) if pd.notna(pct_chg[i]) else False

            # 执行买入信号
            if buys[i - 1] and cash > 0 and not is_limit_up:
                if slippage:
                    exec_price = exec_price * (1 + slippage)
                if buy_amount:
                    # 定投等：每笔固定金额买入
                    spend = min(cash, buy_amount)
                    max_shares = int(spend / (exec_price * (1 + commission_rate)) // lot_size) * lot_size
                else:
                    # 默认全仓买入
                    max_shares = int(cash / (exec_price * (1 + commission_rate)) // lot_size) * lot_size
                if max_shares >= lot_size:
                    cost = exec_price * max_shares
                    fee = max(cost * commission_rate, min_commission) + cost * config.TRANSFER_FEE_RATE
                    cash -= (cost + fee)
                    position += max_shares
                    avg_cost = exec_price
                    buy_date = dates[i]
                    trades.append({
                        "date": dates[i], "type": "买入", "price": exec_price,
                        "shares": max_shares, "amount": cost, "fee": fee,
                        "cash_after": cash,
                    })

            # 执行卖出信号（T+1 检查）
            elif sells[i - 1] and position > 0 and not is_limit_down:
                if buy_date is not None and dates[i] == buy_date:
                    pass  # T+1：当日买入不可卖
                else:
                    if slippage:
                        exec_price = exec_price * (1 - slippage)
                    sell_shares = position
                    revenue = exec_price * sell_shares
                    fee = max(revenue * commission_rate, min_commission) \
                        + revenue * stamp_tax_rate \
                        + revenue * config.TRANSFER_FEE_RATE
                    cash += (revenue - fee)
                    profit = (exec_price - avg_cost) * sell_shares - fee
                    trades.append({
                        "date": dates[i], "type": "卖出", "price": exec_price,
                        "shares": sell_shares, "amount": revenue, "fee": fee,
                        "profit": profit, "cash_after": cash,
                    })
                    position = 0
                    buy_date = None

        # 记录当日权益（收盘价估值）
        equity = cash + position * closes[i]
        equity_curve.append({
            "date": dates[i], "cash": cash, "position": position,
            "equity": equity,
        })

    # 期末平仓估值
    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_cash
    eq_df = pd.DataFrame(equity_curve)
    trades_df = pd.DataFrame(trades)

    return {
        "equity_curve": eq_df,
        "trades": trades_df,
        "final_equity": final_equity,
        "initial_cash": initial_cash,
    }
