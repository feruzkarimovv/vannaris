/* Query evidence stays aligned with its run. Old questions are not inferred
   from today's query text, and incomplete responses never become a zero. */
(function () {
  "use strict";
  function init(options) {
    options = options || {};
    var D = window.SB_DATA;
    var desired = D.latest.week;
    window.SB_DETAIL_STATUS = { week: desired, state: "loading" };
    function ready() {
      if (!window.SB_DETAIL || window.SB_DETAIL.week !== desired) return failed();
      window.SB_DETAIL_STATUS = { week: desired, state: "ready" };
      build(window.SB_DETAIL);
      if (options.onDetail) options.onDetail(window.SB_DETAIL);
    }
    function failed() {
      window.SB_DETAIL_STATUS = { week: desired, state: "unavailable" };
      unavailable();
      if (options.onUnavailable) options.onUnavailable();
    }
    if (window.SB_DETAIL && window.SB_DETAIL.week === desired) return ready();
    document.getElementById("q-count").textContent = "Loading this run's query evidence…";
    var script = document.createElement("script");
    script.src = "data/detail-" + encodeURIComponent(desired) + ".js";
    script.onload = ready;
    script.onerror = failed;
    document.head.appendChild(script);
  }
  function unavailable() {
    document.getElementById("q-count").textContent = "Query detail unavailable for this snapshot";
    document.getElementById("query-table-wrap").hidden = true;
    var empty = document.getElementById("query-empty");
    empty.hidden = false;
    empty.textContent = "The query detail file could not load for this run. Retry the page or download the selected run's CSVs from the data page. Current questions are not substituted for an archived snapshot.";
    ["q-category", "q-search", "q-prev", "q-next"].forEach(function (id) { document.getElementById(id).disabled = true; });
  }
  function build(X) {
    var D = window.SB_DATA, h = window.SBCharts.helpers;
    var vendors = D.latest.vendors;
    var params = new URLSearchParams(location.search);
    var size = 15, page = Math.max(1, parseInt(params.get("page") || "1", 10) || 1);
    var selected = null, lastFocus = null;
    var byQuery = {};
    X.rows.forEach(function (r) { (byQuery[r.q] = byQuery[r.q] || {})[r.v] = r; });
    var head = document.getElementById("query-head");
    var tbody = document.querySelector("#query-table tbody");
    var search = document.getElementById("q-search"), category = document.getElementById("q-category");
    var count = document.getElementById("q-count"), prev = document.getElementById("q-prev"), next = document.getElementById("q-next");
    var dialog = document.getElementById("query-dialog");
    head.textContent = "";
    ["Query", "Category"].concat(vendors.map(function (v) { return v.label; })).forEach(function (t) {
      var th = document.createElement("th"); th.scope = "col"; th.textContent = t; head.appendChild(th);
    });
    category.replaceChildren(category.options[0]);
    D.categories.forEach(function (c) { var o = document.createElement("option"); o.value = c.id; o.textContent = c.label; category.appendChild(o); });
    category.value = params.get("category") || "";
    search.value = params.get("q") || "";
    function updateUrl() {
      var url = new URL(location.href);
      [["q",search.value.trim()],["category",category.value],["page",page > 1 ? String(page) : ""],["query",selected || ""]].forEach(function (entry) {
        if (entry[1]) url.searchParams.set(entry[0], entry[1]); else url.searchParams.delete(entry[0]);
      });
      history.replaceState(null, "", url.href);
    }
    function state(r) {
      if (!r) return "No public response record";
      if (r.e || r.error) return "Vendor request failed; not judged";
      if (r.m == null) {
        var missing = r.missing_judges || X.judges.filter(function (_, i) { return !r.s || r.s[i] == null; });
        return "Incomplete judging" + (missing.length ? ": missing " + missing.join(", ") : "");
      }
      return "Complete ensemble";
    }
    function render() {
      var term = search.value.trim().toLowerCase();
      var rows = X.queries.filter(function (q) { return (!category.value || q.c === category.value) && (!term || q.t.toLowerCase().includes(term)); });
      var pages = Math.max(1, Math.ceil(rows.length / size)); page = Math.min(page, pages);
      var shown = rows.slice((page - 1) * size, page * size);
      tbody.textContent = "";
      shown.forEach(function (q) {
        var tr = document.createElement("tr");
        var name = document.createElement("th"); name.scope = "row"; name.textContent = q.t; tr.appendChild(name);
        var cat = document.createElement("td"); cat.textContent = h.catLabel[q.c] || q.c; tr.appendChild(cat);
        vendors.forEach(function (v) {
          var r = (byQuery[q.id] || {})[v.vendor];
          var td = document.createElement("td"); td.className = "num";
          td.textContent = r && r.m != null ? Number(r.m).toFixed(1) : "Incomplete";
          td.title = state(r); tr.appendChild(td);
        });
        var action = name;
        var button = document.createElement("button"); button.type = "button"; button.className = "query-open"; button.textContent = "Inspect query";
        button.setAttribute("aria-label", "Inspect query: " + q.t); button.setAttribute("data-query-id", q.id);
        button.addEventListener("click", function () { open(q.id, button); }); action.appendChild(document.createElement("br")); action.appendChild(button); tbody.appendChild(tr);
      });
      count.textContent = rows.length + " of " + X.queries.length + " queries";
      document.getElementById("q-page").textContent = rows.length ? "Page " + page + " of " + pages + " · showing " + ((page - 1) * size + 1) + "–" + Math.min(page * size, rows.length) : "No matching queries";
      prev.disabled = page <= 1; next.disabled = page >= pages;
      document.getElementById("query-empty").hidden = rows.length > 0;
      document.getElementById("query-table-wrap").hidden = rows.length === 0;
      updateUrl();
    }
    function open(id, trigger) {
      var q = X.queries.filter(function (x) { return x.id === id; })[0]; if (!q) return;
      selected = id; lastFocus = trigger || document.activeElement;
      document.getElementById("query-dialog-question").textContent = q.t;
      document.getElementById("query-dialog-meta").textContent = (h.catLabel[q.c] || q.c) + " · " + window.SBSite.fmt.when(D.latest.ran_at) + " · query " + q.id;
      var body = document.getElementById("query-dialog-body"); body.textContent = "";
      var wrap = document.createElement("div"); wrap.className = "table-wrap"; wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "Individual judge scores; scroll for every column");
      var table = document.createElement("table"), thd = document.createElement("thead"), hr = document.createElement("tr");
      ["Vendor", "Median"].concat(X.judges, ["Status", "Latency", "Results"]).forEach(function (label) { var th=document.createElement("th"); th.scope="col"; th.textContent=label; hr.appendChild(th); }); thd.appendChild(hr);table.appendChild(thd);
      var bd = document.createElement("tbody");
      vendors.forEach(function (v) {
        var r = (byQuery[id] || {})[v.vendor];
        var tr = document.createElement("tr"); var name = document.createElement("th"); name.scope="row"; name.textContent=v.label;tr.appendChild(name);
        var values=[r && r.m != null ? Number(r.m).toFixed(1) : "Not scored"].concat(X.judges.map(function(_,i){return r && r.s && r.s[i]!=null ? Number(r.s[i]).toFixed(1) : "Missing";}),[state(r),r && r.l!=null ? r.l.toLocaleString()+" ms" : "Unavailable",r && r.n!=null ? r.n : "Unavailable"]);
        values.forEach(function(value){var td=document.createElement("td");td.textContent=value;tr.appendChild(td);});bd.appendChild(tr);
      });table.appendChild(bd);wrap.appendChild(table);body.appendChild(wrap);
      updateUrl();document.getElementById("query-permalink").href=location.href;
      if (typeof dialog.showModal === "function") dialog.showModal(); else dialog.setAttribute("open", "");
      document.getElementById("query-dialog-close").focus();
    }
    function dismiss() {
      if (typeof dialog.close === "function") dialog.close(); else {dialog.removeAttribute("open"); afterClose();}
    }
    function afterClose() { selected=null;updateUrl();if(lastFocus && document.contains(lastFocus))lastFocus.focus(); }
    dialog.addEventListener("close",afterClose);
    dialog.addEventListener("cancel",function(e){e.preventDefault();dismiss();});
    document.getElementById("query-dialog-close").addEventListener("click",dismiss);
    document.addEventListener("keydown",function(e){if(e.key==="Escape"&&dialog.hasAttribute("open")){e.preventDefault();dismiss();}});
    search.addEventListener("input",function(){page=1;render();});category.addEventListener("change",function(){page=1;render();});
    prev.addEventListener("click",function(){page--;render();});next.addEventListener("click",function(){page++;render();});
    var initialQuery=params.get("query");render();if(initialQuery)open(initialQuery,null);
  }
  window.SBExplorer={init:init};
})();
