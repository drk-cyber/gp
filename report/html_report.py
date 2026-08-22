# -*- coding: utf-8 -*-
"""
HTML 报告生成：自包含单文件（内联 CSS + SVG 图表），浏览器打开即可查看
"""
import os
import numpy as np
import pandas as pd

import config
from engine import metrics as metrics_mod


def _line_chart(values, dates, width=760, height=280, color="#e11d48",
                baseline=None, fill=True, y_fmt=lambda v: f"{v:,.0f}"):
    """生成收益/权益曲线 SVG"""
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n == 0:
        return ""
    vmin, vmax = float(v.min()), float(v.max())
    if vmax == vmin:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.08
    vmin -= pad
    vmax += pad
    top, bottom = 14, height - 26
    xs = np.linspace(8, width - 8, n)
    ys = top + (vmax - v) / (vmax - vmin) * (bottom - top)

    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"8,{bottom} " + " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys)) + f" {width-8:.1f},{bottom}"

    fill_svg = ""
    if fill:
        fill_svg = f'<polygon points="{area}" fill="{color}" opacity="0.10"/>'

    # 基线
    base_svg = ""
    if baseline is not None:
        yb = top + (vmax - baseline) / (vmax - vmin) * (bottom - top)
        base_svg = f'<line x1="8" y1="{yb:.1f}" x2="{width-8:.1f}" y2="{yb:.1f}" ' \
                   f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,4"/>'

    # 横轴刻度（5个日期）
    ticks = ""
    for k in range(5):
        idx = int(k * (n - 1) / 4) if n > 1 else 0
        x = xs[idx]
        label = pd.to_datetime(dates[idx]).strftime("%Y-%m")
        ticks += f'<text x="{x:.1f}" y="{height-6}" font-size="11" fill="#64748b" ' \
                 f'text-anchor="middle">{label}</text>'

    return f'''
    <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
      {fill_svg}
      {base_svg}
      <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>
      {ticks}
    </svg>'''


def _drawdown_chart(drawdowns, dates, width=760, height=160):
    """回撤曲线（负值，用柱状）"""
    d = np.asarray(drawdowns, dtype=float)
    n = len(d)
    if n == 0:
        return ""
    top, bottom = 10, height - 24
    xs = np.linspace(8, width - 8, n)
    bars = ""
    for x, dd in zip(xs, d):
        y = top + (0 - dd) / max(0.3, abs(d.min())) * (bottom - top)
        bars += f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{y:.1f}" ' \
                f'stroke="#0ea5e9" stroke-width="1.5" opacity="0.7"/>'
    ticks = ""
    for k in range(5):
        idx = int(k * (n - 1) / 4) if n > 1 else 0
        label = pd.to_datetime(dates[idx]).strftime("%Y-%m")
        ticks += f'<text x="{xs[idx]:.1f}" y="{height-6}" font-size="11" fill="#64748b" ' \
                 f'text-anchor="middle">{label}</text>'
    return f'''
    <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
      {bars}
      {ticks}
    </svg>'''


def _metric_cards(metrics):
    fmt = metrics_mod.fmt_metrics(metrics)
    order = ["总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数"]
    cards = ""
    for k in order:
        v = fmt.get(k, "-")
        color = "#e11d48"
        if k in ("最大回撤",) and metrics.get(k, 0) < 0:
            color = "#0ea5e9"
        cards += f'''<div class="card">
            <div class="card-label">{k}</div>
            <div class="card-value" style="color:{color}">{v}</div>
        </div>'''
    return cards


def _trades_table(trades):
    if trades is None or trades.empty:
        return '<p style="color:#94a3b8">本次回测无交易记录</p>'
    rows = ""
    for _, t in trades.iterrows():
        typ = t["type"]
        color = "#e11d48" if typ == "买入" else "#0ea5e9"
        profit = t.get("profit")
        profit_txt = f'{profit:,.0f}' if profit is not None and profit == profit else "-"
        rows += f'''<tr>
            <td>{pd.to_datetime(t["date"]).strftime("%Y-%m-%d")}</td>
            <td style="color:{color};font-weight:600">{typ}</td>
            <td>{t["price"]:.2f}</td>
            <td>{int(t["shares"])}</td>
            <td>{t["amount"]:,.0f}</td>
            <td>{profit_txt}</td>
        </tr>'''
    return f'''<table class="trades">
        <thead><tr><th>日期</th><th>方向</th><th>价格</th><th>股数</th><th>金额</th><th>盈亏</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>'''


def render_backtest(code, name, strategy_desc, df, backtest_result, metrics, path):
    """生成回测报告 HTML，保存到 path"""
    eq = backtest_result["equity_curve"]
    equity = eq["equity"].tolist()
    dates = eq["date"].tolist()

    # 买入持有基准
    initial = backtest_result["initial_cash"]
    bh = (df["close"] / df["close"].iloc[0] * initial).tolist()

    # 回撤序列
    eq_series = pd.Series(equity)
    cummax = eq_series.cummax()
    dd = (eq_series / cummax - 1).tolist()

    strategy_equity = backtest_result["final_equity"]
    bh_equity = float(bh[-1])

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测报告 - {name} {code}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;
         background:#0f172a; color:#e2e8f0; padding:32px 20px; }}
  .wrap {{ max-width:880px; margin:0 auto; }}
  h1 {{ font-size:24px; margin-bottom:4px; }}
  .sub {{ color:#94a3b8; font-size:14px; margin-bottom:20px; }}
  .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:24px; }}
  .card {{ background:#1e293b; border-radius:12px; padding:16px; }}
  .card-label {{ color:#94a3b8; font-size:12px; margin-bottom:6px; }}
  .card-value {{ font-size:22px; font-weight:700; }}
  .section {{ background:#1e293b; border-radius:16px; padding:20px; margin-bottom:16px; }}
  .section h2 {{ font-size:16px; margin-bottom:12px; color:#cbd5e1; }}
  .vs {{ display:flex; gap:24px; margin-bottom:20px; font-size:14px; }}
  .vs .win {{ color:#10b981; font-weight:600; }}
  .vs .lose {{ color:#ef4444; font-weight:600; }}
  table.trades {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.trades th {{ text-align:left; color:#94a3b8; padding:8px; border-bottom:1px solid #334155; }}
  table.trades td {{ padding:8px; border-bottom:1px solid #1e293b; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>股票回测报告</h1>
  <div class="sub">{name}（{code}）· {strategy_desc} · 回测区间 {pd.to_datetime(dates[0]).strftime('%Y-%m-%d')} ~ {pd.to_datetime(dates[-1]).strftime('%Y-%m-%d')}</div>

  <div class="grid">{_metric_cards(metrics)}</div>

  <div class="section">
    <h2>策略 vs 买入持有</h2>
    <div class="vs">
      <span>策略期末权益：<span class="{('win' if strategy_equity >= bh_equity else 'lose')}">{strategy_equity:,.0f} 元</span></span>
      <span>买入持有期末：{bh_equity:,.0f} 元</span>
    </div>
    <h2>资金曲线（红=策略 / 灰虚线=初始资金）</h2>
    {_line_chart(equity, dates, baseline=initial)}
  </div>

  <div class="section">
    <h2>回撤曲线</h2>
    {_drawdown_chart(dd, dates)}
  </div>

  <div class="section">
    <h2>交易明细</h2>
    {_trades_table(backtest_result["trades"])}
  </div>

  <p style="color:#64748b;font-size:12px;text-align:center;margin-top:16px">
    本报告由本地回测系统自动生成，回测结果不代表未来表现，仅供参考，不构成投资建议。
  </p>
</div>
</body>
</html>'''

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path
    except Exception:
        return None


def render_recommend(result, path):
    """生成选股推荐报告 HTML（支持综合推荐 / 超跌反弹两种模式）"""
    m = result["market"]
    recs = result["recommendations"]
    is_dip = bool(recs) and "take_profit" in recs[0]
    trend_ma = result.get("trend_ma", 60)

    rows = ""
    for i, r in enumerate(recs, 1):
        reasons = " + ".join(r["reasons"][:5]) if r["reasons"] else "-"
        risks = "、".join(r["risks"][:3]) if r["risks"] else "-"
        if is_dip:
            dip = f"{r['dip_pct']:+.1f}%" if r.get("dip_pct") is not None else "-"
            rows += f'''<tr>
                <td>{i}</td>
                <td>{r["code"]}</td>
                <td style="font-weight:600">{r["name"]}</td>
                <td>{r["price"]}</td>
                <td style="color:#0ea5e9">{dip}</td>
                <td style="color:#e11d48">{r["take_profit"]}</td>
                <td style="color:#0ea5e9">{r["stop_loss"]}</td>
                <td style="font-weight:700;color:#f59e0b">{r["score"]}</td>
                <td style="text-align:left">{reasons}</td>
            </tr>
            <tr class="risk"><td></td><td colspan="8" style="color:#f87171;text-align:left">
                风险：{risks}</td></tr>'''
        else:
            pct_color = "#e11d48" if r["pct_chg"] >= 0 else "#0ea5e9"
            pe = f"{r['pe']:.1f}" if r.get("pe") else "-"
            rows += f'''<tr>
                <td>{i}</td>
                <td>{r["code"]}</td>
                <td style="font-weight:600">{r["name"]}</td>
                <td>{r["price"]}</td>
                <td style="color:{pct_color}">{r["pct_chg"]:+.2f}%</td>
                <td>{pe}</td>
                <td style="font-weight:700;color:#f59e0b">{r["score"]}</td>
                <td style="text-align:left">{reasons}</td>
            </tr>
            <tr class="risk"><td></td><td colspan="7" style="color:#f87171;text-align:left">
                风险提示：{risks}</td></tr>'''

    breadth = m["breadth"]
    idx_html = ""
    for idx in m.get("index_trend", []):
        if idx["close"] is not None:
            idx_html += f'<span class="chip">{idx["name"]} {idx["close"]} · {idx["trend"]} · 5日{idx["chg5d"]:+.1f}%</span>'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智能选股推荐</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;
         background:#0f172a; color:#e2e8f0; padding:32px 20px; }}
  .wrap {{ max-width:980px; margin:0 auto; }}
  h1 {{ font-size:24px; margin-bottom:16px; }}
  .state {{ background:linear-gradient(135deg,#1e3a8a,#1e293b); border-radius:16px;
           padding:20px; margin-bottom:20px; }}
  .state h2 {{ font-size:18px; margin-bottom:10px; color:#93c5fd; }}
  .chip {{ display:inline-block; background:#1e293b; border:1px solid #334155;
          border-radius:20px; padding:4px 12px; font-size:12px; margin:4px 4px 0 0; }}
  .stats {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:10px; font-size:13px; color:#cbd5e1; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; background:#1e293b;
          border-radius:16px; overflow:hidden; }}
  th {{ text-align:left; color:#94a3b8; padding:12px 10px; background:#16213a; }}
  td {{ padding:10px; border-bottom:1px solid #1e293b; text-align:center; }}
  tr.risk td {{ border-bottom:1px solid #334155; }}
  .note {{ color:#64748b; font-size:12px; text-align:center; margin-top:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{("超跌反弹选股（" + str(trend_ma) + "日均线）" if is_dip else "智能选股推荐")}</h1>

  <div class="state">
    <h2>{m["state"]}</h2>
    <div>{idx_html}</div>
    <div class="stats">
      <span>上涨 {breadth.get("上涨",0)} 家</span>
      <span>下跌 {breadth.get("下跌",0)} 家</span>
      <span>涨停 {breadth.get("涨停",0)} 家</span>
      <span>跌停 {breadth.get("跌停",0)} 家</span>
    </div>
  </div>

  <table>
    <thead><tr>
      {('<th>排名</th><th>代码</th><th>名称</th><th>现价</th><th>近5日跌幅</th><th>止盈位</th><th>止损位</th><th>得分</th><th style="text-align:left">理由</th>' if is_dip else
        '<th>排名</th><th>代码</th><th>名称</th><th>现价</th><th>涨跌幅</th><th>PE</th><th>综合得分</th><th style="text-align:left">推荐理由</th>')}
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <p class="note">推荐结果由本地量化模型自动生成，仅供参考，不构成投资建议。股市有风险，入市需谨慎。</p>
</div>
</body>
</html>'''

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path
    except Exception:
        return None
