/* RationAI — frontend (Phase 7–10 UI redesign).
   The frontend only DISPLAYS backend data: it contains no detection logic, no
   calculations, no thresholds, and no mock results. Every value rendered comes
   from the real workflow response, the real dataset endpoint, or the real
   health endpoint. Derived dashboard numbers (counts, sums, groupings) are
   plain presentation of the fetched dataset — never fabricated.
   The core "Run Analysis" flow is preserved: real POST /api/analyze, loading,
   error, retry, reset, and the full alert/traceability presentation. */
(function () {
  "use strict";

  var API_BASE = (window.RATIONRIGHT_CONFIG && window.RATIONRIGHT_CONFIG.apiBase) || "";
  var ANALYZE_TIMEOUT_MS = 30000;

  /* ------------------------------------------------------------------ *
   *  State
   * ------------------------------------------------------------------ */
  var state = {
    dataset: null,        // full /api/dataset payload
    health: null,         // /api/health payload
    result: null,         // last workflow result
    running: false,       // analysis in flight
    readAlerts: {},       // alert_id -> true (local, session only)
    analysisDataset: "synthetic",  // synthetic | real
    analysisImportId: null,        // data_import_id for real mode
    availableDatasets: null,       // cached GET /api/datasets payload
    // Phase 9 — AI Analysis Command Center
    analysisTypesRegistry: null,   // cached GET /api/analysis/types
    analysisTypes: null,           // {key: bool} selected analysis types
    analysisFilters: { commodity: "", fps: "", district: "", from: "", to: "" },
    analysisPrecheck: null,        // readiness per type (backend-computed)
    analysisHistory: null,         // cached GET /api/analysis/history
    insightSeverity: "all",       // all | critical | high | medium | low
    insightType: "all",           // all | distribution | operational | inventory | demand | recommendation
    insightQuery: "",
    route: "overview",
    beneficiaryId: null,  // open side panel
    beneficiaryPage: 1,
    beneficiaryQuery: "",
    beneficiaryStatus: "all",   // all | ACTIVE | INACTIVE
    beneficiaryState: "all",
    beneficiaryDistrict: "all",
    beneficiaryCategory: "all",
    // Phase 5 — database-backed analytics (server is the source of truth)
    analytics: {
      overview: null, distribution: null, inventory: null,
      beneficiaries: null, fps: null, opAlerts: null, tx: null,
      range: "all",          // today | 7d | 30d | all | custom
      customFrom: "",
      customTo: "",
      granularity: "day",    // trend bucketing
      txPage: 1,
      txStatus: "all",
      error: null
    },
    alertFilter: "all",
    // Phase 11 — Alert Center / monitoring (persisted alerts, not session-only)
    alertSummary: null,          // cached GET /api/alerts/summary (bell + badge)
    simPreset: null,             // {importId, commodity, fps} from Alert -> Run What-If
    alertCenter: {
      summary: null, trend: null, rules: null, list: null,
      severity: "all", type: "all", status: "all", days: "30", q: "",
      page: 1, expanded: {}, busy: false, error: null
    },
    // Phase 12 — Executive Command Center + intelligence reports
    commandCenter: {
      payload: null, reports: null, filters: {},
      reportBusy: false, reportDetail: null, error: null
    },
    // Phase 13 — UI polish
    dataStatus: null,          // cached /api/pipeline/freshness (top-bar chip)
    dataStatusAt: 0,           // ms timestamp of the last freshness fetch
    searchExtra: null,         // command-palette entity index (datasets/alerts/fps…)
    searchExtraAt: 0,
    searchReturnFocus: null,   // element to restore focus to after the palette closes
    // Phase 14 — auth (opt-in; only enforced when the server requires it)
    auth: { checked: false, enabled: false, authenticated: false, overlayShown: false },
    trendMode: "month",
    trendVisible: {},     // ration type -> bool
    searchIndex: [],
    collapsed: false,
    mobileNavOpen: false
  };

  var ROUTES = {
    command: { title: "Command Center" },
    overview: { title: "Overview" },
    analysis: { title: "Analysis" },
    beneficiaries: { title: "Beneficiaries" },
    distribution: { title: "Ration Distribution" },
    inventory: { title: "Inventory" },
    analytics: { title: "Analytics" },
    insights: { title: "AI Insights" },
    simulation: { title: "Decision Support" },
    alerts: { title: "Alerts" },
    reports: { title: "Reports" },
    settings: { title: "Settings" }
  };

  var RATION_COLORS = ["#059669", "#D97706", "#2563EB", "#0891B2", "#CA8A04", "#16A34A", "#94A3B8"];

  /* ------------------------------------------------------------------ *
   *  Icons (inline stroke SVGs)
   * ------------------------------------------------------------------ */
  var ICONS = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    truck: '<rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2"/><circle cx="18.5" cy="18.5" r="2"/>',
    warehouse: '<path d="M22 8.35V20a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8.35a2 2 0 0 1 1.1-1.79l9-4.5a2 2 0 0 1 1.8 0l9 4.5a2 2 0 0 1 1.1 1.79z"/><path d="M6 17h12"/><path d="M6 13h12"/>',
    chart: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    sparkles: '<path d="M12 3l1.7 4.8L18.5 9.5l-4.8 1.7L12 16l-1.7-4.8L5.5 9.5l4.8-1.7L12 3z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z"/><path d="M5 15l.6 1.6L7.2 17l-1.6.6L5 19l-.6-1.4L2.8 17l1.6-.4L5 15z"/>',
    bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    cloud: '<path d="M17.5 19a4.5 4.5 0 0 0 .9-8.9 6 6 0 0 0-11.7-1.4A4 4 0 0 0 6.5 19h11z"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
    alert: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    arrow: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    clipboard: '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    layers: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    package: '<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    table: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>'
  };

  function icon(name, size) {
    size = size || 19;
    var paths = ICONS[name] || ICONS.info;
    return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size +
      '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths + "</svg>";
  }

  /* ------------------------------------------------------------------ *
   *  Utilities
   * ------------------------------------------------------------------ */
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtNumber(value) {
    if (value == null || isNaN(value)) return "—";
    return Number(value).toLocaleString("en-IN");
  }

  function fmtKg(value) {
    if (value == null || isNaN(value)) return "—";
    return fmtNumber(Math.round(value * 100) / 100) + " kg";
  }

  function fmtDate(ts) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
  }

  function $id(id) { return document.getElementById(id); }
  function $view() { return $id("view"); }

  function toast(message, kind) {
    var box = $id("toasts");
    var t = document.createElement("div");
    t.className = "toast" + (kind ? " " + kind : "");
    var glyph = { success: "✓", error: "✕", warning: "⚠" }[kind] || "ℹ";
    t.setAttribute("role", "status");
    var g = document.createElement("span");
    g.className = "toast-icon";
    g.setAttribute("aria-hidden", "true");
    g.textContent = glyph;
    var m = document.createElement("span");
    m.textContent = message;
    t.appendChild(g);
    t.appendChild(m);
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 3200);
  }

  function animateNumber(el, end, formatter) {
    var start = 0, duration = 700, t0 = null;
    formatter = formatter || fmtNumber;
    function step(ts) {
      if (!t0) t0 = ts;
      var p = Math.min((ts - t0) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = formatter(start + (end - start) * eased);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function download(filename, text, mime) {
    var blob = new Blob([text], { type: mime || "application/octet-stream" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 500);
  }

  function toCsv(rows) {
    // Phase 14: neutralize spreadsheet formula injection (cells beginning
    // with = + - @ or control chars) so exported CSVs cannot execute macros.
    function cell(v) {
      v = v == null ? "" : String(v);
      if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    return rows.map(function (r) { return r.map(cell).join(","); }).join("\n");
  }

  /* ------------------------------------------------------------------ *
   *  API layer (real backend only)
   * ------------------------------------------------------------------ */
  async function fetchJson(url, options, timeoutMs) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeoutMs || ANALYZE_TIMEOUT_MS);
    try {
      var response = await fetch(url, Object.assign({ signal: controller.signal }, options || {}));
      var payload = null;
      try { payload = await response.json(); } catch (e) { payload = null; }
      if (!response.ok) {
        var serverMessage = payload && payload.error ?
          (payload.error.message || payload.error) : null;
        var err = new Error(serverMessage ? "HTTP " + response.status + ": " + serverMessage : "HTTP " + response.status);
        err.httpStatus = response.status;
        err.serverMessage = serverMessage;
        // Phase 14: an expired/missing session must surface the login gate,
        // not a confusing raw error.
        if (response.status === 401 && state.auth.enabled && !state.auth.overlayShown) {
          showAuthOverlay();
        }
        throw err;
      }
      return payload;
    } finally {
      clearTimeout(timer);
    }
  }

  async function loadDataset() {
    state.dataset = await fetchJson(API_BASE + "/api/dataset", {}, 10000);
    buildSearchIndex();
    if (state.route === "overview" || state.route === "beneficiaries" ||
        state.route === "distribution" || state.route === "analytics") renderRoute();
  }

  async function loadHealth() {
    try { state.health = await fetchJson(API_BASE + "/api/health", {}, 8000); } catch (e) { state.health = null; }
  }

  function isValidResult(result) {
    return result && typeof result === "object" &&
      typeof result.workflow_status === "string" &&
      result.stages && typeof result.stages === "object" &&
      ["anomalies", "findings", "cases", "alerts", "errors"].every(function (k) { return Array.isArray(result[k]); });
  }

  async function runAnalysis() {
    if (state.running) return;
    state.running = true;
    renderRoute(); // shows loading UI on the analysis view if active

    var result;
    try {
      var payload = { dataset: state.analysisDataset };
      if (state.analysisDataset === "real") {
        payload.data_import_id = state.analysisImportId;
      }
      // Phase 9: the command center sends the selected analysis types and
      // validated filters; the backend runs the real agents + deterministic
      // checks and returns a merged result (with insights/analysis_run).
      if (!state.analysisTypes) {
        state.analysisTypes = { distribution_anomaly: true, recommendations: true,
                                operational_risk: true, inventory_risk: true, demand_forecast: true };
      }
      var types = Object.keys(state.analysisTypes).filter(function (k) { return state.analysisTypes[k]; });
      if (types.length) payload.types = types;
      var filters = {};
      Object.keys(state.analysisFilters || {}).forEach(function (k) {
        if ((state.analysisFilters[k] || "").trim()) filters[k] = state.analysisFilters[k].trim();
      });
      if (Object.keys(filters).length) payload.filters = filters;
      result = await fetchJson(API_BASE + "/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }, ANALYZE_TIMEOUT_MS);
    } catch (err) {
      var title, detail;
      if (err && err.name === "AbortError") {
        title = "Analysis failed";
        detail = "The analysis is taking longer than expected. The backend did not respond within " +
          (ANALYZE_TIMEOUT_MS / 1000) + " seconds. You can retry.";
      } else if (err && err.httpStatus) {
        title = "Analysis failed";
        detail = "The backend rejected the request: " + err.message + " You can retry.";
      } else {
        title = "Analysis failed";
        detail = "Could not reach the RationAI backend. Check that the server is running, then retry.";
      }
      state.running = false;
      state.result = { workflow_status: "failed", error: { title: title, detail: detail } };
      renderRoute();
      return;
    }

    if (!isValidResult(result)) {
      state.running = false;
      state.result = {
        workflow_status: "failed",
        error: { title: "Received an invalid analysis response.", detail: "The backend returned an unexpected payload." }
      };
      renderRoute();
      return;
    }

    state.running = false;
    state.result = result;
    // fresh run: reset insight filters so the new results are fully visible,
    // and clear the cached history so the table reflects this new run
    state.insightSeverity = "all";
    state.insightType = "all";
    state.insightQuery = "";
    state.analysisHistory = null;
    buildSearchIndex();
    renderRoute();
    updateNotifDot();
    if (result.workflow_status === "completed") {
      toast("Analysis completed" + (result.alerts.length ? " — " + result.alerts.length + " alert(s) for review" : " — no anomalies found"), "success");
    } else if (result.workflow_status === "partial_failure") {
      toast("Analysis completed with partial failures", "error");
    } else {
      toast("Analysis could not be completed", "error");
    }
  }

  function resetDemo() {
    state.result = null;
    state.readAlerts = {};
    state.beneficiaryId = null;
    if (state.route === "analysis") renderRoute();
    else { renderRoute(); }
    updateNotifDot();
    toast("Demo state reset. Ready for a new analysis.");
  }

  function describeErrors(errors) {
    return (errors || []).map(function (err) {
      var where = err.stage ? "Stage " + err.stage : "A workflow stage";
      var what = err.anomaly_id ? " (candidate " + err.anomaly_id + ")" : "";
      return where + what + " failed: " + (err.error || "unknown error");
    }).join(" ");
  }

  /* ------------------------------------------------------------------ *
   *  Data helpers (presentation of the fetched dataset)
   * ------------------------------------------------------------------ */
  function transactions() {
    return (state.dataset && Array.isArray(state.dataset.transactions)) ? state.dataset.transactions : [];
  }

  /* ------------------------------------------------------------------ *
   *  Phase 5 — database analytics data layer
   *  Every dashboard number comes from the backend analytics API (which
   *  aggregates the database). The frontend never computes metrics.
   * ------------------------------------------------------------------ */
  function fetchAnalytics(endpoint, params) {
    var qs = Object.keys(params || {}).filter(function (k) {
      return params[k] != null && params[k] !== "";
    }).map(function (k) {
      return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]);
    }).join("&");
    return fetchJson(API_BASE + "/api/analytics/" + endpoint + (qs ? "?" + qs : ""), {}, 20000);
  }

  function analyticsRangeParams() {
    var p = { range: state.analytics.range };
    if (state.analytics.range === "custom") {
      p.from = state.analytics.customFrom;
      p.to = state.analytics.customTo;
    }
    return p;
  }

  function invalidateAnalytics() {
    var a = state.analytics;
    a.overview = null; a.distribution = null; a.inventory = null;
    a.beneficiaries = null; a.fps = null; a.opAlerts = null; a.tx = null;
    a.error = null;
  }

  function analyticsErrorPanel(detail) {
    return '<div class="error-panel" role="alert"><span class="error-icon">' + icon("alert", 18) + "</span>" +
      "<div><h3>Dashboard data unavailable</h3><p>" + escapeHtml(detail || "The analytics service did not respond.") + "</p>" +
      '<div class="error-actions"><button class="btn btn-secondary" id="analytics-retry" type="button">Retry</button></div>' +
      "</div></div>";
  }

  function analyticsEmptyPanel(iconName, title, detail) {
    return '<div class="card"><div class="card-body">' +
      emptyState(iconName, title, detail, "upload") + "</div></div>";
  }

  function setAnalyticsRange(range, from, to) {
    state.analytics.range = range;
    if (range === "custom") {
      state.analytics.customFrom = from || state.analytics.customFrom || "";
      state.analytics.customTo = to || state.analytics.customTo || "";
    }
    invalidateAnalytics();
    var needsDates = range === "custom" && (!state.analytics.customFrom || !state.analytics.customTo);
    // Selecting Custom without dates only reveals the date pickers — no
    // backend request is fired until both dates are chosen.
    if (needsDates) {
      if (state.route === "overview") { renderOverview(); } else if (state.route === "distribution") { renderDistribution(); }
      return;
    }
    if (state.route === "overview") { renderOverview(); } else if (state.route === "distribution") { renderDistribution(); }
  }

  function refreshAnalytics() {
    invalidateAnalytics();
    if (state.route === "overview") renderOverview();
    else if (state.route === "distribution") renderDistribution();
    else if (state.route === "inventory") renderInventory();
    else if (state.route === "beneficiaries") renderBeneficiaries();
    else if (state.route === "analytics") renderAnalytics();
    else if (state.route === "alerts") renderAlerts();
    toast("Refreshing data from the database…");
  }

  function rangePillsHtml() {
    var a = state.analytics;
    var defs = [["today", "Today"], ["7d", "7 Days"], ["30d", "30 Days"], ["all", "All"], ["custom", "Custom"]];
    var pills = defs.map(function (d) {
      return '<button class="pill' + (a.range === d[0] ? " is-active" : "") + '" data-range="' + d[0] + '" type="button">' + d[1] + "</button>";
    }).join("");
    var custom = a.range === "custom"
      ? '<div style="display:flex;align-items:center;gap:8px">' +
        '<input class="input" id="custom-from" type="date" value="' + escapeHtml(a.customFrom) + '" aria-label="From date" style="width:150px">' +
        '<span class="hint">to</span>' +
        '<input class="input" id="custom-to" type="date" value="' + escapeHtml(a.customTo) + '" aria-label="To date" style="width:150px">' +
        '<button class="btn btn-secondary btn-sm" id="custom-apply" type="button">Apply</button></div>'
      : "";
    return '<div class="filter-row" style="flex-wrap:wrap">' + pills + custom +
      '<span style="flex:1"></span>' +
      '<button class="btn btn-ghost btn-sm" id="analytics-refresh" type="button">' + icon("arrow", 15) + " Refresh data</button>" +
      "</div>";
  }

  function bindRangeControls() {
    var pills = $id("range-pills");
    if (pills) {
      pills.addEventListener("click", function (ev) {
        var b = ev.target.closest(".pill[data-range]");
        if (b) setAnalyticsRange(b.getAttribute("data-range"));
      });
    }
    var apply = $id("custom-apply");
    if (apply) {
      apply.addEventListener("click", function () {
        var from = $id("custom-from").value, to = $id("custom-to").value;
        if (!from || !to) { toast("Choose both a start and end date", "error"); return; }
        if (from > to) { toast("Start date must be before end date", "error"); return; }
        setAnalyticsRange("custom", from, to);
      });
    }
    var refresh = $id("analytics-refresh");
    if (refresh) refresh.addEventListener("click", refreshAnalytics);
  }

  function provenanceHtml(overview) {
    if (!overview || !Array.isArray(overview.data_sources)) return "";
    var sources = overview.data_sources.filter(function (s) { return s.transaction_count > 0; });
    if (!sources.length) return "";
    return '<span class="hint" style="font-size:12px;color:var(--text-3)">' +
      sources.map(function (s) {
        return escapeHtml(s.name) + " (" + fmtNumber(s.transaction_count) + " tx)";
      }).join(" · ") + "</span>";
  }

  function renderTrendPayload(el, payload) {
    var labels = payload.labels || [];
    var series = payload.series || {};
    var types = Object.keys(series);
    if (!types.length || !labels.length) {
      el.innerHTML = emptyState("chart", "No data in the selected range", "No transactions fall inside this range — widen the range or import data.", null);
      return;
    }
    var s = { types: types, buckets: labels, data: series };
    if (!state.trendVisible) state.trendVisible = {};
    types.forEach(function (rt) { if (state.trendVisible[rt] === undefined) state.trendVisible[rt] = true; });
    var visible = types.filter(function (rt) { return state.trendVisible[rt]; });
    var mode = payload.granularity || "day";
    el.innerHTML = '<div class="chart-legend" style="margin-bottom:10px">' + types.map(function (rt, i) {
      var checked = state.trendVisible[rt] ? "checked" : "";
      return '<label><input type="checkbox" data-rt="' + escapeHtml(rt) + '" ' + checked + ' style="accent-color:#059669">' +
        '<span class="swatch" style="background:' + colorFor(i) + '"></span>' + escapeHtml(rt) + "</label>";
    }).join("") + "</div>" +
      '<div class="chart-wrap"><svg viewBox="0 0 640 240" preserveAspectRatio="none" role="img" aria-label="Ration distribution trend">' +
        chartGrid(640, 240, s.buckets.length) + chartSeries(640, 240, s, visible) +
      "</svg><div class=\"chart-tip\" id=\"trend-tip\"></div></div>" +
      '<div style="font-size:11.5px;color:var(--text-3);margin-top:8px">' + s.buckets.length + " period(s) · " +
      (mode === "day" ? "daily" : mode === "week" ? "weekly" : "monthly") + " totals in kg · aggregated by the backend</div>";
    el.querySelectorAll("input[data-rt]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        state.trendVisible[cb.getAttribute("data-rt")] = cb.checked;
        renderTrendPayload(el, payload);
      });
    });
    bindChartTooltip(el, s, visible, mode);
  }

  function renderMixPairs(el, pairs) {
    if (!pairs || !pairs.length) { el.innerHTML = emptyState("chart", "No data", "No ration quantities in this range."); return; }
    var max = Math.max.apply(null, pairs.map(function (p) { return p.quantity; }));
    var barMaxWidth = 250, barX = 80;
    el.innerHTML = '<div class="chart-wrap"><svg viewBox="0 0 320 ' + (pairs.length * 40 + 10) + '" role="img" aria-label="Ration mix">' +
      pairs.map(function (p, i) {
        var width = Math.max(4, Math.round((p.quantity / max) * barMaxWidth));
        var y = i * 40 + 8;
        return '<rect x="' + barX + '" y="' + y + '" width="' + width + '" height="20" rx="6" fill="' + colorFor(i) + '" opacity="0.85"/>' +
          '<text class="axis-label" x="' + (barX - 6) + '" y="' + (y + 14) + '" text-anchor="end" style="font-size:11px;fill:var(--text)">' + escapeHtml(p.commodity) + "</text>" +
          '<text class="axis-label" x="' + (barX + width + 6) + '" y="' + (y + 14) + '" style="font-size:11px;fill:var(--text-2)">' + fmtNumber(Math.round(p.quantity * 100) / 100) + " kg</text>";
      }).join("") + "</svg></div>";
  }

  function beneficiaries() {
    var map = {};
    transactions().forEach(function (t) {
      var id = t && t.beneficiary_id;
      if (!id) return;
      if (!map[id]) map[id] = { beneficiary_id: id, transactions: [] };
      map[id].transactions.push(t);
    });
    return Object.keys(map).sort().map(function (k) { return map[k]; });
  }

  function totalQuantity() {
    return transactions().reduce(function (sum, t) { return sum + (typeof t.quantity === "number" ? t.quantity : 0); }, 0);
  }

  function rationTypes() {
    var set = {};
    transactions().forEach(function (t) { if (t && t.ration_type) set[t.ration_type] = true; });
    return Object.keys(set).sort();
  }

  function colorFor(index) { return RATION_COLORS[index % RATION_COLORS.length]; }

  function anomalyBeneficiaries() {
    var set = {};
    if (state.result) {
      (state.result.anomalies || []).forEach(function (a) {
        if (a.beneficiary_id) set[a.beneficiary_id] = true;
      });
    }
    return set;
  }

  function alertChain() {
    var result = state.result;
    if (!result || !Array.isArray(result.alerts) || !result.alerts.length) return null;
    var casesBy = {}, findingsBy = {}, anomaliesBy = {};
    result.cases.forEach(function (c) { casesBy[c.case_id] = c; });
    result.findings.forEach(function (f) { findingsBy[f.finding_id] = f; });
    result.anomalies.forEach(function (a) { anomaliesBy[a.anomaly_id] = a; });
    var alert = result.alerts[0];
    var caseObj = casesBy[alert.case_id] || null;
    var findings = [];
    if (caseObj && Array.isArray(caseObj.finding_ids)) {
      findings = caseObj.finding_ids.map(function (id) { return findingsBy[id] || null; }).filter(Boolean);
    }
    var anomalies = findings.map(function (f) { return anomaliesBy[f.anomaly_id] || null; }).filter(Boolean);
    var transactionIds = [];
    anomalies.forEach(function (a) {
      (a.transaction_ids || []).forEach(function (id) { if (transactionIds.indexOf(id) === -1) transactionIds.push(id); });
    });
    return { alert: alert, case: caseObj, findings: findings, anomalies: anomalies, transactionIds: transactionIds };
  }

  function buildSearchIndex() {
    var items = [];
    Object.keys(ROUTES).forEach(function (r) {
      items.push({ kind: "View", title: ROUTES[r].title, sub: "Open " + ROUTES[r].title, route: r });
    });
    beneficiaries().forEach(function (b) {
      items.push({ kind: "Beneficiary", title: b.beneficiary_id, sub: b.transactions.length + " transaction(s)", route: "beneficiaries", beneficiary: b.beneficiary_id });
    });
    transactions().forEach(function (t) {
      items.push({ kind: "Transaction", title: t.transaction_id, sub: (t.beneficiary_id || "") + " · " + (t.ration_type || "") + " · " + fmtKg(t.quantity), route: "beneficiaries", beneficiary: t.beneficiary_id, tx: t.transaction_id });
    });
    if (state.result) {
      (state.result.alerts || []).forEach(function (a) {
        items.push({ kind: "Alert", title: a.alert_id, sub: (a.message || "").slice(0, 60), route: "alerts", alertId: a.alert_id });
      });
    }
    state.searchIndex = items;
  }

  /* ------------------------------------------------------------------ *
   *  Router / shell
   * ------------------------------------------------------------------ */
  function currentRoute() {
    var hash = (location.hash || "").replace(/^#\/?/, "");
    return ROUTES[hash] ? hash : "command";
  }

  function renderRoute() {
    var route = currentRoute();
    state.route = route;
    document.querySelectorAll(".nav a[data-route], .bottom-nav a[data-route]").forEach(function (a) {
      var active = a.getAttribute("data-route") === route;
      a.classList.toggle("is-active", active);
      if (active) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $id("breadcrumb-current").textContent = ROUTES[route].title;
    $id("view").innerHTML = "";
    var renderer = {
      command: renderCommandCenter,
      overview: renderOverview,
      analysis: renderAnalysis,
      beneficiaries: renderBeneficiaries,
      distribution: renderDistribution,
      inventory: renderInventory,
      analytics: renderAnalytics,
      insights: renderInsights,
      simulation: renderSimulation,
      alerts: renderAlerts,
      reports: renderReports,
      settings: renderSettings
    }[route];
    // Phase 13: one failing widget must not blank the whole application.
    try {
      renderer();
    } catch (err) {
      console.error("View render failed:", err);
      $id("view").innerHTML = viewHead(ROUTES[route].title, "Something went wrong loading this section.") +
        '<section class="section"><div class="empty-state"><div class="empty-icon">' + icon("alert", 26) + "</div><h3>Unable to render this section</h3>" +
        '<p>The view hit an unexpected error. Your data is safe — retry to reload it.</p>' +
        '<div class="empty-actions"><button class="btn btn-secondary" id="view-retry" type="button">Retry</button></div></div></section>';
      var retry = $id("view-retry");
      if (retry) retry.addEventListener("click", function () { renderRoute(); });
    }
    refreshDataStatus();
    if (state.mobileNavOpen) closeMobileNav();
    updateNotifDot();
  }

  function refreshDataStatus() {
    // Top-bar chip — real backend freshness, throttled, never fabricated.
    if (Date.now() - state.dataStatusAt < 30000 && state.dataStatus) return;
    var chip = $id("data-status-chip");
    if (!chip) return;
    state.dataStatusAt = Date.now();
    fetchJson(API_BASE + "/api/pipeline/freshness", {}, 6000).then(function (payload) {
      state.dataStatus = payload;
      renderDataStatus();
    }).catch(function () {
      state.dataStatus = { status: "UNKNOWN", detail: "Unable to load data status." };
      renderDataStatus();
    });
  }

  function renderDataStatus() {
    var chip = $id("data-status-chip");
    var dot = $id("data-status-dot");
    var label = $id("data-status-label");
    if (!chip || !dot || !label) return;
    var s = state.dataStatus || {};
    var tone = { FRESH: "success", RECENT: "warning", STALE: "error", UNKNOWN: "neutral" }[s.status] || "neutral";
    var text = { FRESH: "Data fresh", RECENT: "Data recent", STALE: "Data stale", UNKNOWN: "No sync data" }[s.status] || "Status unknown";
    dot.className = "status-dot " + tone;
    label.textContent = text;
    chip.title = s.detail || text;
  }

  function viewHead(title, subtitle, extra) {
    return '<div class="view-head"><div class="view-head-row"><div><h1>' + escapeHtml(title) +
      "</h1><p>" + escapeHtml(subtitle) + "</p></div>" + (extra || "") + "</div></div>";
  }

  function skeleton(html) {
    return '<div class="skeleton card"></div>';
  }

  /* ------------------------------------------------------------------ *
   *  Overview
   * ------------------------------------------------------------------ */
  function renderOverview() {
    var v = $view();
    var a = state.analytics;
    var greeting = (function () {
      var h = new Date().getHours();
      return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
    })();
    var chain = alertChain();
    var confidence = chain && chain.case ? chain.case.confidence : null;

    v.innerHTML =
      '<div class="view-head"><div class="view-head-row"><div><h1>Overview</h1><p>Monitor ration distribution, inventory health, and AI-detected operational risks.</p></div>' +
        '<button class="btn btn-secondary" type="button" id="refresh-overview">' + icon("refresh", 15) + ' Refresh</button></div></div>' +
      /* Data status bar */
      '<div class="card" style="margin-bottom:20px"><div class="card-body" style="padding:14px 20px;display:flex;align-items:center;gap:32px;flex-wrap:wrap" id="overview-data-status">' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="status-dot success" style="width:8px;height:8px"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">Data Status</div><div style="font-size:13px;font-weight:600;color:var(--text)">Loading…</div></div></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="status-dot success" style="width:8px;height:8px"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">AI Workflow</div><div style="font-size:13px;font-weight:600;color:var(--text)">Operational</div></div></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="nav-icon" data-icon="clock" style="color:var(--text-3)"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">Last Updated</div><div style="font-size:13px;font-weight:600;color:var(--text)">—</div></div></div>' +
        '<div style="margin-left:auto"><button class="btn btn-ghost btn-sm" type="button">Details</button></div>' +
        '</div></div>' +
      /* Range pills */
      '<div class="filter-row" id="range-pills" style="margin-bottom:20px">' + rangePillsHtml() + "</div>" +
      /* KPI row */
      '<section class="section" style="margin-top:0"><div class="grid kpi-grid" id="kpi-grid">' + skeleton() + skeleton() + skeleton() + "</div></section>" +
      /* Two-column: Recent Investigations + Distribution Overview */
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>Recent Investigations</h3><p class="card-sub">Latest detected anomalies and findings</p></div><a href="#/alerts" class="btn btn-ghost btn-sm" style="font-size:12px">View all →</a></div><div class="card-body" style="padding-top:12px">' +
        '<div id="overview-investigations">' + skeleton() + '</div></div></div>' +
        '<div class="card"><div class="card-head"><div><h3>Distribution Overview</h3><p class="card-sub">Activity across districts</p></div><a href="#/distribution" class="btn btn-ghost btn-sm" style="font-size:12px">View all →</a></div><div class="card-body" style="padding-top:12px">' +
        '<div id="overview-distribution">' + skeleton() + '</div></div></div>' +
      '</div></section>' +
      /* Two-column: Alert Summary + AI Insights */
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>Alert Summary</h3><p class="card-sub">Active alerts by severity</p></div><a href="#/alerts" class="btn btn-ghost btn-sm" style="font-size:12px">View all →</a></div><div class="card-body" id="overview-alerts">' + skeleton() + '</div></div>' +
        '<div class="card ai-card"><div class="card-head"><div class="ai-head"><span class="ai-icon">' + icon("sparkles", 17) + "</span><div><h3>AI Insights</h3><p class=\"card-sub\">AI-powered analysis of the ration network</p></div></div><a href=\"#/insights\" class=\"btn btn-ghost btn-sm\" style=\"font-size:12px\">View all →</a></div><div class=\"card-body\" id=\"insight-preview\">" + skeleton() + "</div></div>" +
      '</div></section>';
    bindRangeControls();

    var load = function () {
      var params = analyticsRangeParams();
      if (params.range === "custom" && (!params.from || !params.to)) {
        // No backend request until both custom dates are chosen.
        var kpiGrid = $id("kpi-grid");
        if (kpiGrid) kpiGrid.innerHTML = emptyState("calendar", "Choose a custom date range", "Select both a start and end date above — the dashboard will reload with that window.", null);
        return;
      }
      Promise.all([
        fetchAnalytics("overview", params),
        fetchAnalytics("distribution", Object.assign({ granularity: "day" }, params)),
        fetchJson(API_BASE + "/api/alerts?per_page=8", {}, 8000).catch(function () { return { alerts: [] }; }),
        fetchJson(API_BASE + "/api/alerts/summary", {}, 8000).catch(function () { return {}; }),
        fetchJson(API_BASE + "/api/pipeline/freshness", {}, 8000).catch(function () { return {}; }),
        fetchJson(API_BASE + "/api/command-center", {}, 12000).catch(function () { return {}; })
      ]).then(function (results) {
        a.overview = results[0];
        a.distribution = results[1];
        state.alerts = (results[2] && results[2].alerts) || [];
        state.alertsSummary = results[3] || {};
        state.pipelineFreshness = results[4] || {};
        state.commandCenter = results[5] || {};
        a.error = null;
        renderOverview();
      }).catch(function (err) {
        a.error = err.serverMessage || err.message || "The analytics service did not respond.";
        renderOverview();
      });
    };

    if (a.error) {
      var kpiGrid = $id("kpi-grid");
      kpiGrid.innerHTML = analyticsErrorPanel(a.error);
      var retry = $id("analytics-retry");
      if (retry) retry.addEventListener("click", function () { a.error = null; invalidateAnalytics(); renderOverview(); });
      return;
    }
    if (!a.overview || !a.distribution) { load(); return; }

    var ov = a.overview;
    var kpiGrid = $id("kpi-grid");
    var trendPayload = a.distribution.trend;

    if (!ov.total_transactions) {
      kpiGrid.innerHTML = analyticsEmptyPanel("package", "No data in the selected range",
        "There are no transactions inside this range. Widen the range or import a dataset to populate the dashboard.");
      $id("trend-card").innerHTML = emptyState("chart", "No data in the selected range", "No transactions fall inside this range.", null);
      $id("mix-card").innerHTML = emptyState("chart", "No data", "No ration quantities in this range.", null);
      renderInsightPreview($id("insight-preview"));
      return;
    }

    var commodities = ov.commodities_distributed || [];
    var trendTotals = (trendPayload.series || {}).rice ? trendPayload.labels.map(function (_, i) {
      return Object.keys(trendPayload.series).reduce(function (sum, rt) { return sum + (trendPayload.series[rt][i] || 0); }, 0);
    }) : [];
    var spark = function (i) {
      if (!trendTotals.length) return [1, 2, 1, 3, 2];
      var step = Math.max(1, Math.round(trendTotals.length / 10));
      return trendTotals.filter(function (_, j) { return j % step === 0; });
    };

    var alertSummary = state.alertsSummary || {};
    var activeAlerts = alertSummary.total_active || 0;
    var openSummary = alertSummary.open || {};
    var highRisk = openSummary.CRITICAL || 0;
    var cc = state.commandCenter || {};
    var ccKpis = {};
    (cc.kpis || []).forEach(function (k) { ccKpis[k.key] = k; });
    var invVal = ccKpis.inventory ? ccKpis.inventory.value : 0;
    var invUnit = ccKpis.inventory ? ccKpis.inventory.unit : "kg";
    var critAlerts = ccKpis.critical_alerts ? ccKpis.critical_alerts.value : highRisk;

    var kpis = [
      { label: "Total Beneficiaries", value: ov.total_beneficiaries, sub: ov.active_beneficiaries + " active", icon: "users", accent: "#087A5B" },
      { label: "Ration Distributed", value: ov.ration_distributed_kg, sub: ov.distribution_count + " records", icon: "package", accent: "#2563EB", fmt: fmtKg },
      { label: "Total Inventory", value: invVal, sub: invVal ? fmtKg(invVal) + " total" : "No data", icon: "database", accent: "#087A5B", fmt: fmtKg },
      { label: "Active Alerts", value: activeAlerts, sub: "Requiring attention", icon: "bell", accent: "#D97706" },
      { label: "High-Risk Cases", value: critAlerts, sub: critAlerts > 0 ? "Critical priority" : "None detected", icon: "shield", accent: critAlerts > 0 ? "#C62828" : "#087A5B" }
    ];

    kpiGrid.innerHTML = kpis.map(function (k, i) {
      var fmt = k.fmt || fmtNumber;
      return '<div class="card kpi hoverable">' +
        '<div class="kpi-top"><span class="kpi-label">' + escapeHtml(k.label) + '</span><span class="kpi-icon" style="color:' + k.accent + ';background:' + k.accent + '11">' + icon(k.icon, 17) + "</span></div>" +
        '<div class="kpi-value" data-idx="' + i + '">' + fmt(k.value) + "</div>" +
        '<div class="kpi-sub">' + escapeHtml(k.sub) + "</div>" +
      "</div>";
    }).join("");

    kpiGrid.querySelectorAll(".kpi-value").forEach(function (el) {
      var k = kpis[Number(el.getAttribute("data-idx"))];
      if (k) animateNumber(el, k.value, k.fmt || fmtNumber);
    });

    /* Populate data status bar */
    var dsBar = $id("overview-data-status");
    if (dsBar) {
      var freshness = state.pipelineFreshness || {};
      var fsLabel = freshness.status === "FRESH" ? "Fresh" : freshness.status === "RECENT" ? "Recent" : freshness.status === "STALE" ? "Stale" : "Unknown";
      var fsCls = freshness.status === "FRESH" ? "success" : freshness.status === "RECENT" ? "success" : freshness.status === "STALE" ? "warning" : "error";
      var dsTime = freshness.latest_data_at ? new Date(freshness.latest_data_at).toLocaleString() : "—";
      dsBar.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px"><span class="status-dot ' + fsCls + '" style="width:8px;height:8px"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">Data Status</div><div style="font-size:13px;font-weight:600;color:var(--text)">' + escapeHtml(fsLabel) + '</div></div></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="status-dot success" style="width:8px;height:8px"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">AI Workflow</div><div style="font-size:13px;font-weight:600;color:var(--text)">Operational</div></div></div>' +
        '<div style="display:flex;align-items:center;gap:8px"><span class="nav-icon" data-icon="clock" style="color:var(--text-3)"></span><div><div style="font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--text-3)">Last Updated</div><div style="font-size:13px;font-weight:600;color:var(--text)">' + escapeHtml(dsTime) + '</div></div></div>' +
        '<div style="margin-left:auto"><button class="btn btn-ghost btn-sm" type="button">Details</button></div>';
    }

    /* Populate Recent Investigations */
    var invEl = $id("overview-investigations");
    if (invEl) {
      var alerts = (state.alerts || []).slice(0, 5);
      if (alerts.length) {
        invEl.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr><th>Case</th><th>Issue</th><th>Severity</th><th>Status</th><th>Updated</th></tr></thead><tbody>' +
          alerts.map(function (a) {
            var sevCls = (a.severity || "").toLowerCase();
            var statusCls = (a.status || "").toLowerCase() === "open" ? "warning" : (a.status || "").toLowerCase() === "acknowledged" ? "info" : "success";
            return '<tr class="row-click" onclick="location.hash=\"#/alerts\"">' +
              '<td class="mono">' + escapeHtml(a.alert_id || a.id || "—") + '</td>' +
              '<td>' + escapeHtml(a.title || a.rule_type || "—") + '</td>' +
              '<td><span class="badge ' + sevCls + '">' + escapeHtml(a.severity || "—") + '</span></td>' +
              '<td><span class="badge ' + statusCls + '">' + escapeHtml(a.status || "—") + '</span></td>' +
              '<td style="color:var(--text-3);font-size:12px">' + escapeHtml(a.created_at ? new Date(a.created_at).toLocaleDateString() : "—") + '</td>' +
            '</tr>';
          }).join("") +
          '</tbody></table></div>' +
          '<div style="text-align:center;padding:12px 0"><a href="#/alerts" class="btn btn-ghost btn-sm" style="font-size:12px;color:var(--forest-2)">View all investigations →</a></div>';
      } else {
        invEl.innerHTML = '<div class="empty-state" style="padding:24px"><p style="color:var(--text-3);font-size:13px">No recent investigations.</p></div>';
      }
    }

    /* Populate Distribution Overview */
    var distEl = $id("overview-distribution");
    if (distEl) {
      var districts = (cc.district_risk || []).slice(0, 6);
      if (districts.length) {
        distEl.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr><th>District</th><th>FPS Centers</th><th>Distributions</th><th>Transactions</th><th>Status</th></tr></thead><tbody>' +
          districts.slice(0, 6).map(function (d) {
            var riskCls = (d.risk || "LOW").toUpperCase() === "HIGH" ? "error" : (d.risk || "LOW").toUpperCase() === "MEDIUM" ? "warning" : "success";
            return '<tr>' +
              '<td style="font-weight:600">' + escapeHtml(d.district || "—") + '</td>' +
              '<td>' + fmtNumber(d.fps_count || 0) + '</td>' +
              '<td>' + fmtKg(d.distribution_kg || 0) + '</td>' +
              '<td>' + fmtNumber(d.transactions || 0) + '</td>' +
              '<td><span class="badge ' + riskCls + '">' + escapeHtml(d.risk || "Low") + '</span></td>' +
            '</tr>';
          }).join("") +
          '</tbody></table></div>';
      } else {
        distEl.innerHTML = '<div class="empty-state" style="padding:24px"><p style="color:var(--text-3);font-size:13px">No district data available.</p></div>';
      }
    }

    /* Populate Alert Summary */
    var alertEl = $id("overview-alerts");
    if (alertEl) {
      var as = state.alertsSummary || {};
      var op = as.open || {};
      alertEl.innerHTML = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">' +
        [{ label: "Critical", count: op.CRITICAL || 0, cls: "error", icon: "alert" },
         { label: "High", count: op.HIGH || 0, cls: "warning", icon: "alert" },
         { label: "Medium", count: op.MEDIUM || 0, cls: "info", icon: "alert" },
         { label: "Low", count: op.LOW || 0, cls: "success", icon: "info" }]
        .map(function (s) {
          var bg = s.label === "Critical" ? "#FEF2F2" :
                   s.label === "High" ? "#FEF2F2" :
                   s.label === "Medium" ? "#FFF7ED" :
                   "#F0FDF4";
          var border = s.label === "Critical" ? "#FEE2E2" :
                       s.label === "High" ? "#FEE2E2" :
                       s.label === "Medium" ? "#FFEDD5" :
                       "#DCFCE7";
          var txt = s.label === "Critical" ? "#991B1B" :
                    s.label === "High" ? "#991B1B" :
                    s.label === "Medium" ? "#C2410C" :
                    "#166534";
          return '<div style="text-align:center;padding:14px 8px;background:' + bg + ';border:1px solid ' + border + ';border-radius:var(--radius)" class="hoverable">' +
            '<div style="margin-bottom:6px;color:' + txt + ';font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase">' + escapeHtml(s.label) + '</div>' +
            '<div style="font-size:28px;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums">' + fmtNumber(s.count) + '</div>' +
          '</div>';
        }).join("") + '</div>';
    }

    renderInsightPreview($id("insight-preview"));
  }

  /* ------------------------------------------------------------------ *
   *  Analysis (core flow — preserved from Phase 7)
   * ------------------------------------------------------------------ */
  function renderAnalysis() {
    var v = $view();
    v.innerHTML = viewHead("AI Analysis", "The command center: select a dataset, choose analysis types, run the real multi-agent workflow, and inspect evidence-backed insights.",
      '<span class="badge ai">' + icon("sparkles", 12) + " Command center</span>");

    if (!state.analysisTypesRegistry) {
      fetchJson(API_BASE + "/api/analysis/types", {}, 8000).then(function (p) {
        state.analysisTypesRegistry = p.types || [];
        if (!state.analysisTypes) {
          state.analysisTypes = {};
          state.analysisTypesRegistry.forEach(function (t) { state.analysisTypes[t.key] = true; });
        }
        if (state.route === "analysis") renderRoute();
      }).catch(function () { state.analysisTypesRegistry = []; });
    }
    if (!state.availableDatasets) {
      fetchJson(API_BASE + "/api/datasets", {}, 8000).then(function (payload) {
        state.availableDatasets = payload;
        if (state.route === "analysis") renderRoute();
      }).catch(function () { state.availableDatasets = { datasets: [] }; });
    }
    if (!state.analysisHistory) loadAnalysisHistory();

    var chain = alertChain();
    var err = state.result && state.result.error;

    var datasetSelect = '<select id="analysis-dataset" class="select" aria-label="Dataset to analyze" disabled="' + (state.running ? "true" : "") + '">' +
      '<option value="synthetic">Synthetic Demo Dataset</option>' +
      (state.availableDatasets ? state.availableDatasets.datasets.map(function (d) {
        return '<option value="real:' + d.id + '">' + escapeHtml(d.dataset_name + " — " + d.transaction_count + " tx") + "</option>";
      }).join("") : "") +
      "</select>";
    if (state.analysisDataset === "synthetic" && state.availableDatasets && state.availableDatasets.datasets.length) {
      datasetSelect = datasetSelect.replace('value="synthetic">', 'value="synthetic" selected>Synthetic Demo Dataset');
    } else if (state.analysisDataset === "real") {
      datasetSelect = datasetSelect.replace('value="real:' + state.analysisImportId + '">', 'value="real:' + state.analysisImportId + '" selected>');
    }

    v.insertAdjacentHTML("beforeend",
      '<section class="section">' +
        '<div class="card"><div class="card-body">' +
          '<div class="toolbar" style="margin-bottom:0">' +
            '<button id="run-button" class="btn btn-primary" type="button">' +
              (state.running ? '<span class="spinner"></span> Running analysis…' : "Run AI Analysis") + "</button>" +
            (state.result && !err ? '<button id="reset-button" class="btn btn-ghost" type="button">Reset Demo</button>' : "") +
            (state.result && !state.running ? '<button id="export-button" class="btn btn-secondary" type="button">' + icon("download", 14) + " Export JSON</button>" : "") +
            datasetSelect +
            '<span style="flex:1"></span>' +
            '<span class="status-line" id="status-line" role="status" aria-live="polite">' +
              (state.running ? '<span class="spinner"></span> RationAI agents are analyzing the dataset…' : "") + "</span>" +
          "</div>" +
        "</div></div>" +
      "</section>");

    v.insertAdjacentHTML("beforeend", analysisConfigHtml());

    if (state.running) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="section-title">Workflow in progress</div>' +
        '<div class="pipeline-list">' + [1, 2, 3, 4].map(function () { return '<div class="card stage-card"><span class="skeleton line"></span><span class="skeleton line" style="width:60%"></span></div>'; }).join("") +
        "</div></section>");
      bindAnalysisControls();
      return;
    }

    if (err) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="error-panel" role="alert">' +
          '<span class="error-icon">' + icon("alert", 18) + "</span>" +
          "<div><h3>" + escapeHtml(err.title) + "</h3><p>" + escapeHtml(err.detail || "") + "</p>" +
          '<div class="error-actions"><button id="retry-button" class="btn btn-secondary" type="button">Retry</button>' +
          '<button id="reset-button" class="btn btn-ghost" type="button">Reset</button></div></div></div></section>');
      v.insertAdjacentHTML("beforeend", analysisHistorySection());
      bindAnalysisControls();
      return;
    }

    if (!state.result) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="card"><div class="card-body">' +
          emptyState("activity", "No analysis run yet", "Select a dataset, choose the analysis types, then click Run AI Analysis. The command center executes the real multi-agent workflow and deterministic checks, then renders evidence-backed insights from the backend response.", null) +
        "</div></div></section>");
      v.insertAdjacentHTML("beforeend", analysisHistorySection());
      bindAnalysisControls();
      return;
    }

    var result = state.result;
    if (result.workflow_status === "failed") {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="error-panel" role="alert"><span class="error-icon">' + icon("alert", 18) + "</span><div><h3>Analysis could not be completed.</h3><p>" +
        escapeHtml(describeErrors(result.errors) || "The backend reported a failure.") + "</p>" +
        '<div class="error-actions"><button id="retry-button" class="btn btn-secondary" type="button">Retry</button></div></div></div></section>');
      v.insertAdjacentHTML("beforeend", analysisHistorySection());
      bindAnalysisControls();
      return;
    }

    var partial = result.workflow_status === "partial_failure";
    if (partial) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="error-panel" role="alert"><span class="error-icon">' + icon("alert", 18) + "</span><div><h3>Analysis completed with partial failures.</h3><p>" +
        escapeHtml(describeErrors(result.errors)) + "</p></div></div></section>");
    }

    v.insertAdjacentHTML("beforeend", analysisTypesStatusHtml(result.types));
    v.insertAdjacentHTML("beforeend", insightsSectionHtml());
    v.insertAdjacentHTML("beforeend", renderPipelineSection(result.stages));

    if (result.dataset) {
      v.insertAdjacentHTML("beforeend", datasetProvenanceHtml(result.dataset));
    }

    var analyzedCount = result.dataset && result.dataset.transaction_count != null
      ? result.dataset.transaction_count
      : transactions().length;
    var stats = [
      ["Transactions analyzed", analyzedCount],
      ["Anomaly candidates", result.anomalies.length],
      ["Verified findings", result.findings.length],
      ["Investigation cases", result.cases.length],
      ["Alerts for review", result.alerts.length],
      ["Insights", (result.insights || []).length]
    ];
    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="section-title">Analysis summary</div>' +
      '<div class="grid cols-4">' + stats.map(function (s) {
        return '<div class="card"><div class="card-body"><div class="kv-item" style="background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">' + escapeHtml(s[0]) + "</div><div style='font-size:24px;font-weight:700;margin-top:4px'>" + s[1] + "</div></div></div></div>";
      }).join("") + "</div></section>");

    if (chain && chain.alert) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="section-title">Generated alert</div>' + alertCardHtml(chain) + "</section>");
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="section-title">Traceability <span class="hint">every ID comes from the backend result</span></div>' +
        '<div class="card"><div class="card-body">' + traceHtml(chain) + "</div></div></section>");
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="section-title">Transactions involved</div>' +
        '<div class="table-wrap">' + transactionsTableHtml(chain.transactionIds) + "</div></section>");
      v.insertAdjacentHTML("beforeend",
        '<div class="no-print" style="margin-top:18px"><a class="btn btn-secondary btn-sm" href="#/alerts">Open Alerts center</a> ' +
        '<a class="btn btn-secondary btn-sm" href="#/insights">View AI Insights</a></div>');
    } else {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="card"><div class="card-body">' +
          emptyState("check", "No potential anomalies found", "The analyzed transactions matched expected patterns. No investigation case or alert was created.", null) +
        "</div></div></section>");
    }

    if (result.timings) {
      v.insertAdjacentHTML("beforeend", activityLogSection(result.timings));
    }
    v.insertAdjacentHTML("beforeend", analysisHistorySection());
    bindAnalysisControls();
  }

  /* ---------- Phase 9 command-center helpers ---------- */

  function analysisConfigHtml() {
    var types = state.analysisTypesRegistry || [];
    var preType = {};
    ((state.analysisPrecheck && state.analysisPrecheck.types) || []).forEach(function (t) { preType[t.key] = t; });
    var typeBoxes = types.map(function (t) {
      var pt = preType[t.key];
      var disabled = pt && !pt.enabled;
      var checked = state.analysisTypes && state.analysisTypes[t.key];
      return '<label class="analysis-type' + (disabled ? " is-disabled" : "") + '">' +
        '<input type="checkbox" data-atype="' + t.key + '" ' + (checked ? "checked" : "") + (disabled ? " disabled" : "") + ">" +
        '<span class="analysis-type-body"><strong>' + escapeHtml(t.label) + "</strong>" +
        "<small>" + escapeHtml(t.description || "") + "</small>" +
        (disabled && pt.reason ? "<em>" + escapeHtml(pt.reason) + "</em>" : "") +
        "</span></label>";
    }).join("");
    var f = state.analysisFilters || {};
    var filters = '<div class="filter-grid">' +
      '<label>Commodity<input class="input" data-af="commodity" value="' + escapeHtml(f.commodity || "") + '" placeholder="e.g. rice"></label>' +
      '<label>FPS code<input class="input" data-af="fps" value="' + escapeHtml(f.fps || "") + '" placeholder="e.g. FPS99"></label>' +
      '<label>District<input class="input" data-af="district" value="' + escapeHtml(f.district || "") + '" placeholder="e.g. Lucknow"></label>' +
      '<label>From<input class="input" type="date" data-af="from" value="' + escapeHtml(f.from || "") + '"></label>' +
      '<label>To<input class="input" type="date" data-af="to" value="' + escapeHtml(f.to || "") + '"></label>' +
      "</div>";
    var precheckHtml = state.analysisPrecheck
      ? analysisPrecheckHtml(state.analysisPrecheck)
      : '<p class="hint">Select a dataset — readiness is prechecked by the backend before anything runs.</p>';
    return '<section class="section"><div class="section-title">Analysis configuration <span class="hint">agent types run the real Phase 6 pipeline; the rest are deterministic database checks</span></div>' +
      '<div class="card"><div class="card-body">' +
      '<div class="grid cols-2 analysis-config">' +
        '<div><div class="kicker">Analysis types</div><div class="analysis-types">' + (typeBoxes || '<p class="hint">Loading analysis types…</p>') + "</div></div>" +
        '<div><div class="kicker">Filters <span class="hint">validated server-side — empty filters analyze the whole dataset</span></div>' + filters + "</div>" +
      "</div>" +
      '<div class="analysis-precheck">' + precheckHtml + "</div>" +
      "</div></div></section>";
  }

  function analysisPrecheckHtml(pre) {
    var d = pre.dataset || {};
    var dsRows = [
      ["Dataset", d.dataset_name], ["Source", d.source_name],
      ["Import", d.data_import_id != null ? "#" + d.data_import_id : "—"],
      ["Records", d.record_count != null ? fmtNumber(d.record_count) : "—"],
      ["Valid", d.valid_records != null ? fmtNumber(d.valid_records) : "—"],
      ["Invalid", d.invalid_records != null ? fmtNumber(d.invalid_records) : "—"],
      ["Duplicates", d.duplicates != null ? fmtNumber(d.duplicates) : "—"],
      ["Quality", d.quality != null ? d.quality + "%" : "—"],
      ["Historical months", d.historical_months != null ? d.historical_months : "—"]
    ];
    var chips = (pre.types || []).map(function (t) {
      return '<span class="badge ' + (t.enabled ? "success" : "neutral") + '">' + escapeHtml(t.label) + (t.enabled ? "" : " · DISABLED") + "</span>";
    }).join("");
    var reasons = (pre.types || []).filter(function (t) { return !t.enabled && t.reason; }).map(function (t) {
      return '<p class="hint" style="margin-top:4px">⚠ ' + escapeHtml(t.label) + ": " + escapeHtml(t.reason) + "</p>";
    }).join("");
    return '<div class="precheck-panel">' +
      '<div class="precheck-head"><span class="badge ' + ((pre.types || []).some(function (t) { return !t.enabled; }) ? "warning" : "success") + '"><span class="dot"></span>ANALYSIS READINESS</span>' +
      '<span class="hint">computed from the database by the backend precheck</span></div>' +
      '<div class="kv">' + dsRows.map(function (r) {
        return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
      }).join("") + "</div>" +
      '<div class="precheck-types">' + chips + "</div>" + reasons +
      "</div>";
  }

  function analysisTypesStatusHtml(typesMap) {
    if (!typesMap || !Object.keys(typesMap).length) return "";
    var label = { distribution_anomaly: "Distribution Anomaly", recommendations: "Recommendations", operational_risk: "Operational Risk", inventory_risk: "Inventory Risk", demand_forecast: "Demand Forecast" };
    var chips = Object.keys(typesMap).map(function (k) {
      var v = typesMap[k];
      var tone = v.status === "completed" ? "success" : v.status === "insufficient_data" ? "warning" : v.status === "failed" ? "error" : "neutral";
      var txt = v.status === "completed" ? (v.count + " insight(s)") : v.status === "insufficient_data" ? "INSUFFICIENT DATA" : v.status.toUpperCase();
      return '<span class="badge ' + tone + '" title="' + escapeHtml(v.reason || "") + '">' + escapeHtml(label[k] || k) + " · " + txt + "</span>";
    }).join("");
    return '<section class="section"><div class="section-title">Analysis types <span class="hint">status per selected type — reported by the backend, never faked</span></div>' +
      '<div class="precheck-types">' + chips + "</div></section>";
  }

  function insightsSectionHtml() {
    var insights = (state.result && state.result.insights) || [];
    var sev = state.insightSeverity, typ = state.insightType, q = (state.insightQuery || "").toLowerCase();
    var filtered = insights.filter(function (i) {
      if (sev !== "all" && i.severity.toLowerCase() !== sev) return false;
      if (typ !== "all" && i.insight_type.toLowerCase().indexOf(typ) === -1) return false;
      if (q) {
        var hay = (i.title + " " + (i.summary || "") + " " + (i.entity_id || "") + " " + i.insight_type).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var sevPill = function (key, labelTxt) {
      return '<button class="pill' + (sev === key ? " is-active" : "") + '" data-isev="' + key + '" type="button">' + labelTxt + "</button>";
    };
    var typePill = function (key, labelTxt) {
      return '<button class="pill' + (typ === key ? " is-active" : "") + '" data-ityp="' + key + '" type="button">' + labelTxt + "</button>";
    };
    var cards = filtered.map(insightCardHtml).join("");
    return '<section class="section" id="insights-section"><div class="section-title">Insights <span class="hint">evidence-backed results from this run — ' + fmtNumber(insights.length) + " generated</span></div>" +
      '<div class="card"><div class="card-body">' +
      '<div class="insight-filters">' +
        '<div class="filter-row">' + sevPill("all", "All") + sevPill("critical", "Critical") + sevPill("high", "High") + sevPill("medium", "Medium") + sevPill("low", "Low") + "</div>" +
        '<div class="filter-row">' + typePill("all", "All types") + typePill("distribution", "Distribution") + typePill("operational", "Operational") + typePill("inventory", "Inventory") + typePill("demand", "Demand") + typePill("recommendation", "Recommendation") + "</div>" +
        '<input class="input" type="search" id="insight-search" placeholder="Search insights (FPS, district, commodity, title)…" value="' + escapeHtml(state.insightQuery || "") + '">' +
      "</div>" +
      '<div class="insight-list" id="insight-list">' +
        (cards || emptyState("search", "No matching insights", "No insight matches the current filters. Clear the filters or run a new analysis.", null)) +
      "</div>" +
      "</div></div></section>";
  }

  function insightCardHtml(i) {
    var sevClass = { critical: "high", high: "high", medium: "medium", low: "low" }[i.severity.toLowerCase()] || "low";
    var det = i.deterministic ? '<span class="badge info">CALCULATED</span>' : '<span class="badge ai">AI INTERPRETATION</span>';
    var conf = i.confidence != null ? Math.round(i.confidence * 100) + "%" : null;
    var ev = i.evidence || {};
    var evRows = Object.keys(ev).map(function (k) {
      var val = ev[k];
      if (val && typeof val === "object") val = JSON.stringify(val);
      return '<div class="kv-item"><dt>' + escapeHtml(String(k).replace(/_/g, " ")) + "</dt><dd>" + escapeHtml(String(val)) + "</dd></div>";
    }).join("");
    var src = i.source || {};
    var srcHtml = '<div class="insight-source">' +
      '<p class="kicker">Source</p>' +
      '<div class="kv">' +
        '<div class="kv-item"><dt>Dataset</dt><dd>' + escapeHtml(src.dataset_name || "—") + "</dd></div>" +
        '<div class="kv-item"><dt>Import</dt><dd>' + (src.data_import_id != null ? "#" + src.data_import_id : "—") + "</dd></div>" +
        '<div class="kv-item"><dt>Analysis</dt><dd>' + escapeHtml(src.analysis_id || "—") + "</dd></div>" +
      "</div></div>";
    return '<div class="card insight-card" data-severity="' + escapeHtml(i.severity) + '" data-type="' + escapeHtml(i.insight_type) + '">' +
      '<div class="card-body">' +
      '<div class="insight-head">' +
        '<span class="priority-chip ' + sevClass + '">' + escapeHtml(i.severity) + "</span>" + det +
        (conf ? '<span class="badge neutral" title="Model/data confidence — not factual certainty">Confidence ' + conf + "</span>" : "") +
        '<span style="flex:1"></span>' +
        '<span class="badge neutral">' + escapeHtml(i.insight_type.replace(/_/g, " ")) + "</span>" +
      "</div>" +
      '<h3 style="margin:10px 0 4px">' + escapeHtml(i.title) + "</h3>" +
      '<p class="insight-summary">' + escapeHtml(i.summary || "") + "</p>" +
      (i.entity_id ? '<div class="ai-meta"><span class="badge neutral">' + escapeHtml(i.entity_type + ": " + i.entity_id) + "</span></div>" : "") +
      '<div class="ai-actions" style="margin-top:10px">' +
        '<button class="btn btn-secondary btn-sm" data-evidence="1" type="button" aria-expanded="false">' + icon("eye", 14) + " View Evidence</button>" +
        (i.recommendation ? '<button class="btn btn-secondary btn-sm" data-reco="1" type="button" aria-expanded="false">' + icon("clipboard", 14) + " Recommendation</button>" : "") +
      "</div>" +
      '<div data-evidence-target hidden><div class="insight-evidence"><p class="kicker">Evidence <span class="hint">values calculated by the backend from the analysis context</span></p>' +
        '<div class="kv">' + (evRows || '<p class="hint">No structured evidence recorded.</p>') + "</div>" + srcHtml + "</div></div>" +
      (i.recommendation ? '<div data-reco-target hidden><div class="insight-evidence"><p class="kicker">Recommendation</p><p style="font-size:13.5px">' + escapeHtml(i.recommendation) + "</p></div></div>" : "") +
      (i.status === "insufficient_data" && i.reason ? '<div class="neutral-panel" style="margin-top:10px"><p style="font-size:12.5px;font-weight:600">INSUFFICIENT DATA</p><p style="font-size:12.5px;color:var(--text-2)">' + escapeHtml(i.reason) + "</p></div>" : "") +
      "</div></div>";
  }

  function activityLogSection(timings) {
    var defs = [
      ["agent_1", "Transaction Analyst", "Detect"],
      ["agent_2", "Anomaly Investigator", "Verify"],
      ["agent_3", "Evidence Case Builder", "Build case"],
      ["agent_4", "Alert Generator", "Generate alert"]
    ];
    var stages = (state.result && state.result.stages) || {};
    var rows = defs.map(function (d) {
      var t = timings[d[0]] || {};
      var st = stages[d[0]] || "pending";
      var time = t.ended_at ? t.ended_at.slice(11, 19) : (t.started_at ? t.started_at.slice(11, 19) : "—");
      var dur = t.duration_ms != null ? " · " + fmtNumber(t.duration_ms) + " ms elapsed" : "";
      return '<div class="log-row"><span class="log-time mono">' + escapeHtml(time) + "</span>" +
        '<span class="log-agent">' + escapeHtml(d[1]) + "</span>" +
        '<span class="log-sub">' + escapeHtml(d[2]) + "</span>" +
        '<span class="log-status"><span class="badge ' + (st === "completed" ? "success" : st === "failed" ? "error" : st === "skipped" ? "neutral" : "info") + '">' + escapeHtml(st) + "</span>" + dur + "</span></div>";
    }).join("");
    return '<section class="section"><div class="section-title">Agent activity <span class="hint">real timestamps and durations recorded by the backend workflow</span></div>' +
      '<div class="card"><div class="card-body"><div class="log-list">' + rows + "</div></div></div></section>";
  }

  function analysisHistorySection() {
    var h = state.analysisHistory;
    if (!h) return '<section class="section" id="analysis-history-section"><div class="section-title">Analysis history</div><div class="card"><div class="card-body">' + skeleton() + "</div></div></section>";
    var rows = (h.runs || []).map(function (r) {
      var badge = { COMPLETED: "success", FAILED: "error", INSUFFICIENT_DATA: "warning" }[r.status] || "neutral";
      var types = (r.analysis_types || []).map(function (t) {
        var short = { distribution_anomaly: "Anomaly", recommendations: "Recs", operational_risk: "Operational", inventory_risk: "Inventory", demand_forecast: "Forecast" }[t] || t;
        return '<span class="badge neutral">' + escapeHtml(short) + "</span>";
      }).join("");
      return '<tr>' +
        '<td class="mono">' + escapeHtml(r.analysis_id) + "</td>" +
        "<td>" + escapeHtml(r.dataset_name || "—") + "</td>" +
        "<td>" + escapeHtml((r.dataset_mode === "real" ? "Real import" : "Synthetic demo")) + "</td>" +
        '<td class="types-cell">' + types + "</td>" +
        '<td class="num">' + fmtNumber(r.insight_count) + "</td>" +
        '<td><span class="badge ' + badge + '">' + escapeHtml(r.status) + "</span></td>" +
        "<td>" + escapeHtml(fmtDate(r.created_at)) + "</td>" +
        '<td class="actions-cell">' +
          '<button class="btn btn-ghost btn-sm" data-hist-view="' + r.id + '" type="button">View</button> ' +
          '<button class="btn btn-secondary btn-sm" data-hist-rerun="' + r.id + '" type="button">Run Again</button>' +
        "</td></tr>";
    }).join("");
    return '<section class="section" id="analysis-history-section"><div class="section-title">Analysis history <span class="hint">real persisted runs — Run Again creates a new analysis id, never overwriting</span></div>' +
      '<div class="card"><div class="card-body flush">' +
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      "<th>Analysis</th><th>Dataset</th><th>Mode</th><th>Types</th><th>Insights</th><th>Status</th><th>Date</th><th></th>" +
      "</tr></thead><tbody>" + (rows || '<tr><td colspan="8">' + emptyState("activity", "No analysis runs yet", "Run an analysis to record history here.", null) + "</td></tr>") + "</tbody></table></div>" +
      '<div id="analysis-history-detail"></div>' +
      "</div></div></section>";
  }

  function loadAnalysisHistory() {
    fetchJson(API_BASE + "/api/analysis/history?per_page=8", {}, 10000).then(function (p) {
      state.analysisHistory = p;
      if (state.route === "analysis") {
        var el = $id("analysis-history-section");
        if (el) el.outerHTML = analysisHistorySection();
        bindAnalysisHistoryControls();
      }
    }).catch(function () {
      state.analysisHistory = { runs: [], total: 0 };
      var el = $id("analysis-history-section");
      if (el) { el.outerHTML = analysisHistorySection(); bindAnalysisHistoryControls(); }
    });
  }

  function bindAnalysisHistoryControls() {
    document.querySelectorAll("[data-hist-view]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-hist-view"));
        var target = $id("analysis-history-detail");
        if (!target) return;
        target.innerHTML = '<div style="margin-top:14px">' + skeleton() + "</div>";
        fetchJson(API_BASE + "/api/analysis/history/" + id, {}, 10000).then(function (d) {
          var rows = [
            ["Analysis", d.analysis_id], ["Dataset", d.dataset_name], ["Source", d.source_name],
            ["Mode", d.dataset_mode === "real" ? "Real imported dataset" : "Synthetic demo dataset"],
            ["Status", d.status], ["Insights", fmtNumber(d.insight_count)],
            ["Anomalies / Findings", d.anomaly_count + " / " + d.finding_count],
            ["Cases / Alerts", d.case_count + " / " + d.alert_count],
            ["Duration", d.duration_ms != null ? fmtNumber(d.duration_ms) + " ms" : "—"],
            ["Created", d.created_at]
          ];
          var typeChips = (d.analysis_types || []).map(function (t) { return '<span class="badge neutral">' + escapeHtml(t) + "</span>"; }).join("");
          var filters = d.filters && Object.keys(d.filters).length
            ? '<div class="kv">' + Object.keys(d.filters).map(function (k) {
                return '<div class="kv-item"><dt>' + escapeHtml(k) + "</dt><dd>" + escapeHtml(String(d.filters[k])) + "</dd></div>";
              }).join("") + "</div>"
            : '<p class="hint">No filters — the whole dataset was analyzed.</p>';
          target.innerHTML = '<div class="card" style="margin-top:14px"><div class="card-body">' +
            '<div class="section-title">Analysis run details <span class="hint">persisted metadata — the full result is returned live during the run</span></div>' +
            '<div class="kv">' + rows.map(function (r) {
              return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
            }).join("") + "</div>" +
            '<div class="section-title" style="margin-top:14px">Types</div><div class="precheck-types">' + typeChips + "</div>" +
            '<div class="section-title" style="margin-top:14px">Configuration / filters</div>' + filters +
            (d.summary ? '<p class="hint" style="margin-top:10px">' + escapeHtml(d.summary) + "</p>" : "") +
            "</div></div>";
        }).catch(function (err) {
          target.innerHTML = analyticsErrorPanel(err.serverMessage || err.message || "Could not load the analysis run.");
        });
      });
    });
    document.querySelectorAll("[data-hist-rerun]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-hist-rerun"));
        var run = ((state.analysisHistory || {}).runs || []).filter(function (r) { return r.id === id; })[0];
        if (!run) return;
        state.analysisPrecheck = null;
        if (run.dataset_mode === "real" && run.data_import_id != null) {
          state.analysisDataset = "real";
          state.analysisImportId = run.data_import_id;
        } else {
          state.analysisDataset = "synthetic";
          state.analysisImportId = null;
        }
        if (Array.isArray(run.analysis_types) && run.analysis_types.length) {
          state.analysisTypes = {};
          run.analysis_types.forEach(function (t) { state.analysisTypes[t] = true; });
        }
        runAnalysis();
      });
    });
  }

  function datasetProvenanceHtml(d) {
    var quality = d.data_quality != null ? Math.round(d.data_quality * 100) + "%" : "—";
    var rows = [
      ["Mode", d.mode === "real" ? "Real imported dataset" : "Synthetic demo dataset"],
      ["Dataset", d.dataset_name || "—"],
      ["Source", d.source_name || "—"],
      d.mode === "real" ? ["Data import ID", String(d.data_import_id)] : null,
      ["Records imported", d.record_count != null ? String(d.record_count) : "—"],
      ["Records analyzed", String(d.transaction_count)],
      ["Data quality", quality]
    ].filter(Boolean);
    return '<section class="section"><div class="section-title">Dataset <span class="hint">provenance reported by the backend — which dataset produced this result</span></div>' +
      '<div class="card"><div class="card-body"><div class="kv">' + rows.map(function (r) {
        return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
      }).join("") + "</div></div></div></section>";
  }

  function renderPipelineSection(stages) {
    var defs = [
      ["agent_1", "Transaction Analyst", "Detect"],
      ["agent_2", "Anomaly Investigator", "Verify"],
      ["agent_3", "Evidence Case Builder", "Build case"],
      ["agent_4", "Alert Generator", "Generate alert"]
    ];
    return '<section class="section"><div class="section-title">Agent pipeline <span class="hint">statuses reported by the backend from the actual workflow run</span></div>' +
      '<div class="pipeline-list">' + defs.map(function (d) {
        var st = stages ? stages[d[0]] : "pending";
        var cls = st === "completed" ? "is-completed" : st === "failed" ? "is-failed" : st === "skipped" ? "is-skipped" : "";
        var badge = st === "completed" ? '<span class="badge success"><span class="dot"></span>Completed</span>'
          : st === "failed" ? '<span class="badge error"><span class="dot"></span>Failed</span>'
          : st === "skipped" ? '<span class="badge neutral">Skipped</span>'
          : '<span class="badge neutral"><span class="dot"></span>Pending</span>';
        return '<div class="card stage-card ' + cls + '"><span class="stage-name">' + d[1] + '</span><span class="stage-sub">' + d[2] + '</span><span class="stage-status">' + badge + "</span></div>";
      }).join("") + "</div></section>";
  }

  function alertCardHtml(chain) {
    var alert = chain.alert, caseObj = chain.case, finding = chain.findings[0] || null, anomaly = chain.anomalies[0] || null;
    var evidence = finding && finding.evidence ? finding.evidence : {};
    var timeDiff = evidence.time_difference_minutes != null ? String(evidence.time_difference_minutes) + " minutes" : "—";
    var distance = evidence.distance_km != null ? String(evidence.distance_km) + " km" : "—";
    var verification = finding && finding.status === "verified" ? "Verified against transaction data" : (finding ? finding.status : "—");
    var statusLabel = alert.status === "open" ? "Pending human review" : String(alert.status || "—");
    var anomalyType = anomaly && anomaly.anomaly_type ? anomaly.anomaly_type.replace(/_/g, " ") : "—";
    var sevClass = { high: "high", medium: "medium", low: "low" }[alert.severity] || "low";
    var rows = [
      ["Alert ID", alert.alert_id], ["Case ID", caseObj && caseObj.case_id],
      ["Finding ID", finding && finding.finding_id], ["Anomaly ID", anomaly && anomaly.anomaly_id],
      ["Beneficiary", anomaly && anomaly.beneficiary_id], ["Transactions", chain.transactionIds.join(", ")],
      ["Anomaly type", anomalyType], ["Time difference", timeDiff],
      ["Geographic distance", distance], ["Verification status", verification],
      ["Status", statusLabel], ["Recommended action", alert.recommended_action || (caseObj && caseObj.recommended_action)]
    ];
    return '<div class="alert-card" aria-label="Generated alert">' +
      '<div class="alert-head"><div><p class="kicker">Potential anomaly</p>' +
      '<p class="alert-message">' + escapeHtml(alert.message || "") + "</p></div>" +
      '<span class="priority-chip ' + sevClass + '">' + escapeHtml(String(alert.severity || "—").toUpperCase()) + "</span></div>" +
      '<dl class="alert-grid">' + rows.map(function (r) {
        var display = r[1] == null || r[1] === "" ? "—" : escapeHtml(String(r[1]));
        return '<div class="alert-row"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + display + "</dd></div>";
      }).join("") + "</dl></div>";
  }

  function traceHtml(chain) {
    var nodes = [];
    if (chain.alert) nodes.push({ id: chain.alert.alert_id, label: "Alert" });
    if (chain.case) nodes.push({ id: chain.case.case_id, label: "Case" });
    chain.findings.forEach(function (f) { nodes.push({ id: f.finding_id, label: "Finding" }); });
    chain.anomalies.forEach(function (a) { nodes.push({ id: a.anomaly_id, label: "Anomaly" }); });
    nodes.push({ id: chain.transactionIds.join(", ") || "—", label: "Transactions" });
    return '<div class="trace-chain">' + nodes.map(function (node, i) {
      return '<div class="trace-item"><div class="trace-node"><span class="trace-id">' + escapeHtml(node.id) +
        '</span><span class="trace-label">' + escapeHtml(node.label) + "</span></div>" +
        (i < nodes.length - 1 ? '<span class="trace-arrow" aria-hidden="true">→</span>' : "") + "</div>";
    }).join("") + "</div>";
  }

  function transactionsTableHtml(ids) {
    var byId = {};
    transactions().forEach(function (t) { byId[t.transaction_id] = t; });
    var header = ["Transaction ID", "Beneficiary", "Timestamp", "Latitude", "Longitude", "Ration type", "Quantity"]
      .map(function (h) { return "<th>" + h + "</th>"; }).join("");
    var rows = ids.map(function (id) {
      var tx = byId[id];
      if (!tx) return '<tr><td class="mono">' + escapeHtml(id) + '</td><td colspan="6">Details unavailable in dataset</td></tr>';
      return "<tr>" +
        '<td class="mono">' + escapeHtml(tx.transaction_id) + "</td>" +
        '<td class="mono">' + escapeHtml(tx.beneficiary_id) + "</td>" +
        "<td>" + escapeHtml(tx.timestamp) + "</td>" +
        '<td class="num">' + escapeHtml(String(tx.latitude)) + "</td>" +
        '<td class="num">' + escapeHtml(String(tx.longitude)) + "</td>" +
        "<td>" + escapeHtml(tx.ration_type) + "</td>" +
        '<td class="num">' + escapeHtml(String(tx.quantity)) + "</td></tr>";
    }).join("");
    return '<table class="data"><thead><tr>' + header + "</tr></thead><tbody>" + (rows || '<tr><td colspan="7">No transactions</td></tr>') + "</tbody></table>";
  }

  function bindAnalysisControls() {
    var runBtn = $id("run-button");
    if (runBtn) runBtn.addEventListener("click", runAnalysis);
    var exportBtn = $id("export-button");
    if (exportBtn) exportBtn.addEventListener("click", function () {
      if (state.result) {
        download("rationai-analysis-" + (state.result.analysis_run ? state.result.analysis_run.analysis_id : "result") + ".json",
          JSON.stringify(state.result, null, 2), "application/json");
      }
    });
    var dsSelect = $id("analysis-dataset");
    if (dsSelect) dsSelect.addEventListener("change", function () {
      var val = dsSelect.value;
      if (val === "synthetic") {
        state.analysisDataset = "synthetic";
        state.analysisImportId = null;
      } else if (val.indexOf("real:") === 0) {
        state.analysisDataset = "real";
        state.analysisImportId = Number(val.slice(5));
      }
      state.analysisPrecheck = null;
      runPrecheck();
    });
    document.querySelectorAll("[data-atype]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        if (!state.analysisTypes) state.analysisTypes = {};
        state.analysisTypes[cb.getAttribute("data-atype")] = cb.checked;
      });
    });
    document.querySelectorAll("[data-af]").forEach(function (input) {
      input.addEventListener("input", function () {
        state.analysisFilters[input.getAttribute("data-af")] = input.value;
      });
    });
    var retryBtn = $id("retry-button");
    if (retryBtn) retryBtn.addEventListener("click", function () {
      if (state.dataset === null) loadDataset().catch(function () {});
      runAnalysis();
    });
    var resetBtn = $id("reset-button");
    if (resetBtn) resetBtn.addEventListener("click", resetDemo);
    bindInsightControls();
    bindAnalysisHistoryControls();
  }

  function runPrecheck() {
    var body = { dataset: state.analysisDataset };
    if (state.analysisDataset === "real" && state.analysisImportId != null) {
      body.data_import_id = state.analysisImportId;
    }
    fetchJson(API_BASE + "/api/analysis/precheck", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    }, 10000).then(function (p) {
      state.analysisPrecheck = p;
      if (state.route === "analysis" && !state.running) renderRoute();
    }).catch(function () { /* keep the hint if the precheck is unavailable */ });
  }

  function bindInsightControls() {
    document.querySelectorAll("[data-isev]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.insightSeverity = btn.getAttribute("data-isev");
        refreshInsights();
      });
    });
    document.querySelectorAll("[data-ityp]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.insightType = btn.getAttribute("data-ityp");
        refreshInsights();
      });
    });
    var search = $id("insight-search");
    if (search) search.addEventListener("input", function () {
      state.insightQuery = search.value;
      refreshInsights();
    });
    document.querySelectorAll("[data-evidence]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest(".insight-card");
        var target = card && card.querySelector("[data-evidence-target]");
        if (!target) return;
        var open = target.hidden;
        target.hidden = !open;
        btn.setAttribute("aria-expanded", String(!open));
      });
    });
    document.querySelectorAll("[data-reco]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest(".insight-card");
        var target = card && card.querySelector("[data-reco-target]");
        if (!target) return;
        var open = target.hidden;
        target.hidden = !open;
        btn.setAttribute("aria-expanded", String(!open));
      });
    });
  }

  function refreshInsights() {
    var sec = $id("insights-section");
    if (sec) {
      sec.outerHTML = insightsSectionHtml();
      bindInsightControls();
    }
  }

  /* ------------------------------------------------------------------ *
   *  Import Data (Phase 3 — real dataset ingestion)
   *  The frontend only drives the flow and displays backend results: file
   *  parsing, column mapping, validation, duplicates, and database import
   *  all happen server-side.
   * ------------------------------------------------------------------ */
  var UPLOAD_TYPES = ["beneficiaries", "fps_centers", "ration_transactions", "inventory", "combined"];
  var UPLOAD_TYPE_LABELS = {
    beneficiaries: "Beneficiaries", fps_centers: "FPS Centers",
    ration_transactions: "Ration Transactions", inventory: "Inventory", combined: "Combined Dataset"
  };

  /* ------------------------------------------------------------------ *
   *  Data Sources (Phase 7 — external connectors)
   * ------------------------------------------------------------------ */
  function renderSources() {
    var v = $view();
    v.innerHTML = viewHead("Data Sources", "External data connectors. Only registered, server-side sources can be synced — the app never fetches user-supplied URLs. Sync results are imported through the same validation pipeline as uploads.");

    var load = function () {
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="grid">' + skeleton() + skeleton() + "</div></section>");
      fetchJson(API_BASE + "/api/data-sources", {}, 15000).then(function (payload) {
        renderSourceList(payload.sources || []);
      }).catch(function () {
        v.insertAdjacentHTML("beforeend", analyticsErrorPanel("Could not load data sources. Check that the backend is running."));
      });
    };

    function renderSourceList(sources) {
      v.querySelector(".grid") && v.querySelector(".grid").remove();
      if (!sources.length) {
        v.insertAdjacentHTML("beforeend", emptyState("cloud", "No data sources configured", "Register a source in the server-side connector configuration.", null));
        return;
      }
      var html = sources.map(function (s) {
        return sourceCard(s);
      }).join("");
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="grid cols-2">' + html + "</div></section>");
      bindSourceControls(sources);
    }

    load();
  }

  function sourceStatusBadge(status) {
    var map = {
      CONNECTED: ["success", "Connected"],
      CONNECTOR_READY: ["info", "Connector ready"],
      SYNCING: ["info", "Syncing"],
      UP_TO_DATE: ["success", "Up to date"],
      PARTIAL: ["warning", "Partial"],
      ERROR: ["error", "Sync error"],
      DISCONNECTED: ["neutral", "Not connected"],
      NOT_CONNECTED: ["neutral", "Not connected"]
    };
    var m = map[status] || ["neutral", status || "Unknown"];
    return '<span class="badge ' + m[0] + '"><span class="dot"></span>' + m[1] + "</span>";
  }

  // Honest data-origin label (Phase 8 §17): LIVE vs REAL IMPORTED vs MOCK vs DEMO.
  function sourceOriginBadge(s) {
    if (s.name === "sample_open_pds") {
      return '<span class="badge warning">MOCK / TEST</span>';
    }
    if (s.name === "ogd_pds_resource") {
      // Only claim a verified link after a real successful sync (Phase 8 §17).
      return s.last_successful_sync_at
        ? '<span class="badge success">OFFICIAL · VERIFIED SYNC</span>'
        : '<span class="badge neutral">OFFICIAL · NOT LIVE</span>';
    }
    if (s.name === "Synthetic Demo Dataset") {
      return '<span class="badge neutral">DEMO</span>';
    }
    return '<span class="badge success">REAL IMPORTED</span>';
  }

  function sourceCard(s) {
    var last = s.last_import;
    var rows = [];
    if (s.label) rows.push(["Source", s.label]);
    if (s.last_successful_sync_at) rows.push(["Last successful sync", s.last_successful_sync_at]);
    else if (s.last_sync_at) rows.push(["Last sync attempt", s.last_sync_at]);
    if (s.type) rows.push(["Type", s.type]);
    if (last) {
      rows.push(["Import", "#" + last.data_import_id + " · " + last.status]);
      rows.push(["Records fetched", String(last.record_count)]);
      rows.push(["Imported", String(last.successful_records)]);
      if (last.duplicate_records) rows.push(["Duplicates", String(last.duplicate_records)]);
      if (last.failed_records) rows.push(["Failed", String(last.failed_records)]);
    }

    var details = [];
    if (s.format) details.push(["Format", String(s.format).toUpperCase()]);
    if (s.dataset_type) details.push(["Dataset type", s.dataset_type.replace(/_/g, " ")]);
    if (s.requires_auth != null) details.push(["Authentication", s.requires_auth ? "API key (server-side env " + (s.name === "ogd_pds_resource" ? "GOVERNMENT_DATA_API_KEY" : "") + ")" : "None"]);
    if (s.requires_auth) details.push(["Credential", s.auth_configured ? "Configured (server-side)" : "Not configured"]);
    if (s.base_url) details.push(["Endpoint", s.base_url]);
    if (s.documentation_url) details.push(["Documentation", '<a href="' + escapeHtml(s.documentation_url) + '" target="_blank" rel="noopener">' + escapeHtml(s.documentation_url) + "</a>"]);

    var note = "";
    if (s.name === "sample_open_pds") {
      note = '<p class="hint" style="font-size:12px;margin-top:10px;color:var(--warning)">Sample data — bundled with RationAI to exercise the connector pipeline end to end. Not an external government source; never presented as live.</p>';
    } else if (s.name === "ogd_pds_resource") {
      note = s.last_successful_sync_at
        ? '<p class="hint" style="font-size:12px;margin-top:10px">Official Open Government Data (OGD) India API resource — verified sync of the real resource, imported as FPS centers with the server-side API key. ' +
          (s.documentation_url ? '<a href="' + escapeHtml(s.documentation_url) + '" target="_blank" rel="noopener">Documentation</a>' : "") + "</p>"
        : '<p class="hint" style="font-size:12px;margin-top:10px">Official Open Government Data (OGD) India API resource. The API key is configured server-side; a live connection requires a successful sync — until then this stays CONNECTOR READY / NOT LIVE. ' +
          (s.documentation_url ? '<a href="' + escapeHtml(s.documentation_url) + '" target="_blank" rel="noopener">Documentation</a>' : "") + "</p>";
    }

    var statusTone = s.connection_status === "CONNECTED" ? "success" : s.connection_status === "ERROR" ? "error" : s.connection_status === "SYNCING" ? "info" : "neutral";
    return '<div class="card hoverable"><div class="card-body">' +
      '<div style="display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap">' +
        '<span class="badge ' + statusTone + '"><span class="dot"></span>' + escapeHtml(String(s.connection_status || "NOT_CONNECTED")) + "</span>" +
        sourceOriginBadge(s) +
        '<span style="flex:1"></span>' +
        '<button class="btn btn-secondary btn-sm" data-sync="' + s.data_source_id + '" type="button">' +
          (s.connection_status === "SYNCING" ? '<span class="spinner"></span> Syncing…' : icon("cloud", 15) + " Sync Now") + "</button>" +
      "</div>" +
      '<h3 style="margin:12px 0 4px">' + escapeHtml(s.label || s.name) + "</h3>" +
      '<p style="font-size:13px;color:var(--text-2);line-height:1.5">' + escapeHtml(s.description || "") + "</p>" +
      (s.last_error ? '<div class="error-panel" style="margin-top:10px" role="alert"><p style="font-size:12.5px">' + escapeHtml(s.last_error) + "</p></div>" : "") +
      (rows.length ? '<div class="kv" style="margin-top:12px">' + rows.map(function (r) {
        return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
      }).join("") + "</div>" : "") +
      note +
      '<div class="btn-row" style="margin-top:12px;gap:8px">' +
        '<button class="btn btn-ghost btn-sm" data-test="' + s.data_source_id + '" type="button">' + icon("activity", 14) + " Test Connection</button>" +
        '<button class="btn btn-ghost btn-sm" data-history="' + s.data_source_id + '" type="button">View import history</button>' +
        (details.length ? '<button class="btn btn-ghost btn-sm" data-details="' + s.data_source_id + '" type="button" aria-expanded="false">Details</button>' : "") +
      "</div>" +
      '<div data-test-target="' + s.data_source_id + '"></div>' +
      (details.length ? '<div class="source-details" data-details-target="' + s.data_source_id + '" hidden><div class="kv">' + details.map(function (r) {
        return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + r[1] + "</dd></div>";
      }).join("") + "</div></div>" : "") +
      '<div data-history-target="' + s.data_source_id + '"></div>' +
    "</div></div>";
  }

  function bindSourceControls(sources) {
    var byId = {};
    sources.forEach(function (s) { byId[s.data_source_id] = s; });
    document.querySelectorAll("[data-sync]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-sync"));
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Syncing…';
        fetchJson(API_BASE + "/api/data-sources/" + id + "/sync", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: "{}"
        }, 90000).then(function (summary) {
          toast(summary.message || "Sync completed.", summary.status === "ERROR" ? "error" : "success");
          renderSources();
        }).catch(function (err) {
          toast("Sync failed: " + (err.serverMessage || err.message || "unknown error"), "error");
          renderSources();
        });
      });
    });
    document.querySelectorAll("[data-test]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-test"));
        var target = document.querySelector('[data-test-target="' + id + '"]');
        if (!target) return;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Testing…';
        target.innerHTML = '<p class="hint" style="margin-top:8px">Probing the source…</p>';
        fetchJson(API_BASE + "/api/data-sources/" + id + "/test", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: "{}"
        }, 20000).then(function (probe) {
          renderTestResult(target, probe);
        }).catch(function (err) {
          target.innerHTML = '<div class="error-panel" style="margin-top:8px" role="alert"><p style="font-size:12.5px">Connection test failed: ' + escapeHtml(err.serverMessage || err.message || "unknown error") + "</p></div>";
        }).finally(function () {
          btn.disabled = false;
          btn.innerHTML = icon("activity", 14) + " Test Connection";
        });
      });
    });
    document.querySelectorAll("[data-details]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-details"));
        var target = document.querySelector('[data-details-target="' + id + '"]');
        if (!target) return;
        var open = !target.hidden;
        target.hidden = open;
        btn.setAttribute("aria-expanded", String(!open));
      });
    });
    document.querySelectorAll("[data-history]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-history"));
        var target = document.querySelector('[data-history-target="' + id + '"]');
        if (!target) return;
        if (target.getAttribute("data-loaded")) {
          target.innerHTML = "";
          target.removeAttribute("data-loaded");
          return;
        }
        target.innerHTML = '<div class="table-wrap" style="margin-top:10px">' + skeleton() + "</div>";
        fetchJson(API_BASE + "/api/data-sources/" + id + "/imports", {}, 15000).then(function (payload) {
          var imports = payload.imports || [];
          if (!imports.length) { target.innerHTML = ""; return; }
          var rows = imports.map(function (i) {
            return "<tr><td class=\"mono\">#" + i.id + "</td><td>" + escapeHtml(i.dataset_name || "") + "</td>" +
              '<td class="num">' + i.record_count + "</td><td class=\"num\">" + i.successful_records + "</td>" +
              '<td class="num">' + (i.failed_records || 0) + "</td><td>" + escapeHtml(i.status) + "</td>" +
              "<td>" + escapeHtml(i.completed_at || "") + "</td></tr>";
          }).join("");
          target.innerHTML = '<div class="table-wrap" style="margin-top:10px"><table class="data"><thead><tr>' +
            "<th>Import</th><th>Dataset</th><th>Fetched</th><th>Imported</th><th>Failed</th><th>Status</th><th>Completed</th>" +
            "</tr></thead><tbody>" + rows + "</tbody></table></div>";
          target.setAttribute("data-loaded", "1");
        }).catch(function () {
          target.innerHTML = "";
        });
      });
    });
  }

  // Render a connection-test outcome without ever faking success: the probe
  // result comes from the backend's actual request to the configured source.
  function renderTestResult(target, probe) {
    var ok = probe.status === "ok";
    var labels = {
      CONNECTION_OK: "✓ Connection successful",
      AUTH_NOT_CONFIGURED: "Connection not tested — credentials not configured",
      AUTH_FAILED: "✕ Authentication failed",
      RATE_LIMITED: "⚠ Rate limited by the source",
      TIMEOUT: "✕ Connection timed out",
      UNREACHABLE: "✕ Endpoint unreachable",
      HTTP_ERROR: "✕ Endpoint returned an error",
      NOT_CONFIGURED: "✕ Source not configured",
      UNKNOWN_SOURCE: "✕ Unknown source",
      ERROR: "✕ Connection failed"
    };
    var label = labels[probe.category] || (ok ? "✓ Connection successful" : "✕ Connection failed");
    target.innerHTML = '<div class="' + (ok ? "ok-panel" : "neutral-panel") + '" style="margin-top:8px" role="status">' +
      '<p style="font-size:12.5px;font-weight:600">' + label + "</p>" +
      "<p style=\"font-size:12.5px;color:var(--text-2);margin-top:2px\">" + escapeHtml(probe.detail || "") + "</p>" +
      "</div>";
  }

  /* ------------------------------------------------------------------ *
   *  Data Pipeline (Phase 8 — source -> extract -> validate -> normalize
   *  -> deduplicate -> database -> analytics -> AI, driven by the database)
   * ------------------------------------------------------------------ */
  var PIPELINE_DEFS = [
    ["source", "Source", "Where data comes from"],
    ["extract", "Extract", "Fetch / parse raw records"],
    ["validate", "Validate", "Required fields + business rules"],
    ["normalize", "Normalize", "Dates, numbers, commodities, units"],
    ["deduplicate", "Deduplicate", "Exact + possible duplicate handling"],
    ["database", "Database", "Normalized tables with provenance"],
    ["analytics", "Analytics", "Phase 5 aggregation layer"],
    ["ai", "AI", "Multi-agent analysis"]
  ];

  function renderPipeline() {
    var v = $view();
    var p = state.pipeline;
    if (!p) {
      p = state.pipeline = {
        status: null, freshness: null, quality: null, runs: null,
        runDetail: null, runsError: null,
        filters: { source: "", status: "", q: "", from: "", to: "" },
        page: 1
      };
    }
    v.innerHTML = viewHead("Data Pipeline", "How data enters RationAI and becomes dashboard analytics and AI insights. Every value below is computed by the backend from the actual database — nothing is invented.",
      '<span class="badge ai">' + icon("layers", 12) + " Data lifecycle</span>") +
      '<section class="section" id="pipeline-overall">' + skeleton() + "</section>" +
      '<section class="section" id="pipeline-stages">' + skeleton() + "</section>" +
      '<section class="section" id="pipeline-quality">' + skeleton() + "</section>" +
      '<section class="section" id="pipeline-runs">' + skeleton() + "</section>";

    loadPipelineStatus();
    loadPipelineQuality();
    loadPipelineRuns();
  }

  function loadPipelineStatus() {
    var p = state.pipeline;
    Promise.all([
      fetchJson(API_BASE + "/api/pipeline/status", {}, 15000),
      fetchJson(API_BASE + "/api/pipeline/freshness", {}, 15000)
    ]).then(function (results) {
      p.status = results[0];
      p.freshness = results[1];
      var el = $id("pipeline-overall");
      if (el) el.outerHTML = pipelineOverallHtml(p.status, p.freshness);
      var stagesEl = $id("pipeline-stages");
      if (stagesEl) stagesEl.outerHTML = pipelineStagesHtml(p.status);
      bindPipelineStageClicks();
    }).catch(function (err) {
      p.statusError = err.serverMessage || err.message || "Could not load pipeline status.";
      var el = $id("pipeline-overall");
      if (el) el.outerHTML = '<section class="section">' + analyticsErrorPanel(p.statusError) + "</section>";
      var stagesEl = $id("pipeline-stages");
      if (stagesEl) stagesEl.remove();
    });
  }

  function pipelineOverallHtml(status, freshness) {
    var tone = { HEALTHY: ["success", "HEALTHY"], WARNING: ["warning", "WARNING"], ERROR: ["error", "ERROR"] }[status.overall] || ["neutral", status.overall];
    var freshTone = { FRESH: "success", RECENT: "success", STALE: "warning", UNKNOWN: "neutral" }[freshness.status] || "neutral";
    var freshLabel = freshness.status === "UNKNOWN" ? "Unknown — no successful import recorded" : (freshness.status + " · " + (freshness.age_label || "—"));
    return '<section class="section"><div class="grid cols-3">' +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Pipeline status</p>' +
        '<div style="display:flex;align-items:center;gap:10px;margin-top:6px">' +
          '<span class="status-dot ' + tone[0] + '"></span><span class="status-label">' + tone[1] + "</span></div>" +
        '<p class="hint" style="margin-top:8px">Computed from the real database: imports, sources, analytics, analysis runs.</p>' +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Data freshness</p>' +
        '<div style="display:flex;align-items:center;gap:10px;margin-top:6px">' +
          '<span class="badge ' + freshTone + '"><span class="dot"></span>' + escapeHtml(freshLabel) + "</span></div>" +
        '<p class="hint" style="margin-top:8px">' + (freshness.latest_data_at ? "Latest data: " + escapeHtml(freshness.latest_data_at) : escapeHtml(freshness.detail || "")) + "</p>" +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Checks</p>' +
        '<ul class="check-list">' + (status.checks || []).map(function (c) {
          return '<li class="' + (c.ok ? "is-ok" : "is-warn") + '">' + (c.ok ? "✓" : "⚠") + " <strong>" + escapeHtml(c.label) + "</strong><span>" + escapeHtml(c.detail || "") + "</span></li>";
        }).join("") + "</ul>" +
      "</div></div>" +
    "</div></section>";
  }

  function pipelineStagesHtml(status) {
    var stages = status.stages || [];
    return '<section class="section"><div class="section-title">Data pipeline stages <span class="hint">click a stage for detail — states come from the backend, not fake progress</span></div>' +
      '<div class="pipe-stages">' + stages.map(function (s, i) {
        var cls = s.status === "ok" ? "is-ok" : s.status === "warn" ? "is-warn" : s.status === "error" ? "is-error" : "is-unknown";
        var badge = s.status === "ok" ? '<span class="badge success">OK</span>'
          : s.status === "warn" ? '<span class="badge warning">WARNING</span>'
          : s.status === "error" ? '<span class="badge error">ERROR</span>'
          : '<span class="badge neutral">N/A</span>';
        return '<button class="card pipe-stage ' + cls + '" type="button" data-stage="' + s.key + '" aria-expanded="false">' +
          '<div class="pipe-stage-head"><span class="pipe-index">' + (i + 1) + "</span>" +
          '<div style="flex:1"><p class="pipe-label">' + escapeHtml(s.label) + "</p>" +
          '<p class="pipe-sub">' + escapeHtml(s.sub || "") + "</p></div>" +
          badge + "</div>" +
          '<div class="pipe-stage-detail" hidden><div class="kv">' +
            '<div class="kv-item"><dt>Records</dt><dd>' + (s.records == null ? "Not available" : fmtNumber(s.records)) + "</dd></div>" +
            '<div class="kv-item"><dt>Detail</dt><dd>' + escapeHtml(s.detail || "—") + "</dd></div>" +
            '<div class="kv-item"><dt>Last execution</dt><dd>' + escapeHtml(s.last_execution || "—") + "</dd></div>" +
          "</div></div></button>";
      }).join("") + "</div></section>";
  }

  function bindPipelineStageClicks() {
    document.querySelectorAll(".pipe-stage").forEach(function (el) {
      el.addEventListener("click", function () {
        var detail = el.querySelector(".pipe-stage-detail");
        var open = detail.hidden;
        detail.hidden = !open;
        el.setAttribute("aria-expanded", String(!open));
      });
    });
  }

  function loadPipelineQuality() {
    var p = state.pipeline;
    fetchJson(API_BASE + "/api/pipeline/quality", {}, 15000).then(function (payload) {
      p.quality = payload;
      var el = $id("pipeline-quality");
      if (el) el.outerHTML = pipelineQualityHtml(payload);
    }).catch(function () {
      var el = $id("pipeline-quality");
      if (el) el.remove();
    });
  }

  function pipelineQualityHtml(q) {
    var b = q.breakdown || {};
    function bar(label, value, suffix) {
      if (value == null) {
        return '<div class="quality-row"><span class="quality-label">' + escapeHtml(label) + '</span><span class="hint">Not available</span></div>';
      }
      return '<div class="quality-row"><span class="quality-label">' + escapeHtml(label) + '</span><span class="quality-bar"><span style="width:' + value + '%"></span></span><span class="quality-value">' + value + (suffix || "%") + "</span></div>";
    }
    return '<section class="section"><div class="section-title">Data quality <span class="hint">Phase 4 formula: 100 − 3.0×invalid% − 2.0×duplicates% − 0.5×warnings% (deterministic, no AI)</span></div>' +
      '<div class="grid cols-3">' +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Overall quality</p>' +
        '<p class="quality-score">' + (q.overall_score == null ? "—" : q.overall_score + "%") + "</p>" +
        '<p class="hint">' + fmtNumber(q.totals.records) + " records across " + q.import_count + " import(s)</p>" +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Breakdown</p>' +
        bar("Validity", b.validity) +
        bar("Consistency", b.consistency) +
        bar("Duplicate rate", b.duplicate_rate) +
        bar("Completeness", b.completeness) +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Totals</p>' +
        '<div class="kv">' +
          '<div class="kv-item"><dt>Valid</dt><dd>' + fmtNumber(q.totals.valid) + "</dd></div>" +
          '<div class="kv-item"><dt>Invalid</dt><dd>' + fmtNumber(q.totals.invalid) + "</dd></div>" +
          '<div class="kv-item"><dt>Duplicates</dt><dd>' + fmtNumber(q.totals.duplicates) + "</dd></div>" +
          '<div class="kv-item"><dt>Warnings</dt><dd>' + fmtNumber(q.totals.warnings) + "</dd></div>" +
        "</div>" +
      "</div></div>" +
    "</div></section>";
  }

  function loadPipelineRuns() {
    var p = state.pipeline;
    var f = p.filters;
    var params = new URLSearchParams();
    if (f.source) params.set("source", f.source);
    if (f.status) params.set("status", f.status);
    if (f.q) params.set("q", f.q);
    if (f.from) params.set("from", f.from);
    if (f.to) params.set("to", f.to);
    params.set("page", String(p.page));
    params.set("per_page", "10");
    fetchJson(API_BASE + "/api/pipeline/runs?" + params.toString(), {}, 15000).then(function (payload) {
      p.runs = payload;
      var el = $id("pipeline-runs");
      if (el) el.outerHTML = pipelineRunsHtml(payload);
      bindPipelineRunsControls();
    }).catch(function (err) {
      p.runsError = err.serverMessage || err.message || "Could not load pipeline runs.";
      var el = $id("pipeline-runs");
      if (el) el.outerHTML = '<section class="section">' + analyticsErrorPanel(p.runsError) + "</section>";
    });
  }

  function pipelineRunsHtml(data) {
    var f = state.pipeline.filters;
    var runs = data.runs || [];
    var rows = runs.map(function (r) {
      var badge = { COMPLETED: "success", PARTIAL: "warning", FAILED: "error", PENDING: "neutral", PROCESSING: "info" }[r.status] || "neutral";
      return '<tr class="run-row" data-import="' + r.id + '" tabindex="0" role="button" aria-label="View lineage for import #' + r.id + '">' +
        '<td class="mono">#' + r.id + "</td>" +
        "<td>" + escapeHtml(r.dataset_name || "") + "</td>" +
        "<td>" + escapeHtml(r.source_name || "") + "</td>" +
        '<td class="num">' + fmtNumber(r.record_count) + "</td>" +
        '<td class="num">' + fmtNumber(r.successful_records) + "</td>" +
        '<td class="num">' + fmtNumber(r.duplicate_records) + "</td>" +
        '<td class="num">' + fmtNumber(r.failed_records) + "</td>" +
        "<td>" + (r.quality_score == null ? "—" : r.quality_score + "%") + "</td>" +
        '<td><span class="badge ' + badge + '">' + escapeHtml(r.status) + "</span></td>" +
        "<td>" + escapeHtml(fmtDate(r.completed_at)) + "</td></tr>";
    }).join("");

    var sourceOpts = (data.sources || []).map(function (s) {
      return '<option value="' + s.id + '"' + (String(f.source) === String(s.id) ? " selected" : "") + ">" + escapeHtml(s.name) + "</option>";
    }).join("");
    var statusOpts = (data.statuses || []).map(function (st) {
      return '<option value="' + escapeHtml(st) + '"' + (f.status === st ? " selected" : "") + ">" + escapeHtml(st) + "</option>";
    }).join("");

    var totalPages = data.pages || 1;
    var pagination = totalPages > 1
      ? '<div class="pager">' +
        '<button class="btn btn-secondary btn-sm" data-page="' + (data.page - 1) + '" type="button" ' + (data.page <= 1 ? "disabled" : "") + ">Prev</button>" +
        '<span class="hint">Page ' + data.page + " of " + totalPages + " · " + fmtNumber(data.total) + " run(s)</span>" +
        '<button class="btn btn-secondary btn-sm" data-page="' + (data.page + 1) + '" type="button" ' + (data.page >= totalPages ? "disabled" : "") + ">Next</button>" +
      "</div>"
      : '<p class="hint">' + fmtNumber(data.total) + " run(s)</p>";

    var table = runs.length
      ? '<div class="table-wrap"><table class="data"><thead><tr>' +
        "<th>Run</th><th>Dataset</th><th>Source</th><th>Fetched</th><th>Valid</th><th>Duplicates</th><th>Errors</th><th>Quality</th><th>Status</th><th>Completed</th>" +
        "</tr></thead><tbody>" + rows + "</tbody></table></div>"
      : emptyState("layers", "No pipeline runs yet", "Import a dataset or run a sync to create the first pipeline run.", "upload");

    return '<section class="section"><div class="section-title">Pipeline runs <span class="hint">real DataImport records — click a run to trace its lineage</span></div>' +
      '<div class="card"><div class="card-body">' +
      '<div class="filter-row" style="flex-wrap:wrap">' +
        '<input class="input" type="search" id="pipeline-q" placeholder="Search dataset, file, source…" value="' + escapeHtml(f.q) + '" aria-label="Search pipeline runs">' +
        '<select class="select" id="pipeline-source" aria-label="Filter by source"><option value="">All sources</option>' + sourceOpts + "</select>" +
        '<select class="select" id="pipeline-status" aria-label="Filter by status"><option value="">All statuses</option>' + statusOpts + "</select>" +
        '<input class="input" type="date" id="pipeline-from" value="' + escapeHtml(f.from) + '" aria-label="From date">' +
        '<input class="input" type="date" id="pipeline-to" value="' + escapeHtml(f.to) + '" aria-label="To date">' +
        '<button class="btn btn-secondary btn-sm" id="pipeline-apply" type="button">Apply</button>' +
        '<button class="btn btn-ghost btn-sm" id="pipeline-clear" type="button">Clear</button>' +
      "</div>" +
      '<div style="margin-top:12px">' + table + "</div>" +
      '<div style="margin-top:12px">' + pagination + "</div>" +
      '<div id="pipeline-run-detail"></div>' +
      "</div></div></section>";
  }

  function bindPipelineRunsControls() {
    var p = state.pipeline;
    var apply = $id("pipeline-apply");
    if (apply) apply.addEventListener("click", function () {
      var f = p.filters;
      f.q = $id("pipeline-q").value.trim();
      f.source = $id("pipeline-source").value;
      f.status = $id("pipeline-status").value;
      f.from = $id("pipeline-from").value;
      f.to = $id("pipeline-to").value;
      p.page = 1;
      p.runDetail = null;
      loadPipelineRuns();
    });
    var clear = $id("pipeline-clear");
    if (clear) clear.addEventListener("click", function () {
      p.filters = { source: "", status: "", q: "", from: "", to: "" };
      p.page = 1;
      p.runDetail = null;
      loadPipelineRuns();
    });
    document.querySelectorAll(".pager [data-page]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pg = Number(btn.getAttribute("data-page"));
        if (pg < 1) return;
        p.page = pg;
        p.runDetail = null;
        loadPipelineRuns();
      });
    });
    document.querySelectorAll(".run-row").forEach(function (row) {
      row.addEventListener("click", function () { loadRunLineage(Number(row.getAttribute("data-import"))); });
      row.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); loadRunLineage(Number(row.getAttribute("data-import"))); }
      });
    });
  }

  function loadRunLineage(importId) {
    var target = $id("pipeline-run-detail");
    if (!target) return;
    if (target.getAttribute("data-import") === String(importId) && target.getAttribute("data-loaded")) {
      target.innerHTML = "";
      target.removeAttribute("data-import");
      target.removeAttribute("data-loaded");
      return;
    }
    target.innerHTML = '<div style="margin-top:16px">' + skeleton() + "</div>";
    fetchJson(API_BASE + "/api/pipeline/runs/" + importId, {}, 15000).then(function (detail) {
      target.setAttribute("data-import", String(importId));
      target.setAttribute("data-loaded", "1");
      target.innerHTML = runLineageHtml(detail);
    }).catch(function (err) {
      target.innerHTML = '<div style="margin-top:16px">' + analyticsErrorPanel(err.serverMessage || err.message || "Could not load the pipeline run.") + "</div>";
    });
  }

  function runLineageHtml(d) {
    var imp = d.import, src = d.source, rec = d.records, db = d.database;
    var nodes = [
      ["Source", src.name + " · " + (src.type || "")],
      ["Import", "#" + imp.data_import_id + " · " + imp.status + (rec.quality ? " · quality " + rec.quality.score + "%" : "")],
      ["Records", fmtNumber(rec.record_count) + " fetched · " + fmtNumber(rec.successful_records) + " valid · " + fmtNumber(rec.duplicate_records) + " duplicates · " + fmtNumber(rec.failed_records) + " failed"],
      ["Database", db.transactions + " transaction(s) · " + db.beneficiaries + " beneficiary(ies) · " + db.inventory + " inventory"],
      ["Analytics", "Phase 5 analytics query this import's records"]
    ];
    var runs = d.analysis_runs || [];
    if (runs.length) {
      runs.forEach(function (r) {
        nodes.push(["Analysis", r.analysis_id + " · " + r.status + " · " + escapeHtml(r.summary || "")]);
      });
    } else {
      nodes.push(["Analysis", "No analysis run recorded for this dataset yet — run it from the Analysis view"]);
    }
    nodes.push(["AI insights", d.ai_insights > 0 ? d.ai_insights + " persisted insight(s)" : "None persisted (workflow results are returned to the UI live)"]);

    return '<div class="card" style="margin-top:16px"><div class="card-body">' +
      '<div class="section-title">Lineage — import #' + imp.data_import_id + " <span class=\"hint\">every AI insight traces back through this chain</span></div>" +
      '<div class="lineage-chain">' + nodes.map(function (n, i) {
        return '<div class="lineage-node"><div class="lineage-head"><span class="lineage-label">' + escapeHtml(n[0]) + "</span></div>" +
          '<div class="lineage-detail">' + n[1] + "</div>" +
          (i < nodes.length - 1 ? '<div class="lineage-arrow" aria-hidden="true">↓</div>' : "") + "</div>";
      }).join("") + "</div>" +
      (imp.error_summary ? '<div class="error-panel" style="margin-top:12px" role="alert"><p style="font-size:12.5px">' + escapeHtml(imp.error_summary) + "</p></div>" : "") +
    "</div></div>";
  }

  function renderUpload() {
    var v = $view();
    var u = state.upload;
    v.innerHTML = viewHead("Import Data", "Upload a real dataset (CSV, XLSX, or JSON). The file is parsed, mapped, validated, and previewed before anything is written to the database — you confirm before importing.",
      '<span class="badge ai">' + icon("upload", 12) + " Real-data pipeline</span>");

    v.insertAdjacentHTML("beforeend", '<section class="section">' + uploadFlowHtml(u) + "</section>");
    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="section-title">Import history <span class="hint">from the database</span></div>' +
      '<div class="card"><div class="card-body flush">' +
        '<div class="table-wrap" id="import-history">' + skeleton() + "</div>" +
      "</div></div></section>");
    bindUploadControls();
    loadImportHistory();
  }

  function uploadFlowHtml(u) {
    if (u.busy && !u.result) {
      return '<div class="card"><div class="card-body">' +
        '<div style="display:flex;align-items:center;gap:10px"><span class="spinner"></span><span id="upload-busy-text">' +
        (u.step === "result" ? "Importing dataset…" : "Processing file…") + "</span></div>" +
      "</div></div>";
    }
    if (u.error) {
      return '<div class="card"><div class="card-body">' +
        '<div class="error-panel" role="alert"><span class="error-icon">' + icon("alert", 18) + "</span>" +
        "<div><h3>" + escapeHtml(u.error.title) + "</h3><p>" + escapeHtml(u.error.detail || "") + "</p>" +
        '<div class="error-actions"><button class="btn btn-secondary" id="upload-reset-error" type="button">Try again</button></div>' +
        "</div></div></div></div>";
    }
    if (!u.token) return uploadChooseHtml();
    if (u.step === "map") return uploadMapHtml(u);
    if (u.step === "preview") return uploadPreviewHtml(u);
    if (u.step === "result") return uploadResultHtml(u);
    return uploadChooseHtml();
  }

  function uploadChooseHtml() {
    return '<div class="card"><div class="card-body">' +
      '<div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Upload a dataset file">' +
        '<span class="drop-icon">' + icon("upload", 26) + "</span>" +
        '<h3>Drag &amp; drop a dataset</h3>' +
        '<p>CSV · XLSX · JSON — up to 10 MB</p>' +
        '<button class="btn btn-primary" id="upload-browse" type="button">Browse files</button>' +
        '<input type="file" id="upload-file" accept=".csv,.xlsx,.json" hidden>' +
      "</div>" +
      '<p style="font-size:12.5px;color:var(--text-2);margin-top:10px">Files are validated on the server before import. No record is written until you confirm the mapping and preview.</p>' +
    "</div></div>";
  }

  function uploadMapHtml(u) {
    var typeOptions = UPLOAD_TYPES.map(function (t) {
      return '<label class="radio-pill' + (t === u.datasetType ? " is-active" : "") + '"><input type="radio" name="up-type" value="' + t + '" ' +
        (t === u.datasetType ? "checked" : "") + ">" + UPLOAD_TYPE_LABELS[t] + "</label>";
    }).join("");
    var sheetPicker = u.sheets && u.sheets.length > 1
      ? '<div style="display:flex;align-items:center;gap:8px;margin-top:12px"><label for="up-sheet" style="font-size:12.5px;color:var(--text-2)">Worksheet:</label>' +
        '<select class="select" id="up-sheet">' + u.sheets.map(function (s) {
          return '<option value="' + escapeHtml(s) + '"' + (s === u.sheet ? " selected" : "") + ">" + escapeHtml(s) + "</option>";
        }).join("") + "</select></div>"
      : "";
    return '<div class="card"><div class="card-body">' +
      '<div class="kv">' +
        '<div class="kv-item"><dt>File</dt><dd class="mono">' + escapeHtml(u.fileName) + "</dd></div>" +
        '<div class="kv-item"><dt>Type</dt><dd>' + escapeHtml((u.fileType || "").toUpperCase()) + "</dd></div>" +
        '<div class="kv-item"><dt>Records</dt><dd>' + fmtNumber(u.recordCount) + "</dd></div>" +
      "</div>" +
      '<div class="section-title" style="margin-top:16px">What type of dataset is this?</div>' +
      '<div class="radio-row" id="up-type-row">' + typeOptions + "</div>" +
      sheetPicker +
      '<div class="section-title" style="margin-top:18px">Column mapping <span class="hint">map external columns to RationAI fields — required fields marked *</span></div>' +
      '<div class="table-wrap"><table class="data map-table"><thead><tr><th>External column</th><th>Maps to</th></tr></thead><tbody id="up-map-body">' +
        uploadMapRows(u) +
      "</tbody></table></div>" +
      '<div style="display:flex;gap:8px;margin-top:16px">' +
        '<button class="btn btn-secondary" id="up-back-choose" type="button">Choose another file</button>' +
        '<span style="flex:1"></span>' +
        '<button class="btn btn-primary" id="up-validate" type="button">Validate &amp; preview</button>' +
      "</div>" +
    "</div></div>";
  }

  function uploadMapRows(u) {
    if (!u.mapping || !u.mapping.length) {
      return '<tr><td colspan="2">' + emptyState("table", "No columns detected", "The file could not be parsed into columns.", null) + "</td></tr>";
    }
    var fields = uploadFieldsFor(u.datasetType);
    return u.mapping.map(function (m) {
      var options = '<option value="">Ignore</option>' + fields.map(function (f) {
        var label = f.label + (f.required ? " *" : "");
        return '<option value="' + f.field + '"' + (m.internal === f.field ? " selected" : "") + ">" + escapeHtml(label) + "</option>";
      }).join("");
      return '<tr><td class="mono">' + escapeHtml(m.external) + '</td><td><select class="select up-map-select" data-col="' + escapeHtml(m.external) + '">' + options + "</select></td></tr>";
    }).join("");
  }

  function uploadFieldsFor(datasetType) {
    var sets = {
      beneficiaries: [["external_reference", true], ["state", false], ["district", false], ["block", false], ["ration_category", false], ["family_size", false], ["status", false]],
      fps_centers: [["fps_code", true], ["name", false], ["state", false], ["district", false], ["block", false], ["location", false], ["latitude", false], ["longitude", false], ["capacity", false], ["status", false]],
      ration_transactions: [["external_transaction_id", false], ["beneficiary_id", false], ["fps_center_id", false], ["transaction_date", true], ["commodity", true], ["quantity", true], ["unit", false], ["latitude", false], ["longitude", false], ["state", false], ["district", false], ["block", false], ["ration_category", false], ["family_size", false], ["status", false]],
      inventory: [["fps_center_id", false], ["commodity", true], ["current_stock", true], ["monthly_consumption", false], ["reorder_threshold", false], ["last_updated", false]],
      combined: [["external_transaction_id", false], ["beneficiary_id", false], ["fps_center_id", false], ["transaction_date", true], ["commodity", true], ["quantity", true], ["unit", false], ["latitude", false], ["longitude", false], ["external_reference", false], ["state", false], ["district", false], ["block", false], ["ration_category", false], ["family_size", false], ["name", false], ["location", false], ["capacity", false], ["status", false]]
    };
    return (sets[datasetType] || sets.ration_transactions).map(function (pair) {
      return { field: pair[0], label: pair[0].replace(/_/g, " "), required: pair[1] };
    });
  }

  function uploadPreviewHtml(u) {
    var v = u.validation || {};
    var counts = [
      ["Total records", fmtNumber(v.record_count)],
      ["Valid", fmtNumber(v.valid_records)],
      ["Invalid", fmtNumber(v.invalid_records)],
      ["Duplicates", fmtNumber(v.duplicate_records)],
      ["Warnings", fmtNumber(v.warning_count)]
    ];
    var q = v.quality || {};
    var dup = v.duplicates || {};
    return '<div class="card"><div class="card-body">' +
      (uploadAlreadyImportedHtml(v.already_imported)) +
      '<div class="kv">' +
        '<div class="kv-item"><dt>File</dt><dd class="mono">' + escapeHtml(u.fileName) + "</dd></div>" +
        '<div class="kv-item"><dt>Dataset</dt><dd>' + escapeHtml(UPLOAD_TYPE_LABELS[u.datasetType] || u.datasetType) + "</dd></div>" +
        '<div class="kv-item"><dt>Mapped columns</dt><dd>' + (u.mapping || []).filter(function (m) { return m.internal; }).length + " / " + (u.headers || []).length + "</dd></div>" +
      "</div>" +
      '<div class="section-title" style="margin-top:16px">Validation summary</div>' +
      '<div class="grid cols-5">' + counts.map(function (c) {
        return '<div class="card"><div class="card-body" style="padding:12px 14px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">' + escapeHtml(c[0]) + '</div><div style="font-size:22px;font-weight:700;margin-top:2px">' + c[1] + "</div></div></div>";
      }).join("") + "</div>" +
      (uploadQualityHtml(q)) +
      (uploadDuplicateHtml(dup)) +
      (uploadWarningsHtml(v.warning_examples)) +
      (uploadErrorsHtml(v.errors)) +
      (uploadNormalizedHtml(v)) +
      '<div class="section-title" style="margin-top:16px">Preview <span class="hint">first ' + (v.preview ? v.preview.shown : 0) + " rows</span></div>" +
      '<div class="table-wrap">' + previewTableHtml(v.preview) + "</div>" +
      '<div style="display:flex;gap:8px;margin-top:16px">' +
        '<button class="btn btn-secondary" id="up-back-map" type="button">Back to mapping</button>' +
        '<span style="flex:1"></span>' +
        (v.already_imported ? '<span class="badge warning">Already imported — no records will be written</span>' :
          (v.invalid_records ? '<span class="badge warning">' + fmtNumber(v.invalid_records) + " invalid — they will be skipped</span>" : "")) +
        (v.already_imported ? "" : '<button class="btn btn-primary" id="up-confirm" type="button">Import dataset</button>') +
      "</div>" +
    "</div></div>";
  }

  function uploadAlreadyImportedHtml(existing) {
    if (!existing) return "";
    return '<div class="error-panel info" style="margin-bottom:14px" role="status"><span class="error-icon">' + icon("info", 16) + "</span><div>" +
      "<h3>This dataset appears to have already been imported</h3>" +
      "<p>Import #" + existing.data_import_id + " (" + escapeHtml(existing.file_name) + ") " +
      "already contains " + fmtNumber(existing.imported) + " record(s) from the same file. " +
      "No new records will be written on import.</p>" +
      '<a class="btn btn-secondary" href="#/upload" style="margin-top:8px">View import history</a>' +
      "</div></div>";
  }

  function uploadQualityHtml(q) {
    if (!q || q.score == null) return "";
    var tone = q.score >= 90 ? "success" : q.score >= 70 ? "warning" : "error";
    return '<div class="section-title" style="margin-top:16px">Data quality report</div>' +
      '<div class="card" style="background:var(--pale-green)"><div class="card-body" style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">' +
      '<div style="text-align:center"><div style="font-size:30px;font-weight:800;color:var(--' + tone + ')">' + q.score + '%</div>' +
      '<div style="font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:.5px">Quality score</div></div>' +
      '<div class="kv" style="flex:1;min-width:220px">' +
        '<div class="kv-item"><dt>Valid records</dt><dd>' + fmtNumber(q.valid_pct) + '%</dd></div>' +
        '<div class="kv-item"><dt>Duplicates</dt><dd>' + fmtNumber(q.duplicate_pct) + '%</dd></div>' +
        '<div class="kv-item"><dt>Warnings</dt><dd>' + fmtNumber(q.warning_pct) + '%</dd></div>' +
      "</div>" +
      '<span class="hint" style="max-width:260px">Deterministic score: 100 minus penalties for invalid records (3×), duplicates (2×), and warnings (0.5×), as % of total.</span>' +
      "</div></div>";
  }

  function uploadDuplicateHtml(dup) {
    if (!dup || (dup.exact + dup.possible) === 0) return "";
    return '<div class="section-title" style="margin-top:16px">Duplicate classification</div>' +
      '<div class="grid cols-2">' +
      '<div class="card"><div class="card-body" style="padding:12px 14px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">Exact duplicates</div>' +
      '<div style="font-size:22px;font-weight:700;margin-top:2px">' + fmtNumber(dup.exact) + '</div><div class="hint">Same ID or identical content already seen</div></div></div>' +
      '<div class="card"><div class="card-body" style="padding:12px 14px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">Possible duplicates</div>' +
      '<div style="font-size:22px;font-weight:700;margin-top:2px">' + fmtNumber(dup.possible) + '</div><div class="hint">Same content under a different ID — review before importing</div></div></div>' +
      "</div>" +
      (dup.samples && dup.samples.length ? '<div class="table-wrap" style="margin-top:10px"><table class="data"><thead><tr><th>Row</th><th>Kind</th><th>Reason</th></tr></thead><tbody>' +
        dup.samples.map(function (s) {
          return '<tr><td class="num">' + s.row + '</td><td><span class="badge ' + (s.kind === "EXACT_DUPLICATE" ? "warning" : "error") + '">' + escapeHtml(s.kind) + "</span></td><td>" + escapeHtml(s.reason) + "</td></tr>";
        }).join("") + "</tbody></table></div>" : "");
  }

  function uploadWarningsHtml(warnings) {
    if (!warnings || !warnings.length) return "";
    return '<div class="section-title" style="margin-top:16px">Example warnings</div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Row</th><th>Warnings</th></tr></thead><tbody>' +
      warnings.map(function (w) {
        return '<tr><td class="num">' + w.row + '</td><td><span class="badge warning">' + escapeHtml(w.warnings.join(" · ")) + "</span></td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function uploadNormalizedHtml(v) {
    var rows = v.preview_normalized || [];
    if (!rows.length) return "";
    var body = "";
    rows.forEach(function (item) {
      var fields = Object.keys(item.normalized || {});
      if (!fields.length) return;
      fields.slice(0, 6).forEach(function (f) {
        var raw = item.original ? item.original[f] : "";
        var norm = item.normalized[f];
        var original = raw == null ? "" : String(raw);
        var normalized = norm == null ? "" : String(norm);
        var changed = original !== normalized ? " style=\"background:var(--pale-green)\"" : "";
        body += "<tr" + changed + "><td class=\"num\">" + item.row + "</td><td class=\"mono\">" + escapeHtml(f) +
          "</td><td>" + escapeHtml(original) + "</td><td class=\"mono\">" + escapeHtml(normalized) + "</td></tr>";
      });
    });
    if (!body) return "";
    return '<div class="section-title" style="margin-top:16px">Normalized preview <span class="hint">original values → internal format</span></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Row</th><th>Field</th><th>Original</th><th>Normalized</th></tr></thead><tbody>' +
      body + "</tbody></table></div>";
  }

  function uploadErrorsHtml(errors) {
    if (!errors || !errors.length) return "";
    return '<div class="section-title" style="margin-top:16px">Example invalid records</div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Row</th><th>Errors</th></tr></thead><tbody>' +
      errors.map(function (e) {
        return '<tr><td class="num">' + e.row + '</td><td><span class="badge error">' + escapeHtml(e.errors.join(" · ")) + "</span></td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function previewTableHtml(preview) {
    if (!preview || !preview.headers || !preview.rows.length) {
      return '<div class="empty-state"><div class="empty-icon">' + icon("table", 22) + "</div><h3>No rows to preview</h3></div>";
    }
    var header = preview.headers.map(function (h) { return "<th>" + escapeHtml(h) + "</th>"; }).join("");
    var rows = preview.rows.map(function (row) {
      return "<tr>" + preview.headers.map(function (_, i) {
        return "<td>" + escapeHtml(String(row[i] == null ? "" : row[i])) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    return '<table class="data"><thead><tr>' + header + "</tr></thead><tbody>" + rows + "</tbody></table>";
  }

  function uploadResultHtml(u) {
    var r = u.result || {};
    if (r.status === "ALREADY_IMPORTED") {
      var existing = r.existing_import || {};
      return '<div class="card"><div class="card-body">' +
        '<div class="error-panel info" role="status"><span class="error-icon">' + icon("info", 18) + "</span><div>" +
        "<h3>" + escapeHtml(r.message || "This dataset appears to have already been imported.") + "</h3>" +
        "<p>Import #" + existing.data_import_id + " already contains " + fmtNumber(existing.imported) +
        " record(s) from <strong class=\"mono\">" + escapeHtml(existing.file_name || "") + "</strong>. No duplicate records were written.</p>" +
        "</div></div>" +
        '<div style="display:flex;gap:8px;margin-top:16px">' +
          '<button class="btn btn-primary" id="up-again" type="button">Import another dataset</button>' +
          '<a class="btn btn-secondary" href="#/analysis">Run analysis</a>' +
        "</div></div></div>";
    }
    var ok = r.status === "COMPLETED";
    var partial = r.status === "PARTIAL";
    var title = ok ? "Dataset imported successfully" : partial ? "Dataset imported with errors" : "Dataset import failed";
    var q = r.quality || {};
    var counts = [
      ["Records processed", fmtNumber(r.record_count)],
      ["Imported", fmtNumber(r.imported)],
      ["Duplicates", fmtNumber(r.duplicates)],
      ["Failed", fmtNumber(r.failed)],
      ["Processing time", (r.processing_time_seconds || 0) + "s"]
    ];
    return '<div class="card"><div class="card-body">' +
      '<div class="alert-head"><div><p class="kicker">' + escapeHtml(title) + "</p>" +
      '<p style="font-size:13.5px;color:var(--text-2)">Dataset <strong class="mono">' + escapeHtml(r.dataset_name) + "</strong> · " + escapeHtml(r.file_name) + "</p></div>" +
      '<span class="priority-chip ' + (ok ? "low" : partial ? "medium" : "high") + '">' + escapeHtml(r.status) + "</span></div>" +
      '<div class="grid cols-5" style="margin-top:14px">' + counts.map(function (c) {
        return '<div class="card"><div class="card-body" style="padding:12px 14px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">' + escapeHtml(c[0]) + '</div><div style="font-size:22px;font-weight:700;margin-top:2px">' + c[1] + "</div></div></div>";
      }).join("") + "</div>" +
      (q.score != null ? '<div style="display:flex;align-items:center;gap:12px;margin-top:14px"><span class="badge ' + (q.score >= 90 ? "success" : q.score >= 70 ? "warning" : "error") + '">Quality ' + q.score + '%</span>' +
        '<span class="hint">' + fmtNumber(q.valid_pct) + '% valid · ' + fmtNumber(q.duplicate_pct) + '% duplicates · ' + fmtNumber(q.warning_pct) + '% warnings</span></div>' : "") +
      (r.error_summary ? '<div class="error-panel" style="margin-top:14px" role="alert"><span class="error-icon">' + icon("alert", 16) + "</span><div><p>" + escapeHtml(r.error_summary) + "</p></div></div>" : "") +
      '<div style="display:flex;gap:8px;margin-top:16px">' +
        '<button class="btn btn-primary" id="up-again" type="button">Import another dataset</button>' +
        '<a class="btn btn-secondary" href="#/analysis">Run analysis</a>' +
      "</div>" +
    "</div></div>";
  }

  function bindUploadControls() {
    var dz = $id("dropzone");
    var fileInput = $id("upload-file");
    if (dz && fileInput) {
      dz.addEventListener("click", function () { fileInput.click(); });
      dz.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); fileInput.click(); } });
      dz.addEventListener("dragover", function (ev) { ev.preventDefault(); dz.classList.add("is-over"); });
      dz.addEventListener("dragleave", function () { dz.classList.remove("is-over"); });
      dz.addEventListener("drop", function (ev) {
        ev.preventDefault(); dz.classList.remove("is-over");
        if (ev.dataTransfer.files && ev.dataTransfer.files.length) uploadFile(ev.dataTransfer.files[0]);
      });
      fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files.length) uploadFile(fileInput.files[0]);
        fileInput.value = "";
      });
    }
    var browse = $id("upload-browse");
    if (browse && fileInput) browse.addEventListener("click", function (ev) { ev.stopPropagation(); fileInput.click(); });

    var validateBtn = $id("up-validate");
    if (validateBtn) validateBtn.addEventListener("click", runUploadValidate);
    var confirmBtn = $id("up-confirm");
    if (confirmBtn) confirmBtn.addEventListener("click", runUploadConfirm);
    var backMap = $id("up-back-map");
    if (backMap) backMap.addEventListener("click", function () { state.upload.step = "map"; state.upload.validation = null; renderRoute(); });
    var backChoose = $id("up-back-choose");
    if (backChoose) backChoose.addEventListener("click", resetUploadState);
    var again = $id("up-again");
    if (again) again.addEventListener("click", resetUploadState);
    var resetError = $id("upload-reset-error");
    if (resetError) resetError.addEventListener("click", function () { state.upload.error = null; renderRoute(); });

    var typeRow = $id("up-type-row");
    if (typeRow) typeRow.addEventListener("change", function (ev) {
      if (ev.target.name === "up-type") state.upload.datasetType = ev.target.value;
    });
    var mapBody = $id("up-map-body");
    if (mapBody) mapBody.addEventListener("change", function (ev) {
      var sel = ev.target.closest(".up-map-select");
      if (sel) {
        state.upload.mapping.forEach(function (m) {
          if (m.external === sel.getAttribute("data-col")) m.internal = sel.value || null;
        });
      }
    });
    var sheetSel = $id("up-sheet");
    if (sheetSel) sheetSel.addEventListener("change", function () { state.upload.sheet = sheetSel.value; });
  }

  function uploadFile(file) {
    var u = state.upload;
    u.busy = true; u.error = null;
    renderRoute();
    var timer = setTimeout(function () {
      u.busy = false;
      u.error = { title: "Upload timed out", detail: "The file could not be uploaded within 60 seconds." };
      renderRoute();
    }, 60000);
    fetch(API_BASE + "/api/upload", {
      method: "POST",
      headers: { "X-Filename": file.name, "Content-Type": file.type || "application/octet-stream" },
      body: file
    }).then(function (response) {
      return response.json().then(function (payload) {
        if (!response.ok) throw { message: (payload && payload.error) || "HTTP " + response.status };
        return payload;
      });
    }).then(function (payload) {
      clearTimeout(timer);
      u.busy = false;
      u.token = payload.token;
      u.fileName = payload.file_name;
      u.fileType = payload.file_type;
      u.datasetType = payload.dataset_type;
      u.headers = payload.detected_columns || [];
      u.sheets = payload.sheets || [];
      u.sheet = null;
      u.mapping = payload.mapping || [];
      u.recordCount = payload.record_count || 0;
      u.step = "map";
      renderRoute();
      toast("File detected: " + payload.record_count + " record(s)", "success");
    }).catch(function (err) {
      clearTimeout(timer);
      u.busy = false;
      u.error = { title: "Upload failed", detail: (err && err.message) || "The file could not be processed." };
      renderRoute();
    });
  }

  function runUploadValidate() {
    var u = state.upload;
    if (u.busy || !u.token) return;
    u.busy = true; u.error = null;
    renderRoute();
    var mapping = {};
    (u.mapping || []).forEach(function (m) { if (m.internal) mapping[m.external] = m.internal; });
    fetchJson(API_BASE + "/api/uploads/" + encodeURIComponent(u.token) + "/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_type: u.datasetType, mapping: mapping, sheet: u.sheet })
    }, 120000).then(function (payload) {
      u.busy = false;
      u.mapping = payload.mapped_columns || u.mapping;
      u.validation = payload;
      u.step = "preview";
      renderRoute();
    }).catch(function (err) {
      u.busy = false;
      u.error = { title: "Validation failed", detail: err.serverMessage || err.message || "The dataset could not be validated." };
      renderRoute();
    });
  }

  function runUploadConfirm() {
    var u = state.upload;
    if (u.busy || !u.token) return;
    u.busy = true; u.error = null;
    renderRoute();
    fetchJson(API_BASE + "/api/uploads/" + encodeURIComponent(u.token) + "/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    }, 120000)    .then(function (payload) {
      u.busy = false;
      u.result = payload;
      u.step = "result";
      loadImportHistory();
      invalidateAnalytics();   // dashboard must reflect the new records
      renderRoute();
      if (payload.status === "ALREADY_IMPORTED") {
        toast("Dataset already imported — no records written", "info");
      } else {
        toast("Import " + payload.status.toLowerCase() + ": " + payload.imported + " record(s)", payload.status === "COMPLETED" ? "success" : "error");
      }
    }).catch(function (err) {
      u.busy = false;
      u.error = { title: "Import failed", detail: err.serverMessage || err.message || "The dataset could not be imported." };
      renderRoute();
    });
  }

  function resetUploadState() {
    state.upload = {
      step: "choose", token: null, fileName: null, fileType: null,
      datasetType: "ration_transactions", headers: [], sheets: [], sheet: null,
      mapping: [], recordCount: 0, preview: null, validation: null,
      result: null, busy: false, error: null
    };
    renderRoute();
  }

  function loadImportHistory() {
    var box = $id("import-history");
    if (!box) return;
    fetchJson(API_BASE + "/api/imports", {}, 15000).then(function (rows) {
      if (!Array.isArray(rows) || !rows.length) {
        box.innerHTML = emptyState("table", "No imports yet", "Imported datasets will appear here with their status, counts, and provenance.", null);
        return;
      }
      var header = ["ID", "Dataset", "Source", "Type", "Records", "Imported", "Duplicates", "Failed", "Status", "Completed"].map(function (h) { return "<th>" + h + "</th>"; }).join("");
      var body = rows.map(function (r) {
        var statusCls = r.status === "COMPLETED" ? "success" : r.status === "FAILED" ? "error" : "warning";
        return "<tr>" +
          '<td class="mono">' + r.id + "</td>" +
          '<td class="mono">' + escapeHtml(r.dataset_name) + "</td>" +
          "<td>" + escapeHtml(r.source_name || "") + "</td>" +
          "<td>" + escapeHtml((r.file_type || "").toUpperCase()) + "</td>" +
          '<td class="num">' + fmtNumber(r.record_count) + "</td>" +
          '<td class="num">' + fmtNumber(r.successful_records) + "</td>" +
          '<td class="num">' + fmtNumber(r.duplicate_records) + "</td>" +
          '<td class="num">' + fmtNumber(r.failed_records) + "</td>" +
          '<td><span class="badge ' + statusCls + '"><span class="dot"></span>' + escapeHtml(r.status) + "</span></td>" +
          "<td>" + escapeHtml((r.completed_at || "").slice(0, 16).replace("T", " ")) + "</td></tr>";
      }).join("");
      box.innerHTML = '<table class="data"><thead><tr>' + header + "</tr></thead><tbody>" + body + "</tbody></table>";
    }).catch(function () {
      box.innerHTML = emptyState("alert", "Could not load import history", "Check that the backend is running.", null);
    });
  }

  /* ------------------------------------------------------------------ *
   *  Beneficiaries
   * ------------------------------------------------------------------ */
  function renderBeneficiaries() {
    var v = $view();
    var a = state.analytics;
    var involved = anomalyBeneficiaries();

    v.innerHTML = viewHead("Beneficiaries", "Beneficiary records from the database. Names and Aadhaar numbers are intentionally excluded — IDs only. Search, filters, sorting, and pagination run on the server.") +
      '<section class="section"><div class="grid kpi-grid" id="ben-kpis">' + skeleton() + skeleton() + "</div></section>" +
      '<section class="section"><div class="section-title">Beneficiary registry <span class="hint" id="ben-total">…</span></div>' +
      '<div class="card"><div class="card-body flush">' +
        '<div class="toolbar" style="padding:14px 16px 0;margin-bottom:0;flex-wrap:wrap;gap:8px">' +
          '<input class="input" id="ben-search" type="search" placeholder="Search beneficiary ID…" value="' + escapeHtml(state.beneficiaryQuery) + '" style="width:200px" aria-label="Search beneficiaries">' +
          '<select class="select" id="ben-state" aria-label="State"></select>' +
          '<select class="select" id="ben-district" aria-label="District"></select>' +
          '<select class="select" id="ben-category" aria-label="Ration category"></select>' +
          '<select class="select" id="ben-status" aria-label="Status"></select>' +
          '<span style="margin-left:auto"></span>' +
          '<button class="btn btn-secondary btn-sm" id="ben-export" type="button">' + icon("download", 15) + " Export CSV</button>" +
        "</div>" +
        '<div style="overflow-x:auto;margin-top:12px" id="ben-table">' + skeleton() + "</div>" +
        '<div class="pagination" id="ben-pagination"></div>' +
      "</div></div></section>" +
      '<section class="section"><div class="section-title">FPS centers <span class="hint">from the database</span></div>' +
      '<div class="card"><div class="card-body flush" id="ben-centers">' + skeleton() + "</div></div></section>";

    var load = function () {
      var params = {
        q: state.beneficiaryQuery || undefined,
        state: state.beneficiaryState === "all" ? undefined : state.beneficiaryState,
        district: state.beneficiaryDistrict === "all" ? undefined : state.beneficiaryDistrict,
        category: state.beneficiaryCategory === "all" ? undefined : state.beneficiaryCategory,
        status: state.beneficiaryStatus === "all" ? undefined : state.beneficiaryStatus,
        page: state.beneficiaryPage,
        per_page: 10,
        sort: "transaction_count"
      };
      Promise.all([
        fetchAnalytics("beneficiaries", params),
        fetchAnalytics("fps", {})
      ]).then(function (results) {
        a.beneficiaries = results[0];
        a.fps = results[1];
        a.error = null;
        renderBeneficiaries();
      }).catch(function (err) {
        a.error = err.serverMessage || err.message || "Could not load beneficiaries.";
        renderBeneficiaries();
      });
    };
    if (a.error) {
      $id("ben-table").innerHTML = analyticsErrorPanel(a.error);
      var retry = $id("analytics-retry");
      if (retry) retry.addEventListener("click", function () { a.error = null; invalidateAnalytics(); renderBeneficiaries(); });
      return;
    }
    if (!a.beneficiaries || !a.fps) { load(); return; }

    var data = a.beneficiaries;
    var filters = data.filters || {};
    $id("ben-kpis").innerHTML =
      '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Total beneficiaries</span><span class="kpi-icon">' + icon("users", 17) + "</span></div><div class=\"kpi-value\">" + fmtNumber(data.total) + "</div><div class=\"kpi-sub\">in the database</div></div>" +
      '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Active</span><span class="kpi-icon">' + icon("activity", 17) + "</span></div><div class=\"kpi-value\">" + fmtNumber(data.active) + "</div><div class=\"kpi-sub\">status = ACTIVE</div></div>" +
      '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Districts</span><span class="kpi-icon">' + icon("layers", 17) + "</span></div><div class=\"kpi-value\">" + (filters.districts || []).length + "</div><div class=\"kpi-sub\">with records</div></div>" +
      '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Matching filters</span><span class="kpi-icon">' + icon("search", 17) + "</span></div><div class=\"kpi-value\">" + fmtNumber(data.total) + "</div><div class=\"kpi-sub\">current query</div></div>";

    $id("ben-total").textContent = data.total + " records (page " + data.page + " of " + Math.max(1, Math.ceil(data.total / data.per_page)) + ")";

    var sel = function (id, options, current, label) {
      var el = $id(id);
      if (!el) return;
      el.innerHTML = '<option value="all">' + label + "</option>" + options.map(function (o) {
        return '<option value="' + escapeHtml(o) + '"' + (o === current ? " selected" : "") + ">" + escapeHtml(o) + "</option>";
      }).join("");
      el.value = current;
    };
    sel("ben-state", filters.states || [], state.beneficiaryState, "All states");
    sel("ben-district", filters.districts || [], state.beneficiaryDistrict, "All districts");
    sel("ben-category", filters.categories || [], state.beneficiaryCategory, "All categories");
    sel("ben-status", filters.statuses || [], state.beneficiaryStatus, "All statuses");
    ["ben-search", "ben-state", "ben-district", "ben-category", "ben-status"].forEach(function (id) {
      var el = $id(id);
      if (el) el.addEventListener(id === "ben-search" ? "input" : "change", function () {
        if (id === "ben-search") state.beneficiaryQuery = el.value;
        if (id === "ben-state") state.beneficiaryState = el.value;
        if (id === "ben-district") state.beneficiaryDistrict = el.value;
        if (id === "ben-category") state.beneficiaryCategory = el.value;
        if (id === "ben-status") state.beneficiaryStatus = el.value;
        state.beneficiaryPage = 1;
        a.beneficiaries = null;
        renderBeneficiaries();
      });
    });

    var header = ["Beneficiary ID", "District", "Category", "Family", "Transactions", "Total qty", "Last distribution", "Anomaly", ""]
      .map(function (h) { return "<th>" + h + "</th>"; }).join("");
    var rows = (data.rows || []).map(function (b) {
      var inAnom = involved[b.external_reference];
      return '<tr class="row-click" data-ben="' + escapeHtml(b.external_reference) + '">' +
        '<td class="mono" style="font-weight:700;color:var(--forest)">' + escapeHtml(b.external_reference) + "</td>" +
        "<td>" + escapeHtml(b.district || "—") + "</td>" +
        "<td>" + escapeHtml(b.ration_category || "—") + "</td>" +
        '<td class="num">' + (b.family_size || "—") + "</td>" +
        '<td class="num">' + b.transaction_count + "</td>" +
        '<td class="num">' + fmtKg(b.total_quantity || 0) + "</td>" +
        "<td>" + fmtDate(b.last_transaction) + "</td>" +
        '<td>' + (inAnom ? '<span class="badge warning"><span class="dot"></span>In anomaly</span>' : '<span class="badge neutral">Clear</span>') + "</td>" +
        '<td><button class="btn btn-ghost btn-sm" type="button" data-view-ben="' + escapeHtml(b.external_reference) + '" aria-label="View ' + escapeHtml(b.external_reference) + '">' + icon("eye", 15) + " View</button></td></tr>";
    }).join("");
    $id("ben-table").innerHTML = data.rows.length
      ? '<table class="data"><thead><tr>' + header + "</tr></thead><tbody>" + rows + "</tbody></table>"
      : emptyState("search", "No matching beneficiaries", "Try a different search or filter.", null);
    $id("ben-table").querySelectorAll("button[data-view-ben]").forEach(function (b) {
      b.addEventListener("click", function () { openBeneficiary(b.getAttribute("data-view-ben")); });
    });

    var box = $id("ben-pagination");
    var pages = Math.max(1, Math.ceil(data.total / data.per_page));
    if (pages <= 1) { box.innerHTML = ""; } else {
      box.innerHTML = '<span>' + data.total + " records</span><span style=\"flex:1\"></span>" +
        Array.from({ length: Math.min(pages, 8) }, function (_, i) {
          var pg = i + 1;
          return '<button type="button" class="' + (pg === state.beneficiaryPage ? "is-active" : "") + '" data-pg="' + pg + '">' + pg + "</button>";
        }).join("");
      box.querySelectorAll("button[data-pg]").forEach(function (b) {
        b.addEventListener("click", function () {
          state.beneficiaryPage = Number(b.getAttribute("data-pg"));
          a.beneficiaries = null;
          renderBeneficiaries();
        });
      });
    }

    var centers = a.fps.centers || [];
    $id("ben-centers").innerHTML = centers.length
      ? '<div class="table-wrap"><table class="data"><thead><tr><th>FPS code</th><th>Name</th><th>District</th><th>Status</th><th>Transactions</th><th>Quantity</th><th>Inventory items</th></tr></thead><tbody>' +
        centers.map(function (c) {
          return '<tr><td class="mono" style="font-weight:700">' + escapeHtml(c.fps_code) + "</td><td>" + escapeHtml(c.name || "—") + "</td>" +
            "<td>" + escapeHtml(c.district || "—") + "</td>" +
            '<td><span class="badge ' + (c.status === "ACTIVE" ? "success" : "neutral") + '"><span class="dot"></span>' + escapeHtml(c.status || "—") + "</span></td>" +
            '<td class="num">' + c.transaction_count + '</td><td class="num">' + fmtKg(c.quantity_distributed) + '</td><td class="num">' + c.inventory_count + "</td></tr>";
        }).join("") + "</tbody></table></div>"
      : emptyState("warehouse", "No FPS centers", "No distribution centers have been imported.", null);

    var exportBtn = $id("ben-export");
    if (exportBtn) exportBtn.addEventListener("click", function () {
      var rows = [["beneficiary_id", "state", "district", "ration_category", "family_size", "status", "transaction_count", "total_quantity_kg", "first_transaction", "last_transaction"]];
      (data.rows || []).forEach(function (b) {
        rows.push([b.external_reference, b.state || "", b.district || "", b.ration_category || "", b.family_size || "", b.status || "", b.transaction_count, b.total_quantity || 0, b.first_transaction || "", b.last_transaction || ""]);
      });
      download("rationai_beneficiaries.csv", toCsv(rows), "text/csv");
      toast("Current page exported to CSV", "success");
    });
  }

  function openBeneficiary(id) {
    var backdrop = document.createElement("div");
    backdrop.className = "drawer-backdrop";
    var drawer = document.createElement("div");
    drawer.className = "drawer";
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("aria-label", "Beneficiary " + id);
    drawer.innerHTML =
      '<div class="drawer-head"><div><h3>' + escapeHtml(id) + "</h3><p>Beneficiary record from the database</p></div>" +
        '<button class="icon-close" type="button" aria-label="Close">' + icon("close", 18) + "</button></div>" +
      '<div class="drawer-body" id="drawer-body">' + skeleton() + "</div>" +
      '<div class="drawer-foot"><button class="btn btn-secondary btn-sm" type="button" id="drawer-close">Close</button>' +
        '<button class="btn btn-primary btn-sm" type="button" id="drawer-alert">View alert context</button></div>';
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);
    var involved = anomalyBeneficiaries();
    function close() { backdrop.remove(); drawer.remove(); state.beneficiaryId = null; }
    backdrop.addEventListener("click", close);
    drawer.querySelector(".icon-close").addEventListener("click", close);
    drawer.querySelector("#drawer-close").addEventListener("click", close);
    drawer.querySelector("#drawer-alert").addEventListener("click", function () {
      close();
      location.hash = involved[id] ? "#/alerts" : "#/analysis";
    });

    fetchAnalytics("beneficiaries/" + encodeURIComponent(id), {}).then(function (payload) {
      var body = $id("drawer-body");
      if (!body) return;
      var b = payload.beneficiary || {};
      var txs = payload.transactions || [];
      var totalQty = txs.reduce(function (s, t) { return s + (t.quantity || 0); }, 0);
      var types = {};
      txs.forEach(function (t) { if (t.ration_type) types[t.ration_type] = true; });
      var rows = txs.map(function (t) {
        return '<tr><td class="mono">' + escapeHtml(t.transaction_id) + '</td><td class="mono">' + escapeHtml(t.beneficiary_id || "—") + "</td><td>" +
          escapeHtml(t.timestamp) + '</td><td class="num">' + escapeHtml(String(t.quantity)) + '</td><td>' + escapeHtml(t.ration_type) + "</td></tr>";
      }).join("");
      body.innerHTML =
        '<div class="kv">' +
          '<div class="kv-item"><dt>District</dt><dd>' + escapeHtml(b.district || "—") + "</dd></div>" +
          '<div class="kv-item"><dt>State</dt><dd>' + escapeHtml(b.state || "—") + "</dd></div>" +
          '<div class="kv-item"><dt>Ration category</dt><dd>' + escapeHtml(b.ration_category || "—") + "</dd></div>" +
          '<div class="kv-item"><dt>Family size</dt><dd>' + (b.family_size || "—") + "</dd></div>" +
          '<div class="kv-item"><dt>Status</dt><dd>' + escapeHtml(b.status || "—") + "</dd></div>" +
          '<div class="kv-item"><dt>Transactions</dt><dd>' + txs.length + "</dd></div>" +
          '<div class="kv-item"><dt>Total quantity</dt><dd>' + fmtKg(totalQty) + "</dd></div>" +
          '<div class="kv-item"><dt>Ration types</dt><dd>' + Object.keys(types).join(", ") + "</dd></div>" +
        "</div>" +
        '<div class="section-title" style="margin-top:22px">Status</div>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
          '<span class="badge ' + (b.status === "ACTIVE" ? "success" : "neutral") + '"><span class="dot"></span>' + escapeHtml(b.status || "Active") + "</span>" +
          (involved[id] ? '<span class="badge warning"><span class="dot"></span>Involved in verified anomaly</span>' : '<span class="badge neutral">Not in any anomaly</span>') +
        "</div>" +
        '<div class="section-title" style="margin-top:22px">Transaction history</div>' +
        '<div class="table-wrap"><table class="data"><thead><tr><th>Transaction ID</th><th>Beneficiary</th><th>Timestamp</th><th>Quantity</th><th>Commodity</th></tr></thead><tbody>' +
        (rows || '<tr><td colspan="5">No transactions</td></tr>') + "</tbody></table></div>";
    }).catch(function () {
      var body = $id("drawer-body");
      if (body) body.innerHTML = emptyState("alert", "Could not load beneficiary", "The beneficiary detail could not be fetched.", null);
    });
    drawer.querySelector(".icon-close").focus();
  }

  /* ------------------------------------------------------------------ *
   *  Ration Distribution
   * ------------------------------------------------------------------ */
  function renderDistribution() {
    var v = $view();
    var a = state.analytics;
    var involved = new Set();
    if (state.result) {
      state.result.anomalies.forEach(function (x) { (x.transaction_ids || []).forEach(function (i) { involved.add(i); }); });
    }

    v.innerHTML = viewHead("Ration Distribution", "All distribution records from the database, in chronological order (server-side pagination). Status reflects record validity — not enforcement.") +
      '<div class="filter-row" id="dist-filters" style="margin-bottom:14px">' +
        '<button class="pill is-active" data-txs="all" type="button">All</button>' +
        '<button class="pill" data-txs="COMPLETED" type="button">Completed</button>' +
        '<button class="pill" data-txs="FAILED" type="button">Failed</button>' +
        '<button class="pill" data-txs="PENDING" type="button">Pending</button>' +
        '<span style="flex:1"></span>' +
        '<button class="btn btn-ghost btn-sm" id="dist-refresh" type="button">' + icon("arrow", 15) + " Refresh</button>" +
      "</div>" +
      '<section class="section"><div class="grid cols-4" id="dist-kpis">' + skeleton() + skeleton() + "</div></section>" +
      '<section class="section"><div class="section-title">Distribution records <span class="hint" id="dist-count">…</span></div>' +
        '<div class="card"><div class="card-body flush"><div class="table-wrap" id="dist-table">' + skeleton() + "</div>" +
        '<div class="pagination" id="dist-pagination"></div></div></div></section>';

    var load = function () {
      var params = Object.assign({}, analyticsRangeParams(), { per_page: 25, page: a.txPage });
      if (a.txStatus !== "all") params.status = a.txStatus;
      Promise.all([
        fetchAnalytics("distribution", Object.assign({ granularity: "day" }, analyticsRangeParams())),
        fetchAnalytics("transactions", params)
      ]).then(function (results) {
        a.distribution = results[0];
        a.tx = results[1];
        a.error = null;
        renderDistribution();
      }).catch(function (err) {
        a.error = err.serverMessage || err.message || "Could not load distribution data.";
        renderDistribution();
      });
    };

    if (a.error) {
      v.querySelector(".section").innerHTML = analyticsErrorPanel(a.error);
      var retry = $id("analytics-retry");
      if (retry) retry.addEventListener("click", function () { a.error = null; invalidateAnalytics(); renderDistribution(); });
      return;
    }
    if (!a.distribution || !a.tx) { load(); return; }

    var d = a.distribution;
    var txPage = a.tx;
    var byStatus = {};
    (d.by_status || []).forEach(function (s) { byStatus[s.status] = s.count; });
    var completed = byStatus.COMPLETED || 0;
    var failed = byStatus.FAILED || 0;
    var counts = [
      { label: "Total records", value: txPage.total, sub: "in selected range", icon: "truck" },
      { label: "Quantity distributed", value: d.total_quantity, sub: "Sum of quantities", icon: "package", fmt: fmtKg },
      { label: "Completed", value: completed, sub: "Recorded without failure", icon: "check" },
      { label: "Failed", value: failed, sub: "Non-completed records", icon: "alert" }
    ];
    $id("dist-kpis").innerHTML = counts.map(function (k) {
      return '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">' + escapeHtml(k.label) + '</span><span class="kpi-icon">' + icon(k.icon, 17) + "</span></div>" +
        '<div class="kpi-value">' + (k.fmt || fmtNumber)(k.value) + '</div><div class="kpi-sub">' + escapeHtml(k.sub) + "</div></div>";
    }).join("");

    var header = ["Transaction ID", "Beneficiary", "Timestamp", "Location", "Ration type", "Quantity", "Status"].map(function (h) { return "<th>" + h + "</th>"; }).join("");
    var rows = (txPage.rows || []).map(function (t) {
      var flagged = involved.has(t.transaction_id);
      return '<tr' + (flagged ? ' style="background:#FFFBEB"' : "") + ">" +
        '<td class="mono" style="font-weight:600">' + escapeHtml(t.transaction_id) + "</td>" +
        '<td class="mono">' + escapeHtml(t.beneficiary_id || "—") + "</td>" +
        "<td>" + escapeHtml(t.timestamp) + "</td>" +
        '<td class="mono">' + escapeHtml(t.latitude != null ? String(t.latitude) : "—") + ", " + escapeHtml(t.longitude != null ? String(t.longitude) : "—") + "</td>" +
        "<td>" + escapeHtml(t.ration_type) + "</td>" +
        '<td class="num">' + escapeHtml(String(t.quantity)) + " kg</td>" +
        "<td>" + (flagged ? '<span class="badge warning"><span class="dot"></span>In anomaly</span>' : '<span class="badge success"><span class="dot"></span>Recorded</span>') + "</td></tr>";
    }).join("");
    $id("dist-count").textContent = txPage.total + " records (page " + txPage.page + " of " + Math.max(1, Math.ceil(txPage.total / txPage.per_page)) + ")";
    $id("dist-table").innerHTML = txPage.total
      ? '<table class="data"><thead><tr>' + header + "</tr></thead><tbody>" + rows + "</tbody></table>"
      : emptyState("truck", "No distribution records", "No transactions match the current filters and range.", null);

    var box = $id("dist-pagination");
    var pages = Math.max(1, Math.ceil(txPage.total / txPage.per_page));
    if (pages <= 1) { box.innerHTML = ""; } else {
      box.innerHTML = '<span>' + txPage.total + " records</span><span style=\"flex:1\"></span>" +
        Array.from({ length: Math.min(pages, 8) }, function (_, i) {
          var pg = i + 1;
          return '<button type="button" class="' + (pg === a.txPage ? "is-active" : "") + '" data-pg="' + pg + '">' + pg + "</button>";
        }).join("");
      box.querySelectorAll("button[data-pg]").forEach(function (b) {
        b.addEventListener("click", function () {
          a.txPage = Number(b.getAttribute("data-pg"));
          a.tx = null;
          renderDistribution();
        });
      });
    }

    $id("dist-filters").querySelectorAll(".pill[data-txs]").forEach(function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-txs") === a.txStatus);
      b.addEventListener("click", function () {
        a.txStatus = b.getAttribute("data-txs");
        a.txPage = 1;
        a.tx = null;
        renderDistribution();
      });
    });
    var refresh = $id("dist-refresh");
    if (refresh) refresh.addEventListener("click", function () { invalidateAnalytics(); renderDistribution(); });
  }

  /* ------------------------------------------------------------------ *
   *  Inventory
   * ------------------------------------------------------------------ */
  function renderInventory() {
    var v = $view();
    var a = state.analytics;
    v.innerHTML = viewHead("Inventory", "Stock health from the database. Risk status is computed by the backend: days remaining = current stock × 30 ÷ monthly consumption — critical below 15 days, warning below 30.") +
      '<section class="section" id="inv-body">' + skeleton() + "</section>";

    var load = function () {
      fetchAnalytics("inventory", {}).then(function (payload) {
        a.inventory = payload;
        a.error = null;
        renderInventory();
      }).catch(function (err) {
        a.error = err.serverMessage || err.message || "Could not load inventory data.";
        renderInventory();
      });
    };
    if (a.error) {
      $id("inv-body").innerHTML = analyticsErrorPanel(a.error);
      var retry = $id("analytics-retry");
      if (retry) retry.addEventListener("click", function () { a.error = null; invalidateAnalytics(); renderInventory(); });
      return;
    }
    if (!a.inventory) { load(); return; }

    var inv = a.inventory;
    var body = $id("inv-body");
    if (!inv.items || !inv.items.length) {
      body.innerHTML = analyticsEmptyPanel("warehouse", "No inventory records in the database",
        "No stock levels have been imported yet. Upload an inventory dataset (CSV/XLSX/JSON) to populate stock health, consumption, and reorder analytics.");
      return;
    }

    var tone = { HEALTHY: "success", WARNING: "warning", CRITICAL: "error", UNKNOWN: "neutral" };
    var cards = inv.by_commodity.map(function (c) {
      var pct = c.days_remaining != null
        ? Math.min(100, Math.round(c.days_remaining / 30 * 100))
        : null;
      return '<div class="card hoverable"><div class="card-body">' +
        '<div style="display:flex;align-items:center;gap:10px"><h3 style="font-weight:700;font-size:15px">' + escapeHtml(c.commodity) + "</h3>" +
        '<span class="badge ' + tone[c.status] + '"><span class="dot"></span>' + escapeHtml(c.status) + "</span></div>" +
        '<div class="kv" style="margin-top:12px">' +
          '<div class="kv-item"><dt>Current stock</dt><dd>' + fmtKg(c.current_stock) + "</dd></div>" +
          '<div class="kv-item"><dt>Monthly consumption</dt><dd>' + fmtKg(c.monthly_consumption || 0) + "</dd></div>" +
          '<div class="kv-item"><dt>Reorder threshold</dt><dd>' + fmtKg(c.reorder_threshold != null ? c.reorder_threshold : 0) + "</dd></div>" +
          '<div class="kv-item"><dt>Days remaining</dt><dd>' + (c.days_remaining != null ? c.days_remaining + " days" : "—") + "</dd></div>" +
          '<div class="kv-item"><dt>Centers</dt><dd>' + c.center_count + "</dd></div>" +
        "</div>" +
        (pct != null ? '<div class="stock-bar" role="img" aria-label="' + pct + '% of 30-day buffer"><div style="width:' + pct + '%;background:' + (c.status === "CRITICAL" ? "var(--error)" : c.status === "WARNING" ? "var(--warning)" : "var(--emerald)") + '"></div></div>' : "") +
      "</div></div>";
    }).join("");

    var lowHtml = inv.low_stock_items && inv.low_stock_items.length
      ? '<div class="table-wrap"><table class="data"><thead><tr><th>FPS</th><th>Commodity</th><th>Current stock</th><th>Reorder threshold</th></tr></thead><tbody>' +
        inv.low_stock_items.map(function (it) {
          return '<tr><td class="mono">' + escapeHtml(it.fps_code) + '</td><td>' + escapeHtml(it.commodity) + "</td>" +
            '<td class="num">' + fmtKg(it.current_stock) + '</td><td class="num">' + fmtKg(it.reorder_threshold) + "</td></tr>";
        }).join("") + "</tbody></table></div>"
      : '<div class="card"><div class="card-body">' + emptyState("check", "No low-stock items", "No inventory is below its reorder threshold.", null) + "</div></div>";

    body.innerHTML =
      '<div class="grid kpi-grid" style="margin-bottom:16px">' +
        '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Total stock</span><span class="kpi-icon">' + icon("warehouse", 17) + "</span></div><div class=\"kpi-value\">" + fmtKg(inv.total_stock_kg) + "</div><div class=\"kpi-sub\">across " + inv.items.length + " record(s)</div></div>" +
        '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Commodities</span><span class="kpi-icon">' + icon("layers", 17) + "</span></div><div class=\"kpi-value\">" + inv.by_commodity.length + "</div><div class=\"kpi-sub\">with stock records</div></div>" +
        '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">Low stock</span><span class="kpi-icon">' + icon("alert", 17) + "</span></div><div class=\"kpi-value\">" + inv.low_stock_items.length + "</div><div class=\"kpi-sub\">below reorder threshold</div></div>" +
        '<div class="card kpi"><div class="kpi-top"><span class="kpi-label">At risk</span><span class="kpi-icon">' + icon("activity", 17) + "</span></div><div class=\"kpi-value\">" + inv.critical_commodities.length + "</div><div class=\"kpi-sub\">warning or critical</div></div>" +
      "</div>" +
      '<div class="grid cols-2">' + cards + "</div>" +
      '<div class="section-title" style="margin-top:20px">Low-stock items <span class="hint">current stock &lt; reorder threshold</span></div>' + lowHtml;
  }

  /* ------------------------------------------------------------------ *
   *  Analytics
   * ------------------------------------------------------------------ */
  function renderAnalytics() {
    var v = $view();
    var a = state.analytics;
    v.innerHTML = viewHead("Analytics", "Visualizations aggregated by the backend from the database. Trend buckets, commodity totals, and district rolls are computed in SQL — the frontend only renders them.") +
      '<div class="filter-row" id="range-pills" style="margin-bottom:14px">' + rangePillsHtml() + "</div>" +
      '<section class="section"><div class="section-title">Ration distribution trend <span class="hint">toggle datasets · hover for values</span></div>' +
        '<div class="card"><div class="card-body">' +
          '<div class="toolbar" style="margin-bottom:6px">' +
            '<div class="segmented" role="group" aria-label="Granularity">' +
              '<button type="button" data-mode="day">Daily</button><button type="button" data-mode="week">Weekly</button><button type="button" data-mode="month">Monthly</button>' +
            "</div>" +
            '<span style="flex:1"></span><div class="chart-legend" id="trend-legend"></div>' +
          "</div>" +
          '<div id="analytics-trend">' + skeleton() + "</div>" +
        "</div></div></section>" +
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>Quantity by commodity</h3><p class="card-sub">Horizontal bars — total kg</p></div></div><div class="card-body"><div class="chart-wrap" id="analytics-bars"></div></div></div>' +
        '<div class="card"><div class="card-head"><div><h3>Geographic distribution</h3><p class="card-sub">Transaction volume by coordinate band (illustrative heatmap, not a map)</p></div></div><div class="card-body" id="analytics-geo"></div></div>' +
      "</div></section>" +
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>Distribution by district</h3><p class="card-sub">Quantity + record count</p></div></div><div class="card-body" id="analytics-districts"></div></div>' +
        '<div class="card"><div class="card-head"><div><h3>Distribution by FPS center</h3><p class="card-sub">Quantity + record count</p></div></div><div class="card-body" id="analytics-centers"></div></div>' +
      "</div></section>";
    bindRangeControls();

    var mode = a.granularity || "day";
    v.querySelectorAll(".segmented button").forEach(function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-mode") === mode);
      b.addEventListener("click", function () {
        a.granularity = b.getAttribute("data-mode");
        a.distribution = null;
        renderAnalytics();
      });
    });

    var load = function () {
      Promise.all([
        fetchAnalytics("distribution", Object.assign({ granularity: a.granularity }, analyticsRangeParams())),
        fetchAnalytics("transactions", Object.assign({ per_page: 200 }, analyticsRangeParams()))
      ]).then(function (results) {
        a.distribution = results[0];
        a.tx = results[1];
        a.error = null;
        renderAnalytics();
      }).catch(function (err) {
        a.error = err.serverMessage || err.message || "Could not load analytics data.";
        renderAnalytics();
      });
    };
    if (a.error) {
      $id("analytics-trend").innerHTML = analyticsErrorPanel(a.error);
      var retry = $id("analytics-retry");
      if (retry) retry.addEventListener("click", function () { a.error = null; invalidateAnalytics(); renderAnalytics(); });
      return;
    }
    if (!a.distribution) { load(); return; }

    var d = a.distribution;
    renderTrendPayload($id("analytics-trend"), d.trend);
    renderMixPairs($id("analytics-bars"), d.by_commodity);
    renderGeo($id("analytics-geo"), (a.tx && a.tx.rows) || []);
    $id("analytics-districts").innerHTML = rollTableHtml(d.by_district, "district", "Distribution by district");
    $id("analytics-centers").innerHTML = rollTableHtml(d.by_center, "fps_code", "Distribution by FPS center");
  }

  function rollTableHtml(rows, labelKey, title) {
    if (!rows || !rows.length) return emptyState("table", "No data", "No records in this range.", null);
    var max = Math.max.apply(null, rows.map(function (r) { return r.quantity; }));
    return '<div class="roll-list">' + rows.slice(0, 8).map(function (r) {
      var pct = max ? Math.round(r.quantity / max * 100) : 0;
      return '<div class="roll-item"><div style="display:flex;justify-content:space-between;gap:8px"><span class="mono" style="font-weight:600">' + escapeHtml(r[labelKey]) + "</span>" +
        '<span class="num">' + fmtKg(r.quantity) + ' · ' + r.count + ' tx</span></div>' +
        '<div class="stock-bar" role="img" aria-label="' + pct + '% of max"><div style="width:' + pct + '%;background:var(--emerald)"></div></div></div>';
    }).join("") + "</div>";
  }

  /* ------------------------------------------------------------------ *
   *  AI Insights
   * ------------------------------------------------------------------ */
  function renderInsights() {
    var v = $view();
    v.innerHTML = viewHead("AI Insights", "AI-powered analysis of the ration distribution network. Insight text is generated by the real workflow — deterministic calculations plus optional LLM narratives.");
    var chain = alertChain();

    if (!chain) {
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="card ai-card"><div class="card-body">' +
          emptyState("sparkles", "No AI insights yet", "Run the multi-agent analysis to generate AI insights from the synthetic dataset.", "analysis") +
        "</div></div></section>");
      return;
    }

    var finding = chain.findings[0] || null;
    var anomaly = chain.anomalies[0] || null;
    var evidence = finding && finding.evidence ? finding.evidence : {};
    var confidence = chain.case ? Math.round((chain.case.confidence || 0) * 100) : null;

    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="ai-banner">' + icon("sparkles", 17) +
        " RationAI Intelligence — insights below come from the real workflow run (Agent 2 evidence, Agent 3 case, Agent 4 alert).</div></section>" +
      '<section class="section"><div class="grid cols-3">' +
        insightCard("alert", "Distribution anomaly detected", chain.alert.message,
          [["Type", anomaly ? anomaly.anomaly_type.replace(/_/g, " ") : "—"],
           ["Severity", chain.alert.severity || "—"],
           ["Status", chain.alert.status === "open" ? "Pending human review" : chain.alert.status]],
          [["Evidence", evidence.time_difference_minutes != null ? evidence.time_difference_minutes + " min apart" : "—"],
           ["Distance", evidence.distance_km != null ? evidence.distance_km + " km" : "—"]],
          "Review alert", "alerts") +
        insightCard("eye", "Verified investigation case", chain.case.summary,
          [["Case", chain.case.case_id], ["Findings", (chain.case.finding_ids || []).join(", ")],
           ["Confidence", confidence != null ? confidence + "%" : "—"]],
          [["Recommended", chain.case.recommended_action || "Human verification"]],
          "View case", "analysis") +
        insightCard("sparkles", "Model-written explanation", finding.explanation,
          [["Finding", finding.finding_id], ["Beneficiary", anomaly ? anomaly.beneficiary_id : "—"],
           ["Transactions", chain.transactionIds.join(", ")]],
          [["Verified", finding.status === "verified" ? "Against transaction data" : finding.status]],
          "Trace to transactions", "analysis") +
      "</div></section>");

    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="section-title">Evidence summary <span class="hint">calculated by Agent 2 — displayed, never recomputed</span></div>' +
      '<div class="kv">' +
        '<div class="kv-item"><dt>Time difference</dt><dd>' + (evidence.time_difference_minutes != null ? evidence.time_difference_minutes + " minutes" : "—") + "</dd></div>" +
        '<div class="kv-item"><dt>Geographic distance</dt><dd>' + (evidence.distance_km != null ? evidence.distance_km + " km" : "—") + "</dd></div>" +
        '<div class="kv-item"><dt>Verification</dt><dd>' + (finding && finding.status === "verified" ? "Verified" : "Unverified") + "</dd></div>" +
        '<div class="kv-item"><dt>Human review</dt><dd>Required</dd></div>' +
      "</div></section>");

    // AI insight -> source lineage (Phase 8 §19): the backend records every
    // analysis run, so the insight traces back to its dataset/import/source.
    var run = state.result.analysis_run;
    if (run) {
      var runRows = [
        ["Analysis run", run.analysis_id],
        ["Dataset mode", run.dataset_mode === "real" ? "Real imported dataset" : "Synthetic demo dataset"],
        ["Status", run.status.replace(/_/g, " ")]
      ];
      if (run.data_import_id) runRows.push(["Data import", "#" + run.data_import_id]);
      if (run.summary) runRows.push(["Outcome", run.summary]);
      v.insertAdjacentHTML("beforeend",
        '<section class="section"><div class="card"><div class="card-body">' +
        '<div class="section-title">Source lineage <span class="hint">recorded by the backend — trace this insight to its dataset</span></div>' +
        '<div class="kv">' + runRows.map(function (r) {
          return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
        }).join("") + "</div>" +
        '<div class="ai-actions" style="margin-top:12px"><a class="btn btn-secondary btn-sm" href="#/pipeline">' + icon("layers", 14) + " View in Data Pipeline</a></div>" +
        "</div></div></section>");
    }
  }

  function insightCard(iconName, title, text, metaGroups1, metaGroups2, actionLabel, route) {
    function metaHtml(rows) {
      return rows.map(function (r) {
        return '<span class="badge neutral" style="font-weight:600">' + escapeHtml(r[0]) + ": " + escapeHtml(r[1]) + "</span>";
      }).join("");
    }
    return '<div class="card ai-card hoverable"><div class="card-body">' +
      '<div class="ai-head"><span class="ai-icon">' + icon(iconName, 17) + '</span><span class="ai-title">' + escapeHtml(title) + "</span>" +
      '<span class="badge ai" style="margin-left:auto">AI</span></div>' +
      '<p class="ai-text">' + escapeHtml(text) + "</p>" +
      '<div class="ai-meta">' + metaHtml(metaGroups1) + "</div>" +
      '<div class="ai-meta">' + metaHtml(metaGroups2) + "</div>" +
      '<div class="ai-actions"><a class="btn btn-primary btn-sm" href="#/' + route + '">' + escapeHtml(actionLabel) + " " + icon("arrow", 14) + "</a></div>" +
    "</div></div>";
  }

  /* ------------------------------------------------------------------ *
   *  Decision Support (Phase 10 — what-if simulation on real data)
   *  Every baseline is calculated by the backend from the selected import;
   *  a scenario NEVER modifies the database — only its metadata is stored.
   * ------------------------------------------------------------------ */
  function renderSimulation() {
    var v = $view();
    var s = state.simulation;
    if (!s) {
      s = state.simulation = {
        importId: null, entities: null, situation: null,
        result: null, history: null, running: false, error: null,
        params: { commodity: "", district: "", fps: "", demandPct: 10, delay: 0, invPct: 0 }
      };
    }
    if (!state.availableDatasets) {
      fetchJson(API_BASE + "/api/datasets", {}, 8000).then(function (payload) {
        state.availableDatasets = payload;
        if (state.route === "simulation") renderRoute();
      }).catch(function () { state.availableDatasets = { datasets: [] }; });
    }
    if (!s.history) loadSimulationHistory();

    var datasets = (state.availableDatasets && state.availableDatasets.datasets) || [];
    // Alert Center -> "Run What-If": pre-select the alert's dataset/commodity.
    // Applied only once datasets are loaded, and only when the alert's import
    // is actually selectable (has transactions) — otherwise we tell the user
    // instead of silently simulating nothing.
    if (state.simPreset && datasets.length) {
      var presetId = Number(state.simPreset.importId);
      var usable = datasets.some(function (d) { return Number(d.id) === presetId; });
      if (usable) {
        s.importId = presetId;
        if (state.simPreset.commodity) s.params.commodity = state.simPreset.commodity;
        if (state.simPreset.fps) s.params.fps = state.simPreset.fps;
        loadSimulationContext();
      } else {
        toast("That alert's dataset has no transactions — pick a dataset below.", "error");
      }
      state.simPreset = null;
    }
    v.innerHTML = viewHead("Decision Support", "What-if simulation on real database data: pick a dataset and ask what happens if demand, supply, or inventory changes. Baselines come from the database; scenarios never modify it.",
      '<span class="badge ai">' + icon("clipboard", 12) + " Decision support</span>");

    var dsSelect = '<select id="sim-dataset" class="select" aria-label="Dataset for simulation"' + (s.running ? " disabled" : "") + ">" +
      '<option value="">Select a dataset…</option>' +
      datasets.map(function (d) {
        return '<option value="' + d.id + '"' + (s.importId === d.id ? " selected" : "") + ">" +
          escapeHtml(d.dataset_name + " — " + d.transaction_count + " tx") + "</option>";
      }).join("") +
      "</select>";
    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="card"><div class="card-body">' +
      '<div class="toolbar" style="margin-bottom:0">' +
        dsSelect +
        '<span style="flex:1"></span>' +
        '<button id="sim-run" class="btn btn-primary" type="button" ' + (s.importId ? "" : "disabled") + ">" +
          (s.running ? '<span class="spinner"></span> Running simulation…' : "Run Simulation") + "</button>" +
      "</div></div></div></section>");

    if (s.running) {
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="card"><div class="card-body">' +
        '<div style="display:flex;align-items:center;gap:10px"><span class="spinner"></span> Computing the scenario from the database…</div></div></div></section>');
      bindSimulationControls();
      return;
    }

    if (!datasets.length) {
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="card"><div class="card-body">' +
        emptyState("clipboard", "No imported datasets yet", "Import a real dataset (CSV/XLSX/JSON) to run what-if simulations on it.", "upload") +
        "</div></div></section>");
      v.insertAdjacentHTML("beforeend", simulationHistorySectionHtml());
      bindSimulationControls();
      return;
    }
    if (!s.importId) {
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="card"><div class="card-body">' +
        emptyState("clipboard", "Select a dataset to begin", "Choose an imported dataset above to load its current situation and run scenarios.", null) +
        "</div></div></section>");
      v.insertAdjacentHTML("beforeend", simulationHistorySectionHtml());
      bindSimulationControls();
      return;
    }

    v.insertAdjacentHTML("beforeend", simulationSituationHtml(s));
    v.insertAdjacentHTML("beforeend", simulationBuilderHtml(s));
    if (s.result) v.insertAdjacentHTML("beforeend", simulationResultHtml(s.result));
    if (s.error) v.insertAdjacentHTML("beforeend", '<section class="section">' + analyticsErrorPanel(s.error) + "</section>");
    v.insertAdjacentHTML("beforeend", simulationHistorySectionHtml());
    bindSimulationControls();
  }

  function simulationSituationHtml(s) {
    var sit = s.situation;
    if (!sit) return '<section class="section" id="sim-situation">' + skeleton() + "</section>";
    var coverage = sit.estimated_coverage_days != null ? sit.estimated_coverage_days + " days" : "Not calculable";
    var kpis = [
      ["Inventory", fmtKg(sit.inventory_stock_kg)],
      ["Avg daily consumption", fmtKg(sit.average_daily_consumption_kg) + "/day"],
      ["Estimated coverage", coverage],
      ["High-risk FPS", String(sit.high_risk_fps.length)],
      ["High-risk districts", String(sit.high_risk_districts.length)],
      ["Total distributed", fmtKg(sit.total_quantity_kg)]
    ];
    var riskRows = (sit.risk_items || []).map(function (r) {
      return '<tr><td class="mono">' + escapeHtml(r.fps_code) + "</td><td>" + escapeHtml(r.district || "—") + "</td>" +
        "<td>" + escapeHtml(r.commodity) + "</td><td class=\"num\">" + fmtKg(r.current_stock) + "</td>" +
        "<td>" + (r.days_remaining != null ? r.days_remaining + " days" : "—") + "</td>" +
        "<td>" + (r.reorder_threshold != null ? fmtKg(r.reorder_threshold) : "—") + "</td></tr>";
    }).join("");
    return '<section class="section" id="sim-situation"><div class="section-title">Current situation <span class="hint">calculated by the backend from this dataset — never invented</span></div>' +
      '<div class="grid cols-3">' + kpis.map(function (k) {
        return '<div class="card"><div class="card-body"><div class="kv-item" style="background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px"><div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">' + escapeHtml(k[0]) + "</div><div style='font-size:22px;font-weight:700;margin-top:4px'>" + k[1] + "</div></div></div></div>";
      }).join("") + "</div>" +
      (riskRows ? '<div class="card" style="margin-top:12px"><div class="card-body flush"><div class="table-wrap"><table class="data"><thead><tr>' +
        "<th>FPS</th><th>District</th><th>Commodity</th><th>Stock</th><th>Coverage</th><th>Reorder threshold</th></tr></thead><tbody>" + riskRows + "</tbody></table></div></div></div>" : "") +
      "</section>";
  }

  function simulationBuilderHtml(s) {
    var e = s.entities || { commodities: [], districts: [], fps: [] };
    var p = s.params;
    var opt = function (list, value, labelFn) {
      return list.map(function (item) {
        return '<option value="' + escapeHtml(item) + '"' + (value === item ? " selected" : "") + ">" + escapeHtml(labelFn ? labelFn(item) : item) + "</option>";
      }).join("");
    };
    return '<section class="section"><div class="section-title">Scenario builder <span class="hint">validated: demand −50%…+100%, delay 0–365 days, inventory −100%…+100%</span></div>' +
      '<div class="card"><div class="card-body">' +
      '<div class="filter-grid">' +
        '<label>Commodity<select class="select" id="sim-commodity"><option value="">Select…</option>' + opt(e.commodities, p.commodity) + "</select></label>" +
        '<label>District<select class="select" id="sim-district"><option value="">All districts</option>' + opt(e.districts, p.district) + "</select></label>" +
        '<label>FPS center<select class="select" id="sim-fps"><option value="">All FPS centers</option>' + opt(e.fps, p.fps) + "</select></label>" +
      "</div>" +
      '<div class="sim-sliders">' +
        '<label class="sim-slider"><span><strong>Demand change</strong><em id="sim-demand-val">' + (p.demandPct >= 0 ? "+" : "") + p.demandPct + "%</em></span>" +
        '<input type="range" id="sim-demand" min="-50" max="100" step="1" value="' + p.demandPct + '"></label>' +
        '<label class="sim-slider"><span><strong>Inventory change</strong><em id="sim-inv-val">' + (p.invPct >= 0 ? "+" : "") + p.invPct + "%</em></span>" +
        '<input type="range" id="sim-inv" min="-100" max="100" step="1" value="' + p.invPct + '"></label>' +
        '<label class="sim-slider"><span><strong>Supply delay</strong><em id="sim-delay-val">' + p.delay + " days</em></span>" +
        '<input type="number" id="sim-delay" min="0" max="365" step="1" value="' + p.delay + '"></label>' +
      "</div>" +
      '<p class="hint" style="margin-top:10px">Simulation only — no database records are modified. The result is a derived projection, not a prediction.</p>' +
      "</div></div></section>";
  }

  function simulationResultHtml(r) {
    var tone = { CRITICAL: "high", WARNING: "medium", HEALTHY: "low", UNKNOWN: "low" }[r.risk] || "low";
    var b = r.baseline, sc = r.scenario;
    var rows = [
      ["Monthly demand", fmtKg(b.monthly_demand_kg), fmtKg(sc.projected_monthly_demand_kg)],
      ["Daily consumption", b.daily_consumption_kg != null ? fmtKg(b.daily_consumption_kg) + "/day" : "—", sc.projected_daily_consumption_kg != null ? fmtKg(sc.projected_daily_consumption_kg) + "/day" : "—"],
      ["Stock", fmtKg(b.current_stock_kg), fmtKg(sc.stock_after_inventory_change_kg)],
      ["Stock after delay", "—", fmtKg(sc.projected_stock_after_delay_kg)],
      ["Coverage", b.coverage_days != null ? b.coverage_days + " days" : "Not calculable", sc.coverage_label]
    ];
    var lineage = r.lineage || {};
    var chain = [
      ["Scenario", r.scenario_id],
      ["Dataset", lineage.dataset_name],
      ["Import", lineage.data_import_id != null ? "#" + lineage.data_import_id : "—"],
      ["Source", lineage.source_name]
    ];
    var insightNote = simulationInsightNote(r.risk);
    return '<section class="section" id="sim-result"><div class="section-title">Scenario result <span class="hint">computed deterministically by the backend</span></div>' +
      '<div class="grid cols-3">' +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Scenario</p>' +
        '<p class="mono" style="font-size:18px;font-weight:700">' + escapeHtml(r.scenario_id) + "</p>" +
        '<p class="hint">' + escapeHtml(r.commodity || "") + " · " + escapeHtml(r.entity.id) + "</p>" +
        (sc.demand_change_pct ? '<p class="hint">Demand ' + (sc.demand_change_pct >= 0 ? "+" : "") + sc.demand_change_pct + "%</p>" : "") +
        (sc.supply_delay_days ? '<p class="hint">' + sc.supply_delay_days + " day supply delay</p>" : "") +
        (sc.inventory_change_pct ? '<p class="hint">Inventory ' + (sc.inventory_change_pct >= 0 ? "+" : "") + sc.inventory_change_pct + "%</p>" : "") +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Projected risk</p>' +
        '<span class="priority-chip ' + tone + '">' + escapeHtml(r.risk) + "</span>" +
        (sc.simulated_reorder_requirement_kg != null ?
          '<div class="kv-item" style="margin-top:12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:12px 14px"><dt style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--text-3)">Simulated requirement</dt><dd style="margin-top:3px;font-size:16px;font-weight:700">' + fmtKg(sc.simulated_reorder_requirement_kg) + "</dd></div>" : "") +
      "</div></div>" +
      '<div class="card"><div class="card-body">' +
        '<p class="kicker">Lineage</p>' +
        '<div class="trace-chain" style="flex-direction:column;align-items:stretch;gap:6px">' + chain.map(function (c, i) {
          return '<div style="display:flex;align-items:center;gap:8px"><span class="trace-label" style="min-width:70px">' + escapeHtml(c[0]) + '</span><span class="mono" style="font-size:12.5px">' + escapeHtml(String(c[1])) + "</span>" +
            (i < chain.length - 1 ? '<span class="trace-arrow" aria-hidden="true">↓</span>' : "") + "</div>";
        }).join("") + "</div>" +
      "</div></div>" +
      "</div>" +
      '<div class="card" style="margin-top:12px"><div class="card-body flush"><div class="table-wrap"><table class="data"><thead><tr><th>Metric</th><th>Current</th><th>Scenario</th></tr></thead><tbody>' + rows.map(function (r2) {
        return '<tr><td>' + escapeHtml(r2[0]) + "</td><td>" + escapeHtml(String(r2[1])) + "</td><td><strong>" + escapeHtml(String(r2[2])) + "</strong></td></tr>";
      }).join("") + "</tbody></table></div></div></div>" +
      (r.interpretation ? '<div class="card" style="margin-top:12px"><div class="card-body">' +
        '<div class="section-title">Why? <span class="hint">' + (r.interpretation.generated_by === "llm" ? "AI interpretation of the calculated values" : "deterministic explanation (LLM unavailable or not enabled)") + "</span></div>" +
        '<p style="font-size:13.5px;line-height:1.6">' + escapeHtml(r.interpretation.summary) + "</p>" +
      "</div></div>" : "") +
      (insightNote ? '<div class="card" style="margin-top:12px"><div class="card-body">' + insightNote + "</div></div>" : "") +
      "</section>";
  }

  function simulationInsightNote(risk) {
    var result = state.result;
    if (!result || !Array.isArray(result.insights)) return "";
    var relevant = result.insights.filter(function (i) {
      return i.insight_type === "INVENTORY_RISK" || i.insight_type === "DISTRIBUTION_ANOMALY" || i.insight_type === "OPERATIONAL_RISK";
    });
    if (!relevant.length) return "";
    var severe = relevant.some(function (i) { return i.severity === "HIGH" || i.severity === "CRITICAL"; });
    if (risk === "CRITICAL" && severe) {
      return '<p class="kicker">AI insight integration</p><p style="font-size:13.5px">Scenario confirms the existing high-risk AI insight.</p>';
    }
    if (risk === "HEALTHY" && severe) {
      return '<p class="kicker">AI insight integration</p><p style="font-size:13.5px">Scenario produces a different risk outcome than the latest analysis.</p>';
    }
    return "";
  }

  function simulationHistorySectionHtml() {
    var h = state.simulation && state.simulation.history;
    if (!h) return '<section class="section" id="sim-history-section"><div class="section-title">Scenario history</div><div class="card"><div class="card-body">' + skeleton() + "</div></div></section>";
    var rows = (h.scenarios || []).map(function (sc) {
      var tone = { CRITICAL: "high", WARNING: "medium", HEALTHY: "low", UNKNOWN: "low" }[sc.risk] || "low";
      return '<tr>' +
        '<td class="mono">' + escapeHtml(sc.scenario_id) + "</td>" +
        "<td>" + escapeHtml(sc.dataset_name || "—") + "</td>" +
        "<td>" + escapeHtml(sc.commodity || "—") + "</td>" +
        "<td>" + escapeHtml(sc.entity_id || "—") + "</td>" +
        "<td>" + escapeHtml(sc.scenario_type.replace(/_/g, " ")) + "</td>" +
        '<td><span class="priority-chip ' + tone + '">' + escapeHtml(sc.risk) + "</span></td>" +
        "<td>" + escapeHtml(fmtDate(sc.created_at)) + "</td>" +
        '<td class="actions-cell"><button class="btn btn-ghost btn-sm" data-sim-view="' + sc.id + '" type="button">View</button> ' +
        '<button class="btn btn-secondary btn-sm" data-sim-rerun="' + sc.id + '" type="button">Run Again</button></td></tr>';
    }).join("");
    return '<section class="section" id="sim-history-section"><div class="section-title">Scenario history <span class="hint">persisted simulation metadata only — real data is never changed</span></div>' +
      '<div class="card"><div class="card-body flush"><div class="table-wrap"><table class="data"><thead><tr>' +
      "<th>Scenario</th><th>Dataset</th><th>Commodity</th><th>Scope</th><th>Type</th><th>Risk</th><th>Date</th><th></th>" +
      "</tr></thead><tbody>" + (rows || '<tr><td colspan="8"><p class="hint" style="padding:14px">No scenarios run yet.</p></td></tr>') + "</tbody></table></div>" +
      '<div id="sim-history-detail"></div>' +
      "</div></div></section>";
  }

  function loadSimulationHistory() {
    var s = state.simulation;
    if (!s) return;
    fetchJson(API_BASE + "/api/simulation/history?per_page=8", {}, 10000).then(function (p) {
      s.history = p;
      var el = $id("sim-history-section");
      if (el) { el.outerHTML = simulationHistorySectionHtml(); bindSimulationHistoryControls(); }
    }).catch(function () {
      s.history = { scenarios: [], total: 0 };
      var el = $id("sim-history-section");
      if (el) { el.outerHTML = simulationHistorySectionHtml(); bindSimulationHistoryControls(); }
    });
  }

  function bindSimulationControls() {
    var s = state.simulation;
    var ds = $id("sim-dataset");
    if (ds) ds.addEventListener("change", function () {
      var val = ds.value;
      s.importId = val ? Number(val) : null;
      s.entities = null; s.situation = null; s.result = null; s.error = null;
      if (s.importId) {
        loadSimulationContext();
      } else {
        renderRoute();
      }
    });
    var run = $id("sim-run");
    if (run) run.addEventListener("click", runSimulation);
    var commodity = $id("sim-commodity");
    if (commodity) commodity.addEventListener("change", function () { s.params.commodity = commodity.value; });
    var district = $id("sim-district");
    if (district) district.addEventListener("change", function () { s.params.district = district.value; });
    var fps = $id("sim-fps");
    if (fps) fps.addEventListener("change", function () { s.params.fps = fps.value; });
    var demand = $id("sim-demand");
    if (demand) demand.addEventListener("input", function () {
      s.params.demandPct = Number(demand.value);
      var label = $id("sim-demand-val");
      if (label) label.textContent = (s.params.demandPct >= 0 ? "+" : "") + s.params.demandPct + "%";
    });
    var inv = $id("sim-inv");
    if (inv) inv.addEventListener("input", function () {
      s.params.invPct = Number(inv.value);
      var label = $id("sim-inv-val");
      if (label) label.textContent = (s.params.invPct >= 0 ? "+" : "") + s.params.invPct + "%";
    });
    var delay = $id("sim-delay");
    if (delay) delay.addEventListener("input", function () {
      var v = Math.max(0, Math.min(365, Number(delay.value) || 0));
      s.params.delay = v;
      var label = $id("sim-delay-val");
      if (label) label.textContent = v + " days";
    });
    bindSimulationHistoryControls();
  }

  function loadSimulationContext() {
    var s = state.simulation;
    s.running = false;
    Promise.all([
      fetchJson(API_BASE + "/api/simulation/entities?import_id=" + s.importId, {}, 10000),
      fetchJson(API_BASE + "/api/simulation/situation?import_id=" + s.importId, {}, 10000)
    ]).then(function (results) {
      s.entities = results[0];
      s.situation = results[1];
      if (!s.params.commodity && s.entities.commodities.length) s.params.commodity = s.entities.commodities[0];
      if (state.route === "simulation") renderRoute();
    }).catch(function (err) {
      s.error = err.serverMessage || err.message || "Could not load the dataset context.";
      if (state.route === "simulation") renderRoute();
    });
  }

  function runSimulation() {
    var s = state.simulation;
    if (!s.importId || s.running) return;
    if (!s.params.commodity) {
      toast("Select a commodity to simulate.", "error");
      return;
    }
    s.running = true;
    s.error = null;
    renderRoute();
    fetchJson(API_BASE + "/api/simulation/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        import_id: s.importId,
        commodity: s.params.commodity,
        district: s.params.district || null,
        fps_code: s.params.fps || null,
        demand_change_pct: s.params.demandPct,
        supply_delay_days: s.params.delay,
        inventory_change_pct: s.params.invPct
      })
    }, 20000).then(function (result) {
      s.running = false;
      s.result = result;
      s.history = null;  // refresh history to include this scenario
      renderRoute();
      loadSimulationHistory();
    }).catch(function (err) {
      s.running = false;
      s.error = err.serverMessage || err.message || "The simulation could not be completed.";
      renderRoute();
    });
  }

  function bindSimulationHistoryControls() {
    document.querySelectorAll("[data-sim-view]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-sim-view"));
        var target = $id("sim-history-detail");
        if (!target) return;
        target.innerHTML = '<div style="margin-top:14px">' + skeleton() + "</div>";
        fetchJson(API_BASE + "/api/simulation/history/" + id, {}, 10000).then(function (d) {
          var b = (d.results || {}).baseline || {};
          var sc = (d.results || {}).scenario || {};
          var rows = [
            ["Scenario", d.scenario_id], ["Dataset", d.dataset_name], ["Source", d.source_name],
            ["Commodity", d.commodity], ["Scope", d.entity_id],
            ["Type", d.scenario_type.replace(/_/g, " ")], ["Risk", d.risk],
            ["Demand", b.monthly_demand_kg != null ? fmtKg(b.monthly_demand_kg) + " → " + fmtKg(sc.projected_monthly_demand_kg) : "—"],
            ["Coverage", b.coverage_days != null ? b.coverage_days + " days → " + (sc.coverage_label || "—") : "—"],
            ["Created", d.created_at]
          ];
          var ai = d.ai_interpretation;
          target.innerHTML = '<div class="card" style="margin-top:14px"><div class="card-body">' +
            '<div class="section-title">Scenario details <span class="hint">persisted metadata — parameters and results only</span></div>' +
            '<div class="kv">' + rows.map(function (r) {
              return '<div class="kv-item"><dt>' + escapeHtml(r[0]) + "</dt><dd>" + escapeHtml(String(r[1])) + "</dd></div>";
            }).join("") + "</div>" +
            (ai && ai.summary ? '<p class="hint" style="margin-top:12px">' + escapeHtml(ai.summary) + "</p>" : "") +
            "</div></div>";
        }).catch(function (err) {
          target.innerHTML = analyticsErrorPanel(err.serverMessage || err.message || "Could not load the scenario.");
        });
      });
    });
    document.querySelectorAll("[data-sim-rerun]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-sim-rerun"));
        var entry = ((state.simulation && state.simulation.history) || { scenarios: [] }).scenarios.filter(function (s) { return s.id === id; })[0];
        if (!entry) return;
        var s = state.simulation;
        s.importId = entry.data_import_id;
        s.entities = null; s.situation = null; s.result = null; s.error = null;
        s.params.commodity = entry.commodity || "";
        s.params.district = entry.entity_type === "district" ? entry.entity_id : "";
        s.params.fps = entry.entity_type === "fps_center" ? entry.entity_id : "";
        loadSimulationContext();
      });
    });
  }

  /* ------------------------------------------------------------------ *
   *  Executive Command Center (Phase 12)
   * ------------------------------------------------------------------ */
  function loadCommandCenter(alsoReports) {
    var cc = state.commandCenter;
    var f = cc.filters || {};
    var q = [];
    ["state", "district", "fps", "commodity", "from", "to", "trend_range"].forEach(function (k) {
      if (f[k]) q.push(encodeURIComponent(k) + "=" + encodeURIComponent(f[k]));
    });
    var url = API_BASE + "/api/command-center" + (q.length ? "?" + q.join("&") : "");
    cc.error = null;
    fetchJson(url, {}, 15000).then(function (payload) {
      cc.payload = payload;
      if (alsoReports || !cc.reports) loadCommandReports();
      if (state.route === "command") renderRoute();
    }).catch(function (err) {
      cc.error = (err && err.serverMessage) || "Unable to load command center.";
      if (state.route === "command") renderRoute();
    });
  }

  function loadCommandReports() {
    var cc = state.commandCenter;
    fetchJson(API_BASE + "/api/reports", {}, 8000).then(function (payload) {
      cc.reports = (payload && payload.reports) || [];
      if (state.route === "command") renderRoute();
    }).catch(function () {
      cc.reports = [];
      if (state.route === "command") renderRoute();
    });
  }

  function ccSevChip(sev) {
    var cls = { CRITICAL: "high", HIGH: "high", MEDIUM: "medium", LOW: "low", INFO: "low" }[String(sev || "").toUpperCase()] || "low";
    return '<span class="priority-chip ' + cls + '">' + escapeHtml(sev || "—") + "</span>";
  }

  function ccKpiCard(kpi) {
    var c = kpi.comparison || {};
    var change = '<span class="kpi-badge neutral">no comparison available</span>';
    if (c.available && c.previous != null && c.change_pct != null) {
      var up = c.change_pct >= 0;
      change = '<span class="kpi-badge ' + (up ? "success" : "warning") + '">' + (up ? "▲" : "▼") + " " +
        fmtNumber(Math.round(Math.abs(c.change_pct) * 10) / 10) + "% vs previous</span>";
    } else if (c.available && c.previous == null) {
      change = '<span class="kpi-badge neutral">no previous period</span>';
    }
    var display = kpi.value == null ? "—" :
      fmtNumber(Math.round(kpi.value * 100) / 100) + (kpi.unit ? " " + kpi.unit : "");
    return '<div class="card kpi hoverable"><div class="kpi-top"><span class="kpi-label">' + escapeHtml(kpi.label) + "</span>" +
      '<span class="kpi-icon">' + icon(kpi.key === "active_alerts" || kpi.key === "critical_alerts" ? "bell" : kpi.key === "data_quality" ? "check" : kpi.key === "inventory" || kpi.key === "coverage" ? "warehouse" : "truck", 17) + "</span></div>" +
      '<div class="kpi-value">' + escapeHtml(display) + "</div>" + change +
      (kpi.note ? '<div class="kpi-sub">' + escapeHtml(kpi.note) + "</div>" : "") + "</div>";
  }

  function ccFreshness(p) {
    var fr = p.freshness || {};
    var tone = { FRESH: "success", RECENT: "warning", STALE: "error", UNKNOWN: "neutral" }[fr.status] || "neutral";
    var sources = (p.sources || []).map(function (s) {
      return escapeHtml(s.name) + " (" + escapeHtml(s.status || "—") + ")";
    }).join(", ");
    return '<section class="section cc-freshness"><div class="cc-freshness-item"><span class="status-dot ' + tone + '"></span>' +
      '<div><div class="cc-freshness-label">Data status</div><div class="cc-freshness-value">' + escapeHtml(fr.status || "UNKNOWN") + "</div></div></div>" +
      '<div class="cc-freshness-item"><div class="cc-freshness-label">Last updated</div><div class="cc-freshness-value">' + escapeHtml(fr.detail || "No successful import recorded yet.") + "</div></div>" +
      '<div class="cc-freshness-item"><div class="cc-freshness-label">Sources</div><div class="cc-freshness-value">' + (sources || "—") + "</div></div>" +
      '<div class="cc-freshness-note">' + icon("info", 13) + " " + escapeHtml(p.disclaimer || "") + "</div></section>";
  }

  function ccFilters(p) {
    var fo = p.filter_options || { states: [], districts: [], fps: [], commodities: [] };
    var f = state.commandCenter.filters || {};
    function group(list, key, label) {
      if (!list.length) return "";
      return '<label class="cc-filter"><span>' + label + "</span><select data-cc-filter=\"" + key + "\">" +
        '<option value="">All</option>' +
        list.map(function (o) {
          return '<option value="' + escapeHtml(o) + '"' + (f[key] === o ? " selected" : "") + ">" + escapeHtml(o) + "</option>";
        }).join("") + "</select></label>";
    }
    return '<section class="section cc-filters"><div class="cc-filter-row">' +
      group(fo.states, "state", "State") + group(fo.districts, "district", "District") +
      group(fo.fps, "fps", "FPS") + group(fo.commodities, "commodity", "Commodity") +
      '<label class="cc-filter"><span>Trend range</span><select data-cc-filter="trend_range">' +
      [["7d", "Last 7 days"], ["30d", "Last 30 days"], ["90d", "Last 90 days"]].map(function (o) {
        return '<option value="' + o[0] + '"' + (f.trend_range === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
      }).join("") + "</select></label>" +
      '<label class="cc-filter"><span>From</span><input type="date" data-cc-filter="from" value="' + escapeHtml(f.from || "") + '"></label>' +
      '<label class="cc-filter"><span>To</span><input type="date" data-cc-filter="to" value="' + escapeHtml(f.to || "") + '"></label>' +
      "</div></section>";
  }

  function ccExecSummary(p) {
    var es = p.executive_summary || {};
    var byLlm = es.generated_by === "llm";
    return '<section class="section cc-exec"><div class="section-title-row"><h2>Executive summary</h2>' +
      '<span class="badge ' + (byLlm ? "ai" : "") + '">' + (byLlm ? "AI interpretation" : "Deterministic summary") + "</span></div>" +
      '<p class="cc-exec-text">' + escapeHtml(es.summary || "Insufficient data to provide a reliable executive summary.") + "</p></section>";
  }

  function ccRiskOverview(p) {
    var ro = p.risk_overview || {};
    var at = p.alert_trend || { series: [], total: 0 };
    var order = [["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"], ["info", "Info"]];
    var chips = order.map(function (pair) {
      return '<button type="button" class="cc-sev ' + pair[0] + '" data-cc-severity="' + pair[0].toUpperCase() + '" title="View ' + pair[1] + ' alerts">' +
        '<span class="cc-sev-count">' + (ro[pair[0]] || 0) + "</span><span class=\"cc-sev-label\">" + pair[1] + "</span></button>";
    }).join("");
    var max = Math.max.apply(null, at.series.map(function (s) { return s.count; }).concat([1]));
    var bars = at.series.map(function (s) {
      var h = s.count ? Math.round(s.count / max * 100) : 2;
      return '<div class="cc-trend-col" title="' + escapeHtml(s.date) + ": " + s.count + '"><div class="cc-trend-bar"><div class="cc-trend-fill warn" style="height:' + h + '%"></div></div><div class="cc-trend-date">' + escapeHtml(String(s.date).slice(5)) + "</div></div>";
    }).join("");
    return '<section class="section"><div class="section-title-row"><h2>Risk overview</h2><span class="section-sub">Active alerts by severity — click a severity to open the Alert Center</span></div>' +
      '<div class="cc-risk-grid"><div class="cc-sev-chips">' + chips +
      '<div class="cc-sev-total">Total: <b>' + (ro.total || 0) + "</b></div></div>" +
      '<div class="cc-alert-trend"><div class="cc-trend-head">Alert trend · last ' + (at.days || 7) + " days</div>" +
      '<div class="cc-trend-bars">' + (bars || '<div class="muted-cell">No alert history.</div>') + "</div></div></div></section>";
  }

  function ccRiskTables(p) {
    var distRows = (p.district_risk || []).map(function (d) {
      return '<tr><td>' + escapeHtml(d.district || "—") + "</td><td>" + fmtNumber(d.distribution_kg) + " kg</td><td>" + fmtNumber(d.transactions) + "</td><td>" +
        (d.coverage_days == null ? "—" : fmtNumber(d.coverage_days) + " d") + "</td><td>" + fmtNumber(d.alerts) + "</td><td>" + ccSevChip(d.risk) + "</td></tr>";
    }).join("");
    var fpsRows = (p.fps_risk || []).map(function (f) {
      return '<tr><td>' + escapeHtml(f.fps_code || "—") + "</td><td>" + escapeHtml(f.district || "—") + "</td><td>" +
        (f.coverage_days == null ? "—" : fmtNumber(f.coverage_days) + " d") + "</td><td>" + fmtNumber(f.alerts) + "</td><td>" + ccSevChip(f.risk) + "</td></tr>";
    }).join("");
    return '<section class="section"><div class="section-title-row"><h2>Geographic & FPS risk</h2></div><div class="cc-tables">' +
      '<div class="cc-table-wrap"><h3>District risk</h3><div class="table-wrap"><table class="data"><thead><tr><th>District</th><th>Distribution</th><th>Tx</th><th>Coverage</th><th>Alerts</th><th>Risk</th></tr></thead><tbody>' +
      (distRows || '<tr><td colspan="6" class="muted-cell">No district data available.</td></tr>') + "</tbody></table></div></div>" +
      '<div class="cc-table-wrap"><h3>FPS risk</h3><div class="table-wrap"><table class="data"><thead><tr><th>FPS</th><th>District</th><th>Coverage</th><th>Alerts</th><th>Risk</th></tr></thead><tbody>' +
      (fpsRows || '<tr><td colspan="5" class="muted-cell">No FPS data available.</td></tr>') + "</tbody></table></div></div></div></section>";
  }

  function ccTrends(p) {
    var t = p.trends || {};
    var series = t.distribution || [];
    var max = Math.max.apply(null, series.map(function (s) { return s.quantity; }).concat([1]));
    var cols = series.map(function (s) {
      var h = s.quantity > 0 ? Math.max(s.quantity / max * 100, 4) : 1;
      return '<div class="cc-trend-col" title="' + escapeHtml(s.date) + ": " + fmtNumber(s.quantity) + ' kg"><div class="cc-trend-bar"><div class="cc-trend-fill" style="height:' + h + '%"></div></div><div class="cc-trend-date">' + escapeHtml(String(s.date).slice(5)) + "</div></div>";
    }).join("");
    var byComm = (t.by_commodity || []).map(function (c) {
      var pct = t.total_quantity ? Math.round(c.quantity / t.total_quantity * 100) : 0;
      return '<div class="cc-comm-row"><span class="cc-comm-name">' + escapeHtml(c.commodity) + '</span><div class="cc-comm-bar"><div class="cc-comm-fill" style="width:' + pct + '%"></div></div><span class="cc-comm-val">' + fmtNumber(c.quantity) + " kg</span></div>";
    }).join("");
    return '<section class="section"><div class="section-title-row"><h2>Trend intelligence</h2><span class="section-sub">' + escapeHtml(t.range || "") + " · " + escapeHtml(t.from || "") + " → " + escapeHtml(t.to || "") + "</span></div>" +
      '<div class="cc-trend-grid"><div class="cc-chart"><div class="cc-chart-title">Distribution over time (kg)</div>' +
      '<div class="cc-trend-bars tall">' + (cols || '<div class="muted-cell">No distribution data in this range.</div>') + "</div></div>" +
      '<div class="cc-chart"><div class="cc-chart-title">Distribution by commodity</div>' +
      (byComm || '<div class="muted-cell">No commodity data.</div>') + "</div></div></section>";
  }

  function ccInsightsAlertsActions(p) {
    var insights = (p.top_insights || []).slice(0, 5).map(function (i) {
      return '<div class="cc-list-item hoverable" data-cc-insight="' + i.id + '" role="button" tabindex="0">' + ccSevChip(i.severity) +
        '<div class="cc-list-body"><div class="cc-list-title">' + escapeHtml(i.title || "Untitled insight") + "</div>" +
        '<div class="cc-list-sub">' + escapeHtml(String(i.description || "").slice(0, 180)) + "</div></div>" +
        '<span class="cc-list-link">View →</span></div>';
    }).join("");
    var alerts = (p.active_alerts || []).slice(0, 5).map(function (a) {
      var who = (a.entity_type ? a.entity_type + ": " + (a.entity_id || "—") : "") + (a.commodity ? " · " + a.commodity : "");
      return '<div class="cc-list-item hoverable" data-cc-alert="' + escapeHtml(a.alert_id) + '" role="button" tabindex="0">' + ccSevChip(a.severity) +
        '<div class="cc-list-body"><div class="cc-list-title">' + escapeHtml(a.title || "Alert") + "</div>" +
        '<div class="cc-list-sub">' + escapeHtml(who) + "</div></div><span class=\"cc-list-link\">Open →</span></div>";
    }).join("");
    var actions = (p.recommended_actions || []).slice(0, 6).map(function (r) {
      return '<div class="cc-list-item">' + ccSevChip(r.priority) +
        '<div class="cc-list-body"><div class="cc-list-title">' + escapeHtml(r.action || "—") + "</div>" +
        '<div class="cc-list-sub">' + escapeHtml((r.source || "") + (r.entity ? " · " + r.entity : "")) + "</div></div></div>";
    }).join("");
    return '<section class="section cc-columns">' +
      '<div class="cc-col"><div class="section-title-row"><h2>Top AI insights</h2><a class="link" href="#/analysis">Open Analysis →</a></div>' +
      (insights || '<div class="empty-state small"><p>No completed AI analyses yet.</p></div>') + "</div>" +
      '<div class="cc-col"><div class="section-title-row"><h2>Active alerts</h2><a class="link" href="#/alerts">Open Alert Center →</a></div>' +
      (alerts || '<div class="empty-state small"><p>All monitored conditions are within configured thresholds.</p></div>') + "</div>" +
      '<div class="cc-col"><div class="section-title-row"><h2>Recommended actions</h2></div>' +
      (actions || '<div class="empty-state small"><p>No recommendations yet.</p></div>') + "</div></section>";
  }

  function ccReports() {
    var cc = state.commandCenter;
    var rows = (cc.reports || []).map(function (r) {
      return '<tr><td><a href="#" class="link" data-cc-report="' + escapeHtml(r.report_id) + '">' + escapeHtml(r.report_id) + "</a></td>" +
        "<td>" + escapeHtml(r.period_label || "—") + "</td><td>" + escapeHtml(r.source_label || "—") + "</td>" +
        "<td>" + fmtDate(r.created_at) + "</td><td><span class=\"badge ok\">" + escapeHtml(r.status || "READY") + "</span></td></tr>";
    }).join("");
    return '<section class="section"><div class="section-title-row"><h2>Intelligence reports</h2><span class="section-sub">Generate an auditable report from the current filtered state — stored, never overwritten</span></div>' +
      '<div class="cc-report-actions">' +
      '<button class="btn btn-secondary btn-sm" id="cc-report-json" type="button">' + icon("download", 14) + " Export JSON</button>" +
      '<button class="btn btn-secondary btn-sm" id="cc-report-csv" type="button">' + icon("download", 14) + " Export CSV</button></div>" +
      '<div id="cc-report-detail"></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Report</th><th>Period</th><th>Source</th><th>Generated</th><th>Status</th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="5" class="muted-cell">No reports generated yet.</td></tr>') + "</tbody></table></div></section>";
  }

  function ccLineage(p) {
    var lg = p.lineage || {};
    var imports = (lg.latest_imports || []).slice(0, 4).map(function (i) {
      return '<div class="cc-lineage-item"><span class="cc-lineage-id">#' + i.id + "</span><span>" + escapeHtml(i.dataset_name || "—") + "</span>" +
        '<span class="badge ' + (i.status === "COMPLETED" ? "ok" : "warning") + '">' + escapeHtml(i.status || "—") + "</span><span>" + fmtNumber(i.successful_records) + "/" + fmtNumber(i.record_count) + " records</span></div>";
    }).join("");
    var analyses = (lg.latest_analysis_runs || []).slice(0, 4).map(function (a) {
      return '<div class="cc-lineage-item"><span class="cc-lineage-id">' + escapeHtml(a.analysis_id || "—") + "</span><span>" + escapeHtml(a.dataset_mode || "—") + "</span><span>" + fmtNumber(a.insight_count) + " insights</span></div>";
    }).join("");
    return '<section class="section"><div class="section-title-row"><h2>Data lineage</h2><span class="section-sub">Latest imports and analysis runs — every metric traces back to a stored import</span></div>' +
      '<div class="cc-lineage-grid"><div><h3>Latest imports (' + fmtNumber(lg.import_count) + ")</h3>" +
      (imports || '<div class="muted-cell">No imports yet.</div>') + "</div><div><h3>Latest analysis runs (" + fmtNumber(lg.analysis_count) + ")</h3>" +
      (analyses || '<div class="muted-cell">No analyses yet.</div>') + "</div></div></section>";
  }

  function renderCommandReportDetail(report) {
    var cc = state.commandCenter;
    cc.reportDetail = report;
    if (state.route === "command" || state.route === "reports") renderRoute();
  }

  function generateCommandReport() {
    var cc = state.commandCenter;
    cc.reportBusy = true;
    if (state.route === "command") renderRoute();
    var f = cc.filters || {};
    fetchJson(API_BASE + "/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filters: f })
    }, 25000).then(function (report) {
      cc.reportBusy = false;
      toast("Report " + report.report_id + " generated.", "ok");
      cc.reports = cc.reports || [];
      cc.reports.unshift({ report_id: report.report_id, period_label: report.period, source_label: report.source, created_at: report.generated_at, status: "READY" });
      renderCommandReportDetail(report);
    }).catch(function (err) {
      cc.reportBusy = false;
      toast((err && err.serverMessage) || "Could not generate the report.", "error");
      if (state.route === "command") renderRoute();
    });
  }

  function viewCommandReport(reportId) {
    fetchJson(API_BASE + "/api/reports/" + encodeURIComponent(reportId), {}, 10000).then(function (report) {
      renderCommandReportDetail(report);
    }).catch(function () {
      toast("Could not load the report.", "error");
    });
  }

  function renderCommandReportDetailPanel(report) {
    var host = $id("cc-report-detail");
    if (!host || !report) return;
    var kpis = (report.kpis || []).map(function (k) {
      return '<div class="cc-det-kpi"><span>' + escapeHtml(k.label) + "</span><b>" + escapeHtml(k.value == null ? "—" : fmtNumber(k.value) + (k.unit ? " " + k.unit : "")) + "</b></div>";
    }).join("");
    var risk = report.risk_overview || {};
    var alerts = (report.active_alerts || []).slice(0, 6).map(function (a) {
      return "<li>" + ccSevChip(a.severity) + " " + escapeHtml(a.title || "") + "</li>";
    }).join("");
    var insights = (report.top_insights || []).slice(0, 6).map(function (i) {
      return "<li>" + ccSevChip(i.severity) + " " + escapeHtml(i.title || "") + "</li>";
    }).join("");
    var actions = (report.recommended_actions || []).slice(0, 6).map(function (a) {
      return "<li>" + ccSevChip(a.priority) + " " + escapeHtml(a.action || "") + "</li>";
    }).join("");
    var dq = report.data_quality || {};
    var lg = report.lineage || {};
    var latestImport = (lg.latest_imports || [])[0];
    host.innerHTML = '<div class="cc-report-detail"><div class="cc-report-det-head"><h3>' + escapeHtml(report.report_id || "Report") + "</h3>" +
      '<span class="badge ok">' + escapeHtml(report.status || "READY") + "</span></div>" +
      '<p class="cc-report-meta">Period: ' + escapeHtml(report.period || "—") + " · Source: " + escapeHtml(report.source || "—") + " · Generated: " + fmtDate(report.created_at || report.generated_at) + "</p>" +
      '<p class="cc-report-disclaimer">' + escapeHtml(report.disclaimer || "") + "</p>" +
      '<div class="cc-det-block"><h4>Executive summary</h4><p>' + escapeHtml((report.executive_summary && report.executive_summary.summary) || "—") + "</p></div>" +
      '<div class="cc-det-block"><h4>Key metrics</h4><div class="cc-det-kpis">' + (kpis || "<p>—</p>") + "</div></div>" +
      '<div class="cc-det-block"><h4>Risk overview</h4><p>Critical ' + (risk.critical || 0) + " · High " + (risk.high || 0) + " · Medium " + (risk.medium || 0) + " · Low " + (risk.low || 0) + "</p></div>" +
      '<div class="cc-det-block"><h4>Major alerts</h4><ul class="cc-det-list">' + (alerts || "<li>No active alerts.</li>") + "</ul></div>" +
      '<div class="cc-det-block"><h4>AI insights</h4><ul class="cc-det-list">' + (insights || "<li>No completed analyses.</li>") + "</ul></div>" +
      '<div class="cc-det-block"><h4>Recommended actions</h4><ul class="cc-det-list">' + (actions || "<li>No recommendations.</li>") + "</ul></div>" +
      '<div class="cc-det-block"><h4>Data quality</h4><p>' + escapeHtml(dq.overall_score != null ? "Score " + fmtNumber(dq.overall_score) + "% · " + fmtNumber(dq.import_count) + " imports · " + fmtNumber(dq.totals ? dq.totals.records : 0) + " records" : "Not available") + "</p></div>" +
      '<div class="cc-det-block"><h4>Data lineage</h4><p>' + escapeHtml(latestImport ? "Import #" + latestImport.id + " · " + (latestImport.dataset_name || "") + " · " + (latestImport.source_name || "") : "—") + "</p></div>" +
      '<button class="btn btn-secondary btn-sm" id="cc-det-export" type="button">' + icon("download", 14) + " Export JSON</button></div>";
    var ex = $id("cc-det-export");
    if (ex) ex.addEventListener("click", function () {
      download("rationai-report-" + report.report_id + ".json", JSON.stringify(report, null, 2), "application/json");
    });
  }

  function renderCommandCenter() {
    var v = $view();
    var cc = state.commandCenter;
    if (!cc.filters) cc.filters = {};
    if (!cc.payload && !cc.error) loadCommandCenter(true);

    var headExtra = '<div class="view-actions">' +
      '<button class="btn btn-primary" id="cc-refresh" type="button">' + icon("refresh", 16) + " Refresh</button></div>";
    v.innerHTML = viewHead("Command Center", "Monitor PDS activity, investigate anomalies, and review evidence-backed cases.", headExtra);

    if (cc.error) {
      v.insertAdjacentHTML("beforeend", '<section class="section"><div class="empty-state"><div class="empty-icon">' + icon("alert", 26) + "</div><h3>Unable to load command center</h3><p>" + escapeHtml(cc.error) + "</p><div class=\"empty-actions\"><button class=\"btn btn-secondary\" id=\"cc-retry\" type=\"button\">Retry</button></div></div></section>");
      bindCommandCenterControls();
      return;
    }
    if (!cc.payload) {
      v.insertAdjacentHTML("beforeend", '<section class="section">' + skeleton() + "</section>");
      v.insertAdjacentHTML("beforeend", '<section class="section">' + skeleton() + "</section>");
      bindCommandCenterControls();
      return;
    }
    var p = cc.payload;
    v.insertAdjacentHTML("beforeend", ccFreshness(p));
    v.insertAdjacentHTML("beforeend", ccFilters(p));
    v.insertAdjacentHTML("beforeend", ccExecSummary(p));
    /* --- Operational metrics (compact 4-card row) --- */
    var kpis = p.kpis || [];
    function findKpi(key) { for (var i = 0; i < kpis.length; i++) { if (kpis[i].key === key) return kpis[i]; } return null; }
    var txKpi = findKpi("total_transactions") || kpis[0];
    var anomalyKpi = findKpi("anomalies") || findKpi("total_anomalies") || kpis[1];
    var caseKpi = findKpi("open_cases") || findKpi("cases") || kpis[2];
    var alertKpi = findKpi("active_alerts") || kpis[3];
    var metricCards = [txKpi, anomalyKpi, caseKpi, alertKpi].filter(Boolean).map(function (k) {
      var val = k.value == null ? "\u2014" : fmtNumber(Math.round(k.value * 100) / 100) + (k.unit ? " " + k.unit : "");
      return '<div class="cc-metric"><div class="cc-metric-value">' + escapeHtml(String(val)) + '</div><div class="cc-metric-label">' + escapeHtml(k.label || k.key || "") + '</div>' +
        (k.comparison && k.comparison.available && k.comparison.change_pct != null ? '<div class="cc-metric-change">' + (k.comparison.change_pct >= 0 ? '\u25b2' : '\u25bc') + ' ' + fmtNumber(Math.round(Math.abs(k.comparison.change_pct) * 10) / 10) + '%</div>' : '') + '</div>';
    }).join("");
    v.insertAdjacentHTML("beforeend", '<section class="section"><div class="cc-metrics-row">' + metricCards + '</div></section>');
    /* --- Recent Investigations --- */
    var insights = (p.top_insights || []).slice(0, 8);
    var invRows = insights.map(function (i) {
      var status = (i.status || "OPEN").toUpperCase();
      return '<tr><td>' + escapeHtml(i.id || "\u2014") + '</td><td>' + escapeHtml(i.title || "\u2014") + '</td><td>' + ccSevChip(i.severity) + '</td>' +
        '<td><span class="badge ' + (status === 'VERIFIED' ? 'ok' : status === 'DISMISSED' ? 'neutral' : 'warning') + '">' + escapeHtml(status) + '</span></td>' +
        '<td>' + fmtDate(i.created_at || i.detected_at) + '</td></tr>';
    }).join("");
    v.insertAdjacentHTML("beforeend", '<section class="section"><div class="section-title-row"><h2>Recent Investigations</h2><a class="link" href="#/analysis">View all \u2192</a></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Case</th><th>Issue</th><th>Severity</th><th>Status</th><th>Updated</th></tr></thead><tbody>' +
      (invRows || '<tr><td colspan="5" class="muted-cell">No investigations yet. Run AI Analysis to begin.</td></tr>') + '</tbody></table></div></section>');
    /* --- Recent Alerts --- */
    var alerts = (p.active_alerts || []).slice(0, 8);
    var alertRows = alerts.map(function (a) {
      var entity = (a.entity_type ? a.entity_type + ': ' + (a.entity_id || '\u2014') : '\u2014') + (a.commodity ? ' \u00b7 ' + a.commodity : '');
      return '<tr><td>' + ccSevChip(a.severity) + '</td><td>' + escapeHtml(a.title || 'Alert') + '</td><td>' + escapeHtml(entity) + '</td>' +
        '<td><span class="badge ' + (a.status === 'RESOLVED' ? 'ok' : a.status === 'DISMISSED' ? 'neutral' : 'warning') + '">' + escapeHtml(a.status || 'OPEN') + '</span></td></tr>';
    }).join("");
    v.insertAdjacentHTML("beforeend", '<section class="section"><div class="section-title-row"><h2>Recent Alerts</h2><a class="link" href="#/alerts">View all \u2192</a></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Priority</th><th>Alert</th><th>Entity</th><th>Status</th></tr></thead><tbody>' +
      (alertRows || '<tr><td colspan="4" class="muted-cell">No active alerts.</td></tr>') + '</tbody></table></div></section>');
    if (cc.reportDetail) renderCommandReportDetailPanel(cc.reportDetail);
    bindCommandCenterControls();
  }

  function bindCommandCenterControls() {
    var v = $view();
    var el = $id("cc-refresh");
    if (el) el.addEventListener("click", function () { loadCommandCenter(true); });
    var retry = $id("cc-retry");
    if (retry) retry.addEventListener("click", function () { loadCommandCenter(true); });
    var reportBtn = $id("cc-report");
    if (reportBtn) reportBtn.addEventListener("click", generateCommandReport);

    v.querySelectorAll("[data-cc-filter]").forEach(function (ctl) {
      ctl.addEventListener("change", function () {
        var f = state.commandCenter.filters;
        f[ctl.getAttribute("data-cc-filter")] = ctl.value;
        loadCommandCenter(false);
      });
    });
    v.querySelectorAll("[data-cc-severity]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.alertCenter.severity = btn.getAttribute("data-cc-severity");
        location.hash = "#/alerts";
      });
    });
    v.querySelectorAll("[data-cc-insight]").forEach(function (item) {
      item.addEventListener("click", function () { location.hash = "#/analysis"; });
      item.addEventListener("keydown", function (ev) { if (ev.key === "Enter") location.hash = "#/analysis"; });
    });
    v.querySelectorAll("[data-cc-alert]").forEach(function (item) {
      item.addEventListener("click", function () {
        state.alertCenter.q = item.getAttribute("data-cc-alert");
        location.hash = "#/alerts";
      });
      item.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") { state.alertCenter.q = item.getAttribute("data-cc-alert"); location.hash = "#/alerts"; }
      });
    });
    v.querySelectorAll("[data-cc-report]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        viewCommandReport(a.getAttribute("data-cc-report"));
      });
    });
    var jsonBtn = $id("cc-report-json");
    if (jsonBtn) jsonBtn.addEventListener("click", function () {
      var p = state.commandCenter.payload;
      if (p) download("rationai-command-center.json", JSON.stringify(p, null, 2), "application/json");
    });
    var csvBtn = $id("cc-report-csv");
    if (csvBtn) csvBtn.addEventListener("click", function () {
      var p = state.commandCenter.payload;
      if (!p) return;
      var rows = [["district", "distribution_kg", "transactions", "coverage_days", "alerts", "risk"]].concat(
        (p.district_risk || []).map(function (d) {
          return [d.district, d.distribution_kg, d.transactions, d.coverage_days, d.alerts, d.risk];
        })
      );
      download("rationai-district-risk.csv", toCsv(rows), "text/csv");
    });
  }

  /* ------------------------------------------------------------------ *
   *  Alerts center
   * ------------------------------------------------------------------ */
  function renderAlerts() {
    var v = $view();
    var ac = state.alertCenter;
    v.innerHTML = viewHead("Alert Center", "Proactive early warning: deterministic monitoring rules watch the database and surface alerts with evidence, AI explanation, and recommended actions. Monitoring never modifies source data — only the alert log.",
      '<button class="btn btn-primary" id="mon-run" type="button"' + (ac.busy ? " disabled" : "") + ">" +
        (ac.busy ? '<span class="spinner"></span> Monitoring…' : icon("activity", 16) + " Run Monitoring") + "</button>");
    v.insertAdjacentHTML("beforeend", '<section class="section" id="alert-summary">' + skeleton() + "</section>");
    v.insertAdjacentHTML("beforeend", '<section class="section" id="alert-trend">' + skeleton() + "</section>");
    v.insertAdjacentHTML("beforeend", '<section class="section" id="alert-rules-section">' + skeleton() + "</section>");
    v.insertAdjacentHTML("beforeend", alertFiltersHtml());
    v.insertAdjacentHTML("beforeend", '<section class="section" id="alert-list">' + skeleton() + "</section>");
    loadAlertCenterData(ac);
    bindAlertControls();
  }

  var ALERT_TYPE_LABELS = {
    INVENTORY_RISK: "Inventory risk", OPERATIONAL_RISK: "Operational risk",
    DISTRIBUTION_ANOMALY: "Distribution anomaly", DEMAND_SPIKE: "Demand spike",
    DEMAND_DROP: "Demand drop", SUPPLY_DELAY: "Supply delay",
    DATA_QUALITY: "Data quality", DATA_FRESHNESS: "Data freshness",
    SOURCE_FAILURE: "Source failure"
  };

  function alertFiltersHtml() {
    var ac = state.alertCenter;
    var typeOptions = Object.keys(ALERT_TYPE_LABELS).map(function (t) {
      return '<option value="' + t + '"' + (ac.type === t ? " selected" : "") + ">" + ALERT_TYPE_LABELS[t] + "</option>";
    }).join("");
    return '<section class="section"><div class="card"><div class="card-body">' +
      '<div class="toolbar" style="margin-bottom:0;flex-wrap:wrap">' +
        '<input class="input" style="min-width:220px" type="search" id="alert-q" placeholder="Search alert ID, FPS, district, commodity, title…" value="' + escapeHtml(ac.q) + '">' +
        '<select class="select" id="alert-sev" aria-label="Severity filter">' +
          '<option value="all">All severities</option>' +
          ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map(function (s) {
            return '<option value="' + s + '"' + (ac.severity === s ? " selected" : "") + ">" + s + "</option>";
          }).join("") +
        "</select>" +
        '<select class="select" id="alert-type" aria-label="Type filter">' +
          '<option value="all">All types</option>' + typeOptions +
        "</select>" +
        '<select class="select" id="alert-status" aria-label="Status filter">' +
          '<option value="all">All statuses</option>' +
          ["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"].map(function (s) {
            return '<option value="' + s + '"' + (ac.status === s ? " selected" : "") + ">" + s + "</option>";
          }).join("") +
        "</select>" +
        '<select class="select" id="alert-days" aria-label="Date range filter">' +
          [["7", "Last 7 days"], ["30", "Last 30 days"], ["90", "Last 90 days"], ["all", "All time"]].map(function (o) {
            return '<option value="' + o[0] + '"' + (String(ac.days) === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
          }).join("") +
        "</select>" +
        '<button class="btn btn-secondary btn-sm" id="alert-refresh" type="button">' + icon("check", 14) + " Apply</button>" +
        '<span style="flex:1"></span>' +
        '<span class="badge neutral" id="alert-count-label">—</span>' +
      "</div></div></div></section>";
  }

  function loadAlertCenterData(ac) {
    loadAlertSummary();
    var listParams = ["q", "severity", "type", "status", "days", "page"].map(function (k) {
      var val = k === "type" ? ac.type : ac[k];
      return val && val !== "all" ? k + "=" + encodeURIComponent(val) : "";
    }).filter(Boolean).join("&");
    fetchJson(API_BASE + "/api/alerts?per_page=12&" + listParams, {}, 15000).then(function (payload) {
      ac.list = payload;
      var label = $id("alert-count-label");
      if (label) label.textContent = payload.total + " alert" + (payload.total === 1 ? "" : "s");
      renderAlertList(payload);
    }).catch(function (err) {
      ac.error = err.serverMessage || err.message || "Could not load alerts.";
      renderAlertError();
    });
    fetchJson(API_BASE + "/api/alerts/summary", {}, 10000).then(function (payload) {
      ac.summary = payload;
      renderAlertSummary(payload);
    }).catch(function () {
      var el = $id("alert-summary");
      if (el) el.outerHTML = '<section class="section">' + analyticsErrorPanel("Could not load the alert summary.") + "</section>";
    });
    fetchJson(API_BASE + "/api/alerts/trend?days=7", {}, 10000).then(function (payload) {
      ac.trend = payload;
      renderAlertTrend(payload);
    }).catch(function () {
      var el = $id("alert-trend");
      if (el) el.outerHTML = "";
    });
    fetchJson(API_BASE + "/api/alerts/rules", {}, 10000).then(function (payload) {
      ac.rules = payload.rules || [];
      renderAlertRules(ac.rules);
    }).catch(function () {
      var el = $id("alert-rules-section");
      if (el) el.outerHTML = "";
    });
  }

  function renderAlertError() {
    var el = $id("alert-list");
    if (el) el.outerHTML = '<section class="section" id="alert-list">' + analyticsErrorPanel(state.alertCenter.error) +
      '<div style="margin-top:10px"><button class="btn btn-secondary btn-sm" id="alert-retry" type="button">Retry</button></div></section>';
    var btn = $id("alert-retry");
    if (btn) btn.addEventListener("click", function () { state.alertCenter.list = null; state.alertCenter.error = null; renderRoute(); });
  }

  function renderAlertSummary(s) {
    var el = $id("alert-summary");
    if (!el) return;
    var cards = [
      ["Critical", s.open.CRITICAL, "error"], ["High", s.open.HIGH, "error"],
      ["Medium", s.open.MEDIUM, "warning"], ["Low", s.open.LOW, "info"],
      ["Open total", s.total_open, "neutral"]
    ];
    el.outerHTML = '<section class="section"><div class="section-title">Open alerts <span class="hint">active (OPEN + acknowledged: ' + s.total_acknowledged + ")</span></div>" +
      '<div class="grid cols-5">' + cards.map(function (c) {
        return '<div class="card"><div class="card-body" style="text-align:center">' +
          '<div class="kv-item" style="padding:14px 8px"><span class="badge ' + c[2] + '">' + c[0] + "</span>" +
          '<div style="font-size:30px;font-weight:800;margin-top:8px">' + c[1] + "</div></div></div></div>";
      }).join("") + "</div></section>";
  }

  function renderAlertTrend(t) {
    var el = $id("alert-trend");
    if (!el) return;
    if (!t.total) {
      el.outerHTML = '<section class="section" id="alert-trend"><div class="section-title">Alert trend <span class="hint">last ' + t.days + ' days</span></div>' +
        '<div class="card"><div class="card-body"><p class="hint">Insufficient history for trend.</p></div></div></section>';
      return;
    }
    var max = Math.max.apply(null, t.series.map(function (s) { return s.count; }));
    var bars = t.series.map(function (s) {
      var h = max ? Math.max(4, Math.round(s.count / max * 60)) : 4;
      return '<div class="trend-col" title="' + escapeHtml(s.date) + " · " + s.count + ' alert(s)"><div class="trend-bar" style="height:' + h + 'px"></div>' +
        '<div class="trend-day">' + escapeHtml(s.date.slice(8)) + "</div><div class=\"trend-val\">" + s.count + "</div></div>";
    }).join("");
    el.outerHTML = '<section class="section" id="alert-trend"><div class="section-title">Alert trend <span class="hint">alerts created per day — ' + t.total + ' total</span></div>' +
      '<div class="card"><div class="card-body"><div class="trend-chart">' + bars + "</div></div></div></section>";
  }

  function renderAlertRules(rules) {
    var el = $id("alert-rules-section");
    if (!el) return;
    var rows = rules.map(function (r) {
      return '<div class="rule-row" data-rule="' + r.id + '">' +
        '<label class="switch-row"><input type="checkbox" data-rule-enabled="' + r.id + '"' + (r.enabled ? " checked" : "") + ">" +
        '<span class="switch"></span><span style="font-weight:600;font-size:13.5px">' + escapeHtml(r.name) + "</span></label>" +
        '<span class="badge ' + (r.severity === "CRITICAL" || r.severity === "HIGH" ? "error" : r.severity === "MEDIUM" ? "warning" : "info") + '">' + r.severity + "</span>" +
        '<span class="hint" style="flex:1;font-size:12px">' + escapeHtml(r.description || "") + "</span>" +
        (r.threshold != null ? '<span class="rule-threshold"><input class="input" style="width:90px" type="number" min="0" step="any" data-rule-threshold="' + r.id + '" value="' + r.threshold + '"> <span class="hint">' + escapeHtml(r.threshold_unit || "") + "</span></span>" : "") +
        '<button class="btn btn-ghost btn-sm" type="button" data-rule-save="' + r.id + '">Save</button>' +
      "</div>";
    }).join("");
    el.outerHTML = '<section class="section" id="alert-rules-section"><div class="section-title">Alert rules <span class="hint">deterministic thresholds — enabling/disabling applies on the next monitoring run</span></div>' +
      '<div class="card"><div class="card-body"><div class="rules-list">' + rows + "</div></div></div></section>";
    bindAlertControls();
  }

  function renderAlertList(payload) {
    var el = $id("alert-list");
    if (!el) return;
    var ac = state.alertCenter;
    var alerts = payload.alerts || [];
    var body;
    if (!alerts.length) {
      body = '<div class="card"><div class="card-body">' +
        emptyState("check", "No alerts match", payload.total === 0 ? "All monitored conditions are within configured thresholds." : "No alert matches the current filters.", null) +
        "</div></div>";
    } else {
      body = '<div class="grid">' + alerts.map(alertCardHtml).join("") + "</div>";
    }
    var pages = payload.pages || 1;
    el.outerHTML = '<section class="section" id="alert-list">' + body +
      (pages > 1 ? '<div class="pager" style="display:flex;align-items:center;gap:10px;margin-top:14px">' +
        '<button class="btn btn-ghost btn-sm" id="alert-prev" type="button"' + (ac.page <= 1 ? " disabled" : "") + ">Prev</button>" +
        '<span class="hint">Page ' + ac.page + " of " + pages + "</span>" +
        '<button class="btn btn-ghost btn-sm" id="alert-next" type="button"' + (ac.page >= pages ? " disabled" : "") + ">Next</button></div>" : "") +
      "</section>";
    // The list replaced the DOM after the first bind pass — re-bind actions.
    bindAlertControls();
  }

  function alertCardHtml(a) {
    var sevClass = { CRITICAL: "high", HIGH: "high", MEDIUM: "medium", LOW: "low" }[a.severity] || "low";
    var statusTone = { OPEN: "error", ACKNOWLEDGED: "warning", RESOLVED: "success", DISMISSED: "neutral" }[a.status] || "neutral";
    var ev = a.evidence || {};
    var cur = a.current_value != null ? String(Math.round(a.current_value * 100) / 100) : null;
    var thr = a.threshold != null ? String(Math.round(a.threshold * 100) / 100) : null;
    var entity = a.entity_type && a.entity_id ? escapeHtml(a.entity_type.replace(/_/g, " ") + ": " + a.entity_id) : null;
    var expanded = !!state.alertCenter.expanded[a.alert_id];
    return '<div class="card alert-card" data-alert-id="' + escapeHtml(a.alert_id) + '">' +
      '<div class="card-body">' +
        '<div style="display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap">' +
          '<span class="priority-chip ' + sevClass + '">' + escapeHtml(a.severity) + "</span>" +
          '<span class="badge neutral">' + escapeHtml(ALERT_TYPE_LABELS[a.rule_type] || a.rule_type.replace(/_/g, " ")) + "</span>" +
          '<span class="badge ' + statusTone + '">' + escapeHtml(a.status) + "</span>" +
          '<span style="flex:1"></span>' +
          '<span class="badge neutral">' + escapeHtml(a.alert_id) + "</span>" +
        "</div>" +
        '<h3 style="margin:10px 0 4px;font-size:15px">' + escapeHtml(a.title) + "</h3>" +
        '<p style="font-size:13px;color:var(--text-2);margin:0 0 10px">' + escapeHtml(a.description || "") + "</p>" +
        '<div class="kv" style="margin-top:8px">' +
          (entity ? '<div class="kv-item"><dt>Entity</dt><dd class="mono">' + entity + "</dd></div>" : "") +
          (a.commodity ? '<div class="kv-item"><dt>Commodity</dt><dd>' + escapeHtml(a.commodity) + "</dd></div>" : "") +
          (cur != null ? '<div class="kv-item"><dt>Current value</dt><dd class="mono">' + cur + (a.threshold != null ? " · threshold " + thr : "") + "</dd></div>" : "") +
          '<div class="kv-item"><dt>Detected</dt><dd>' + escapeHtml((a.last_detected_at || a.created_at || "—").slice(0, 16).replace("T", " ")) + "</dd></div>" +
          (a.dismissed_reason ? '<div class="kv-item"><dt>Dismiss reason</dt><dd>' + escapeHtml(a.dismissed_reason) + "</dd></div>" : "") +
        "</div>" +
        '<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">' +
          '<button class="btn btn-secondary btn-sm" type="button" data-alert-toggle="' + escapeHtml(a.alert_id) + '" aria-expanded="' + expanded + '">' + icon("eye", 14) + (expanded ? " Hide details" : " View details") + "</button>" +
          (a.status === "OPEN" ? '<button class="btn btn-ghost btn-sm" type="button" data-alert-action="acknowledge" data-alert="' + escapeHtml(a.alert_id) + '">Acknowledge</button>' : "") +
          (a.status === "OPEN" || a.status === "ACKNOWLEDGED" ? '<button class="btn btn-ghost btn-sm" type="button" data-alert-action="resolve" data-alert="' + escapeHtml(a.alert_id) + '">Resolve</button>' : "") +
          (a.status === "OPEN" || a.status === "ACKNOWLEDGED" ? '<button class="btn btn-ghost btn-sm" type="button" data-alert-action="dismiss" data-alert="' + escapeHtml(a.alert_id) + '">Dismiss</button>' : "") +
          (a.analysis_id ? '<a class="btn btn-ghost btn-sm" href="#/analysis" data-alert-analysis="' + escapeHtml(a.analysis_id) + '">' + icon("activity", 13) + " View Analysis</a>" : "") +
          (a.import_id ? '<button class="btn btn-ghost btn-sm" type="button" data-alert-whatif="' + a.import_id + '" data-alert-commodity="' + escapeHtml(a.commodity || "") + '">' + icon("clipboard", 13) + " Run What-If</button>" : "") +
        "</div>" +
        (expanded ? alertDetailHtml(a) : "") +
      "</div></div>";
  }

  function alertDetailHtml(a) {
    var ev = a.evidence || {};
    var evRows = Object.keys(ev).map(function (k) {
      var val = ev[k];
      if (val && typeof val === "object") val = JSON.stringify(val);
      return '<div class="kv-item"><dt>' + escapeHtml(String(k).replace(/_/g, " ")) + "</dt><dd>" + escapeHtml(String(val)) + "</dd></div>";
    }).join("");
    var ai = a.ai_explanation || {};
    var lineage = a.lineage || {};
    var lin = [];
    if (lineage.source) lin.push(["Source", lineage.source.name + " (" + (lineage.source.type || "") + ")"]);
    if (lineage.import) lin.push(["Dataset", lineage.import.dataset_name + " · import #" + a.import_id + " · " + lineage.import.import_status]);
    if (a.source_id && lineage.source) lin.push(["Source", lineage.source.name]);
    if (lineage.analysis) lin.push(["Analysis", lineage.analysis.analysis_id + " · " + lineage.analysis.status + " · " + lineage.analysis.insight_count + " insight(s)"]);
    return '<div class="alert-detail" style="margin-top:14px;border-top:1px solid var(--border);padding-top:14px">' +
      (evRows ? '<p class="kicker">Evidence <span class="hint">calculated by the backend — never invented</span></p><div class="kv">' + evRows + "</div>" : "") +
      (ai.summary ? '<div style="margin-top:12px"><p class="kicker">AI explanation</p>' +
        '<div class="ai-note"><span class="badge ' + (ai.generated_by === "llm" ? "ai" : "info") + '">' + (ai.generated_by === "llm" ? "AI interpretation" : "Deterministic explanation") + "</span>" +
        '<p style="font-size:13.5px;margin:8px 0 0">' + escapeHtml(ai.summary) + "</p></div></div>" : "") +
      (a.recommendation ? '<div style="margin-top:12px"><p class="kicker">Recommended action</p><p style="font-size:13.5px">' + escapeHtml(a.recommendation) + "</p></div>" : "") +
      (lin.length ? '<div style="margin-top:12px"><p class="kicker">Data lineage</p><div class="kv">' +
        lin.map(function (item) { return '<div class="kv-item"><dt>' + item[0] + "</dt><dd>" + escapeHtml(item[1]) + "</dd></div>"; }).join("") + "</div></div>" : "") +
      "</div>";
  }

  function runMonitoringNow() {
    var ac = state.alertCenter;
    if (ac.busy) return;
    ac.busy = true;
    renderRoute();
    fetchJson(API_BASE + "/api/monitoring/run", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}"
    }, 20000).then(function (result) {
      ac.busy = false;
      toast("Monitoring complete: " + result.created + " new, " + result.updated + " updated, " + result.resolved + " resolved.", "success");
      ac.summary = null; ac.trend = null; ac.list = null; ac.rules = null;
      loadAlertSummary();
      renderRoute();
    }).catch(function (err) {
      ac.busy = false;
      toast(err.serverMessage || err.message || "Monitoring could not be completed.", "error");
      renderRoute();
    });
  }

  function alertAction(id, action) {
    var payload = {};
    if (action === "dismiss") {
      var reason = window.prompt("Dismiss reason (optional):", "False positive");
      if (reason === null) return;
      payload.reason = reason;
    }
    fetchJson(API_BASE + "/api/alerts/" + encodeURIComponent(id) + "/" + action, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }, 10000).then(function () {
      toast("Alert " + id + " " + action + "d", "success");
      var ac = state.alertCenter;
      ac.summary = null; ac.list = null;
      loadAlertSummary();
      renderRoute();
    }).catch(function (err) {
      toast(err.serverMessage || err.message || "Could not update the alert.", "error");
    });
  }

  function bindAlertControls() {
    var run = $id("mon-run");
    if (run) run.addEventListener("click", runMonitoringNow);
    var ac = state.alertCenter;
    function applyFilters() {
      var q = $id("alert-q"), sev = $id("alert-sev"), typ = $id("alert-type"),
          st = $id("alert-status"), days = $id("alert-days");
      if (q) ac.q = q.value.trim();
      if (sev) ac.severity = sev.value;
      if (typ) ac.type = typ.value;
      if (st) ac.status = st.value;
      if (days) ac.days = days.value;
      ac.page = 1;
      ac.list = null;
      renderRoute();
    }
    var apply = $id("alert-refresh");
    if (apply) apply.addEventListener("click", applyFilters);
    var qInput = $id("alert-q");
    if (qInput) qInput.addEventListener("keydown", function (ev) { if (ev.key === "Enter") applyFilters(); });
    var prev = $id("alert-prev");
    if (prev) prev.addEventListener("click", function () { if (ac.page > 1) { ac.page -= 1; ac.list = null; renderRoute(); } });
    var next = $id("alert-next");
    if (next) next.addEventListener("click", function () { if (ac.page < (ac.list ? ac.list.pages : 1)) { ac.page += 1; ac.list = null; renderRoute(); } });
    document.querySelectorAll("[data-alert-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-alert-toggle");
        if (ac.expanded[id]) delete ac.expanded[id]; else ac.expanded[id] = true;
        renderRoute();
      });
    });
    document.querySelectorAll("button[data-alert-action]").forEach(function (b) {
      b.addEventListener("click", function () {
        alertAction(b.getAttribute("data-alert"), b.getAttribute("data-alert-action"));
      });
    });
    document.querySelectorAll("button[data-alert-whatif]").forEach(function (b) {
      b.addEventListener("click", function () {
        state.simPreset = {
          importId: Number(b.getAttribute("data-alert-whatif")),
          commodity: b.getAttribute("data-alert-commodity") || ""
        };
        state.availableDatasets = null;  // force a fresh dataset list
        window.location.hash = "#/simulation";
      });
    });
    document.querySelectorAll("[data-rule-enabled]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        saveRule(cb.getAttribute("data-rule-enabled"), { enabled: cb.checked });
      });
    });
    document.querySelectorAll("[data-rule-save]").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-rule-save");
        var input = document.querySelector('[data-rule-threshold="' + id + '"]');
        var val = input ? Number(input.value) : null;
        if (input && (isNaN(val) || val < 0)) { toast("Threshold must be a non-negative number.", "error"); return; }
        saveRule(id, { threshold: val });
      });
    });
  }

  function saveRule(id, payload) {
    fetchJson(API_BASE + "/api/alerts/rules/" + id, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }, 10000).then(function () {
      toast("Alert rule updated", "success");
      state.alertCenter.rules = null;
      renderRoute();
    }).catch(function (err) {
      toast(err.serverMessage || err.message || "Could not update the rule.", "error");
    });
  }

  function loadAlertSummary() {
    fetchJson(API_BASE + "/api/alerts/summary", {}, 10000).then(function (payload) {
      state.alertSummary = payload;
      updateNotifDot();
    }).catch(function () { state.alertSummary = null; updateNotifDot(); });
  }

  /* ------------------------------------------------------------------ *
   *  Reports
   * ------------------------------------------------------------------ */
  function renderReports() {
    var v = $view();
    var chain = alertChain();
    v.innerHTML = viewHead("Reports", "Generated from the database and the workflow result. PDF uses the browser print dialog; CSV exports actual data.");

    var reports = [
      { title: "Dataset Summary Report", desc: "Beneficiaries, transactions, ration mix, and coverage window from the database.", icon: "file", ready: true, route: "overview", csv: datasetCsv },
      { title: "Anomaly Report", desc: chain ? "The verified anomaly, its evidence, and the full traceability chain." : "Run the analysis to generate the anomaly report.", icon: "alert", ready: !!chain, route: "alerts", csv: anomalyCsv },
      { title: "Analysis Report", desc: chain ? "Workflow result: pipeline stages, findings, case, and alert summary." : "Run the analysis to generate this report.", icon: "activity", ready: !!chain, route: "analysis", csv: analysisCsv },
      { title: "AI Insight Report", desc: chain ? "Agent 2 explanation, Agent 3 summary, and Agent 4 message from the real workflow." : "Run the analysis to generate AI insights.", icon: "sparkles", ready: !!chain, route: "insights", csv: null }
    ];

    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="grid cols-2">' + reports.map(function (r) {
        return '<div class="card hoverable"><div class="card-body">' +
          '<div style="display:flex;align-items:center;gap:10px"><span class="ai-icon" style="width:34px;height:34px;border-radius:10px;display:grid;place-items:center;color:var(--emerald);background:var(--pale-green)">' + icon(r.icon, 17) + "</span>" +
          '<div><h3 style="font-weight:600;font-size:15px">' + escapeHtml(r.title) + "</h3><p style=\"font-size:12.5px;color:var(--text-2);margin-top:2px\">" + escapeHtml(r.desc) + "</p></div></div>" +
          '<div style="display:flex;gap:8px;margin-top:16px">' +
            '<a class="btn btn-primary btn-sm" href="#/' + r.route + '">View</a>' +
            '<button class="btn btn-secondary btn-sm" type="button" data-print="' + escapeHtml(r.title) + '">Download PDF</button>' +
            (r.csv ? '<button class="btn btn-secondary btn-sm" type="button" data-csv="' + escapeHtml(r.title) + '">Export CSV</button>' : "") +
          "</div></div></div>";
      }).join("") + "</div></section>" +
      '<section class="section"><div class="card"><div class="card-body"><p style="font-size:12.5px;color:var(--text-2)">' +
        "Reports contain no real personal data: the dataset is synthetic and intentionally excludes names and Aadhaar numbers." +
      "</p></div></div></section>");

    v.querySelectorAll("button[data-csv]").forEach(function (b) {
      b.addEventListener("click", function () {
        var title = b.getAttribute("data-csv");
        var fn = { "Dataset Summary Report": datasetCsv, "Anomaly Report": anomalyCsv, "Analysis Report": analysisCsv }[title];
        if (fn) fn();
      });
    });
    v.querySelectorAll("button[data-print]").forEach(function (b) {
      b.addEventListener("click", function () { window.print(); });
    });

    // Phase 16: surface the Phase 12 Intelligence Reports (history, generate,
    // view, export) on this page so the Reports nav entry reaches the report
    // system that backs the demo — not just the legacy cards above.
    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="section-title-row"><h2>Intelligence reports</h2><span class="section-sub">Auditable reports generated from the database — stored, never overwritten</span></div>' +
      '<div class="cc-report-actions">' +
      '<button class="btn btn-primary btn-sm" id="reports-generate" type="button">' + icon("file", 14) + " Generate Report</button>" +
      '<button class="btn btn-secondary btn-sm" id="reports-export-json" type="button">' + icon("download", 14) + " Export JSON</button>" +
      '<button class="btn btn-secondary btn-sm" id="reports-export-csv" type="button">' + icon("download", 14) + " Export CSV</button></div>" +
      '<div id="cc-report-detail"></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>Report</th><th>Period</th><th>Source</th><th>Generated</th><th>Status</th></tr></thead>' +
      '<tbody id="reports-tbody"><tr><td colspan="5" class="muted-cell">Loading reports…</td></tr></tbody></table></div></section>');
    loadReportsPage();
    if (state.commandCenter.reportDetail) renderCommandReportDetailPanel(state.commandCenter.reportDetail);
  }

  function loadReportsPage() {
    fetchJson(API_BASE + "/api/reports", {}, 8000).then(function (payload) {
      var cc = state.commandCenter;
      cc.reports = (payload && payload.reports) || [];
      var tbody = $id("reports-tbody");
      if (!tbody) return;
      tbody.innerHTML = cc.reports.length ? cc.reports.map(function (r) {
        return '<tr><td><a href="#" class="link" data-cc-report="' + escapeHtml(r.report_id) + '">' + escapeHtml(r.report_id) + "</a></td>" +
          "<td>" + escapeHtml(r.period_label || "—") + "</td><td>" + escapeHtml(r.source_label || "—") + "</td>" +
          "<td>" + fmtDate(r.created_at) + "</td><td><span class=\"badge ok\">" + escapeHtml(r.status || "READY") + "</span></td></tr>";
      }).join("") : '<tr><td colspan="5" class="muted-cell">No reports generated yet.</td></tr>';
      bindReportsControls();
    }).catch(function () {
      var tbody = $id("reports-tbody");
      if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="muted-cell">Unable to load reports. <button class="btn btn-secondary btn-sm" id="reports-retry" type="button">Retry</button></td></tr>';
      bindReportsControls();
    });
  }

  function bindReportsControls() {
    var gen = $id("reports-generate");
    if (gen) gen.addEventListener("click", generateCommandReport);
    $view().querySelectorAll("[data-cc-report]").forEach(function (a) {
      a.addEventListener("click", function (ev) { ev.preventDefault(); viewCommandReport(a.getAttribute("data-cc-report")); });
    });
    var jsonBtn = $id("reports-export-json");
    if (jsonBtn) jsonBtn.addEventListener("click", function () {
      var rep = state.commandCenter.reportDetail;
      if (!rep) { toast("Open a report first.", "info"); return; }
      download(rep.report_id + ".json", JSON.stringify(rep, null, 2), "application/json");
    });
    var csvBtn = $id("reports-export-csv");
    if (csvBtn) csvBtn.addEventListener("click", function () {
      var rep = state.commandCenter.reportDetail;
      if (!rep) { toast("Open a report first.", "info"); return; }
      var rows = [["district", "distribution_kg", "transactions", "coverage_days", "alerts", "risk"]].concat(
        (rep.district_risk || []).map(function (d) {
          return [d.district, d.distribution_kg, d.transactions, d.coverage_days, d.alerts, d.risk];
        })
      );
      download(rep.report_id + "-district-risk.csv", toCsv(rows), "text/csv");
    });
    var retry = $id("reports-retry");
    if (retry) retry.addEventListener("click", loadReportsPage);
  }

  function datasetCsv() {
    // Export the real database contents (up to 200 records per request).
    fetchAnalytics("transactions", { per_page: 200, page: 1 }).then(function (payload) {
      var rows = [["transaction_id", "beneficiary_id", "timestamp", "latitude", "longitude", "ration_type", "quantity"]];
      (payload.rows || []).forEach(function (t) {
        rows.push([t.transaction_id, t.beneficiary_id, t.timestamp, t.latitude, t.longitude, t.ration_type, t.quantity]);
      });
      download("rationai_dataset.csv", toCsv(rows), "text/csv");
      toast("Database exported to CSV (" + payload.total + " total records)", "success");
    }).catch(function (err) {
      toast("Could not export: " + (err.message || "analytics unavailable"), "error");
    });
  }

  function anomalyCsv() {
    if (!state.result) return;
    var rows = [["anomaly_id", "anomaly_type", "beneficiary_id", "transaction_ids", "severity"]];
    (state.result.anomalies || []).forEach(function (a) {
      rows.push([a.anomaly_id, a.anomaly_type, a.beneficiary_id, (a.transaction_ids || []).join("|"), a.severity]);
    });
    download("rationai_anomalies.csv", toCsv(rows), "text/csv");
    toast("Anomaly report exported to CSV", "success");
  }

  function analysisCsv() {
    if (!state.result) return;
    var rows = [["alert_id", "case_id", "finding_id", "anomaly_id", "severity", "status", "time_difference_minutes", "distance_km", "message"]];
    var chain = alertChain();
    if (chain) {
      rows.push([chain.alert.alert_id, chain.alert.case_id,
        (chain.findings[0] || {}).finding_id || "",
        (chain.anomalies[0] || {}).anomaly_id || "",
        chain.alert.severity, chain.alert.status,
        chain.findings[0] && chain.findings[0].evidence ? chain.findings[0].evidence.time_difference_minutes : "",
        chain.findings[0] && chain.findings[0].evidence ? chain.findings[0].evidence.distance_km : "",
        chain.alert.message]);
    }
    download("rationai_analysis.csv", toCsv(rows), "text/csv");
    toast("Analysis report exported to CSV", "success");
  }

  /* ------------------------------------------------------------------ *
   *  Settings
   * ------------------------------------------------------------------ */
  function renderSettings() {
    var v = $view();
    var meta = state.dataset && state.dataset.metadata ? state.dataset.metadata : null;
    var health = state.health;
    var llm = health && health.checks && health.checks.llm ? health.checks.llm : null;
    var config = health && health.checks && health.checks.config ? health.checks.config : null;

    v.innerHTML = viewHead("Settings", "System configuration, dataset details, and demo controls.");

    v.insertAdjacentHTML("beforeend",
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>Dataset</h3><p class="card-sub">Synthetic demo data</p></div></div><div class="card-body">' +
          '<div class="kv">' +
            '<div class="kv-item"><dt>Name</dt><dd>' + escapeHtml(meta ? meta.dataset_name : "—") + "</dd></div>" +
            '<div class="kv-item"><dt>Version</dt><dd>' + escapeHtml(meta ? meta.version : "—") + "</dd></div>" +
            '<div class="kv-item"><dt>Label</dt><dd>' + escapeHtml(meta ? meta.label : "—") + "</dd></div>" +
            '<div class="kv-item"><dt>Transactions</dt><dd>' + transactions().length + "</dd></div>" +
            '<div class="kv-item"><dt>Beneficiaries</dt><dd>' + beneficiaries().length + "</dd></div>" +
            '<div class="kv-item"><dt>Coverage</dt><dd>' + escapeHtml(meta ? meta.time_window : "—") + "</dd></div>" +
          "</div>" +
          '<p style="font-size:12.5px;color:var(--text-2);margin-top:12px">' + escapeHtml(meta ? meta.description : "") + "</p>" +
        "</div></div>" +
        '<div class="card"><div class="card-head"><div><h3>Detection configuration</h3><p class="card-sub">Shared pattern thresholds</p></div></div><div class="card-body">' +
          '<div class="kv">' +
            '<div class="kv-item"><dt>Pattern</dt><dd>Rapid geographic transaction</dd></div>' +
            '<div class="kv-item"><dt>Rule</dt><dd>' + escapeHtml(config ? config.detail : "—") + "</dd></div>" +
            '<div class="kv-item"><dt>Severity</dt><dd>High</dd></div>' +
            '<div class="kv-item"><dt>Engine</dt><dd>Deterministic code + optional LLM narratives</dd></div>' +
          "</div>" +
        "</div></div>" +
      "</div></section>" +
      '<section class="section"><div class="grid cols-2">' +
        '<div class="card"><div class="card-head"><div><h3>AI narratives (Phase 10)</h3><p class="card-sub">Optional LLM-written explanations</p></div></div><div class="card-body">' +
          '<div style="display:flex;align-items:center;gap:10px">' +
            '<span class="badge ' + (llm && llm.detail.indexOf("enabled") === 0 ? "ai" : "neutral") + '"><span class="dot"></span>' + escapeHtml(llm ? llm.detail : "unknown") + "</span>" +
          "</div>" +
          '<p style="font-size:12.5px;color:var(--text-2);margin-top:10px">When enabled, the model writes Agent 2 explanations, Agent 3 summaries, and Agent 4 messages. All calculations remain deterministic; failures fall back to templates. The API key stays server-side and is never shown here.</p>' +
        "</div></div>" +
        '<div class="card"><div class="card-head"><div><h3>Demo controls</h3><p class="card-sub">Session state</p></div></div><div class="card-body">' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
            '<a class="btn btn-primary" href="#/analysis">Run analysis</a>' +
            '<button class="btn btn-secondary" id="settings-reset" type="button">Reset demo state</button>' +
            '<a class="btn btn-secondary" href="' + API_BASE + '/api/health" target="_blank" rel="noopener">Health JSON</a>' +
          "</div>" +
          '<p style="font-size:12.5px;color:var(--text-2);margin-top:10px">Results are session-only: refreshing the browser returns to a clean state. Resetting does not delete the source dataset.</p>' +
        "</div></div>" +
      "</div></section>" +
      '<section class="section"><div class="card"><div class="card-head"><div><h3>System status</h3><p class="card-sub">Phase 14 — live readiness checks; no secrets are shown</p></div></div><div class="card-body">' +
        '<div id="sys-status">' + skeleton() + "</div>" +
        '<p class="kicker" style="margin-top:16px">Audit trail <span class="hint">append-only operational log</span></p>' +
        '<div id="sys-audit">' + skeleton() + "</div>" +
      "</div></div></section>");

    loadSystemStatus();
    var resetBtn = $id("settings-reset");
    if (resetBtn) resetBtn.addEventListener("click", resetDemo);
  }

  function loadSystemStatus() {
    fetchJson(API_BASE + "/api/ready", {}, 8000).then(function (ready) {
      var host = $id("sys-status");
      if (!host) return;
      var checks = ready.checks || {};
      var tone = { READY: "success", CONFIGURED: "success",
                   NOT_CONFIGURED: "neutral", ERROR: "error", CONNECTED: "success" };
      var rows = Object.keys(checks).map(function (k) {
        var v = checks[k];
        return '<div class="kv-item"><dt>' + escapeHtml(k.replace(/_/g, " ")) +
          "</dt><dd><span class=\"badge " + (tone[v] || "neutral") + "\">" +
          escapeHtml(v) + "</span></dd></div>";
      }).join("");
      host.innerHTML = '<div class="kv">' + rows + "</div>" +
        '<p style="font-size:12px;color:var(--text-3);margin-top:10px">Checked at ' +
        escapeHtml(ready.timestamp || "") + "</p>";
    }).catch(function () {
      var host = $id("sys-status");
      if (host) host.innerHTML = '<p style="color:var(--text-2);font-size:13px">Unable to load system status.</p>';
    });
    fetchJson(API_BASE + "/api/audit?limit=8", {}, 8000).then(function (payload) {
      var host = $id("sys-audit");
      if (!host) return;
      var rows = (payload.entries || []).map(function (e) {
        return '<div class="cc-lineage-item"><span class="cc-lineage-id">' +
          escapeHtml((e.created_at || "").slice(11, 19)) + "</span><span>" +
          escapeHtml(e.action || "") + "</span><span>" +
          escapeHtml(e.entity_type ? (e.entity_type + " " + (e.entity_id || "")) : "") +
          "</span></div>";
      }).join("");
      host.innerHTML = rows || '<p style="color:var(--text-3);font-size:13px">No audit entries yet.</p>';
    }).catch(function () {
      var host = $id("sys-audit");
      if (host) host.innerHTML = '<p style="color:var(--text-2);font-size:13px">Audit trail unavailable.</p>';
    });
  }

  /* ------------------------------------------------------------------ *
   *  Charts (SVG, dependency-free)
   * ------------------------------------------------------------------ */
  function sparkline(values) {
    if (!values || !values.length) return "";
    var w = 120, h = 26, max = Math.max.apply(null, values), min = Math.min.apply(null, values);
    var range = max - min || 1;
    var pts = values.map(function (val, i) {
      var x = i / (values.length - 1) * w;
      var y = h - 3 - (val - min) / range * (h - 6);
      return Math.round(x) + "," + Math.round(y);
    }).join(" ");
    var area = "0," + h + " " + pts + " " + w + "," + h;
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" height="' + h + '" aria-hidden="true">' +
      '<polygon points="' + area + '" fill="rgba(5,150,105,.10)"/>' +
      '<polyline points="' + pts + '" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }

  function chartGrid(w, h, nBuckets) {
    var out = "";
    for (var i = 0; i <= 4; i++) {
      var y = 12 + i * (h - 24) / 4;
      out += '<line class="grid-line" x1="40" y1="' + y + '" x2="' + (w - 8) + '" y2="' + y + '"/>';
      var val = Math.round((4 - i) / 4 * 100);
      out += '<text class="axis-label" x="34" y="' + (y + 4) + '" text-anchor="end">' + val + "</text>";
    }
    return out;
  }

  function chartSeries(w, h, s, visible) {
    var n = s.buckets.length;
    if (!n) return "";
    var max = 1;
    s.types.forEach(function (rt) {
      s.data[rt].forEach(function (v) { if (v > max) max = v; });
    });
    var xPad = 44, right = 8, top = 12, bottom = 26;
    var plotW = w - xPad - right, plotH = h - top - bottom;
    var out = "";
    visible.forEach(function (rt, idx) {
      var typeIndex = s.types.indexOf(rt);
      var color = colorFor(typeIndex);
      var pts = s.data[rt].map(function (v, i) {
        var x = n === 1 ? xPad + plotW / 2 : xPad + i / (n - 1) * plotW;
        var y = top + plotH - (v / max) * plotH;
        return [x, y];
      });
      var line = pts.map(function (p, i) { return (i ? "L" : "M") + Math.round(p[0]) + " " + Math.round(p[1]); }).join(" ");
      var area = line + " L" + Math.round(pts[pts.length - 1][0]) + " " + (top + plotH) + " L" + Math.round(pts[0][0]) + " " + (top + plotH) + " Z";
      out += '<path d="' + area + '" fill="' + color + '" opacity="0.10"/>';
      out += '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
      pts.forEach(function (p, i) {
        out += '<circle class="pt" cx="' + Math.round(p[0]) + '" cy="' + Math.round(p[1]) + '" r="3.2" fill="' + color + '" stroke="#fff" stroke-width="1.2" data-b="' + i + '" data-rt="' + escapeHtml(rt) + '" style="cursor:pointer"/>';
      });
    });
    // x labels (a few)
    var labelStep = Math.max(1, Math.ceil(n / 6));
    for (var i = 0; i < n; i += labelStep) {
      var x = n === 1 ? xPad + plotW / 2 : xPad + i / (n - 1) * plotW;
      out += '<text class="axis-label" x="' + Math.round(x) + '" y="' + (h - 6) + '" text-anchor="middle">' + escapeHtml(shortLabel(s.buckets[i])) + "</text>";
    }
    return out;
  }

  function shortLabel(bucket) {
    if (bucket.length === 7) { // YYYY-MM
      var parts = bucket.split("-");
      var names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      return names[Number(parts[1]) - 1] + " " + parts[0].slice(2);
    }
    if (bucket.indexOf("W") > 0) return bucket.slice(2);
    return bucket.slice(5); // MM-DD
  }

  function bindChartTooltip(el, s, visible, mode) {
    var wrap = el.querySelector(".chart-wrap");
    var tip = el.querySelector("#trend-tip");
    if (!wrap || !tip) return;
    function move(ev) {
      var svg = wrap.querySelector("svg");
      if (!svg) return;
      var rect = svg.getBoundingClientRect();
      var x = ev.clientX - rect.left, y = ev.clientY - rect.top;
      var target = ev.target;
      if (target.classList && target.classList.contains("pt")) {
        var i = Number(target.getAttribute("data-b"));
        var rt = target.getAttribute("data-rt");
        var lines = ["<div class='tip-title'>" + escapeHtml(shortLabel(s.buckets[i])) + "</div>"];
        visible.forEach(function (t) {
          lines.push("<div class='tip-row'><span>" + escapeHtml(t) + "</span><strong>" + fmtNumber(s.data[t][i]) + " kg</strong></div>");
        });
        tip.innerHTML = lines.join("");
        tip.style.opacity = "1";
        tip.style.left = Math.min(x + 12, wrap.clientWidth - 170) + "px";
        tip.style.top = Math.max(8, y - 10) + "px";
      } else {
        tip.style.opacity = "0";
      }
    }
    wrap.addEventListener("mousemove", move);
    wrap.addEventListener("mouseleave", function () { tip.style.opacity = "0"; });
  }

  function renderGeo(el, tx) {
    var lats = tx.map(function (t) { return t.latitude; });
    var lons = tx.map(function (t) { return t.longitude; });
    var latMin = Math.min.apply(null, lats), latMax = Math.max.apply(null, lats);
    var lonMin = Math.min.apply(null, lons), lonMax = Math.max.apply(null, lons);
    var rows = 3, cols = 4;
    var cells = {};
    tx.forEach(function (t) {
      var r = Math.min(rows - 1, Math.floor((t.latitude - latMin) / ((latMax - latMin) || 1) * rows));
      var c = Math.min(cols - 1, Math.floor((t.longitude - lonMin) / ((lonMax - lonMin) || 1) * cols));
      var k = r + "-" + c;
      cells[k] = (cells[k] || 0) + (t.quantity || 0);
    });
    var max = Math.max.apply(null, Object.keys(cells).map(function (k) { return cells[k]; }).concat([1]));
    function color(v) {
      var p = v / max;
      if (p === 0) return "#F1F5F9";
      if (p < 0.34) return "#D1FAE5";
      if (p < 0.67) return "#6EE7B7";
      return "#059669";
    }
    var html = '<div class="geo-heat" style="grid-template-columns:repeat(' + cols + ',1fr)">';
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var v = cells[r + "-" + c] || 0;
        var latBand = (latMin + r / rows * (latMax - latMin)).toFixed(1);
        var lonBand = (lonMin + c / cols * (lonMax - lonMin)).toFixed(1);
        html += '<div class="geo-cell" style="background:' + color(v) + '" title="Band ' + latBand + ', ' + lonBand + '">' + (v ? fmtNumber(v) + " kg" : "·") + "</div>";
      }
    }
    html += "</div><div class=\"geo-legend\"><span class=\"swatch\" style=\"background:#F1F5F9\"></span> none" +
      '<span class="swatch" style="background:#D1FAE5"></span> low' +
      '<span class="swatch" style="background:#6EE7B7"></span> medium' +
      '<span class="swatch" style="background:#059669"></span> high</div>';
    el.innerHTML = html;
  }

  /* ------------------------------------------------------------------ *
   *  Shared rendering bits
   * ------------------------------------------------------------------ */
  function emptyState(iconName, title, detail, actionRoute) {
    var action = actionRoute
      ? '<div class="empty-actions"><a class="btn btn-primary btn-sm" href="#/' + actionRoute + '">Go to ' + escapeHtml(ROUTES[actionRoute].title) + "</a></div>"
      : "";
    return '<div class="empty-state"><div class="empty-icon">' + icon(iconName, 24) +
      "</div><h3>" + escapeHtml(title) + "</h3><p>" + escapeHtml(detail) + "</p>" + action + "</div>";
  }

  function emptyCard(iconName, title, detail) {
    return '<section class="section"><div class="card"><div class="card-body">' + emptyState(iconName, title, detail, null) + "</div></div></section>";
  }

  function renderInsightPreview(el) {
    var chain = alertChain();
    if (!chain) {
      el.innerHTML = emptyState("sparkles", "No insights yet", "Run the multi-agent analysis to generate AI insights.", "analysis");
      return;
    }
    var finding = chain.findings[0] || null;
    var evidence = finding && finding.evidence ? finding.evidence : {};
    el.innerHTML =
      '<div class="ai-text" style="font-size:13.5px;line-height:1.55">' + escapeHtml((chain.alert.message || "").slice(0, 220)) + "</div>" +
      '<div class="ai-meta"><span class="badge warning"><span class="dot"></span>Anomaly ' + escapeHtml((chain.anomalies[0] || {}).anomaly_id || "") + "</span>" +
      '<span class="badge ai">' + (evidence.time_difference_minutes != null ? evidence.time_difference_minutes + " min" : "") + (evidence.distance_km != null ? " · " + evidence.distance_km + " km" : "") + "</span></div>" +
      '<div class="ai-actions"><a class="btn btn-primary btn-sm" href="#/insights">View AI Insights</a>' +
      '<a class="btn btn-secondary btn-sm" href="#/alerts">Review alert</a></div>';
  }

  /* ------------------------------------------------------------------ *
   *  Shell behaviors
   * ------------------------------------------------------------------ */
  function updateNotifDot() {
    var active = (state.alertSummary && state.alertSummary.total_active) || 0;
    var dot = $id("notif-dot");
    if (dot) dot.hidden = !active;
    var count = $id("nav-alert-count");
    if (count) {
      count.hidden = !active;
      count.textContent = String(active);
    }
  }

  function renderNotifications() {
    var box = $id("notif-drop");
    if (!box) return;
    var active = (state.alertSummary && state.alertSummary.total_active) || 0;
    if (!active) {
      box.innerHTML = '<div class="notif-empty">No open alerts. All monitored conditions are within configured thresholds.</div>';
      return;
    }
    fetchJson(API_BASE + "/api/alerts?status=OPEN&per_page=10", {}, 10000).then(function (payload) {
      var alerts = payload.alerts || [];
      if (!alerts.length) {
        box.innerHTML = '<div class="notif-empty">' + active + " active alert(s) — open the Alert Center to review.</div>";
        return;
      }
      box.innerHTML = alerts.map(function (a) {
        var sev = a.severity === "CRITICAL" || a.severity === "HIGH" ? "var(--error)" : a.severity === "MEDIUM" ? "var(--warning)" : "var(--success)";
        return '<a class="notif-item" href="#/alerts"><span class="notif-dot-s" style="background:' + sev + '"></span>' +
          '<div class="notif-body"><span class="notif-title">' + escapeHtml(a.alert_id) + " · " + escapeHtml(a.severity) + " · " + escapeHtml(a.status) + "</span>" +
          '<span class="notif-sub">' + escapeHtml((a.title || "").slice(0, 80)) + "</span></div></a>";
      }).join("");
    }).catch(function () {
      box.innerHTML = '<div class="notif-empty">' + active + " active alert(s) — open the Alert Center to review.</div>";
    });
  }

  function closeAllDropdowns() {
    var notifDrop = $id("notif-drop"), profileDrop = $id("profile-drop");
    if (notifDrop) notifDrop.hidden = true;
    if (profileDrop) profileDrop.hidden = true;
    var nb = $id("notif-button"), pb = $id("profile-button");
    if (nb) nb.setAttribute("aria-expanded", "false");
    if (pb) pb.setAttribute("aria-expanded", "false");
  }

  function toggleDropdown(buttonId, dropId) {
    var btn = $id(buttonId), drop = $id(dropId);
    if (!btn || !drop) return;
    var willOpen = drop.hidden;
    closeAllDropdowns();
    drop.hidden = !willOpen;
    btn.setAttribute("aria-expanded", willOpen ? "true" : "false");
    if (willOpen && buttonId === "notif-button") renderNotifications();
  }

  function openMobileNav() {
    state.mobileNavOpen = true;
    document.body.classList.add("nav-open");
    $id("sidebar").style.transform = "";
  }

  function closeMobileNav() {
    state.mobileNavOpen = false;
    document.body.classList.remove("nav-open");
  }

  /* ---------- Command palette ---------- */
  function loadSearchExtra() {
    // Command palette entity index — reuses existing endpoints, cached 2 min.
    if (state.searchExtra && Date.now() - state.searchExtraAt < 120000) {
      renderSearchResults($id("search-input").value);
      return;
    }
    state.searchExtraAt = Date.now();
    Promise.all([
      fetchJson(API_BASE + "/api/datasets", {}, 8000).catch(function () { return { datasets: [] }; }),
      fetchJson(API_BASE + "/api/alerts?per_page=30", {}, 8000).catch(function () { return { alerts: [] }; }),
      fetchJson(API_BASE + "/api/command-center", {}, 12000).catch(function () { return { filter_options: {} }; })
    ]).then(function (results) {
      state.searchExtra = {
        datasets: (results[0] && results[0].datasets) || [],
        alerts: (results[1] && results[1].alerts) || [],
        options: (results[2] && results[2].filter_options) || { fps: [], districts: [], commodities: [] }
      };
      renderSearchResults($id("search-input").value);
    });
  }

  function searchItemsFor(query) {
    var q = (query || "").toLowerCase().trim();
    var out = [];
    var ex = state.searchExtra || { datasets: [], alerts: [], options: {} };
    function push(kind, title, sub, payload, group) {
      if (q && (title + " " + sub).toLowerCase().indexOf(q) === -1) return;
      out.push({ kind: kind, title: title, sub: sub, group: group, payload: payload });
    }
    // Views always first so quick navigation stays one keystroke away.
    var base = state.searchIndex.filter(function (it) {
      if (!q) return it.kind === "View";
      return (it.title + " " + it.sub).toLowerCase().indexOf(q) !== -1 && it.kind === "View";
    }).map(function (it) { it.group = 0; return it; }).slice(0, 10);
    out = out.concat(base);
    function matchesQ(title, sub) {
      return !q || (title + " " + sub).toLowerCase().indexOf(q) !== -1;
    }
    var ds = (ex.datasets || []).filter(function (d) {
      return matchesQ(d.dataset_name || ("Dataset #" + d.id), "dataset");
    }).slice(0, 5);
    ds.forEach(function (d) {
      push("Dataset", d.dataset_name || ("Dataset #" + d.id),
        (d.record_count != null ? fmtNumber(d.record_count) + " records" : "") + (d.status ? " · " + d.status : ""),
        { datasetId: d.id }, 1);
    });
    (ex.alerts || []).filter(function (a) {
      return matchesQ(a.alert_id, a.title || "");
    }).slice(0, 5).forEach(function (a) {
      push("Alert", a.alert_id, (a.title || "") + (a.severity ? " · " + a.severity : ""), { alertId: a.alert_id }, 2);
    });
    (ex.options.fps || []).filter(function (f) { return matchesQ(f, "FPS center"); })
      .slice(0, q ? 10 : 4).forEach(function (f) {
        push("FPS", f, "Open Command Center scoped to this center", { filterKey: "fps", filterValue: f }, 3);
      });
    (ex.options.districts || []).filter(function (d) { return matchesQ(d, "district"); })
      .slice(0, q ? 10 : 4).forEach(function (d) {
        push("District", d, "Open Command Center scoped to this district", { filterKey: "district", filterValue: d }, 3);
      });
    (ex.options.commodities || []).filter(function (c) { return matchesQ(c, "commodity"); })
      .slice(0, q ? 10 : 4).forEach(function (c) {
        push("Commodity", c, "Open Command Center scoped to this commodity", { filterKey: "commodity", filterValue: c }, 3);
      });
    if (!q) return out.slice(0, 30);
    // With a query, also surface matching beneficiaries / transactions.
    var records = state.searchIndex.filter(function (it) {
      if (it.kind === "View") return false;
      return (it.title + " " + it.sub).toLowerCase().indexOf(q) !== -1;
    }).slice(0, 6);
    return out.concat(records).slice(0, 30);
  }

  function openSearch() {
    var overlay = $id("search-overlay");
    overlay.hidden = false;
    state.searchReturnFocus = document.activeElement;
    var input = $id("search-input");
    input.value = "";
    input.focus();
    loadSearchExtra();
    renderSearchResults("");
  }

  function closeSearch() {
    $id("search-overlay").hidden = true;
    if (state.searchReturnFocus && state.searchReturnFocus.focus) {
      try { state.searchReturnFocus.focus(); } catch (e) { /* noop */ }
    }
    state.searchReturnFocus = null;
  }

  function renderSearchResults(query) {
    var box = $id("search-results");
    var q = (query || "").toLowerCase().trim();
    var items = searchItemsFor(query);
    if (!items.length) {
      box.innerHTML = '<div class="search-empty">No matches for "' + escapeHtml(query) + '"</div>';
      box.setAttribute("aria-label", "No search results");
      return;
    }
    var html = "";
    var lastGroup = -1;
    var idx = 0;
    items.forEach(function (it) {
      if (it.group !== lastGroup) {
        var names = ["Navigate", "Datasets", "Alerts", "Entities"];
        html += '<p class="search-group">' + names[it.group] + "</p>";
        lastGroup = it.group;
      }
      html += '<button type="button" class="search-item' + (idx === 0 ? " is-active" : "") + '" data-i="' + idx + '">' +
        '<span class="si-kind">' + escapeHtml(it.kind) + "</span>" +
        '<span style="min-width:0"><span class="si-title" style="display:block">' + escapeHtml(it.title) + '</span>' +
        '<span class="si-sub">' + escapeHtml(it.sub || "") + "</span></span></button>";
      idx += 1;
    });
    box.innerHTML = html;
    box.setAttribute("aria-label", items.length + " search results");
    box.querySelectorAll(".search-item").forEach(function (b) {
      b.addEventListener("click", function () { activateSearchItem(Number(b.getAttribute("data-i"))); });
    });
    box._items = items;
    box._active = 0;
  }

  function activateSearchItem(i) {
    var box = $id("search-results");
    var items = box._items || [];
    var item = items[i];
    if (!item) return;
    closeSearch();
    var p = item.payload || {};
    function go(target) {
      // Re-render immediately when already on the target route (no hashchange).
      if (location.hash === target) renderRoute();
      else location.hash = target;
    }
    if (item.beneficiary) {
      state.beneficiaryQuery = "";
      state.beneficiaryStatus = "all";
      go("#/beneficiaries");
      setTimeout(function () {
        if (state.beneficiaryId !== item.beneficiary) { state.beneficiaryId = item.beneficiary; openBeneficiary(item.beneficiary); }
      }, 60);
    } else if (p.datasetId != null) {
      state.analysisDataset = "real";
      state.analysisImportId = p.datasetId;
      go("#/analysis");
    } else if (p.alertId) {
      state.alertCenter.q = p.alertId;
      go("#/alerts");
    } else if (p.filterKey) {
      state.commandCenter.payload = null;
      state.commandCenter.filters = state.commandCenter.filters || {};
      state.commandCenter.filters[p.filterKey] = p.filterValue;
      go("#/command");
    } else {
      go("#/" + item.route);
      if (item.alertId) setTimeout(function () { state.alertFilter = "all"; }, 0);
    }
  }

  /* ------------------------------------------------------------------ *
   *  Auth gate (Phase 14, opt-in)
   * ------------------------------------------------------------------ */
  function checkAuth() {
    if (state.auth.checked) return;
    fetchJson(API_BASE + "/api/auth/status", {}, 6000).then(function (payload) {
      state.auth.checked = true;
      state.auth.enabled = !!payload.auth_enabled;
      state.auth.authenticated = !!payload.authenticated;
      document.getElementById("profile-logout").hidden = !state.auth.authenticated;
      if (state.auth.enabled && !state.auth.authenticated) showAuthOverlay();
    }).catch(function () {
      // Server unreachable — leave the dashboard to render its own errors.
      state.auth.checked = true;
    });
  }

  function showAuthOverlay() {
    state.auth.overlayShown = true;
    var overlay = $id("auth-overlay");
    overlay.hidden = false;
    var input = $id("auth-token");
    input.value = "";
    $id("auth-error").hidden = true;
    input.focus();
  }

  function hideAuthOverlay() {
    state.auth.overlayShown = false;
    $id("auth-overlay").hidden = true;
  }

  function doAuthLogin(token) {
    var submit = $id("auth-submit");
    submit.disabled = true;
    var errEl = $id("auth-error");
    fetchJson(API_BASE + "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token })
    }, 10000).then(function () {
      state.auth.authenticated = true;
      document.getElementById("profile-logout").hidden = false;
      hideAuthOverlay();
      location.reload();
    }).catch(function (err) {
      submit.disabled = false;
      var msg = (err && err.serverMessage) || "Sign-in failed. Check the access token and try again.";
      if (err && err.httpStatus === 429) msg = "Too many sign-in attempts. Wait a moment and try again.";
      errEl.textContent = msg;
      errEl.hidden = false;
      $id("auth-token").focus();
    });
  }

  function doLogout() {
    fetchJson(API_BASE + "/api/auth/logout", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}"
    }, 10000).then(function () {
      location.reload();
    }).catch(function () {
      location.reload();
    });
  }

  /* ------------------------------------------------------------------ *
   *  Init
   * ------------------------------------------------------------------ */
  function init() {
    // Inline icons
    document.querySelectorAll("[data-icon]").forEach(function (el) {
      el.innerHTML = icon(el.getAttribute("data-icon"), el.classList.contains("nav-icon") ? 19 : 18);
    });

    // Router
    window.addEventListener("hashchange", function () { renderRoute(); });

    // Sidebar collapse (desktop) / toggle (mobile)
    $id("sidebar-collapse").addEventListener("click", function () {
      state.collapsed = !state.collapsed;
      document.querySelector(".app").classList.toggle("is-collapsed", state.collapsed);
      $id("sidebar-collapse").setAttribute("aria-expanded", String(!state.collapsed));
    });
    $id("nav-toggle").addEventListener("click", function () {
      var app = document.querySelector(".app");
      var isOpen = app.classList.contains("is-collapsed");
      app.classList.toggle("is-collapsed", !isOpen);
    });

    // Dropdowns
    $id("notif-button").addEventListener("click", function () { toggleDropdown("notif-button", "notif-drop"); });
    $id("profile-button").addEventListener("click", function () { toggleDropdown("profile-button", "profile-drop"); });
    document.addEventListener("click", function (ev) {
      if (!ev.target.closest(".menu-wrap")) closeAllDropdowns();
    });
    $id("profile-reset").addEventListener("click", function () { closeAllDropdowns(); resetDemo(); });
    $id("profile-logout").addEventListener("click", function () { closeAllDropdowns(); doLogout(); });

    // Auth gate
    $id("auth-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      doAuthLogin($id("auth-token").value.trim());
    });
    checkAuth();

    // Search
    $id("search-trigger").addEventListener("click", openSearch);
    document.addEventListener("keydown", function (ev) {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); openSearch(); return; }
      if (ev.key === "Escape") {
        if (!$id("search-overlay").hidden) closeSearch();
        closeAllDropdowns();
        closeMobileNav();
      }
    });
    $id("search-input").addEventListener("input", function () { renderSearchResults(this.value); });
    $id("search-input").addEventListener("keydown", function (ev) {
      var box = $id("search-results");
      var items = box.querySelectorAll(".search-item");
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        var idx = Array.prototype.indexOf.call(items, box.querySelector(".is-active"));
        var next = ev.key === "ArrowDown" ? Math.min(idx + 1, items.length - 1) : Math.max(idx - 1, 0);
        items.forEach(function (b, i) { b.classList.toggle("is-active", i === next); });
        box._active = next;
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        var active = box.querySelector(".is-active");
        if (active) active.click();
      }
    });
    $id("search-overlay").addEventListener("click", function (ev) {
      if (ev.target === this) closeSearch();
    });

    // Delegated clicks: beneficiary rows / view buttons
    $id("view").addEventListener("click", function (ev) {
      var row = ev.target.closest("tr[data-ben]");
      if (row) { openBeneficiary(row.getAttribute("data-ben")); return; }
      var btn = ev.target.closest("button[data-view-ben]");
      if (btn) { openBeneficiary(btn.getAttribute("data-view-ben")); }
    });

    buildSearchIndex();
    loadHealth();
    loadAlertSummary();
    loadDataset().catch(function () {
      if ($id("view")) {
        $id("view").innerHTML = viewHead("Backend unreachable", "The dashboard could not load the dataset.") +
          '<section class="section"><div class="card"><div class="card-body">' +
          emptyState("alert", "Could not reach the RationAI backend", "Check that the server is running, then reload.", null) +
          "</div></div></section>";
      }
    });

    renderRoute();
  }

  init();
})();
