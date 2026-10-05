/* Select a frozen run before page/chart modules capture SB_DATA. Navigation
 * reloads a snapshot; historical query detail is loaded separately, never
 * borrowed from the latest run. No request is needed for the aggregate view. */
(function () {
  "use strict";
  var D = window.SB_DATA;
  if (!D || !D.latest) return;
  var params = new URLSearchParams(location.search);
  var wanted = params.get("run");
  window.SB_LATEST = D.latest;
  if (wanted && wanted !== D.latest.week) {
    var archive = D.all_weeks || {};
    var selected = Array.isArray(archive)
      ? archive.filter(function (w) { return w.week === wanted; })[0] : archive[wanted];
    if (selected) {
      D.latest = selected;
      window.SB_ARCHIVE = true;
      if (selected.categories) D.categories = selected.categories;
      /* File row counts belong to the selected export. Where an old manifest
       * is unavailable, show unknown counts rather than current-run counts. */
      D.export = Object.assign({}, D.export, selected.export || { week: selected.week,
        files: (D.export.files || []).map(function (f) {
          var copy = Object.assign({}, f);
          if (/-\d{4}-W\d{2}\./.test(copy.file)) {
            copy.file = copy.file.replace(/-\d{4}-W\d{2}(?=\.)/, "-" + selected.week);
            copy.rows = null;
          }
          return copy;
        }) });
    } else window.SB_RUN_ERROR = "That archived run is unavailable. Showing the latest published snapshot.";
  }
  window.SBRun = { week: D.latest.week, latest: window.SB_LATEST.week };
})();
