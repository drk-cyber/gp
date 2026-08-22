// A股回测系统 — 前端逻辑
(function () {
  "use strict";

  // ---------- 视图切换 ----------
  const navItems = document.querySelectorAll(".nav-item");
  const views = document.querySelectorAll(".view");
  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      navItems.forEach((b) => b.classList.remove("active"));
      views.forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      const view = document.getElementById("view-" + btn.dataset.view);
      if (view) view.classList.add("active");
      if (btn.dataset.view === "reports") loadReports();
    });
  });

  // ---------- 工具函数 ----------
  const $ = (sel) => document.querySelector(sel);

  function fmtPct(v) {
    if (v === null || v === undefined) return "-";
    return (v > 0 ? "+" : "") + v.toFixed(2) + "%";
  }
  function cls(v) { return v > 0 ? "up" : v < 0 ? "down" : ""; }

  // ---------- 加载策略列表 ----------
  async function loadStrategies() {
    try {
      const res = await fetch("/api/strategies");
      const list = await res.json();
      const sel = $("#bt-strategy");
      sel.innerHTML = "";
      list.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.name;
        opt.textContent = s.name + " · " + s.desc;
        sel.appendChild(opt);
      });
    } catch (e) {
      console.error(e);
    }
  }

  // ---------- 选股推荐 ----------
  const recBtn = $("#rec-btn");
  const recStatus = $("#rec-status");
  const recResult = $("#rec-result");
  let recPolling = null;

  recBtn.addEventListener("click", async () => {
    recBtn.disabled = true;
    recStatus.classList.remove("hidden", "error");
    recStatus.innerHTML = '<span class="spinner"></span>正在提交扫描任务...';
    recResult.classList.add("hidden");

    const payload = {
      top: parseInt($("#rec-top").value || "10", 10),
      style: $("#rec-style").value || null,
      mode: $("#rec-mode").value || "general",
    };

    try {
      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.task_id) {
        startRecommendPolling(data.task_id);
      } else {
        showStatus(recStatus, data.error || "提交失败", true);
        recBtn.disabled = false;
      }
    } catch (e) {
      showStatus(recStatus, "网络错误：" + e, true);
      recBtn.disabled = false;
    }
  });

  function startRecommendPolling(taskId) {
    clearInterval(recPolling);
    recPolling = setInterval(async () => {
      try {
        const res = await fetch("/api/recommend/status/" + taskId);
        const task = await res.json();
        if (task.status === "running") {
          recStatus.innerHTML = '<span class="spinner"></span>' + escapeHtml(task.message || "扫描中...");
        } else if (task.status === "done") {
          clearInterval(recPolling);
          recBtn.disabled = false;
          recStatus.classList.add("hidden");
          renderRecommend(task.result);
        } else if (task.status === "error") {
          clearInterval(recPolling);
          recBtn.disabled = false;
          showStatus(recStatus, task.message || "扫描失败", true);
        }
      } catch (e) {
        clearInterval(recPolling);
        recBtn.disabled = false;
        showStatus(recStatus, "查询状态失败：" + e, true);
      }
    }, 1200);
  }

  function renderRecommend(result) {
    if (!result || !result.recommendations || !result.recommendations.length) {
      recResult.classList.remove("hidden");
      recResult.innerHTML = '<p class="empty">未筛选出符合条件的股票。</p>';
      return;
    }

    const m = result.market || {};
    const b = m.breadth || {};
    const idx = (m.index_trend || [])
      .filter((i) => i.close !== null)
      .map((i) => `${i.name} ${i.close} · ${i.trend} · 5日${fmtPct(i.chg5d)}`)
      .join("　");
    const isDip = result.recommendations[0] && result.recommendations[0].take_profit !== undefined;

    let rows = "";
    result.recommendations.forEach((r, i) => {
      const reasons = (r.reasons || []).slice(0, 5).join(" · ");
      const risks = (r.risks || []).slice(0, 3).join("、");
      if (isDip) {
        const dip = r.dip_pct != null ? (r.dip_pct > 0 ? "+" : "") + r.dip_pct.toFixed(1) + "%" : "-";
        rows += `<tr>
          <td class="mono">${i + 1}</td>
          <td class="mono">${r.code}</td>
          <td><b>${escapeHtml(r.name)}</b></td>
          <td class="mono">${r.price !== null ? r.price : "-"}</td>
          <td class="mono down">${dip}</td>
          <td class="mono up">${r.take_profit}</td>
          <td class="mono down">${r.stop_loss}</td>
          <td class="score mono">${r.score}</td>
          <td><span class="reason">${escapeHtml(reasons || "-")}</span>${risks ? '<br><span class="risk">风险：' + escapeHtml(risks) + "</span>" : ""}</td>
        </tr>`;
      } else {
        const pe = r.pe !== null && r.pe !== undefined ? r.pe.toFixed(1) : "-";
        rows += `<tr>
          <td class="mono">${i + 1}</td>
          <td class="mono">${r.code}</td>
          <td><b>${escapeHtml(r.name)}</b></td>
          <td class="mono">${r.price !== null ? r.price : "-"}</td>
          <td class="mono ${cls(r.pct_chg)}">${fmtPct(r.pct_chg)}</td>
          <td class="mono">${pe}</td>
          <td class="score mono">${r.score}</td>
          <td><span class="reason">${escapeHtml(reasons || "-")}</span>${risks ? '<br><span class="risk">风险：' + escapeHtml(risks) + "</span>" : ""}</td>
        </tr>`;
      }
    });

    let reportLink = "";
    if (result.report_url) {
      reportLink = `<p style="margin-top:16px"><a class="report-open" href="${result.report_url}" target="_blank">打开完整推荐报告 →</a></p>`;
    }

    const thead = isDip
      ? '<th>排名</th><th>代码</th><th>名称</th><th>现价</th><th>近5日跌幅</th><th>止盈位</th><th>止损位</th><th>得分</th><th>理由</th>'
      : '<th>排名</th><th>代码</th><th>名称</th><th>现价</th><th>涨跌幅</th><th>PE</th><th>得分</th><th>推荐理由</th>';

    recResult.innerHTML = `
      <div class="market">
        <div class="market-state"><span class="dot"></span>${escapeHtml(m.state || "未知")}</div>
        <div class="market-stats">
          <span>上涨 <b>${b["上涨"] ?? 0}</b></span>
          <span>下跌 <b>${b["下跌"] ?? 0}</b></span>
          <span>涨停 <b>${b["涨停"] ?? 0}</b></span>
          <span>跌停 <b>${b["跌停"] ?? 0}</b></span>
        </div>
        ${idx ? `<div class="market-stats" style="margin-top:8px">${escapeHtml(idx)}</div>` : ""}
      </div>
      <table>
        <thead><tr>${thead}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${reportLink}
    `;
    recResult.classList.remove("hidden");
  }

  // ---------- 策略回测 ----------
  const btBtn = $("#bt-btn");
  const btStatus = $("#bt-status");
  const btResult = $("#bt-result");

  btBtn.addEventListener("click", async () => {
    const code = $("#bt-code").value.trim();
    if (!code) { showStatus(btStatus, "请填写股票代码", true); return; }

    btBtn.disabled = true;
    btStatus.classList.remove("hidden", "error");
    btStatus.innerHTML = '<span class="spinner"></span>正在拉取数据并回测...';
    btResult.classList.add("hidden");

    const payload = {
      strategy: $("#bt-strategy").value,
      code: code,
      start: $("#bt-start").value || null,
      end: $("#bt-end").value || null,
      initial_cash: parseFloat($("#bt-cash").value || "100000"),
    };

    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.error) {
        showStatus(btStatus, data.error, true);
      } else {
        btStatus.classList.add("hidden");
        renderBacktest(data);
      }
    } catch (e) {
      showStatus(btStatus, "网络错误：" + e, true);
    } finally {
      btBtn.disabled = false;
    }
  });

  function renderBacktest(data) {
    const m = data.metrics || {};
    const order = ["总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数"];
    let cards = "";
    order.forEach((k) => {
      const v = m[k] ?? "-";
      let color = "var(--text)";
      if (k === "总收益率" || k === "年化收益率") {
        color = v.startsWith("-") ? "var(--down)" : "var(--up)";
      } else if (k === "最大回撤") {
        color = "var(--down)";
      }
      cards += `<div class="metric">
        <div class="metric-label">${k}</div>
        <div class="metric-value" style="color:${color}">${v}</div>
      </div>`;
    });

    btResult.innerHTML = `
      <h2>${escapeHtml(data.name || data.code)}（${data.code}）</h2>
      <p class="view-desc" style="margin-bottom:14px">${escapeHtml(data.strategy_desc || "")} · 共 ${data.days ?? 0} 个交易日</p>
      <div class="metrics">${cards}</div>
      <p style="margin-top:16px"><a class="report-open" href="${data.report_url}" target="_blank">打开完整回测报告 →</a></p>
    `;
    btResult.classList.remove("hidden");
  }

  // ---------- 报告列表 ----------
  async function loadReports() {
    const box = $("#reports-list");
    try {
      const res = await fetch("/api/reports");
      const list = await res.json();
      if (!list.length) {
        box.innerHTML = '<p class="empty">暂无报告，先运行一次回测或推荐。</p>';
        return;
      }
      box.innerHTML = list.map((r) => `
        <div class="report-item">
          <div class="report-meta">
            <span class="report-tag ${r.type === "回测" ? "bt" : ""}">${r.type}</span>
            <span class="report-name">${escapeHtml(r.filename)}</span>
            <span class="report-time">${r.mtime}</span>
          </div>
          <a class="report-open" href="${r.url}" target="_blank">查看 →</a>
        </div>
      `).join("");
    } catch (e) {
      box.innerHTML = '<p class="empty">加载失败：' + escapeHtml(e) + "</p>";
    }
  }
  $("#reports-refresh").addEventListener("click", loadReports);

  // ---------- 辅助 ----------
  function showStatus(el, msg, isError) {
    el.classList.remove("hidden");
    el.classList.toggle("error", !!isError);
    el.innerHTML = (isError ? "" : '<span class="spinner"></span>') + escapeHtml(msg);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---------- 初始化 ----------
  loadStrategies();
})();
