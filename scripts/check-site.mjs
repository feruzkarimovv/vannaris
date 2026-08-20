/* Smoke test for the published site.
 *
 * The pages are generated-data-driven: every figure in the copy is filled from
 * site/data/bundle.js at load. That is only safe if something checks that the
 * filling actually happened — an unresolved data-val renders as an em dash,
 * which looks like a design choice rather than a broken build.
 *
 * Run:  node scripts/check-site.mjs [site-root]
 * The optional argument checks a build somewhere other than ./site, which is
 * how a state the live data does not currently show — a started schedule, a
 * second published week — gets tested before it happens for real.
 * Needs jsdom. If it is not installed the script says so and exits 0, so it
 * never becomes the reason a machine without it cannot work on the repo.
 */
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = process.argv[2] ? resolve(process.argv[2]) : join(ROOT, "site");

// The per-vendor pages are generated (scripts/make_vendor_pages.py), so they
// are discovered rather than listed: a list here would be one more place to
// forget when the vendor set changes, which is exactly the failure the check
// below exists to catch.
const VENDOR_DIR = join(SITE, "vendors");
const VENDOR_PAGES = existsSync(VENDOR_DIR)
  ? readdirSync(VENDOR_DIR).filter((f) => f.endsWith(".html")).sort().map((f) => join("vendors", f))
  : [];
const PAGES = ["index.html", "results.html", "methodology.html", "data.html", "evals.html", ...VENDOR_PAGES];

const STRICT = process.env.CHECK_STRICT === "1" || process.argv.includes("--strict");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  if (STRICT) {
    console.error("jsdom is not installed and CHECK_STRICT is set — refusing to report a pass");
    console.error("  npm install");
    process.exit(2);
  }
  console.log("jsdom not installed — skipping site checks (npm install to enable)");
  process.exit(0);
}

let failures = 0;
const fail = (page, msg) => { failures++; console.error(`  FAIL  ${page}: ${msg}`); };

// One page per vendor in the published data, and no page for a vendor that is
// not in it. Getting this wrong is silent in every other gate: the site would
// simply be missing the page for a newly-added vendor, or still be serving a
// page for one that was pulled — which for a benchmark scoped by contract is
// the worse of the two.
try {
  const bundle = readFileSync(join(SITE, "data", "bundle.js"), "utf8");
  const data = JSON.parse(bundle.slice(bundle.indexOf("{"), bundle.lastIndexOf("}") + 1));
  const want = new Set(data.latest.vendors.map((v) => `vendors/${v.vendor}.html`));
  const have = new Set(VENDOR_PAGES);
  for (const p of want) if (!have.has(p)) fail("vendors/", `no page for vendor in the export: ${p} — run scripts/make_vendor_pages.py`);
  for (const p of have) if (!want.has(p)) fail("vendors/", `page for a vendor not in the export: ${p} — run scripts/make_vendor_pages.py`);
} catch (e) {
  fail("vendors/", `could not compare vendor pages against the export: ${e.message}`);
}

for (const page of PAGES) {
  const path = join(SITE, page);
  if (!existsSync(path)) { fail(page, "missing"); continue; }
  // Relative hrefs resolve against the page's own directory, not the site
  // root. Those are the same thing only for pages that sit at the root, which
  // every page did until the per-vendor ones were added.
  const here = dirname(path);

  const errors = [];
  const dom = new JSDOM(readFileSync(path, "utf8"), {
    runScripts: "dangerously",
    resources: undefined,
    url: "http://localhost/" + page,
    pretendToBeVisual: true,
    virtualConsole: new (await import("jsdom")).VirtualConsole()
      .on("jsdomError", (e) => errors.push(String(e.message)))
      .on("error", (m) => errors.push(String(m))),
  });

  const { window } = dom;
  // jsdom does not fetch <script src>, so every script is evaluated by hand in
  // document order, which is exactly the order a browser would use.
  for (const node of window.document.querySelectorAll("script")) {
    const src = node.getAttribute("src");
    let code;
    if (src) {
      const file = join(here, src);
      if (!existsSync(file)) { fail(page, `script not found: ${src}`); continue; }
      code = readFileSync(file, "utf8");
    } else {
      code = node.textContent;
    }
    try {
      window.eval(code);
    } catch (e) {
      fail(page, `${src || "inline script"} threw: ${e.message}`);
    }
  }

  // The page defers its own wiring to DOMContentLoaded, which jsdom fires
  // asynchronously — so the assertions below have to wait for it, or they
  // inspect the page in its pre-JavaScript state and report every value as
  // unresolved.
  await new Promise((r) => setTimeout(r, 50));

  for (const e of errors) fail(page, `console: ${e.slice(0, 200)}`);

  const doc = window.document;

  // 1. Every data-val resolved to something.
  const unresolved = [...doc.querySelectorAll("[data-val]")]
    .filter((el) => el.textContent.trim() === "" || el.textContent.trim() === "—")
    .map((el) => el.getAttribute("data-val"));
  if (unresolved.length) fail(page, `unresolved data-val: ${[...new Set(unresolved)].join(", ")}`);

  // Visible copy dates a run from ran_at, not from the ISO week id that names
  // the export files. A leftover 2026-W33 in a heading looks like an internal
  // filename leaking onto the page. Hrefs may still point at those files.
  const weekRe = /\d{4}-W\d{2}/;
  const walker = doc.createTreeWalker(doc.body, window.NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (!parent || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(parent.tagName)) continue;
    const text = walker.currentNode.textContent;
    if (weekRe.test(text)) {
      fail(page, `ISO week id in visible copy: ${text.trim().slice(0, 80)}`);
      break;
    }
  }

  // 2. Every chart mount produced an SVG, and every chart has a table view.
  for (const mount of doc.querySelectorAll('[id^="fig-"]')) {
    if (!mount.querySelector("svg")) fail(page, `#${mount.id} rendered no svg`);
    if (!mount.querySelector("table")) fail(page, `#${mount.id} has no table equivalent`);
  }

  // 3. Internal links point at files that exist.
  for (const a of doc.querySelectorAll("a[href]")) {
    const href = a.getAttribute("href");
    if (/^(https?:|mailto:|#)/.test(href)) continue;
    const target = join(here, href.split("#")[0]);
    if (!existsSync(target)) fail(page, `dead link: ${href}`);
  }

  // 4. Fragment links resolve to an element on the target page.
  for (const a of doc.querySelectorAll('a[href*="#"]')) {
    const href = a.getAttribute("href");
    if (/^https?:/.test(href)) continue;
    const [file, frag] = href.split("#");
    if (!frag) continue;
    if (file && !existsSync(join(here, file))) continue; // already reported as a dead link
    const targetDoc = file
      ? new JSDOM(readFileSync(join(here, file), "utf8")).window.document
      : doc;
    if (!targetDoc.getElementById(frag)) fail(page, `dead anchor: ${href}`);
  }

  // 5. Accessibility floor: one h1, images described, tables have headers.
  const h1s = doc.querySelectorAll("h1");
  if (h1s.length !== 1) fail(page, `expected exactly one h1, found ${h1s.length}`);
  for (const svg of doc.querySelectorAll("svg[role='group']")) {
    if (!svg.getAttribute("aria-label")) fail(page, "svg without aria-label");
  }
  for (const t of doc.querySelectorAll("table")) {
    if (!t.querySelector("th")) fail(page, "table without header cells");
  }

  if (!failures) console.log(`  ok    ${page}`);
  window.close();
}

if (failures) {
  console.error(`\n${failures} problem(s) found.`);
  process.exit(1);
}
console.log("\nsite checks passed");
