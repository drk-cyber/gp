// A股回测系统 — 页面交互与数据展示
(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const viewNames = { recommend: "选股推荐", backtest: "策略回测", reports: "报告归档" };
  const generalGuideHtml = $("#guide-body")?.innerHTML || "";
  const strategyNames = {
    ma_cross: "双均线策略", macd: "MACD 策略", rsi: "RSI 策略",
    bollinger: "布林带策略", kdj: "KDJ 策略", volume_price: "量价配合策略",
    grid: "网格交易", dca: "定投策略", turtle: "海龟法则",
  };
  const modes = {
    general: {
      title: "综合推荐", summary: "结合市场状态，从技术、估值、资金与风险四个维度筛选。",
      guide: "综合评分如何构成",
      steps: ["判断大盘状态，自动匹配进攻、防守或均衡风格。", "过滤 ST、停牌及流动性不足的股票，缩小候选范围。", "综合多维度信号打分，查看推荐理由与风险提示。"],
    },
    dip: {
      title: "60 日线反弹", summary: "围绕 60 日趋势线，寻找近期回调后的反弹候选。",
      guide: "寻找中期趋势中的回调机会",
      steps: ["以 60 日均线作为趋势参考，筛选超跌反弹候选。", "结合近期跌幅、技术信号和成交情况进行排序。", "对照止盈位、止损位及风险提示，评估交易空间。"],
    },
    dip120: {
      title: "120 日线反弹", summary: "以 120 日半年线为趋势参考，筛选超跌反弹机会。",
      guide: "以半年线观察更长趋势",
      steps: ["以 120 日均线作为趋势参考，观察更长周期的支撑。", "筛选近期回调的股票，结合技术条件进行评分。", "查看止盈止损位置与推荐理由，进一步研究候选。"],
    },
  };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function reportUrl(value) {
    if (typeof value !== "string" || !/^\/reports\/[^?#]+\.html$/.test(value)) return null;
    try {
      const url = new URL(value, window.location.origin);
      const decoded = decodeURIComponent(url.pathname);
      if (url.origin !== window.location.origin || !url.pathname.startsWith("/reports/") ||
          !decoded.startsWith("/reports/") || decoded.includes("\\") ||
          decoded.split("/").some((part) => part === ".." || part === ".")) return null;
      return url.pathname;
    } catch (_) { return null; }
  }
  function reportLink(value, label) {
    const url = reportUrl(value);
    return url ? `<a class="report-open" href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>` : "";
  }
  function setText(selector, value) { const el = $(selector); if (el) el.textContent = value; }
  function hide(selector, hidden = true) { const el = $(selector); if (el) el.classList.toggle("hidden", hidden); }
  function finite(value) { return value === null || value === undefined || value === "" ? null : Number.isFinite(Number(value)) ? Number(value) : null; }
  function fmtPct(value, digits = 2) {
    const n = finite(value);
    return n === null ? "—" : (n > 0 ? "+" : "") + n.toFixed(digits) + "%";
  }
  function fmtNumber(value, digits = 2) {
    const n = finite(value);
    return n === null ? "—" : n.toLocaleString("zh-CN", { maximumFractionDigits: digits });
  }
  function cls(value) { const n = finite(value); return n > 0 ? "up" : n < 0 ? "down" : ""; }

  async function requestJson(url, options) {
    let response;
    try { response = await fetch(url, options); }
    catch (_) { throw new Error("无法连接本地服务，请确认服务运行后重试。"); }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error(`服务返回了无法读取的内容（HTTP ${response.status}），请稍后重试。`); }
    if (!response.ok) {
      const error = new Error(data?.error || data?.message || `请求失败（HTTP ${response.status}），请重试。`);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }
  function showStatus(el, message, isError = false) {
    el.classList.remove("hidden");
    el.classList.toggle("error", isError);
    el.setAttribute("role", isError ? "alert" : "status");
    el.innerHTML = (isError ? "" : '<span class="spinner" aria-hidden="true"></span>') + escapeHtml(message);
  }
  function invalid(input, message, status) {
    input.setAttribute("aria-invalid", "true");
    input.setCustomValidity(message);
    showStatus(status, message, true);
    input.focus();
    return false;
  }
  $$("input, select").forEach((input) => {
    const clear = () => { input.removeAttribute("aria-invalid"); input.setCustomValidity(""); };
    input.addEventListener("input", clear);
    input.addEventListener("change", clear);
  });

  // 导航：地址栏保存当前页面，支持刷新与浏览器前进/后退。
  function activateView(name) {
    const current = Object.prototype.hasOwnProperty.call(viewNames, name) ? name : "recommend";
    $$(".nav-item").forEach((button) => {
      const active = button.dataset.view === current;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $$(".view").forEach((view) => view.classList.toggle("active", view.id === "view-" + current));
    setText("#breadcrumb-current", viewNames[current]);
    document.title = viewNames[current] + " · A股研究台";
    if (current === "reports") loadReports();
  }
  $$("[data-view]").forEach((button) => button.addEventListener("click", () => {
    const name = button.dataset.view;
    if (!Object.prototype.hasOwnProperty.call(viewNames, name)) return;
    if (window.location.hash === "#" + name) activateView(name);
    else window.location.hash = name;
  }));
  window.addEventListener("hashchange", () => activateView(window.location.hash.slice(1)));

  function updateMode() {
    const selected = $("#rec-mode").value;
    const mode = modes[selected] || modes.general;
    $$("[data-mode]").forEach((button) => {
      const active = button.dataset.mode === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const isDip = selected !== "general";
    $("#rec-style").disabled = isDip;
    setText("#rec-mode-summary", mode.summary);
    setText("#guide-title", mode.guide);
    setText("#rec-style-hint", isDip ? "超跌模式使用独立筛选逻辑，无需设置风格。" : "自动判断将根据大盘状态选择推荐风格。");
    const guide = $("#guide-body");
    if (guide) guide.innerHTML = selected === "general" && generalGuideHtml
      ? generalGuideHtml
      : `<ol>${mode.steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`;
  }
  $$("[data-mode]").forEach((button) => button.addEventListener("click", () => {
    if (!Object.prototype.hasOwnProperty.call(modes, button.dataset.mode)) return;
    $("#rec-mode").value = button.dataset.mode;
    updateMode();
  }));
  $("#rec-mode").addEventListener("change", updateMode);

  // 策略说明与加载失败后的重试。
  let strategies = [];
  const btBtn = $("#bt-btn");
  const btStatus = $("#bt-status");
  const btResult = $("#bt-result");
  function updateStrategy() {
    const selected = strategies.find((strategy) => strategy.name === $("#bt-strategy").value);
    setText("#strategy-description", selected ? selected.desc : "选择策略后查看具体交易规则。");
  }
  async function loadStrategies() {
    const select = $("#bt-strategy");
    const previous = select.value;
    select.disabled = true;
    btBtn.disabled = true;
    hide("#strategy-retry");
    setText("#strategy-description", "正在加载策略列表…");
    try {
      const list = await requestJson("/api/strategies");
      if (!Array.isArray(list) || !list.length) throw new Error("暂无可用策略，请重试加载。");
      strategies = list.filter((strategy) => strategy && typeof strategy.name === "string");
      if (!strategies.length) throw new Error("策略列表格式异常，请重试加载。");
      select.innerHTML = "";
      strategies.forEach((strategy) => {
        const option = document.createElement("option");
        option.value = strategy.name;
        option.textContent = strategyNames[strategy.name] || strategy.name;
        select.appendChild(option);
      });
      if (strategies.some((strategy) => strategy.name === previous)) select.value = previous;
      select.disabled = false;
      btBtn.disabled = false;
      updateStrategy();
    } catch (error) {
      setText("#strategy-description", "策略加载失败：" + error.message);
      hide("#strategy-retry", false);
    }
  }
  $("#bt-strategy").addEventListener("change", updateStrategy);
  if ($("#strategy-retry")) $("#strategy-retry").addEventListener("click", loadStrategies);

  // 选股任务：逐次查询，避免慢网络下并发轮询。
  const recBtn = $("#rec-btn");
  const recStatus = $("#rec-status");
  const recResult = $("#rec-result");
  let recPolling = null;
  let submittedMode = "general";
  function finishRecommendError(message) {
    clearTimeout(recPolling);
    recBtn.disabled = false;
    recResult.setAttribute("aria-busy", "false");
    showStatus(recStatus, message, true);
    hide("#rec-empty", false);
  }
  recBtn.addEventListener("click", async () => {
    if (recBtn.disabled) return;
    const count = $("#rec-top");
    const top = Number(count.value);
    if (!Number.isInteger(top) || top < 1 || top > 50) {
      invalid(count, "推荐数量请输入 1 至 50 之间的整数。", recStatus);
      return;
    }
    submittedMode = $("#rec-mode").value || "general";
    recBtn.disabled = true;
    recResult.setAttribute("aria-busy", "true");
    showStatus(recStatus, "正在提交扫描任务…");
    hide("#rec-result");
    hide("#rec-empty");
    try {
      const data = await requestJson("/api/recommend", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ top, style: submittedMode === "general" ? $("#rec-style").value || null : null, mode: submittedMode }),
      });
      if (!data?.task_id) throw new Error(data?.error || "未收到扫描任务编号，请重新提交。");
      pollRecommend(data.task_id);
    } catch (error) { finishRecommendError(error.message || "无法连接服务，请稍后重试。"); }
  });
  async function pollRecommend(taskId) {
    clearTimeout(recPolling);
    try {
      const task = await requestJson("/api/recommend/status/" + encodeURIComponent(taskId));
      if (task?.status === "running") {
        showStatus(recStatus, task.message || "正在扫描，请稍候…");
        recPolling = setTimeout(() => pollRecommend(taskId), 1200);
      } else if (task?.status === "done") {
        recBtn.disabled = false;
        recResult.setAttribute("aria-busy", "false");
        hide("#rec-status");
        renderRecommend(task.result);
        loadReports();
      } else if (task?.status === "error") {
        finishRecommendError(task.message || "扫描失败，请稍后重试。");
      } else if (task?.status === "not_found") {
        finishRecommendError("扫描任务已失效，服务可能已重启，请重新开始扫描。");
      } else {
        finishRecommendError("扫描返回了未知状态，请重新开始扫描。");
      }
    } catch (error) {
      finishRecommendError(error.status === 404 || error.data?.status === "not_found"
        ? "扫描任务已失效，服务可能已重启，请重新开始扫描。"
        : "查询扫描状态失败：" + error.message);
    }
  }

  function marketPanel(market) {
    const m = market || {};
    const breadth = m.breadth || {};
    const up = Math.max(0, finite(breadth["上涨"]) || 0);
    const down = Math.max(0, finite(breadth["下跌"]) || 0);
    const total = up + down;
    const upWidth = total ? (up / total * 100).toFixed(1) : "0";
    const downWidth = total ? (down / total * 100).toFixed(1) : "0";
    const chips = (Array.isArray(m.index_trend) ? m.index_trend : [])
      .filter((index) => index && finite(index.close) !== null)
      .map((index) => `<span class="index-chip"><span class="ix-name">${escapeHtml(index.name)}</span><span class="ix-close">${fmtNumber(index.close)}</span><span class="ix-chg ${cls(index.chg5d)}">5日 ${fmtPct(index.chg5d)}</span></span>`).join("");
    return `<div class="panel market"><div class="panel-head"><span class="panel-title">市场概览</span><span class="panel-hint">本次扫描快照 · 红涨绿跌</span></div>
      <div class="panel-body"><div class="market-state-row"><div class="market-state"><span class="dot" aria-hidden="true"></span>${escapeHtml(m.state || "暂无市场状态")}</div><span class="panel-hint">${total ? "上涨占比 " + upWidth + "%" : "暂无涨跌家数"}</span></div>
        <div class="thermo" aria-hidden="true"><div class="seg up" data-w="${upWidth}%"></div><div class="seg down" data-w="${downWidth}%"></div></div>
        <div class="thermo-legend"><span class="lk-up">上涨<b>${total ? fmtNumber(up, 0) : "—"}</b></span><span class="lk-down">下跌<b>${total ? fmtNumber(down, 0) : "—"}</b></span><span>涨停<b>${fmtNumber(breadth["涨停"], 0)}</b></span><span>跌停<b>${fmtNumber(breadth["跌停"], 0)}</b></span></div>
        ${chips ? `<div class="index-row">${chips}</div>` : ""}</div></div>`;
  }
  function scoreCell(value) {
    const score = finite(value);
    if (score === null) return '<td class="r">—</td>';
    return `<td class="r"><span class="score-cell"><span class="score-num">${fmtNumber(score)}</span><span class="scorebar" aria-hidden="true"><i style="width:${Math.max(0, Math.min(100, score))}%"></i></span></span></td>`;
  }
  function reasonCell(stock) {
    const reasons = (Array.isArray(stock.reasons) ? stock.reasons : []).slice(0, 5).join(" · ");
    const risks = (Array.isArray(stock.risks) ? stock.risks : []).slice(0, 3).join("、");
    const breakdown = stock.score_breakdown && typeof stock.score_breakdown === "object"
      ? Object.entries(stock.score_breakdown).slice(0, 4).map(([key, value]) => `${key} ${fmtNumber(value, 1)}`).join(" · ") : "";
    const plan = stock.entry_low != null && stock.entry_high != null
      ? `计划入场 ${fmtNumber(stock.entry_low)}–${fmtNumber(stock.entry_high)} · 止损 ${fmtNumber(stock.stop_loss)} · 目标 ${fmtNumber(stock.take_profit)}`
      : "";
    const trigger = stock.entry_trigger ? `触发：${stock.entry_trigger}` : "";
    return `<td><span class="reason">${escapeHtml(reasons || "暂无说明")}</span>${breakdown ? `<span class="report-detail">评分拆解：${escapeHtml(breakdown)}</span>` : ""}${plan ? `<span class="risk">${escapeHtml(plan)}</span>` : ""}${trigger ? `<span class="report-detail">${escapeHtml(trigger)} · 信号约 ${escapeHtml(stock.signal_valid_days ?? "—")} 个交易日有效</span>` : ""}${risks ? `<span class="risk">风险提示：${escapeHtml(risks)}</span>` : ""}</td>`;
  }
  function renderRecommend(result) {
    const recommendations = Array.isArray(result?.recommendations) ? result.recommendations.filter(Boolean) : [];
    if (!recommendations.length) {
      recResult.innerHTML = '<div class="panel empty"><p class="empty-title">暂未找到符合条件的股票</p><p class="empty-copy">尝试切换推荐模式，或待行情变化后重新扫描。</p></div>';
      hide("#rec-result", false);
      return;
    }
    const isDip = recommendations[0].dip_pct !== undefined;
    const rows = recommendations.map((stock, index) => {
      const base = `<td class="mono">${String(index + 1).padStart(2, "0")}</td><td class="mono stock-code">${escapeHtml(stock.code)}</td><td class="stock-name">${escapeHtml(stock.name)}</td><td class="r mono">${fmtNumber(stock.price)}</td>`;
      const values = isDip
        ? `<td class="r mono ${cls(stock.dip_pct)}">${fmtPct(stock.dip_pct, 1)}</td><td class="r mono up">${fmtNumber(stock.take_profit)}</td><td class="r mono down">${fmtNumber(stock.stop_loss)}</td>`
        : `<td class="r mono ${cls(stock.pct_chg)}">${fmtPct(stock.pct_chg)}</td><td class="r mono">${finite(stock.pe) === null ? "—" : Number(stock.pe).toFixed(1)}</td>`;
      return `<tr>${base}${values}${scoreCell(stock.score)}${reasonCell(stock)}</tr>`;
    }).join("");
    const columns = ["排名", "代码", "名称", "现价", ...(isDip ? ["近5日跌幅", "止盈位", "止损位"] : ["涨跌幅", "PE"]), "得分", "推荐理由"];
    const headings = columns.map((column, index) => `<th scope="col"${index >= 3 && index < columns.length - 1 ? ' class="r"' : ""}>${column}</th>`).join("");
    const link = reportLink(result.report_url, "查看完整推荐报告 ↗");
    recResult.innerHTML = `${marketPanel(result.market)}<div class="section-heading"><h2>优选名单</h2><span class="section-count">${escapeHtml((modes[submittedMode] || modes.general).title)} · ${recommendations.length} 只股票</span></div>
      <div class="table-wrap"><div class="table-scroll" tabindex="0" role="region" aria-label="选股推荐结果，可横向滚动"><table><thead><tr>${headings}</tr></thead><tbody>${rows}</tbody></table></div></div>${link ? `<p class="report-link-row">${link}</p>` : ""}`;
    hide("#rec-result", false);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      recResult.querySelectorAll(".thermo .seg").forEach((segment) => { segment.style.width = segment.dataset.w; });
    }));
  }

  // 回测参数验证与结果。
  btBtn.addEventListener("click", async () => {
    if (btBtn.disabled) return;
    const codeInput = $("#bt-code");
    const cashInput = $("#bt-cash");
    const startInput = $("#bt-start");
    const endInput = $("#bt-end");
    const code = codeInput.value.trim();
    const cash = Number(cashInput.value);
    if (!/^\d{6}$/.test(code)) return invalid(codeInput, "请输入 6 位股票代码，例如 600519。", btStatus);
    if (!Number.isFinite(cash) || cash <= 0) return invalid(cashInput, "初始资金请输入大于 0 的金额。", btStatus);
    if (startInput.validity.badInput) return invalid(startInput, "请输入完整有效的起始日期。", btStatus);
    if (endInput.validity.badInput) return invalid(endInput, "请输入完整有效的结束日期。", btStatus);
    if (startInput.value && endInput.value && startInput.value > endInput.value) return invalid(endInput, "结束日期不能早于起始日期。", btStatus);
    if (!strategies.some((strategy) => strategy.name === $("#bt-strategy").value)) return invalid($("#bt-strategy"), "请选择一个有效的回测策略。", btStatus);
    btBtn.disabled = true;
    btResult.setAttribute("aria-busy", "true");
    showStatus(btStatus, "正在获取历史数据并运行回测…");
    hide("#bt-result");
    hide("#bt-empty");
    try {
      const data = await requestJson("/api/backtest", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: $("#bt-strategy").value, code, start: startInput.value || null, end: endInput.value || null, initial_cash: cash }),
      });
      if (!data || data.error) throw new Error(data?.error || "回测结果为空，请稍后重试。");
      hide("#bt-status");
      renderBacktest(data);
      loadReports();
    } catch (error) {
      showStatus(btStatus, error.message || "无法连接服务，请稍后重试。", true);
      hide("#bt-empty", false);
    } finally {
      btBtn.disabled = false;
      btResult.setAttribute("aria-busy", "false");
    }
  });
  function renderBacktest(data) {
    const metrics = data.metrics || {};
    const order = ["总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数"];
    const cards = order.map((key) => {
      const value = metrics[key] ?? "—";
      const numeric = parseFloat(String(value).replace(/[,%]/g, ""));
      const color = key === "最大回撤" && Number.isFinite(numeric) ? "down" : (key === "总收益率" || key === "年化收益率") ? cls(numeric) : "";
      return `<div class="metric"><div class="metric-label">${key}</div><div class="metric-value ${color}">${escapeHtml(value)}</div></div>`;
    }).join("");
    const link = reportLink(data.report_url, "查看资金曲线与交易明细 ↗");
    btResult.innerHTML = `<div class="section-heading"><h2>回测表现</h2><span class="section-count">${fmtNumber(data.days || 0, 0)} 个交易日</span></div>
      <div class="result-lead"><span class="result-title">${escapeHtml(data.name || data.code)}</span><span class="result-sub mono">${escapeHtml(data.code)}</span></div>
      <p class="result-description">${escapeHtml(data.strategy_desc || "")}</p><div class="metrics">${cards}</div>${link ? `<p class="report-link-row">${link}</p>` : ""}`;
    hide("#bt-result", false);
  }

  // 报告归档：同一份真实数据用于最近报告、总数和筛选。
  let reports = [];
  let reportsLoaded = false;
  let reportsRequest = null;
  let reportFilter = "all";
  function reportInfo(report) {
    const filename = String(report.filename || "");
    const match = /^backtest_(\d{6})_(.+)_\d{8}_\d{6}\.html$/.exec(filename);
    const type = report.type === "回测" || match ? "回测" : "推荐";
    let title = type === "回测" ? "策略回测报告" : "选股推荐报告";
    let detail = type === "回测" ? "历史策略表现" : "市场分析与优选名单";
    if (match) {
      title = match[1] + " · " + (strategyNames[match[2]] || match[2]);
      detail = "回测报告";
    } else if (/^recommend_dip120_/.test(filename)) title = "120 日线反弹报告";
    else if (/^recommend_dip_/.test(filename)) title = "60 日线反弹报告";
    else if (!/^recommend_/.test(filename)) title = filename.replace(/\.html$/i, "") || title;
    return { type, title, detail, filename };
  }
  function renderReports() {
    if (!reportsLoaded) return;
    const search = ($("#reports-search")?.value || "").trim().toLocaleLowerCase("zh-CN");
    const filtered = reports.filter((report) => {
      const info = reportInfo(report);
      return (reportFilter === "all" || info.type === reportFilter) &&
        (!search || [info.title, info.detail, info.filename, report.mtime].join(" ").toLocaleLowerCase("zh-CN").includes(search));
    });
    setText("#archive-count", reports.length);
    setText("#reports-count", filtered.length === reports.length ? `共 ${reports.length} 份` : `${filtered.length} / ${reports.length} 份`);
    const box = $("#reports-list");
    if (!reports.length) box.innerHTML = '<div class="empty"><p class="empty-title">报告归档从这里开始</p><p class="empty-copy">完成一次选股扫描或策略回测后，生成的报告会自动保存在这里。</p></div>';
    else if (!filtered.length) box.innerHTML = '<div class="empty"><p class="empty-title">没有找到匹配的报告</p><p class="empty-copy">尝试其他股票代码、策略名称或日期，也可以切换报告类型。</p></div>';
    else box.innerHTML = filtered.map((report) => {
      const info = reportInfo(report);
      return `<div class="report-item"><div class="report-meta"><span class="report-tag ${info.type === "回测" ? "bt" : ""}">${info.type}</span><div class="report-main"><span class="report-name" title="${escapeHtml(info.filename)}">${escapeHtml(info.title)}</span><span class="report-detail">${escapeHtml(info.detail)}</span></div></div><time class="report-time">${escapeHtml(report.mtime || "日期未知")}</time>${reportLink(report.url, "查看报告 ↗")}</div>`;
    }).join("");
    const recent = $("#recent-reports");
    if (recent) recent.innerHTML = reports.length ? reports.slice(0, 3).map((report) => {
      const info = reportInfo(report);
      return `<div class="recent-report"><div class="report-main"><span class="report-name">${escapeHtml(info.title)}</span><span class="report-detail">${escapeHtml(report.mtime || "日期未知")}</span></div>${reportLink(report.url, "查看 ↗")}</div>`;
    }).join("") : '<p class="empty-copy">暂无历史报告，完成扫描或回测后会自动归档。</p>';
  }
  async function loadReports() {
    if (reportsRequest) return reportsRequest;
    const box = $("#reports-list");
    const refresh = $("#reports-refresh");
    box.setAttribute("aria-busy", "true");
    refresh.disabled = true;
    if (!reportsLoaded) {
      box.innerHTML = '<p class="empty" role="status">正在加载报告…</p>';
      if ($("#recent-reports")) $("#recent-reports").innerHTML = '<p class="empty-copy" role="status">正在加载最近报告…</p>';
    }
    reportsRequest = (async () => {
      try {
        const list = await requestJson("/api/reports");
        if (!Array.isArray(list)) throw new Error("报告列表格式异常，请刷新重试。");
        reports = list.filter((report) => report && typeof report.filename === "string")
          .sort((a, b) => String(b.mtime || "").localeCompare(String(a.mtime || "")) || b.filename.localeCompare(a.filename));
        reportsLoaded = true;
        renderReports();
      } catch (error) {
        box.innerHTML = `<div class="empty" role="alert"><p class="empty-title">报告暂时无法加载</p><p class="empty-copy">${escapeHtml(error.message)} 点击“刷新列表”重试。</p></div>`;
        if (!reportsLoaded) {
          setText("#archive-count", "—");
          setText("#reports-count", "加载失败");
          if ($("#recent-reports")) $("#recent-reports").innerHTML = '<p class="empty-copy">暂时无法读取历史报告，可前往报告归档重试。</p>';
        }
      } finally {
        box.setAttribute("aria-busy", "false");
        refresh.disabled = false;
        reportsRequest = null;
      }
    })();
    return reportsRequest;
  }
  $("#reports-refresh").addEventListener("click", loadReports);
  if ($("#reports-search")) $("#reports-search").addEventListener("input", renderReports);
  $$("[data-report-filter]").forEach((button) => button.addEventListener("click", () => {
    reportFilter = button.dataset.reportFilter;
    $$("[data-report-filter]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    renderReports();
  }));

  setText("#today-date", new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date()));
  updateMode();
  activateView(window.location.hash.slice(1));
  loadStrategies();
  loadReports();
})();
