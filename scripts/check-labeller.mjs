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

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  console.log("jsdom not installed — skipping labeller checks (npm i -D jsdom to enable)");
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
const page = readFileSync(join(dir, "label.html"), "utf8").replace(
  '<script src="task.js"></script>',
  "<script>" + readFileSync(join(dir, "task.js"), "utf8") + "</script>",
);
const dom = new JSDOM(page, {
  runScripts: "dangerously",
  url: "http://localhost/",
  pretendToBeVisual: true,
});
if (dom.window.document.readyState !== "complete") {
  await new Promise((r) => dom.window.addEventListener("load", r));
}
const { window } = dom;
const { document } = window;
const task = window.VN_TASK;

check(task && task.items.length > 0, "task.js did not load any items");
const first = task.items[0];

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
let exported = null;
window.URL.createObjectURL = (blob) => { exported = blob; return "blob:x"; };
window.HTMLAnchorElement.prototype.click = function () {};
document.getElementById("export").click();
check(exported !== null, "export produced no blob");
if (exported) {
  const text = await exported.text();
  const payload = JSON.parse(text);
  check(payload.set_id === task.set_id, "export omits set_id");
  check(Array.isArray(payload.labels) && payload.labels.length === 1,
        `export should carry only labelled items, got ${payload.labels?.length}`);
  const l = payload.labels[0];
  ["response_id", "relevance", "freshness", "citation_quality", "overall", "note", "seconds"]
    .forEach((k) => check(k in l, `export label is missing ${k}`));
}

console.log(`  ${task.items.length} items in ${dir.replace(ROOT + "/", "")}`);
if (fails.length) {
  console.error("\nlabeller checks FAILED:");
  fails.forEach((f) => console.error("  ✗ " + f));
  process.exit(1);
}
console.log("\nlabeller checks passed");
