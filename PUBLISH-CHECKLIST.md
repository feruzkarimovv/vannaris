# Publish checklist

The site in `site/` is complete and correct. This file is the gate between "built" and "published",
and the items in the first section are founder decisions, not engineering tasks — none of them
should be resolved by whoever happens to be doing the next commit.

> **The site went public on 2026-08-03**, on the founder's explicit instruction, with the blocking
> items in §1, §2 and §3 below **still open**. Both crawler blocks (§5) were removed deliberately as
> the launch step. This note exists so that an unchecked box below is read as what it is — an open
> item on a live site — rather than as an oversight nobody noticed. Specifically still open at
> launch: the USPTO search on `VANNARIS`, an attorney reading the methodology, a re-read of Exa's,
> Perplexity's and You.com's current terms, the Tavily/Brave decision, and `REPO_URL`, which is
> still unset — so the "Source" link on every page renders as inert text reading "not public yet"
> on a site whose central claim is that you can check the work.

---

## 1. Blocking — the name

**The name is "Vannaris", chosen 2026-08-01.** It replaced the working name "SearchBench", which was
never cleared and had four same-name projects in this exact vertical. The selection sweep and its
primary sources are in `docs/10-name-clearance-2026-08-01.md`; the conflicts that killed the old name
are recorded there too, and should stay recorded — they are the reason this section exists.

- [x] **Conflict check** — done 2026-08-01. `Vannaris` is free on `.com`, `.ai`, `.dev` and `.io`,
      free on PyPI and npm, free as a GitHub organisation, has no repository or Hugging Face model
      carrying the name, and returns **zero results** on the open web. Checked against registry RDAP
      records and the registries' own APIs, not search results. `docs/10` §6.
- [x] **`vannaris.com` is registered and serving** — done by 2026-08-02, when the site went up as a
      private Vercel preview on that domain (§5). The rest of this item is still open: **`.ai` is
      not held**, and the name appears on a live public site, which is exactly the condition under
      which squatting a matching domain becomes worth someone's while. Cheap today, not tomorrow.
- [ ] **A real USPTO search** (Trademark Search / TESS), not a general web search. Still open, and
      still the blocker it was — every programmatic route is closed, see `docs/10` §3 for the two
      ways to close it. Search **`VANNARIS`** in classes 009 (software) and 042 (SaaS). A federal
      search is free. An invented word is the strongest position a mark can have, which makes this
      likely to clear — likely is not cleared.
- [ ] **Claim the handles** the name will need: GitHub organisation, PyPI, npm, X. All were free on
      2026-08-01 except X, which could not be checked without authentication.

Renaming again is one command, and stays cheap until something public carries the name:

```bash
python scripts/rename.py --dry-run NewName   # see what would change
python scripts/rename.py NewName
.venv/bin/python scripts/make_og_image.py    # the social card renders the name as text
.venv/bin/python -m src.export && node scripts/check-site.mjs
```

Do this **before** buying a domain, filing anything, or putting a public URL anywhere.

## 2. Blocking — legal

- [ ] **An attorney reads the methodology** before launch: what is stored, what is published,
      whether the derived-scores-only boundary holds, and whether BYOK insulates the router layer.
      `docs/03` says explicitly that this is the highest-value dollar spent before going public and
      that it is not a substitute for counsel.
- [ ] **Confirm the vendor set one more time** against each vendor's *current* terms. Terms change,
      and the readings in `docs/03` were taken on 2026-07-30. **Two of five are done:** Linkup and
      Serper — the two `docs/03` flagged as unverified — were read in full on 2026-08-02, and both
      clear the benchmark (`docs/11`). Exa, Perplexity and You.com still want a re-read. Note that
      Serper reserves the right to change its terms without notice, so this expires.
- [ ] **Decide on Tavily and Brave.** Approach them for written consent, or launch without them and
      say why. Both run public self-benchmarks of their own, which is real leverage in that
      conversation. Either answer is defensible; leaving it undecided while publishing is not.
- [ ] Confirm the "not affiliated with any vendor" disclaimer is present on every page footer. It is,
      as of this writing — re-check after any footer edit.
- [x] **`REPO_URL` is set** — `src/export.py:87` points at <https://github.com/feruzkarimovv/vannaris>,
      which is public, and `scripts/check-quality.mjs` now fails the build if a page claims the
      source is readable while `repo_url` is null. Done 2026-08-04. The "Source" link on every page
      resolves, which on a site whose whole claim is that you can check the work was the single most
      important link on it.

## 3. Blocking — don't overclaim

The site currently reports **1 published week** and states in the hero that the weekly schedule has
not started. That is true today, and the site now reads both facts from the data rather than
asserting them: every run records whether a scheduler or a person invoked it, and the cadence
sentences on the landing, results and methodology pages are derived from
`track_record.schedule_started`. They will change on their own the first time the cron fires, and
not before. Before launch:

- [ ] Confirm nothing on the site, in the README, or in any launch post describes the benchmark as
      "continuously", "weekly", or "regularly" run. The site derives that count from the data
      (`track_record.weeks_published`), so it cannot drift on its own — launch copy written elsewhere
      can, and so can the README, which is hand-written.
- [x] **Decided by launching, 2026-08-03, at one published week.** The alternative — hold until
      three or four weeks, when "continuously run" becomes true on its own — was not taken. The
      cost of that choice is real and is being paid: the site's most-repeated caveat is still up,
      and `track_record.scheduled_weeks` was still 0 on 2026-08-07 because the 2026-08-03 scheduled
      run died on a credit preflight. The first scheduler-invoked run is expected 2026-08-10.

## 4. Before the repository goes public

- [ ] `git status` and confirm `.env` is ignored. Verify **before** the first push, not after.
- [ ] `git log -p | grep -i -E "sk-|api[_-]?key"` on the full history. A key committed once and
      deleted later is still in the history and still needs rotating.
- [ ] Move all eight keys into GitHub Actions secrets — `.github/workflows/weekly.yml` reads them
      from there and from nowhere else. See the weekly-run section of `README.md`. Note that arming
      the scheduled runner is **not** gated by this checklist: the runner can start accruing weeks
      while the name and legal questions are still open, and the recommended sequencing is that it
      does.
- [ ] Confirm `data/*.db` is ignored. The database holds raw vendor responses, which are exactly what
      this project's scoping avoids publishing.
- [ ] `node scripts/check-site.mjs` passes.
- [ ] `.venv/bin/python -m src.export` runs clean and the diff to `site/data/` and `site/export/` is
      committed.

## 5. Hosting

**Deployed as a private preview on 2026-08-02** to `vannaris.com` (Vercel, static, no build
step), then **made public on 2026-08-03.** Both crawler blocks were removed together, which is
how they were always meant to come off:

- [x] Delete `site/robots.txt`, which sent `Disallow: /`. Removed 2026-08-03.
- [x] Remove the `X-Robots-Tag: noindex, nofollow, noarchive` header from `vercel.json`. Removed
      2026-08-03, in the same commit — they cover different failure modes and taking off only one
      leaves the site invisible in a way that stays invisible.

Forgetting either one launches a site search engines have been told to ignore, which is the
kind of mistake that stays invisible for weeks. They are paired on purpose: the header covers
anything already crawled, the file covers anything that never fetches a page.

`site/` is static with no build step and no external requests, so GitHub Pages serving from the
`site/` directory works with no configuration. Two things to check after the first deploy:

- [ ] The four pages load and every chart renders (a chart that draws nothing still passes a naive
      link check; `scripts/check-site.mjs` catches it, so run it against the deployed HTML too).
- [ ] **Make the `og:image` and `og:url` tags absolute.** They are relative right now because there
      is no canonical domain yet, and most platforms will not resolve a relative `og:image` — the
      link will preview blank. Regenerate the card after any run with
      `python scripts/make_og_image.py`; it is drawn from the current export, so a stale card means
      a stale export.
- [ ] The CSV download links resolve. They are relative paths and will break if the site is deployed
      under a path prefix without the whole `site/` directory moving together.

## 6. Not blocking, but the first thing a reviewer will attack

- [ ] **The human-labelled calibration set.** 100–200 examples labelled by hand, compared against the
      ensemble monthly, rubric refined against the specific disagreements found. The measured
      spread between judge families is published on the site precisely because it is the
      largest caveat on every other number — and right now nothing audits it. Note that the
      disagreement *rates* added on 2026-08-04 do not close this: they measure agreement between
      models, which `docs/12` is explicit is a different and weaker quantity than agreement with
      a human.

- [ ] **Set `SB_HELDOUT_JSON` in Actions secrets** before the next scheduled run, or the withheld
      set will not run in CI and the overfitting check stays absent. The set is registered
      (`src/queries/heldout/manifest.json`, committed 2026-08-04) and its questions are in
      `data/heldout/`, outside git. Paste that file's contents as the secret. A missing secret is
      handled — the run proceeds on the public set alone and says so — so this fails quietly rather
      than loudly, which is the reason it is written down here.

- [ ] **Read `docs/13-conflict-of-interest.md` alongside the methodology in the attorney review**
      above. It contains public commitments made by a named person about payments not taken and
      relationships not held, and a disclosure register that has to stay accurate as the business
      changes. The site mirrors it at `methodology.html#conflicts`.

---

## What is already done

Recorded so it is not re-litigated:

- The site publishes derived scores only. Retrieved URLs, titles, snippets and synthesized answers
  never reach the export, and `src/export.py` fails the build if they do.
- The published run is chosen by coverage rather than recency, so a smoke test cannot become a
  published result. A previous smoke test did exactly that; the fix is in `src/runner.py`, the
  column that made it detectable is in `src/storage/schema.sql`, and the incident is in the site's
  methodology changelog rather than quietly repaired.
- Every figure on the site is generated from the export, including figures inside sentences.
  `scripts/check-site.mjs` fails on any that does not resolve.
- Data is CC BY 4.0, code is MIT, and both licences are in the repository.
