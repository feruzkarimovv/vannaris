/* The public page explains how to run the demo; only the separately generated,
   explicitly synthetic site loads an execution manifest. */
(function () {
  "use strict";
  var menu = document.querySelector(".nav-toggle"), bar = document.querySelector(".navbar");
  menu.addEventListener("click", function () { var open = menu.getAttribute("aria-expanded") !== "true"; menu.setAttribute("aria-expanded", String(open)); if (open) bar.setAttribute("data-menu", "open"); else bar.removeAttribute("data-menu"); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { menu.setAttribute("aria-expanded", "false"); bar.removeAttribute("data-menu"); } });
  if (!window.SB_DATA || !window.SB_DATA.synthetic) return;
  fetch("demo.json").then(function (r) { if (!r.ok) throw new Error("Demo evidence unavailable"); return r.json(); }).then(function (D) {
    if (!D.synthetic || D.kind !== "synthetic_offline_demo") throw new Error("The manifest is not identified as synthetic");
    document.getElementById("demo-status").textContent = D.warning;
    document.getElementById("demo-setup").hidden = true; document.getElementById("demo-evidence").hidden = false;
    var controls = document.getElementById("demo-controls");
    function title(key) { return key.replace(/_/g, " "); }
    function show(stage) {
      controls.querySelectorAll("button").forEach(function (button) { button.setAttribute("aria-pressed", String(button.dataset.stage === stage.id)); });
      document.getElementById("demo-stage-title").textContent = stage.title;
      document.getElementById("demo-stage-status").textContent = stage.status;
      document.getElementById("demo-stage-detail").textContent = stage.detail;
      var metrics = document.getElementById("demo-stage-metrics"); metrics.textContent = "";
      Object.keys(stage.metrics || {}).forEach(function (key) { var row=document.createElement("div"),dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=title(key);dd.textContent=typeof stage.metrics[key] === "object" ? JSON.stringify(stage.metrics[key]) : String(stage.metrics[key]);row.appendChild(dt);row.appendChild(dd);metrics.appendChild(row); });
    }
    D.stages.forEach(function (stage) { var b=document.createElement("button");b.type="button";b.className="demo-step";b.dataset.stage=stage.id;b.textContent=stage.title;b.setAttribute("aria-pressed","false");b.addEventListener("click",function(){show(stage);});controls.appendChild(b); });
    (D.checks || []).forEach(function (check) {var row=document.createElement("div"),dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=(check.passed ? "Passed · " : "Failed · ")+check.title;dd.textContent=check.detail;row.appendChild(dt);row.appendChild(dd);document.getElementById("demo-checks").appendChild(row);});
    if(D.stages.length) show(D.stages[0]);
  }).catch(function () { document.getElementById("demo-status").textContent = "SYNTHETIC DEMO — execution evidence could not load. Regenerate the offline demo or retry this page. The setup instructions below remain available."; });
})();
