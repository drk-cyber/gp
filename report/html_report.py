# -*- coding: utf-8 -*-
"""
HTML 报告生成：自包含单文件（内联 CSS + SVG 图表），浏览器打开即可查看
视觉与主界面「行情终端」主题保持同一套 token：墨黑底 / 琥珀金 / 红涨绿跌 / 等宽数字
"""
import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
from engine import metrics as metrics_mod

# 与 static/style.css 保持一致的图表配色
CLR_ACCENT = "#e8b33c"   # 琥珀金：系统色 / 策略权益曲线
CLR_UP = "#ef5350"       # A股红：上涨 / 盈利
CLR_DOWN = "#22b573"     # A股绿：下跌 / 亏损 / 回撤
CLR_MUTED = "#6a675f"    # 次要文字 / 基准线
CLR_TEXT2 = "#a29d90"
CLR_BORDER = "#24272d"

FONT_MONO = "Consolas, 'Cascadia Mono', 'SF Mono', Menlo, monospace"

# 两类报告共用的基础样式（非 f-string，避免大括号转义）
_REPORT_CSS = """
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family:"PingFang SC","Microsoft YaHei UI","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
    background:#0b0c0e; color:#eae5d9; padding:36px 22px 48px;
    -webkit-font-smoothing:antialiased;
  }
  .wrap { max-width:920px; margin:0 auto; }
  .eyebrow {
    font-family:__MONO__; font-size:11px; letter-spacing:3px;
    color:#e8b33c; margin-bottom:8px;
  }
  h1 { font-size:24px; font-weight:700; margin-bottom:6px; }
  .sub { color:#a29d90; font-size:13.5px; margin-bottom:26px; line-height:1.6; }
  .panel {
    background:#14161a; border:1px solid #24272d; border-radius:12px;
    margin-bottom:16px; overflow:hidden;
  }
  .panel-head {
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    padding:13px 20px; border-bottom:1px solid #24272d;
  }
  .panel-head h2 { font-size:13.5px; font-weight:600; }
  .panel-head .hint { font-size:12px; color:#6a675f; }
  .panel-body { padding:18px 20px; }
  .mono { font-family:__MONO__; font-variant-numeric:tabular-nums; }
  .up { color:#ef5350; }
  .down { color:#22b573; }
  footer {
    color:#6a675f; font-size:12px; text-align:center; margin-top:20px; line-height:1.7;
  }
""".replace("__MONO__", FONT_MONO)


def _safe_write(path, html):
    """写入报告文件；目标路径必须位于 REPORT_DIR 内，拒绝路径穿越"""
    base = Path(config.REPORT_DIR).resolve()
    target = Path(path).resolve()
    if not target.is_relative_to(base):
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return str(target)
    except Exception:
        return None


def _line_chart(values, dates, width=760, height=280, color=CLR_ACCENT,
                baseline=None, compare=None, compare_color=CLR_TEXT2,
                y_fmt=lambda v: f"{v:,.0f}"):
    """生成权益曲线 SVG；compare 为可选的对照序列（如买入持有）"""
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n == 0:
        return ""

    series = [v]
    if compare is not None:
        series.append(np.asarray(compare, dtype=float))
    vmin = min(float(s.min()) for s in series)
    vmax = max(float(s.max()) for s in series)
    if vmax == vmin:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.08
    vmin -= pad
    vmax += pad
    top, bottom = 16, height - 26
    xs = np.linspace(8, width - 8, n)
    ys = top + (vmax - v) / (vmax - vmin) * (bottom - top)

    def y_of(val):
        return top + (vmax - val) / (vmax - vmin) * (bottom - top)

    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"8,{bottom} " + points + f" {width - 8:.1f},{bottom}"

    # 横向网格线
    grid = ""
    for frac in (0.25, 0.5, 0.75):
        gy = top + (bottom - top) * frac
        grid += (f'<line x1="8" y1="{gy:.1f}" x2="{width - 8:.1f}" y2="{gy:.1f}" '
                 f'stroke="{CLR_BORDER}" stroke-width="1"/>')
    # 上下沿数值标注
    y_labels = (
        f'<text x="8" y="{top - 3:.0f}" font-size="10" fill="{CLR_MUTED}" '
        f'font-family="{FONT_MONO}">{y_fmt(vmax - (vmax - vmin) * 0.08)}</text>'
        f'<text x="8" y="{bottom + 11:.0f}" font-size="10" fill="{CLR_MUTED}" '
        f'font-family="{FONT_MONO}">{y_fmt(vmin + (vmax - vmin) * 0.08)}</text>'
    )

    fill_svg = (f'<polygon points="{area}" fill="{color}" opacity="0.08"/>')
    base_svg = ""
    if baseline is not None:
        yb = y_of(baseline)
        base_svg = (f'<line x1="8" y1="{yb:.1f}" x2="{width - 8:.1f}" y2="{yb:.1f}" '
                    f'stroke="{CLR_MUTED}" stroke-width="1" stroke-dasharray="4,4"/>')
    compare_svg = ""
    if compare is not None:
        cys = [y_of(c) for c in compare]
        cpts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, cys))
        compare_svg = (f'<polyline points="{cpts}" fill="none" '
                       f'stroke="{compare_color}" stroke-width="1.5" opacity="0.85"/>')

    ticks = ""
    for k in range(5):
        idx = int(k * (n - 1) / 4) if n > 1 else 0
        x = xs[idx]
        label = pd.to_datetime(dates[idx]).strftime("%Y-%m")
        ticks += (f'<text x="{x:.1f}" y="{height - 6}" font-size="11" fill="{CLR_MUTED}" '
                  f'font-family="{FONT_MONO}" text-anchor="middle">{label}</text>')

    return f'''
    <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
      {grid}
      {fill_svg}
      {base_svg}
      {compare_svg}
      <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>
      {y_labels}
      {ticks}
    </svg>'''


def _drawdown_chart(drawdowns, dates, width=760, height=160):
    """回撤曲线（负值，用柱状，A股绿=亏损）"""
    d = np.asarray(drawdowns, dtype=float)
    n = len(d)
    if n == 0:
        return ""
    top, bottom = 10, height - 24
    xs = np.linspace(8, width - 8, n)
    bars = ""
    for x, dd in zip(xs, d):
        y = top + (0 - dd) / max(0.3, abs(d.min())) * (bottom - top)
        bars += (f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                 f'stroke="{CLR_DOWN}" stroke-width="1.5" opacity="0.7"/>')
    worst = float(d.min())
    label = (f'<text x="{width - 8}" y="{top + 10:.0f}" font-size="10" fill="{CLR_MUTED}" '
             f'font-family="{FONT_MONO}" text-anchor="end">最深 {worst * 100:.1f}%</text>')
    ticks = ""
    for k in range(5):
        idx = int(k * (n - 1) / 4) if n > 1 else 0
        label_t = pd.to_datetime(dates[idx]).strftime("%Y-%m")
        ticks += (f'<text x="{xs[idx]:.1f}" y="{height - 6}" font-size="11" fill="{CLR_MUTED}" '
                  f'font-family="{FONT_MONO}" text-anchor="middle">{label_t}</text>')
    return f'''
    <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
      {bars}
      {label}
      {ticks}
    </svg>'''


def _metric_cards(metrics):
    fmt = metrics_mod.fmt_metrics(metrics)
    order = ["总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数"]
    cards = ""
    for k in order:
        v = fmt.get(k, "-")
        color = "#eae5d9"
        if k in ("总收益率", "年化收益率"):
            color = CLR_UP if metrics.get(k, 0) >= 0 else CLR_DOWN
        elif k == "最大回撤":
            color = CLR_DOWN
        cards += f'''<div class="metric">
            <div class="metric-label">{k}</div>
            <div class="metric-value" style="color:{color}">{v}</div>
        </div>'''
    return cards


def _trades_table(trades):
    if trades is None or trades.empty:
        return '<p style="color:#a29d90">本次回测无交易记录</p>'
    rows = ""
    for _, t in trades.iterrows():
        typ = t["type"]
        color = CLR_UP if typ == "买入" else CLR_DOWN
        profit = t.get("profit")
        if profit is not None and profit == profit:
            p_color = CLR_UP if profit >= 0 else CLR_DOWN
            profit_txt = f'<span style="color:{p_color}">{profit:,.0f}</span>'
        else:
            profit_txt = "-"
        rows += f'''<tr>
            <td class="mono">{pd.to_datetime(t["date"]).strftime("%Y-%m-%d")}</td>
            <td style="color:{color};font-weight:600">{typ}</td>
            <td class="mono r">{t["price"]:.2f}</td>
            <td class="mono r">{int(t["shares"])}</td>
            <td class="mono r">{t["amount"]:,.0f}</td>
            <td class="mono r">{profit_txt}</td>
        </tr>'''
    return f'''<table class="trades">
        <thead><tr><th>日期</th><th>方向</th><th class="r">价格</th><th class="r">股数</th><th class="r">金额</th><th class="r">盈亏</th></tr></thead>
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
    excess = (strategy_equity / bh_equity - 1) * 100 if bh_equity else 0

    bt_css = _REPORT_CSS + """
  .grid { display:grid; grid-template-columns:repeat(3,1fr); margin-bottom:16px;
          border:1px solid #24272d; border-radius:12px; overflow:hidden; background:#14161a; }
  .metric { padding:18px 20px; border-right:1px solid #24272d; border-bottom:1px solid #24272d; }
  .metric:nth-child(3n) { border-right:none; }
  .metric:nth-last-child(-n+3) { border-bottom:none; }
  .metric-label { color:#6a675f; font-size:12px; margin-bottom:8px; }
  .metric-value { font-family:__MONO__; font-size:23px; font-weight:650;
                  font-variant-numeric:tabular-nums; letter-spacing:-.5px; }
  .vs { display:flex; gap:28px; flex-wrap:wrap; font-size:13.5px; color:#a29d90; margin-bottom:16px; }
  .vs b { font-family:__MONO__; font-variant-numeric:tabular-nums; font-weight:650; }
  .legend { display:flex; gap:18px; flex-wrap:wrap; font-size:12px; color:#a29d90; margin-bottom:10px; }
  .legend .k { display:inline-flex; align-items:center; gap:6px; }
  .legend .swatch { width:16px; height:2px; border-radius:1px; display:inline-block; }
  table.trades { width:100%; border-collapse:collapse; font-size:13px; }
  table.trades th { text-align:left; color:#6a675f; font-weight:500; padding:9px 8px;
                    border-bottom:1px solid #24272d; font-size:12px; white-space:nowrap; }
  table.trades th.r { text-align:right; }
  table.trades td { padding:9px 8px; border-bottom:1px solid #1d2025; }
  table.trades td.r { text-align:right; }
  table.trades tr:hover td { background:#1b1e23; }
  @media (max-width:720px) {
    .grid { grid-template-columns:repeat(2,1fr); }
    .metric:nth-child(3n) { border-right:1px solid #24272d; }
    .metric:nth-child(2n) { border-right:none; }
    .metric:nth-last-child(-n+3) { border-bottom:1px solid #24272d; }
    .metric:nth-last-child(-n+2) { border-bottom:none; }
  }
""" .replace("__MONO__", FONT_MONO)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测报告 - {name} {code}</title>
<style>{bt_css}</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">BACKTEST REPORT</div>
  <h1>股票回测报告</h1>
  <div class="sub">{name}（{code}）· {strategy_desc} · 回测区间
    <span class="mono">{pd.to_datetime(dates[0]).strftime('%Y-%m-%d')} ~ {pd.to_datetime(dates[-1]).strftime('%Y-%m-%d')}</span></div>

  <div class="grid">{_metric_cards(metrics)}</div>

  <div class="panel">
    <div class="panel-head"><h2>策略 vs 买入持有</h2><span class="hint">初始资金 <span class="mono">{initial:,.0f}</span> 元</span></div>
    <div class="panel-body">
      <div class="vs">
        <span>策略期末权益 <b class="{'up' if strategy_equity >= bh_equity else 'down'}">{strategy_equity:,.0f} 元</b></span>
        <span>买入持有期末 <b>{bh_equity:,.0f} 元</b></span>
        <span>超额收益 <b class="{'up' if excess >= 0 else 'down'}">{excess:+.2f}%</b></span>
      </div>
      <div class="legend">
        <span class="k"><span class="swatch" style="background:{CLR_ACCENT}"></span>策略权益</span>
        <span class="k"><span class="swatch" style="background:{CLR_TEXT2}"></span>买入持有</span>
        <span class="k"><span class="swatch" style="background:repeating-linear-gradient(90deg,{CLR_MUTED} 0 4px,transparent 4px 8px)"></span>初始资金</span>
      </div>
      {_line_chart(equity, dates, baseline=initial, compare=bh)}
    </div>
  </div>

  <div class="panel">
    <div class="panel-head"><h2>回撤曲线</h2><span class="hint">绿柱越深，回撤越大</span></div>
    <div class="panel-body">{_drawdown_chart(dd, dates)}</div>
  </div>

  <div class="panel">
    <div class="panel-head"><h2>交易明细</h2><span class="hint">按 A股规则 T+1 · 含手续费</span></div>
    <div class="panel-body">{_trades_table(backtest_result["trades"])}</div>
  </div>

  <footer>
    本报告由本地回测系统自动生成 · {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}<br>
    回测结果不代表未来表现，仅供参考，不构成投资建议。
  </footer>
</div>
</body>
</html>'''

    return _safe_write(path, html)


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
                <td class="mono">{i:02d}</td>
                <td class="mono" style="color:#6a675f">{r["code"]}</td>
                <td style="font-weight:600;white-space:nowrap">{r["name"]}</td>
                <td class="mono r">{r["price"]}</td>
                <td class="mono r down">{dip}</td>
                <td class="mono r up">{r["take_profit"]}</td>
                <td class="mono r down">{r["stop_loss"]}</td>
                <td class="mono r" style="font-weight:650;color:{CLR_ACCENT}">{r["score"]}</td>
                <td style="text-align:left">{reasons}<br>
                    <span style="color:#d98a3f;font-size:12px">风险：{risks}</span></td>
            </tr>'''
        else:
            pct_color = "up" if r["pct_chg"] >= 0 else "down"
            pe = f"{r['pe']:.1f}" if r.get("pe") else "-"
            rows += f'''<tr>
                <td class="mono">{i:02d}</td>
                <td class="mono" style="color:#6a675f">{r["code"]}</td>
                <td style="font-weight:600;white-space:nowrap">{r["name"]}</td>
                <td class="mono r">{r["price"]}</td>
                <td class="mono r {pct_color}">{r["pct_chg"]:+.2f}%</td>
                <td class="mono r">{pe}</td>
                <td class="mono r" style="font-weight:650;color:{CLR_ACCENT}">{r["score"]}</td>
                <td style="text-align:left">{reasons}<br>
                    <span style="color:#d98a3f;font-size:12px">风险提示：{risks}</span></td>
            </tr>'''

    breadth = m["breadth"]
    up_n = int(breadth.get("上涨", 0))
    down_n = int(breadth.get("下跌", 0))
    total = up_n + down_n
    up_pct = (up_n / total * 100) if total else 50
    down_pct = 100 - up_pct

    idx_html = ""
    for idx in m.get("index_trend", []):
        if idx["close"] is not None:
            chg_cls = "up" if (idx["chg5d"] or 0) >= 0 else "down"
            idx_html += (f'<span class="chip"><span class="ix-name">{idx["name"]}</span>'
                         f'<span class="mono ix-close">{idx["close"]}</span>'
                         f'<span class="mono {chg_cls}">5日{idx["chg5d"]:+.1f}%</span></span>')

    rec_css = _REPORT_CSS + """
  .thermo { display:flex; height:8px; border-radius:4px; background:#1b1e23;
            overflow:hidden; margin-bottom:10px; }
  .thermo .seg-up { background:#ef5350; }
  .thermo .seg-down { background:#22b573; }
  .tlegend { display:flex; gap:20px; flex-wrap:wrap; font-size:12.5px; color:#a29d90; margin-bottom:14px; }
  .tlegend b { font-family:__MONO__; font-variant-numeric:tabular-nums; margin-left:4px; }
  .tlegend .lk-up { color:#ef5350; }
  .tlegend .lk-down { color:#22b573; }
  .chip { display:inline-flex; align-items:baseline; gap:8px; padding:7px 12px;
          border-radius:8px; background:#1b1e23; border:1px solid #24272d;
          font-size:12.5px; margin:0 8px 8px 0; }
  .chip .ix-name { color:#a29d90; }
  .chip .ix-close { font-weight:600; }
  .state-row { display:flex; align-items:center; gap:8px; font-size:15px; font-weight:650; margin-bottom:14px; }
  .state-row .dot { width:8px; height:8px; border-radius:50%; background:#e8b33c;
                    box-shadow:0 0 0 3px rgba(232,179,60,.15); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { color:#6a675f; font-weight:500; padding:11px 10px; font-size:12px;
       background:#101216; white-space:nowrap; }
  th.r { text-align:right; }
  td { padding:10px; border-bottom:1px solid #1d2025; text-align:center; }
  td.r { text-align:right; }
  tr:hover td { background:#1b1e23; }
  tbody tr:last-child td { border-bottom:none; }
  .tablewrap { border:1px solid #24272d; border-radius:12px; overflow:hidden;
               background:#14161a; margin-bottom:16px; }
""" .replace("__MONO__", FONT_MONO)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{("超跌反弹选股（" + str(trend_ma) + "日均线）" if is_dip else "智能选股推荐")}</title>
<style>{rec_css}</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">SCREENER REPORT</div>
  <h1>{("超跌反弹选股（" + str(trend_ma) + "日均线）" if is_dip else "智能选股推荐")}</h1>
  <div class="sub">生成于 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")} · 共 {len(recs)} 只</div>

  <div class="panel">
    <div class="panel-head"><h2>市场状态</h2><span class="hint">红为上涨家数 · 绿为下跌家数</span></div>
    <div class="panel-body">
      <div class="state-row"><span class="dot"></span>{m["state"]}</div>
      <div class="thermo">
        <div class="seg-up" style="width:{up_pct:.1f}%"></div>
        <div class="seg-down" style="width:{down_pct:.1f}%"></div>
      </div>
      <div class="tlegend">
        <span class="lk-up">上涨<b>{up_n}</b></span>
        <span class="lk-down">下跌<b>{down_n}</b></span>
        <span>涨停<b>{breadth.get("涨停",0)}</b></span>
        <span>跌停<b>{breadth.get("跌停",0)}</b></span>
      </div>
      {idx_html}
    </div>
  </div>

  <div class="tablewrap">
  <table>
    <thead><tr>
      {('<th>排名</th><th>代码</th><th>名称</th><th class="r">现价</th><th class="r">近5日跌幅</th><th class="r">止盈位</th><th class="r">止损位</th><th class="r">得分</th><th style="text-align:left">理由</th>' if is_dip else
        '<th>排名</th><th>代码</th><th>名称</th><th class="r">现价</th><th class="r">涨跌幅</th><th class="r">PE</th><th class="r">综合得分</th><th style="text-align:left">推荐理由</th>')}
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>

  <footer>
    推荐结果由本地量化模型自动生成 · {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}<br>
    仅供参考，不构成投资建议。股市有风险，入市需谨慎。
  </footer>
</div>
</body>
</html>'''

    return _safe_write(path, html)
