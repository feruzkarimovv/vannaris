/* Quality gate for the published site: accessibility, integrity, weight.
 *
 * check-site.mjs answers "did every generated figure resolve?". This answers
 * "is the page any good, and is it still the page we claim it is?" — the
 * questions an autonomous improvement loop cannot be trusted to self-assess,
 * because a model asked to improve a page will report that it improved the
 * page. These are the checks that disagree.
 *
 * Run:  node scripts/check-quality.mjs [site-root]
 * Needs jsdom and axe-core; exits 0 with a note if either is missing, matching
 * check-site.mjs, so a machine without them is never blocked from working.
 *
 * Three invariants here are product claims, not preferences:
 *
 *   - No external requests. The site's pitch is that you can read the whole
 *     thing; a page that phones out to a CDN or an analytics host is a page
 *     with a dependency nobody audited, and on a benchmark that judges
 *     vendors, a third-party beacon is a conflict-of-interest question.
 *   - Every internal link and asset resolves. The "Source" link and the CSV
 *     downloads ARE the product for a project whose claim is checkability.
 *   - Weight stays bounded. The dashboard ships its own data; without a budget
 *     the honest thing (publishing everything) silently becomes a page nobody
 *     on a slow connection can open.
 */
import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { dirname, join, resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = process.argv[2] ? resolve(process.argv[2]) : join(ROOT, "site");

// Generated per-vendor pages are discovered, not listed — see check-site.mjs,
// which owns the assertion that the set of them matches the published vendors.
const VENDOR_DIR = join(SITE, "vendors");
const VENDOR_PAGES = existsSync(VENDOR_DIR)
  ? readdirSync(VENDOR_DIR).filter((f) => f.endsWith(".html")).sort().map((f) => join("vendors", f))
  : [];
const PAGES = ["index.html", "results.html", "methodology.html", "data.html", ...VENDOR_PAGES];

// Budgets in KB. Set from the measured size at the time of writing plus room to
// grow, not from a round number: a budget nobody can hit is a budget nobody
// keeps, and one already exceeded is noise on every run.
const BUDGET = {
  html: 60,        // per page
  css: 120,        // total stylesheet weight
  js: 200,         // total script weight, excluding the data bundle
  data: 1200,      // the published week bundle — grows with every week
  pageTotal: 1600, // everything one page pulls in
};

const STRICT = process.env.CHECK_STRICT === "1" || process.argv.includes("--strict");

let JSDOM, axe;
try {
  ({ JSDOM } = await import("jsdom"));
  axe = (await import("axe-core")).default;
} catch (e) {
  if (STRICT) {
    console.error("dependencies missing and CHECK_STRICT is set — refusing to report a pass:", e.message);
    console.error("  npm install");
    process.exit(2);
  }
  console.log("jsdom/axe-core not installed — skipping quality checks:", e.message);
  console.log("  npm install   to enable");
  process.exit(0);
}

const fails = [];
const warns = [];
const fail = (page, msg) => fails.push(`${page}: ${msg}`);
const warn = (page, msg) => warns.push(`${page}: ${msg}`);
const kb = (bytes) => Math.round(bytes / 102.4) / 10;

function sizeOf(p) {
  try { return statSync(p).size; } catch { return 0; }
}

// ------------------------------------------------------------------ weight

const cssBytes = readdirSync(join(SITE, "assets"))
  .filter((f) => f.endsWith(".css"))
  .reduce((n, f) => n + sizeOf(join(SITE, "assets", f)), 0);
const jsBytes = readdirSync(join(SITE, "assets"))
  .filter((f) => f.endsWith(".js"))
  .reduce((n, f) => n + sizeOf(join(SITE, "assets", f)), 0);
const dataBytes = existsSync(join(SITE, "data"))
  ? readdirSync(join(SITE, "data")).reduce((n, f) => n + sizeOf(join(SITE, "data", f)), 0)
  : 0;

if (kb(cssBytes) > BUDGET.css) fail("assets", `css ${kb(cssBytes)}KB over budget ${BUDGET.css}KB`);
if (kb(jsBytes) > BUDGET.js) fail("assets", `js ${kb(jsBytes)}KB over budget ${BUDGET.js}KB`);
if (kb(dataBytes) > BUDGET.data) {
  // Deliberately a warning: the data growing is the project working. It still
  // has to be noticed, because the growth is linear in published weeks and the
  // page loads all of it.
  warn("data", `published data ${kb(dataBytes)}KB over ${BUDGET.data}KB — time to split by week`);
}

// ------------------------------------------------------------------- pages

for (const page of PAGES) {
  const file = join(SITE, page);
  if (!existsSync(file)) { fail(page, "missing"); continue; }

  const html = readFileSync(file, "utf8");
  // Relative hrefs resolve against the page's own directory. Identical to the
  // site root for every page that sits at the root, which is why this went
  // unnoticed until the per-vendor pages moved into a subdirectory.
  const here = dirname(file);
  if (kb(sizeOf(file)) > BUDGET.html) fail(page, `html ${kb(sizeOf(file))}KB over budget ${BUDGET.html}KB`);

  const dom = new JSDOM(html, { url: "http://localhost/", pretendToBeVisual: true });
  const { document } = dom.window;

  // --- no external requests -------------------------------------------------
  const external = [];
  document.querySelectorAll("[src],[href]").forEach((el) => {
    const v = el.getAttribute("src") || el.getAttribute("href") || "";
    if (/^(https?:)?\/\//i.test(v)) {
      // Anchors to other sites are content, not a load-time dependency. Only
      // subresources — anything the browser fetches or opens a connection for —
      // are the claim being enforced.
      //
      // <link> is the subtle one. rel="canonical" and friends are metadata and
      // must be absolute to work at all; rel="stylesheet"/"preload"/"preconnect"
      // are real network activity. So links are judged by rel, against an
      // allowlist of the metadata ones — an unrecognised rel is treated as a
      // fetch, because failing closed is the right default for the check that
      // guards "this page talks to nobody".
      const METADATA_RELS = new Set(["canonical", "alternate", "me", "author",
                                     "license", "next", "prev", "help"]);
      const rel = (el.getAttribute("rel") || "").toLowerCase().trim();
      let isSubresource;
      if (el.tagName === "A") isSubresource = false;
      else if (el.tagName === "LINK") isSubresource = !METADATA_RELS.has(rel);
      else isSubresource = true;
      if (isSubresource) external.push(`${el.tagName.toLowerCase()}[rel=${rel || "-"}] ${v}`);
    }
  });
  external.forEach((e) => fail(page, `external subresource: ${e}`));

  // --- local assets and anchors resolve ------------------------------------
  let pageBytes = sizeOf(file);
  document.querySelectorAll("[src],link[href]").forEach((el) => {
    const v = el.getAttribute("src") || el.getAttribute("href") || "";
    if (!v || /^(https?:)?\/\//i.test(v) || v.startsWith("data:") || v.startsWith("#")) return;
    const target = join(here, v.split(/[?#]/)[0]);
    if (!existsSync(target)) return fail(page, `missing asset: ${v}`);
    pageBytes += sizeOf(target);
  });
  if (kb(pageBytes) > BUDGET.pageTotal) {
    warn(page, `page pulls ${kb(pageBytes)}KB over ${BUDGET.pageTotal}KB budget`);
  }

  document.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (!href || /^(https?:|mailto:|tel:)/i.test(href)) return;
    if (href.startsWith("#")) {
      // getElementById rather than a selector: ids in this project are simple,
      // and CSS.escape is not a Node global — reaching for it here crashed the
      // gate, which on a check script is worse than the bug it was guarding.
      if (href !== "#" && !document.getElementById(href.slice(1))) {
        fail(page, `anchor goes nowhere: ${href}`);
      }
      return;
    }
    const target = join(here, href.split(/[?#]/)[0]);
    if (!existsSync(target)) fail(page, `dead link: ${href}`);
  });

  // --- social preview -------------------------------------------------------
  // Relative og:image previews blank on most platforms. It cannot be made
  // absolute until a canonical URL exists, so this is a warning that turns into
  // a launch blocker rather than a silent bad first impression.
  // Absolute since 2026-08-02, when the domain was bought. This was a warning
  // while there was no canonical URL to be absolute against; it is a failure now
  // because a relative og:image previews blank on most platforms, and the launch
  // post is exactly the moment nobody gets to re-share.
  const og = document.querySelector('meta[property="og:image"]')?.getAttribute("content");
  if (!og) fail(page, "no og:image");
  else if (!/^https:\/\//i.test(og)) fail(page, `og:image must be absolute, got "${og}"`);

  const ogUrl = document.querySelector('meta[property="og:url"]')?.getAttribute("content");
  if (!ogUrl) fail(page, "no og:url");
  else if (!/^https:\/\//i.test(ogUrl)) fail(page, `og:url must be absolute, got "${ogUrl}"`);

  // One canonical per page, absolute, and matching og:url — two URLs claiming to
  // be the same page is how a site with four pages gets indexed as eight.
  const canon = document.querySelector('link[rel="canonical"]')?.getAttribute("href");
  if (!canon) fail(page, "no canonical link");
  else if (!/^https:\/\//i.test(canon)) fail(page, `canonical must be absolute, got "${canon}"`);
  else if (ogUrl && canon !== ogUrl) fail(page, `canonical (${canon}) and og:url (${ogUrl}) disagree`);

  // --- accessibility --------------------------------------------------------
  // jsdom has no layout, so colour-contrast and any rule needing geometry are
  // not evaluated here. What remains — labels, alt text, heading order, landmark
  // structure, ARIA validity — is most of what actually breaks a screen reader.
  // axe reads window/document off the global scope and cannot deduce them from
  // a Document passed as context, so they are set per page — each page gets its
  // own jsdom instance and axe must be pointed at the current one.
  globalThis.window = dom.window;
  globalThis.document = document;
  globalThis.Node = dom.window.Node;
  globalThis.Element = dom.window.Element;
  globalThis.NodeList = dom.window.NodeList;
  globalThis.HTMLElement = dom.window.HTMLElement;
  globalThis.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);

  const results = await axe.run(document.documentElement, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } },
  });
  for (const v of results.violations) {
    const where = v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(", ");
    const line = `a11y ${v.id} (${v.nodes.length}×): ${v.help} [${where}]`;
    (v.impact === "critical" || v.impact === "serious") ? fail(page, line) : warn(page, line);
  }

  dom.window.close();
}

// -------------------------------------------- inspectability claims resolve
//
// Six sentences across the site tell the reader they can go and read the
// harness — including the one saying the withheld set's hash is committed
// before it runs, which is the entire basis for trusting a private score. All
// six were shipping while `repo_url` was null and the "Source" nav item
// rendered as an inert grey span, so the site was promising something it did
// not deliver. This makes the two impossible to separate again: claim the
// repository is readable, or set repo_url, but not neither.
{
  const bundlePath = join(SITE, "data", "bundle.js");
  if (existsSync(bundlePath)) {
    const bundle = readFileSync(bundlePath, "utf8");
    const m = bundle.match(/"repo_url":\s*(null|"([^"]*)")/);
    const repoUrl = m && m[2] ? m[2] : null;

    // Phrases that only make sense if a reader can actually reach the source.
    const CLAIMS = [
      /public repository/i,
      /in the repository/i,
      /committed to (this |the )?repository/i,
      /is in the source\b/i,
      /git clone/i,
    ];
    for (const page of PAGES) {
      const file = join(SITE, page);
      if (!existsSync(file)) continue;
      const html = readFileSync(file, "utf8");
      const hit = CLAIMS.find((re) => re.test(html));
      if (hit && !repoUrl) {
        fail(page, `claims the source is readable (${hit}) but repo_url is null — ` +
                   `either publish the repository and set export.REPO_URL, or drop the claim`);
      }
    }
    // And the placeholder that outlived its reason to exist.
    for (const page of PAGES) {
      const file = join(SITE, page);
      if (!existsSync(file)) continue;
      if (/git clone\s*&lt;repository&gt;/.test(readFileSync(file, "utf8"))) {
        fail(page, "reproduce block still says `git clone <repository>`");
      }
    }
  }
}

// ------------------------------------------------------- robots and sitemap
//
// The sitemap is hand-written and machine-checked rather than generated. What
// makes it go stale is the vendor set changing, and adding a vendor is a
// deliberate act under docs/03 with a gate of its own — so the right behaviour
// is for an unlisted page to stop the build, not for a generator to paper over
// the omission. The comparison runs both ways: a page missing from the sitemap
// and a sitemap entry pointing at a page that no longer exists are both wrong.

const CANONICAL_ORIGIN = "https://vannaris.com";
const asUrl = (page) =>
  CANONICAL_ORIGIN + "/" + (page === "index.html" ? "" : page);

for (const f of ["robots.txt", "sitemap.xml"]) {
  if (!existsSync(join(SITE, f))) fail(f, "missing");
}

if (existsSync(join(SITE, "sitemap.xml"))) {
  const xml = readFileSync(join(SITE, "sitemap.xml"), "utf8");
  const listed = new Set([...xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/g)].map((m) => m[1]));
  const expected = new Set(PAGES.map(asUrl));

  for (const url of expected) {
    if (!listed.has(url)) fail("sitemap.xml", `does not list ${url}`);
  }
  for (const url of listed) {
    if (!expected.has(url)) fail("sitemap.xml", `lists ${url}, which is not a page here`);
  }
  // A sitemap and a page disagreeing about the canonical origin would send
  // crawlers to one host and readers to another.
  for (const page of PAGES) {
    const file = join(SITE, page);
    if (!existsSync(file)) continue;
    const canonical = readFileSync(file, "utf8")
      .match(/<link[^>]+rel="canonical"[^>]+href="([^"]+)"/i)?.[1];
    if (canonical && canonical !== asUrl(page)) {
      fail(page, `canonical is ${canonical}, sitemap says ${asUrl(page)}`);
    }
  }
}

if (existsSync(join(SITE, "robots.txt"))) {
  const robots = readFileSync(join(SITE, "robots.txt"), "utf8");
  if (!/^\s*Sitemap:\s*\S+/mi.test(robots)) {
    fail("robots.txt", "does not point at the sitemap");
  }
  // docs/03 keeps vendor content off this site entirely, so there is nothing
  // here that needs hiding — and a Disallow would read as though there were.
  const disallowed = [...robots.matchAll(/^\s*Disallow:\s*(\S+)/gim)].map((m) => m[1]);
  if (disallowed.some((d) => d !== "")) {
    fail("robots.txt", `disallows ${disallowed.join(", ")} — the data is meant to be checkable`);
  }
}

// ------------------------------------------------------------------ report

console.log(`  css ${kb(cssBytes)}KB · js ${kb(jsBytes)}KB · data ${kb(dataBytes)}KB`);
if (warns.length) {
  console.log("\nwarnings:");
  warns.forEach((w) => console.log("  ! " + w));
}
if (fails.length) {
  console.error("\nquality checks FAILED:");
  fails.forEach((f) => console.error("  ✗ " + f));
  process.exit(1);
}
console.log("\nquality checks passed");
