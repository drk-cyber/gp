# -*- coding: utf-8 -*-
"""
HTML 报告生成：自包含单文件（内联 CSS + SVG 图表），浏览器打开即可查看
视觉与主界面保持一致：蓝黑底 / 蓝紫强调 / 红涨绿跌 / 等宽数字。
style_report_html 同时为历史报告提供幂等的展示层主题，不改写原报告文件。
"""
import datetime
import re
from pathlib import Path

import numpy as np
import pandas as pd

import config
from engine import metrics as metrics_mod

# 与 static/style.css 保持一致的图表配色
CLR_ACCENT = "#91a4ff"   # 蓝紫：系统色 / 策略权益曲线
CLR_UP = "#ff7f8c"       # A股红：上涨 / 盈利
CLR_DOWN = "#42d6a4"     # A股绿：下跌 / 亏损 / 回撤
CLR_MUTED = "#91a1be"    # 次要文字 / 基准线
CLR_TEXT2 = "#b4c0d8"
CLR_BORDER = "#29364e"

FONT_MONO = "Bahnschrift, Consolas, 'Cascadia Mono', 'SF Mono', Menlo, monospace"

# 两类报告共用的基础样式（非 f-string，避免大括号转义）
_REPORT_CSS = """
  :root {
    color-scheme:dark;
    --bg:#0b1020; --bg-raise:#0f1629; --surface:#141d32; --surface-2:#1b2740;
    --border:#29364e; --text:#edf2ff; --text-2:#b4c0d8; --text-3:#91a1be;
    --accent:#91a4ff; --accent-strong:#b2bdff; --up:#ff7f8c; --down:#42d6a4;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  html { scroll-behavior:smooth; }
  body {
    font-family:"Microsoft YaHei UI","PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
    background:radial-gradient(ellipse at 85% 0,rgba(114,136,247,.08),transparent 46%),var(--bg);
    color:var(--text); padding:0 28px 36px; font-size:14px; line-height:1.6;
    -webkit-font-smoothing:antialiased; min-width:320px;
  }
  ::selection { background:rgba(145,164,255,.28); color:var(--text); }
  .wrap,.report-tools { max-width:1360px; margin:0 auto; }
  .wrap { padding-top:25px; }
  .report-tools {
    display:flex; align-items:center; justify-content:space-between; gap:20px;
    min-height:70px; border-bottom:1px solid var(--border);
    position:sticky; top:0; z-index:10; background:rgba(11,16,32,.94); backdrop-filter:blur(12px);
  }
  .report-brand { display:flex; align-items:center; gap:10px; font-size:13px; font-weight:650; letter-spacing:.3px; }
  .report-brand-mark {
    display:grid; place-items:center; width:32px; height:32px; border-radius:10px;
    background:var(--surface-2); border:1px solid #3a4970; color:var(--accent-strong);
  }
  .report-brand small { color:var(--text-3); font-size:12px; font-weight:400; margin-left:6px; }
  .report-actions { display:flex; align-items:center; gap:10px; }
  .report-action {
    display:inline-flex; align-items:center; justify-content:center; gap:7px; min-height:38px;
    border:1px solid var(--border); border-radius:10px; padding:0 13px;
    background:var(--surface); color:var(--text-2); font:inherit; font-size:12px;
    text-decoration:none; cursor:pointer; transition:background .16s ease,border-color .16s ease;
  }
  .report-action:hover { background:var(--surface-2); border-color:#576899; color:var(--text); }
  .report-action-primary { background:#7288f7; border-color:#7288f7; color:#0b1020; font-weight:650; }
  .report-action-primary:hover { background:#91a4ff; border-color:#91a4ff; color:#0b1020; }
  :focus-visible { outline:2px solid var(--accent-strong); outline-offset:4px; }
  .eyebrow {
    font-family:__MONO__; font-size:11px; letter-spacing:2px;
    color:var(--accent); margin-bottom:6px;
  }
  h1 { font-size:27px; line-height:1.35; font-weight:700; letter-spacing:-.6px; margin-bottom:8px; }
  .sub { color:var(--text-3); font-size:12px; margin-bottom:22px; line-height:1.8; }
  .panel,.section,.state,.tablewrap {
    background:var(--surface); border:1px solid var(--border); border-radius:16px;
    margin-bottom:14px; overflow:hidden; box-shadow:0 8px 26px rgba(0,0,0,.12);
    min-width:0;
  }
  .section,.state { padding:18px 20px; }
  .panel-head {
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    padding:13px 18px; border-bottom:1px solid var(--border); min-height:49px;
  }
  .panel-head h2,.section h2 { color:var(--text); font-size:14px; font-weight:650; }
  .section h2 { margin-bottom:12px; }
  .panel-head .hint { font-size:12px; color:var(--text-3); font-weight:400; }
  .panel-body { padding:16px 18px; min-width:0; }
  .mono { font-family:__MONO__; font-variant-numeric:tabular-nums; }
  .up,.vs .win { color:var(--up); }
  .down,.vs .lose { color:var(--down); }
  .grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; margin-bottom:16px; background:none; border:0; border-radius:0; overflow:visible; }
  .metric,.card {
    padding:16px; background:linear-gradient(145deg,rgba(145,164,255,.035),transparent 70%),var(--surface);
    border:1px solid var(--border); border-radius:14px; min-width:0; box-shadow:0 5px 18px rgba(0,0,0,.1);
  }
  .grid .metric { border:1px solid var(--border); }
  .metric-label,.card-label { color:var(--text-3); font-size:12px; margin-bottom:7px; }
  .metric-value,.card-value { font-family:__MONO__; font-size:25px; line-height:1.25; font-weight:600; font-variant-numeric:tabular-nums; letter-spacing:-.6px; }
  .vs { display:flex; gap:12px 24px; flex-wrap:wrap; font-size:12px; color:var(--text-2); margin-bottom:15px; }
  .vs b,.vs .win,.vs .lose { font-family:__MONO__; font-variant-numeric:tabular-nums; font-weight:600; font-size:15px; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--text-3); margin-bottom:10px; }
  .legend .k { display:inline-flex; align-items:center; gap:6px; }
  .legend .swatch { width:18px; height:3px; border-radius:2px; display:inline-block; }
  .wrap svg { display:block; max-width:100%; overflow:visible; }
  .report-table-scroll { overflow-x:auto; overscroll-behavior-x:contain; scrollbar-width:thin; scrollbar-color:#445578 var(--bg-raise); }
  .wrap > .report-table-scroll { border:1px solid var(--border); border-radius:16px; }
  table,table.trades { width:100%; border-collapse:collapse; font-size:13px; line-height:1.65; background:var(--surface); }
  th,table.trades th { color:var(--text-3); font-size:12px; font-weight:500; padding:11px 12px; background:var(--bg-raise); white-space:nowrap; border-bottom:1px solid var(--border); }
  td,table.trades td { padding:11px 12px; border-bottom:1px solid var(--border); text-align:center; vertical-align:top; }
  table.trades th,table.trades td { text-align:left; }
  th.r,td.r,table.trades th.r,table.trades td.r { text-align:right; }
  tbody tr:last-child td { border-bottom:0; }
  tbody tr:hover td,table.trades tbody tr:hover td { background:rgba(145,164,255,.055); }
  table.trades { min-width:560px; }
  table.trades td { font-family:__MONO__; font-variant-numeric:tabular-nums; }
  body[data-report-kind="recommend"] table { min-width:900px; }
  body[data-report-kind="recommend"] td:not(:last-child) { white-space:nowrap; }
  body[data-report-kind="recommend"] td:nth-child(1),body[data-report-kind="recommend"] td:nth-child(2),
  body[data-report-kind="recommend"] td:nth-child(n+4):not(:last-child) { font-family:__MONO__; font-variant-numeric:tabular-nums; }
  body[data-report-kind="recommend"] td:last-child { min-width:240px; max-width:470px; overflow-wrap:anywhere; }
  body[data-report-kind="recommend"] td:first-child { color:var(--text-3); }
  body[data-report-kind="recommend"] tbody tr:not(.risk):first-child td:first-child { color:var(--accent-strong); font-weight:700; }
  tr.risk td { padding-top:0; font-size:12px; border-bottom:1px solid var(--border); }
  .thermo { display:flex; height:8px; border-radius:6px; background:var(--surface-2); overflow:hidden; margin-bottom:12px; }
  .thermo .seg-up { background:var(--up); }
  .thermo .seg-down { background:var(--down); }
  .tlegend,.stats { display:flex; gap:16px 25px; flex-wrap:wrap; font-size:12px; color:var(--text-2); margin-bottom:13px; }
  .tlegend b { font-family:__MONO__; font-variant-numeric:tabular-nums; font-size:15px; font-weight:500; margin-left:6px; }
  .tlegend .lk-up { color:var(--up); }
  .tlegend .lk-down { color:var(--down); }
  .chip { display:inline-flex; align-items:baseline; gap:8px; padding:8px 12px; border-radius:10px; background:var(--bg-raise); border:1px solid var(--border); font-size:12px; margin:0 8px 0 0; }
  .chip .ix-name { color:var(--text-3); }
  .chip .ix-close { font-size:15px; font-weight:500; }
  .state h2 { font-size:16px; color:var(--text); margin-bottom:12px; }
  .state .stats { margin-top:13px; margin-bottom:0; }
  .state-row { display:flex; align-items:center; gap:9px; font-size:16px; font-weight:650; margin-bottom:15px; }
  .state-row .dot { width:7px; height:7px; border-radius:50%; background:var(--accent); box-shadow:0 0 0 4px rgba(145,164,255,.1); }
  .report-empty { text-align:center; color:var(--text-3); padding:28px 18px; }
  footer,.note { color:var(--text-3); font-size:12px; text-align:center; margin-top:22px; padding-top:16px; border-top:1px solid var(--border); line-height:1.8; }
  body[data-report-kind="backtest"] .wrap { display:grid; grid-template-columns:minmax(0,1.7fr) minmax(0,1fr); gap:14px; }
  body[data-report-kind="backtest"] .wrap > * { grid-column:1 / -1; margin-bottom:0; }
  body[data-report-kind="backtest"] .wrap > .eyebrow { margin-bottom:-9px; }
  body[data-report-kind="backtest"] .wrap > h1 { margin-bottom:-8px; }
  body[data-report-kind="backtest"] .wrap > .sub { margin-bottom:3px; }
  body[data-report-kind="backtest"] .wrap > .report-equity { grid-column:1; }
  body[data-report-kind="backtest"] .wrap > .report-drawdown { grid-column:2; display:flex; flex-direction:column; }
  .report-drawdown .panel-head { flex-wrap:wrap; gap:4px 10px; }
  .report-drawdown .panel-body { flex:1; display:flex; align-items:center; }
  .report-drawdown svg { max-height:260px; }
  .report-drawdown > svg { margin-top:auto; margin-bottom:auto; }
  @media (min-width:1450px) { body { padding-left:40px; padding-right:40px; } }
  @media (max-width:1100px) {
    .grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
    body[data-report-kind="backtest"] .wrap { grid-template-columns:minmax(0,1fr); }
    body[data-report-kind="backtest"] .wrap > .report-equity,body[data-report-kind="backtest"] .wrap > .report-drawdown { grid-column:1; }
    .report-drawdown svg { max-height:190px; }
    .chip { margin-bottom:8px; }
  }
  @media (max-width:640px) {
    body { padding:0 14px 24px; }
    .report-tools { min-height:66px; gap:12px; }
    .report-brand small,.report-action-secondary { display:none; }
    .report-action { min-height:44px; }
    .wrap { padding-top:20px; }
    h1 { font-size:23px; }
    .grid { grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; }
    .metric,.card { padding:13px 14px; }
    .metric-value,.card-value { font-size:24px; }
    .panel-head { align-items:flex-start; flex-wrap:wrap; gap:4px; padding:12px 14px; }
    .panel-body,.section,.state { padding:14px; }
    .vs { gap:9px; }
    .vs > span { width:100%; }
    .chip { display:flex; width:100%; margin-right:0; justify-content:space-between; }
    .chip:last-child { margin-bottom:0; }
    .tlegend,.stats { gap:9px 17px; }
  }
  @media (prefers-reduced-motion:reduce) {
    html { scroll-behavior:auto; }
    *,*::before,*::after { transition:none!important; animation:none!important; }
  }
  @media print {
    :root { color-scheme:light; --bg:#fff; --bg-raise:#f1f4f9; --surface:#fff; --surface-2:#f1f4f9; --border:#cdd5e3; --text:#16213a; --text-2:#384760; --text-3:#526079; --accent:#4d5aa9; --accent-strong:#414c92; --up:#b82341; --down:#127953; }
    @page { size:A4 landscape; margin:12mm; }
    body { background:#fff; color:var(--text); padding:0; font-size:11px; }
    .report-tools { display:none; }
    .wrap { padding:0; max-width:none; }
    body[data-report-kind="backtest"] .wrap { display:block; }
    body[data-report-kind="backtest"] .wrap > * { margin-bottom:12px; }
    .grid { grid-template-columns:repeat(6,minmax(0,1fr)); }
    .panel,.section,.state,.metric,.card,.tablewrap { box-shadow:none; background:#fff; break-inside:avoid; }
    .tablewrap { break-inside:auto; }
    .report-table-scroll { overflow:visible; }
    table,table.trades,body[data-report-kind="recommend"] table { min-width:0; font-size:10px; }
    th,td,table.trades th,table.trades td { padding:6px; }
    body[data-report-kind="recommend"] td:last-child { min-width:0; }
    tr { break-inside:avoid; }
    thead { display:table-header-group; }
    [style*="color:"] { color:var(--text-2)!important; }
    .wrap svg { max-height:245px; }
    svg text { fill:#526079; }
    svg [stroke="#91a4ff"] { stroke:#4d5aa9; }
    svg [stroke="#42d6a4"] { stroke:#127953; }
    svg [stroke="#ff7f8c"] { stroke:#b82341; }
    svg [stroke="#29364e"] { stroke:#cdd5e3; }
    footer,.note { font-size:10px; }
  }
""".replace("__MONO__", FONT_MONO)

_REPORT_TOOLS = '''<nav class="report-tools" id="report-top" aria-label="报告工具">
  <div class="report-brand"><span class="report-brand-mark" aria-hidden="true">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18V6M4 18h16M8 14l4-5 4 3 4-7"/></svg>
  </span>A 股投研<small>分析报告</small></div>
  <div class="report-actions"><a class="report-action report-action-secondary" href="#report-top">返回顶部</a>
    <button class="report-action report-action-primary" type="button" onclick="window.print()">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 8V3h10v5M7 17H4V9h16v8h-3M7 14h10v7H7z"/></svg>打印报告
    </button>
  </div>
</nav>'''

# 仅映射报告生成器用过的颜色；不在正文、证券代码或 SVG 坐标中做替换。
_LEGACY_COLORS = {
    "#0b0c0e": "#0b1020", "#0f172a": "#0b1020",
    "#14161a": "#141d32", "#1e293b": "#141d32", "#1e3a8a": "#1b2740",
    "#1b1e23": "#1b2740", "#101216": "#0f1629", "#16213a": "#0f1629",
    "#24272d": "#29364e", "#334155": "#29364e", "#1d2025": "#29364e",
    "#eae5d9": "#edf2ff", "#e2e8f0": "#edf2ff",
    "#a29d90": "#b4c0d8", "#cbd5e1": "#b4c0d8",
    "#6a675f": "#91a1be", "#64748b": "#91a1be", "#94a3b8": "#91a1be",
    "#e8b33c": "#91a4ff", "#f59e0b": "#91a4ff", "#93c5fd": "#b2bdff",
    "#ef5350": "#ff7f8c", "#e11d48": "#ff7f8c", "#10b981": "#ff7f8c",
    "#22b573": "#42d6a4", "#0ea5e9": "#42d6a4", "#ef4444": "#42d6a4",
    "#d98a3f": "#e8b779", "#f87171": "#e8b779",
}


def style_report_html(html: str) -> str:
    """为新旧自包含报告应用一致主题；保持原有数据和正文，重复调用无变化。"""
    if 'id="report-theme-v2"' in html:
        return html

    def recolor(match):
        return re.sub(r"#[0-9a-fA-F]{6}\b", lambda color: _LEGACY_COLORS.get(
            color.group(0).lower(), color.group(0)), match.group(0))

    html = re.sub(r"<style\b[^>]*>.*?</style>|\b(?:style|fill|stroke)\s*=\s*([\"']).*?\1",
                  recolor, html, flags=re.IGNORECASE | re.DOTALL)
    kind = "backtest" if re.search(r"<title>[^<]*回测报告", html) else "recommend"

    # 早期卡片把多类指标统一着色；按已有标签和值修正显示语义，不重新计算指标。
    def style_old_metric(match):
        label, opening, value, closing = match.groups()
        if label in ("总收益率", "年化收益率"):
            color = CLR_DOWN if value.strip().startswith("-") else CLR_UP
        elif label == "最大回撤":
            color = CLR_DOWN
        else:
            color = "#edf2ff"
        opening = re.sub(r"color\s*:\s*#[0-9a-fA-F]{6}", "color:" + color, opening)
        return '<div class="card-label">' + label + '</div>' + opening + value + closing

    html = re.sub(r'<div class="card-label">([^<]+)</div>(\s*<div class="card-value"[^>]*>)([^<]*)(</div>)',
                  style_old_metric, html)
    for title, cls in (("策略 vs 买入持有", "report-equity"), ("回撤曲线", "report-drawdown")):
        html = re.sub(r'(<div class=")(panel|section)(">\s*(?:<div class="panel-head">)?\s*<h2>)' + re.escape(title),
                      lambda match: match[1] + match[2] + " " + cls + match[3] + title, html)

    # 每张表有自己的键盘可访问滚动容器，旧版直接放在 wrap 内的表格也不会撑宽页面。
    table_label = "交易明细" if kind == "backtest" else "选股结果"
    html = re.sub(r"<table\b[^>]*>.*?</table>", lambda match:
                  '<div class="report-table-scroll" tabindex="0" role="region" aria-label="' + table_label +
                  '，可横向滚动">' + match[0] + '</div>', html, flags=re.IGNORECASE | re.DOTALL)
    theme = '<style id="report-theme-v2">' + _REPORT_CSS + '</style>\n'
    html = re.sub(r"</head>", lambda _: theme + '</head>', html, count=1, flags=re.IGNORECASE)
    html = re.sub(r"<body([^>]*)>", lambda match: '<body' + match[1] +
                  ' data-report-kind="' + kind + '">\n' + _REPORT_TOOLS, html, count=1, flags=re.IGNORECASE)
    return html


def _safe_write(path, html):
    """写入报告文件；目标路径必须位于 REPORT_DIR 内，拒绝路径穿越"""
    base = Path(config.REPORT_DIR).resolve()
    target = Path(path).resolve()
    if not target.is_relative_to(base):
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(style_report_html(html), encoding="utf-8")
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
    top, bottom = 16, height - 36
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
        anchor = "start" if k == 0 else "end" if k == 4 else "middle"
        ticks += (f'<text x="{x:.1f}" y="{height - 6}" font-size="11" fill="{CLR_MUTED}" '
                  f'font-family="{FONT_MONO}" text-anchor="{anchor}">{label}</text>')

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
        anchor = "start" if k == 0 else "end" if k == 4 else "middle"
        ticks += (f'<text x="{xs[idx]:.1f}" y="{height - 6}" font-size="11" fill="{CLR_MUTED}" '
                  f'font-family="{FONT_MONO}" text-anchor="{anchor}">{label_t}</text>')
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
        color = "#edf2ff"
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
        return '<p class="report-empty">本次回测无交易记录</p>'
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

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测报告 - {name} {code}</title>
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
    <div class="panel-body">{_drawdown_chart(dd, dates, width=480, height=260)}</div>
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
    is_dip = bool(recs) and "dip_pct" in recs[0]
    trend_ma = result.get("trend_ma", 60)

    rows = ""
    for i, r in enumerate(recs, 1):
        reasons = " + ".join(r["reasons"][:5]) if r["reasons"] else "-"
        risks = "、".join(r["risks"][:3]) if r["risks"] else "-"
        if is_dip:
            dip = f"{r['dip_pct']:+.1f}%" if r.get("dip_pct") is not None else "-"
            rows += f'''<tr>
                <td class="mono">{i:02d}</td>
                <td class="mono" style="color:{CLR_MUTED}">{r["code"]}</td>
                <td style="font-weight:600;white-space:nowrap">{r["name"]}</td>
                <td class="mono r">{r["price"]}</td>
                <td class="mono r down">{dip}</td>
                <td class="mono r up">{r["take_profit"]}</td>
                <td class="mono r down">{r["stop_loss"]}</td>
                <td class="mono r" style="font-weight:650;color:{CLR_ACCENT}">{r["score"]}</td>
                <td style="text-align:left">{reasons}<br>
                    <span style="color:{CLR_ACCENT};font-size:12px">入场 {r.get('entry_low', '-')} ~ {r.get('entry_high', '-')} · 触发：{r.get('entry_trigger', '反转确认')}</span><br>
                    <span style="color:#e8b779;font-size:12px">风险：{risks}</span></td>
            </tr>'''
        else:
            pct_value = r.get("pct_chg")
            pct_color = "up" if pct_value is not None and pct_value >= 0 else "down"
            pe = f"{r['pe']:.1f}" if r.get("pe") else "-"
            pct_text = f"{pct_value:+.2f}%" if pct_value is not None else "-"
            rows += f'''<tr>
                <td class="mono">{i:02d}</td>
                <td class="mono" style="color:{CLR_MUTED}">{r["code"]}</td>
                <td style="font-weight:600;white-space:nowrap">{r["name"]}</td>
                <td class="mono r">{r["price"]}</td>
                <td class="mono r {pct_color}">{pct_text}</td>
                <td class="mono r">{pe}</td>
                <td class="mono r" style="font-weight:650;color:{CLR_ACCENT}">{r["score"]}</td>
                <td style="text-align:left">{reasons}<br>
                    <span style="color:{CLR_ACCENT};font-size:12px">入场 {r.get('entry_low', '-')} ~ {r.get('entry_high', '-')} · 止损 {r.get('stop_loss', '-')} · 目标 {r.get('take_profit', '-')}</span><br>
                    <span style="color:#e8b779;font-size:12px">风险提示：{risks}</span></td>
            </tr>'''

    if not rows:
        rows = f'<tr><td colspan="{9 if is_dip else 8}" class="report-empty">本次筛选暂无符合条件的股票</td></tr>'

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

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{("超跌反弹选股（" + str(trend_ma) + "日均线）" if is_dip else "智能选股推荐")}</title>
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
