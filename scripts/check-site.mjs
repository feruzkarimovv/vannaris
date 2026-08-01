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
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = process.argv[2] ? resolve(process.argv[2]) : join(ROOT, "site");
const PAGES = ["index.html", "results.html", "methodology.html", "data.html"];

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  console.log("jsdom not installed — skipping site checks (npm i -D jsdom to enable)");
  process.exit(0);
}

let failures = 0;
const fail = (page, msg) => { failures++; console.error(`  FAIL  ${page}: ${msg}`); };

for (const page of PAGES) {
  const path = join(SITE, page);
  if (!existsSync(path)) { fail(page, "missing"); continue; }

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
      const file = join(SITE, src);
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

  // 2. Every chart mount produced an SVG, and every chart has a table view.
  for (const mount of doc.querySelectorAll('[id^="fig-"]')) {
    if (!mount.querySelector("svg")) fail(page, `#${mount.id} rendered no svg`);
    if (!mount.querySelector("table")) fail(page, `#${mount.id} has no table equivalent`);
  }

  // 3. Internal links point at files that exist.
  for (const a of doc.querySelectorAll("a[href]")) {
    const href = a.getAttribute("href");
    if (/^(https?:|mailto:|#)/.test(href)) continue;
    const target = join(SITE, href.split("#")[0]);
    if (!existsSync(target)) fail(page, `dead link: ${href}`);
  }

  // 4. Fragment links resolve to an element on the target page.
  for (const a of doc.querySelectorAll('a[href*="#"]')) {
    const href = a.getAttribute("href");
    if (/^https?:/.test(href)) continue;
    const [file, frag] = href.split("#");
    if (!frag) continue;
    if (file && !existsSync(join(SITE, file))) continue; // already reported as a dead link
    const targetDoc = file
      ? new JSDOM(readFileSync(join(SITE, file), "utf8")).window.document
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
