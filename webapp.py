# -*- coding: utf-8 -*-
"""
A股本地回测系统 —— Web 版后端（Flask）
启动：python webapp.py  然后浏览器打开 http://127.0.0.1:8000
"""
import os
import uuid
import threading
import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory

import config
from data import fetcher
from strategies import get_strategy, list_strategies
from engine import backtest, metrics as metrics_mod
from report import html_report
from screener import recommend as recommend_mod

app = Flask(__name__)
app.json.ensure_ascii = False  # 让 JSON 直接返回中文

config.ensure_dirs()

# 推荐任务状态（内存）
TASKS = {}
# 股票名称缓存（避免每次回测都拉全市场快照）
_NAME_CACHE = {}


def get_name(code):
    """带缓存的股票名称查询"""
    code = str(code).zfill(6)
    if code in _NAME_CACHE:
        return _NAME_CACHE[code]
    try:
        spot = fetcher.get_all_spot()
        for _, r in spot.iterrows():
            _NAME_CACHE[str(r["code"]).zfill(6)] = str(r.get("name", r["code"]))
    except Exception:
        pass
    return _NAME_CACHE.get(code, code)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/strategies")
def api_strategies():
    return jsonify(list_strategies())


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.get_json(force=True) or {}
    strategy = data.get("strategy", "ma_cross")
    code = (data.get("code") or "").strip()
    start = data.get("start") or None
    end = data.get("end") or None
    initial_cash = data.get("initial_cash") or config.INITIAL_CASH

    if not code:
        return jsonify({"error": "请填写股票代码"}), 400
    valid = [s["name"] for s in list_strategies()]
    if strategy not in valid:
        return jsonify({"error": f"未知策略 {strategy}"}), 400

    try:
        df = fetcher.get_stock_daily(code, start_date=start, end_date=end)
        if df is None or df.empty:
            return jsonify({"error": "未获取到数据，请检查股票代码或网络"}), 400

        name = get_name(code)
        strat = get_strategy(strategy)
        buy, sell = strat.generate_signals(df)
        result = backtest.run_backtest(
            df, buy, sell, code=code, initial_cash=float(initial_cash),
            buy_amount=strat.buy_amount)
        m = metrics_mod.calc_metrics(
            result["equity_curve"], result["trades"], result["initial_cash"])
        fmt = metrics_mod.fmt_metrics(m)

        # 生成 HTML 报告（写失败时静默降级，不影响回测结果返回）
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"backtest_{code}_{strategy}_{ts}.html"
        path = os.path.join(config.REPORT_DIR, fname)
        report_ok = html_report.render_backtest(code, name, strat.describe(), df, result, m, path)

        return jsonify({
            "metrics": fmt,
            "report_url": f"/reports/{fname}" if report_ok else None,
            "name": name,
            "code": code,
            "strategy_desc": strat.describe(),
            "days": int(m.get("回测天数", 0)),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json(force=True) or {}
    top_n = data.get("top") or config.TOP_N
    style = data.get("style") or None
    candidate_limit = data.get("candidate_limit") or config.CANDIDATE_LIMIT
    mode = data.get("mode") or "general"

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "running", "message": "正在初始化...", "result": None}

    def run():
        def progress(msg):
            TASKS[task_id]["message"] = msg
        try:
            result = recommend_mod.recommend(
                top_n=int(top_n), candidate_limit=int(candidate_limit),
                style=style, verbose=False, progress=progress, mode=mode)
            # 生成推荐报告（写失败时静默降级，不影响结果返回）
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"recommend_{ts}.html"
            path = os.path.join(config.REPORT_DIR, fname)
            report_ok = html_report.render_recommend(result, path)
            if report_ok:
                result["report_url"] = f"/reports/{fname}"
            TASKS[task_id] = {
                "status": "done", "message": "扫描完成",
                "result": result,
            }
        except Exception as e:
            TASKS[task_id] = {"status": "error", "message": str(e), "result": None}

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


@app.route("/api/recommend/status/<task_id>")
def api_recommend_status(task_id):
    task = TASKS.get(task_id)
    if task is None:
        return jsonify({"status": "not_found"}), 404
    return jsonify(task)


@app.route("/api/reports")
def api_reports():
    reports = []
    d = config.REPORT_DIR
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d), reverse=True):
            if fn.endswith(".html"):
                p = os.path.join(d, fn)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p))
                reports.append({
                    "filename": fn,
                    "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "回测" if fn.startswith("backtest_") else "推荐",
                    "url": f"/reports/{fn}",
                })
    return jsonify(reports)


@app.route("/reports/<path:filename>")
def view_report(filename):
    return send_from_directory(config.REPORT_DIR, filename)


if __name__ == "__main__":
    print("A股回测系统 Web 版已启动： http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
