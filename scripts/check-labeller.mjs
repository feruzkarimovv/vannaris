/* Smoke test for the calibration labelling UI.
 *
 * This page is the only piece of the project a human spends a continuous hour
 * inside, and the expensive failure is silent: a label that renders fine but
 * never reaches localStorage is an hour of expert attention destroyed, noticed
 * only at export. So the things checked here are persistence and export shape
 * rather than appearance.
 *
 * Run:  node scripts/check-labeller.mjs [calibration-set-dir]
 * With no argument it picks the most recently written set under ./calibration.
 * Needs jsdom; exits 0 with a note if it is missing, like check-site.mjs.
 */
import { readdirSync, existsSync, statSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const STRICT = process.env.CHECK_STRICT === "1" || process.argv.includes("--strict");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  if (STRICT) {
    console.error("jsdom is not installed and CHECK_STRICT is set — refusing to report a pass");
    process.exit(2);
  }
  console.log("jsdom not installed — skipping labeller checks (npm install to enable)");
  process.exit(0);
}

let dir = process.argv[2] && resolve(process.argv[2]);
if (!dir) {
  const base = join(ROOT, "calibration");
  if (!existsSync(base)) {
    console.log("no calibration/ directory — run `python -m src.calibrate sample` first");
    process.exit(0);
  }
  const sets = readdirSync(base)
    .map((n) => join(base, n))
    .filter((p) => statSync(p).isDirectory() && existsSync(join(p, "label.html")))
    .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
  if (!sets.length) {
    console.log("no calibration set found under calibration/");
    process.exit(0);
  }
  dir = sets[0];
}

const fails = [];
const check = (cond, msg) => { if (!cond) fails.push(msg); };

// task.js is inlined rather than loaded as a sibling resource, for two reasons:
// jsdom resolves the relative src against the document URL, and the page needs a
// real http origin because a file:// document gets an opaque origin where
// localStorage throws — and localStorage is precisely what is under test here.
//
// The replacement is a *function*, not a string, and that is load-bearing
// rather than stylistic. String.replace interprets `$&`, `` $` ``, `$'` and
// `$$` inside a replacement string, so any of those appearing in a vendor's
// title or snippet splices part of the page into the middle of the script and
// leaves it a syntax error — after which `window.VN_TASK` is simply undefined
// and this gate reports "task.js did not load any items" while the real page,
// which never goes through this substitution, works perfectly. A function
// replacer is passed through verbatim.
//
// Not hypothetical: the first pairwise task written to disk contained two
// occurrences of `` $` `` in retrieved web content, and the 42-item absolute
// set that this check had only ever run against contained none.
const page = readFileSync(join(dir, "label.html"), "utf8").replace(
  '<script src="task.js"></script>',
  () => "<script>" + readFileSync(join(dir, "task.js"), "utf8") + "</script>",
);
const dom = new JSDOM(page, {
  runScripts: "dangerously",
  url: "http://localhost/",
  pretendToBeVisual: true,
  // jsdom 27 has HTMLDialogElement and the `open` property but neither
  // showModal() nor close(). The pairwise page opens the anchors dialog before
  // it renders the first screen, so without a stub the UI script dies on its
  // first statement and every assertion below fails describing a page that was
  // never built — which reads like a broken labeller rather than a missing
  // jsdom feature.
  //
  // Stubbed rather than worked around, and stated plainly: modal *behaviour* is
  // not what this gate covers. The labelling flow is.
  beforeParse(window) {
    const proto = window.HTMLDialogElement?.prototype;
    if (proto && typeof proto.showModal !== "function") {
      proto.showModal = function () { this.setAttribute("open", ""); };
      proto.close = function () { this.removeAttribute("open"); };
    }
  },
});
if (dom.window.document.readyState !== "complete") {
  await new Promise((r) => dom.window.addEventListener("load", r));
}
const { window } = dom;
const { document } = window;
const task = window.VN_TASK;

if (!task || !task.items?.length) {
  console.error(`task.js did not load any items from ${dir.replace(ROOT + "/", "")}`);
  process.exit(1);
}
const first = task.items[0];

// The two task shapes are different measurements, not two skins on one. The
// absolute set asks for four 0-10 scores per response; the pairwise set asks
// which of two responses is better, and `docs/12` is explicit that the second
// exists because the first failed — twelve of fifteen human scores landed on 9
// or 10, and a correlation over a variable that barely varies is mostly noise.
//
// This gate only ever ran against the absolute shape, because the pairwise set
// drawn on 2026-08-05 had no task on disk for it to find. The UI that will
// actually collect the calibration labels was therefore the one with no smoke
// test, which is the wrong way round: it is the one a person spends an hour
// inside.
if (task.kind === "pairwise") {
  checkPairwise();
} else {
  checkAbsolute();
}

function checkPairwise() {
  const key = "vn-pair-" + task.set_id;
  const readState = () => JSON.parse(window.localStorage.getItem(key) || "{}");

  // The anchors dialog opens over the first item and swallows keystrokes, which
  // is right for a person and wrong for the rest of this file.
  const dlg = document.getElementById("anchdlg");
  if (dlg?.open) dlg.close();

  // 1. Both sides of the comparison render, with the query above them.
  check(document.querySelector(".q")?.textContent.includes(first.query.slice(0, 20)),
        "the query is not on the page");
  const sides = document.querySelectorAll(".pair .side");
  check(sides.length === 2, `expected two responses side by side, got ${sides.length}`);
  check(sides[0]?.querySelectorAll("ol.results li").length === first.left.results.length,
        "the left response does not render all its results");
  check(sides[1]?.querySelectorAll("ol.results li").length === first.right.results.length,
        "the right response does not render all its results");

  // 2. Blinding, and the pairwise-specific half of it. A labeller who can tell
  //    that a screen is a repeat, or a swap of one they have already seen, is
  //    answering a different question — and those two strata are the only
  //    measure of whether they agree with themselves and of position bias.
  const pane = document.querySelector("main").textContent;
  check(!/\b(exa|serper|linkup|perplexity|you\.com|youcom)\b/i.test(pane),
        "a vendor name is visible in the labelling pane — blinding is broken");
  check(!/judge|ensemble|median/i.test(pane),
        "judge scoring language is visible to the labeller");
  for (const leak of ["stratum", "ensemble_gap", "source_pair_id", "vendor", "judges"]) {
    check(!(leak in first),
          `task.js carries ${leak} — the labeller can tell the strata apart`);
  }

  // 3. A tie is a real answer, not a missing one: forcing a choice between two
  //    responses a person cannot separate manufactures a coin flip and reports
  //    it as agreement.
  check(["pL", "pT", "pR"].every((id) => document.getElementById(id)),
        "the three choices are not all offered");

  // 4. Persistence — the failure that costs an hour of someone's life.
  document.getElementById("pL").click();
  check(readState()[first.pair_id]?.choice === "left",
        "clicking a choice did not persist it to localStorage");
  check(typeof readState()[first.pair_id]?.seconds === "number",
        "time-on-task was not recorded");

  // 5. Keyboard entry, which is how anyone gets through 280 screens.
  document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "3", bubbles: true }));
  check(readState()[first.pair_id]?.choice === "right",
        "keyboard scoring did not record a choice");

  // 6. Export shape must match what `calibrate import` parses. Keyed on
  //    pair_id, never response_id: the same response appears in more than one
  //    screen by design, and keying on it would collapse every repeat and swap.
  const exported = captureExport();
  check(exported !== null, "export produced no blob");
  if (exported) {
    const payload = JSON.parse(exported);
    check(payload.set_id === task.set_id, "export omits set_id");
    check(payload.kind === "pairwise",
          "export does not declare its kind — import cannot tell the two apart");
    check(Array.isArray(payload.labels) && payload.labels.length === 1,
          `export should carry only judged screens, got ${payload.labels?.length}`);
    const l = payload.labels?.[0];
    ["pair_id", "choice", "note", "seconds"].forEach(
      (k) => check(l && k in l, `export label is missing ${k}`));
    check(!(l && "response_id" in l),
          "export keys a pairwise label on response_id, which collapses repeats");
    check(!JSON.parse(exported).labels.some((x) => x.pair_id === "__idx"),
          "export leaked the UI's own bookkeeping keys as labels");
  }
}

function captureExport() {
  // Captured at the Blob constructor rather than by reading the Blob back:
  // jsdom's Blob has no .text() in every version, and a check that breaks on a
  // dependency bump is a check that gets deleted.
  let text = null;
  const RealBlob = window.Blob;
  window.Blob = class extends RealBlob {
    constructor(parts, opts) { super(parts, opts); text = String(parts[0]); }
  };
  window.URL.createObjectURL = () => "blob:x";
  window.HTMLAnchorElement.prototype.click = function () {};
  document.getElementById("export").click();
  window.Blob = RealBlob;
  return text;
}

function checkAbsolute() {

// 1. The item renders, and renders the thing being judged.
check(document.querySelector(".q")?.textContent.includes(first.query.slice(0, 20)),
      "the query is not on the page");
check(document.querySelectorAll("ol.results li").length === first.results.length,
      `expected ${first.results.length} result cards, got ${document.querySelectorAll("ol.results li").length}`);

// 2. Blinding. The whole design rests on the labeller not seeing these, and a
//    regression here would not look like a bug — it would look like a page.
const html = document.documentElement.innerHTML;
check(!/\b(exa|serper|linkup|perplexity|you\.com|youcom)\b/i.test(
        document.querySelector("main").textContent),
      "a vendor name is visible in the labelling pane — blinding is broken");
check(!/judge|ensemble|median/i.test(document.querySelector("main").textContent),
      "judge scoring language is visible to the labeller");
check(!("judges" in first) && !("median" in first) && !("vendor" in first),
      "task.js carries judge scores or vendor identity — blinding is broken at the source");

// 3. Every dimension offers 0-10.
const groups = document.querySelectorAll(".btns");
check(groups.length === task.dimensions.length,
      `expected ${task.dimensions.length} score rows, got ${groups.length}`);
groups.forEach((g) =>
  check(g.querySelectorAll("button").length === 11,
        `dimension ${g.dataset.dim} does not offer 0-10`));

// 4. Persistence: a click must survive a reload. This is the failure that costs
//    an hour of someone's life, so it is exercised rather than assumed.
document.querySelector('.btns[data-dim="overall"] button[data-v="7"]').click();
const stored = JSON.parse(window.localStorage.getItem("vn-calib-" + task.set_id) || "{}");
check(stored[first.response_id]?.overall === 7,
      "clicking a score did not persist it to localStorage");
check(typeof stored[first.response_id]?.seconds === "number",
      "time-on-task was not recorded");

// 5. Keyboard entry, which is how anyone actually gets through 150 items.
const press = (key) => window.document.dispatchEvent(
  new window.KeyboardEvent("keydown", { key, bubbles: true }));
press("Tab"); press("4");
const after = JSON.parse(window.localStorage.getItem("vn-calib-" + task.set_id) || "{}");
check(Object.values(after[first.response_id]).includes(4),
      "keyboard scoring did not record a value");

// 6. Export shape must match what `calibrate import` parses, including dropping
//    unlabelled items rather than exporting them as zeros.
const exportedText = captureExport();
check(exportedText !== null, "export produced no blob");
if (exportedText) {
  const payload = JSON.parse(exportedText);
  check(payload.set_id === task.set_id, "export omits set_id");
  check(Array.isArray(payload.labels) && payload.labels.length === 1,
        `export should carry only labelled items, got ${payload.labels?.length}`);
  const l = payload.labels[0];
  ["response_id", "relevance", "freshness", "citation_quality", "overall", "note", "seconds"]
    .forEach((k) => check(k in l, `export label is missing ${k}`));
}

}   // end checkAbsolute

console.log(`  ${task.items.length} ${task.kind === "pairwise" ? "screens" : "items"} `
            + `in ${dir.replace(ROOT + "/", "")}`);
if (fails.length) {
  console.error("\nlabeller checks FAILED:");
  fails.forEach((f) => console.error("  ✗ " + f));
  process.exit(1);
}
console.log("\nlabeller checks passed");
