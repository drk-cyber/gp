# -*- coding: utf-8 -*-
"""
A股本地股票回测系统 —— 主入口
用法：
  交互模式：        python main.py
  选股推荐：        python main.py --recommend [--top 10] [--style aggressive]
  单策略回测：      python main.py --strategy ma_cross --stock 600519 --start 2015-01-01 --end 2025-01-01
  查看策略列表：    python main.py --list
"""
import argparse
import os
import sys
import datetime

import config
from data import fetcher
from strategies import get_strategy, list_strategies
from engine import backtest, metrics as metrics_mod
from report import html_report
from screener import recommend as recommend_mod


def _parse_date(s):
    if not s:
        return None
    return str(s).replace("-", "")


def do_backtest(strategy_name, code, start, end, params=None, open_report=True):
    """执行单策略回测，返回报告路径"""
    params = params or {}
    print(f"\n===== 策略回测 =====")
    print(f"股票：{code} | 策略：{strategy_name} | 区间：{start or '全部'} ~ {end or '最新'}")

    print("正在获取行情数据...")
    df = fetcher.get_stock_daily(code, start_date=start, end_date=end)
    if df is None or df.empty:
        print("未获取到数据")
        return None
    print(f"共 {len(df)} 个交易日")

    name = fetcher.get_stock_name(code)
    strategy = get_strategy(strategy_name, **params)
    print(f"策略说明：{strategy.describe()}")

    print("正在生成买卖信号...")
    buy, sell = strategy.generate_signals(df)

    print("正在执行回测...")
    result = backtest.run_backtest(df, buy, sell, code=code,
                                   buy_amount=strategy.buy_amount)

    print("正在计算绩效指标...")
    m = metrics_mod.calc_metrics(result["equity_curve"], result["trades"], result["initial_cash"])
    fmt = metrics_mod.fmt_metrics(m)
    print("\n----- 回测结果 -----")
    for k in ["总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数"]:
        print(f"  {k}: {fmt[k]}")

    # 生成报告
    config.ensure_dirs()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"backtest_{code}_{strategy_name}_{ts}.html"
    path = os.path.join(config.REPORT_DIR, fname)
    html_report.render_backtest(code, name, strategy.describe(), df, result, m, path)
    print(f"\n报告已生成：{path}")
    if open_report:
        try:
            os.startfile(path)
        except Exception:
            pass
    return path


def do_recommend(top_n, style, open_report=True, mode="general"):
    """执行选股推荐"""
    is_dip = mode in ("dip", "dip120")
    print(f"\n===== {'超跌反弹选股' if is_dip else '智能选股推荐'} =====")
    result = recommend_mod.recommend(top_n=top_n, style=style, mode=mode)

    if is_dip:
        text = recommend_mod.fmt_dip_recommendations(result)
    else:
        text = recommend_mod.fmt_recommendations(result)
    print("\n" + text)

    config.ensure_dirs()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"recommend_dip_{ts}.html" if is_dip else f"recommend_{ts}.html"
    path = os.path.join(config.REPORT_DIR, fname)
    html_report.render_recommend(result, path)
    print(f"\n推荐报告已生成：{path}")
    if open_report:
        try:
            os.startfile(path)
        except Exception:
            pass
    return path


def interactive():
    """交互式菜单"""
    while True:
        print("\n" + "=" * 40)
        print("   A股本地股票回测系统")
        print("=" * 40)
        print(" 1. 根据当前行情推荐股票 ★")
        print(" 2. 运行单个策略回测")
        print(" 3. 查看内置策略列表")
        print(" 0. 退出")
        choice = input("\n请选择操作: ").strip()

        if choice == "1":
            top = input("推荐股票数量（默认10）: ").strip()
            top = int(top) if top else 10
            mode = input("推荐模式 general综合/dip超跌反弹（默认general）: ").strip() or "general"
            style = input("推荐风格 aggressive/defensive/balanced（默认自动）: ").strip() or None
            do_recommend(top, style, mode=mode)

        elif choice == "2":
            print("\n内置策略：")
            for s in list_strategies():
                print(f"  {s['name']:<14}{s['desc']}")
            strat = input("请输入策略名: ").strip()
            code = input("请输入股票代码（如 600519）: ").strip()
            start = input("起始日期 YYYY-MM-DD（可留空）: ").strip()
            end = input("结束日期 YYYY-MM-DD（可留空）: ").strip()
            if not code:
                print("股票代码不能为空")
                continue
            do_backtest(strat, code, _parse_date(start), _parse_date(end))

        elif choice == "3":
            print("\n内置策略：")
            for s in list_strategies():
                print(f"  {s['name']:<14}{s['desc']}")

        elif choice == "0":
            print("再见！")
            break
        else:
            print("无效选择，请重新输入")


def main():
    parser = argparse.ArgumentParser(description="A股本地股票回测系统")
    parser.add_argument("--recommend", action="store_true", help="根据当前行情推荐股票")
    parser.add_argument("--top", type=int, default=None, help="推荐数量")
    parser.add_argument("--style", type=str, default=None, help="推荐风格 aggressive/defensive/balanced")
    parser.add_argument("--mode", type=str, default="general", help="推荐模式 general/dip(60日)/dip120(120日半年线)")
    parser.add_argument("--strategy", type=str, default=None, help="策略名")
    parser.add_argument("--stock", type=str, default=None, help="股票代码")
    parser.add_argument("--start", type=str, default=None, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--list", action="store_true", help="列出内置策略")
    parser.add_argument("--no-open", action="store_true", help="生成报告后不自动打开")
    args = parser.parse_args()

    config.ensure_dirs()
    open_report = not args.no_open

    if args.list:
        print("内置策略：")
        for s in list_strategies():
            print(f"  {s['name']:<14}{s['desc']}")
        return

    if args.recommend:
        do_recommend(args.top, args.style, open_report, mode=args.mode)
        return

    if args.strategy and args.stock:
        do_backtest(args.strategy, args.stock,
                    _parse_date(args.start), _parse_date(args.end),
                    open_report=open_report)
        return

    # 无参数 -> 交互模式
    interactive()


if __name__ == "__main__":
    main()
