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

  // 市场状态面板：温度计 + 宽度统计 + 指数行情
  function marketPanel(m) {
    const b = (m && m.breadth) || {};
    const up = Number(b["上涨"] || 0);
    const down = Number(b["下跌"] || 0);
    const total = up + down;
    const upW = total > 0 ? (up / total * 100).toFixed(1) : "50";

    const chips = (m.index_trend || [])
      .filter((i) => i.close !== null)
      .map((i) => {
        const c = i.chg5d == null ? "" : "ix-chg " + (i.chg5d >= 0 ? "pos" : "neg");
        const chg = i.chg5d == null ? "" : " 5日" + fmtPct(i.chg5d);
        return `<span class="index-chip">
          <span class="ix-name">${escapeHtml(i.name)}</span>
          <span class="ix-close">${i.close}</span>
          <span class="${c}">${escapeHtml(chg)}</span>
        </span>`;
      })
      .join("");

    return `<div class="panel market">
      <div class="panel-head">
        <span class="panel-title">市场状态</span>
        <span class="panel-hint">红为上涨家数 · 绿为下跌家数</span>
      </div>
      <div class="panel-body">
        <div class="market-state-row">
          <div class="market-state"><span class="dot"></span>${escapeHtml((m && m.state) || "未知")}</div>
        </div>
        <div class="thermo">
          <div class="seg up" data-w="${upW}%"></div>
          <div class="seg down" data-w="${total > 0 ? (100 - upW).toFixed(1) : 50}%"></div>
        </div>
        <div class="thermo-legend">
          <span class="lk-up">上涨<b>${up}</b></span>
          <span class="lk-down">下跌<b>${down}</b></span>
          <span>涨停<b>${b["涨停"] ?? 0}</b></span>
          <span>跌停<b>${b["跌停"] ?? 0}</b></span>
        </div>
        ${chips ? `<div class="index-row">${chips}</div>` : ""}
      </div>
    </div>`;
  }

  function scoreCell(score) {
    const s = Number(score);
    if (!isFinite(s)) return `<td class="r">-</td>`;
    const w = Math.max(0, Math.min(100, s));
    return `<td class="r"><span class="score-cell">
      <span class="score-num">${score}</span>
      <span class="scorebar"><i style="width:${w}%"></i></span>
    </span></td>`;
  }

  function reasonCell(r) {
    const reasons = (r.reasons || []).slice(0, 5).join(" · ");
    const risks = (r.risks || []).slice(0, 3).join("、");
    return `<td><span class="reason">${escapeHtml(reasons || "-")}</span>` +
      (risks ? `<span class="risk">风险提示：${escapeHtml(risks)}</span>` : "") +
      `</td>`;
  }

  function renderRecommend(result) {
    if (!result || !result.recommendations || !result.recommendations.length) {
      recResult.classList.remove("hidden");
      recResult.innerHTML = '<p class="empty">本次扫描未筛选出符合条件的股票，换个模式或稍后再试。</p>';
      return;
    }

    const m = result.market || {};
    const isDip = result.recommendations[0] && result.recommendations[0].take_profit !== undefined;

    let rows = "";
    result.recommendations.forEach((r, i) => {
      const rank = `<td class="mono">${String(i + 1).padStart(2, "0")}</td>`;
      const code = `<td class="mono stock-code">${r.code}</td>`;
      const name = `<td class="stock-name">${escapeHtml(r.name)}</td>`;
      const price = `<td class="r mono">${r.price !== null && r.price !== undefined ? r.price : "-"}</td>`;
      if (isDip) {
        const dip = r.dip_pct != null ? (r.dip_pct > 0 ? "+" : "") + r.dip_pct.toFixed(1) + "%" : "-";
        rows += `<tr>
          ${rank}${code}${name}${price}
          <td class="r mono down">${dip}</td>
          <td class="r mono up">${r.take_profit}</td>
          <td class="r mono down">${r.stop_loss}</td>
          ${scoreCell(r.score)}
          ${reasonCell(r)}
        </tr>`;
      } else {
        const pe = r.pe !== null && r.pe !== undefined ? r.pe.toFixed(1) : "-";
        rows += `<tr>
          ${rank}${code}${name}${price}
          <td class="r mono ${cls(r.pct_chg)}">${fmtPct(r.pct_chg)}</td>
          <td class="r mono">${pe}</td>
          ${scoreCell(r.score)}
          ${reasonCell(r)}
        </tr>`;
      }
    });

    const thead = isDip
      ? '<th>排名</th><th>代码</th><th>名称</th><th class="r">现价</th><th class="r">近5日跌幅</th><th class="r">止盈位</th><th class="r">止损位</th><th class="r">得分</th><th>理由</th>'
      : '<th>排名</th><th>代码</th><th>名称</th><th class="r">现价</th><th class="r">涨跌幅</th><th class="r">PE</th><th class="r">得分</th><th>推荐理由</th>';

    let reportLink = "";
    if (result.report_url) {
      reportLink = `<p class="report-link-row"><a class="report-open" href="${result.report_url}" target="_blank">打开完整推荐报告 →</a></p>`;
    }

    recResult.innerHTML = `
      ${marketPanel(m)}
      <div class="table-wrap"><div class="table-scroll">
        <table>
          <thead><tr>${thead}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div></div>
      ${reportLink}
    `;
    recResult.classList.remove("hidden");

    // 温度计入场动画：先渲染 0 宽，再过渡到目标宽度
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        recResult.querySelectorAll(".thermo .seg").forEach((el) => {
          el.style.width = el.dataset.w;
        });
      });
    });
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
        color = String(v).startsWith("-") ? "var(--down)" : "var(--up)";
      } else if (k === "最大回撤") {
        color = "var(--down)";
      }
      cards += `<div class="metric">
        <div class="metric-label">${k}</div>
        <div class="metric-value" style="color:${color}">${escapeHtml(String(v))}</div>
      </div>`;
    });

    btResult.innerHTML = `
      <div class="result-lead">
        <span class="result-title">${escapeHtml(data.name || data.code)}</span>
        <span class="result-sub mono">${data.code} · 共 ${data.days ?? 0} 个交易日</span>
      </div>
      <p class="view-desc" style="margin-bottom:14px">${escapeHtml(data.strategy_desc || "")}</p>
      <div class="metrics">${cards}</div>
      ${data.report_url
        ? `<p class="report-link-row"><a class="report-open" href="${data.report_url}" target="_blank">打开完整回测报告 →</a></p>`
        : ""}
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
        box.innerHTML = '<p class="empty">暂无报告 — 运行一次回测或选股扫描后，报告会归档在这里。</p>';
        return;
      }
      box.innerHTML = list.map((r) => `
        <div class="report-item">
          <div class="report-meta">
            <span class="report-tag ${r.type === "回测" ? "bt" : ""}">${r.type}</span>
            <span class="report-name">${escapeHtml(r.filename)}</span>
          </div>
          <span class="report-time">${r.mtime}</span>
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
