# Release validation

Executed October 4, 2026 against the integrated working tree on `codex/vannaris-demo-release`. The starting repository commit was `ecd59bc7ad88187f8abb24c1e933ccc406346cca`. This records local verification, not a remote CI run or deployment.

| Check | Executed result |
| --- | --- |
| `make setup` | Exit 0; repeated installation and dependency consistency check |
| Fresh isolated runtime | Python 3.13.5; only the eight hash-locked runtime packages installed |
| `make check VANNARIS_PYTHON=/tmp/vannaris-release-venv/bin/python` after the redesign | Exit 0; 414 Python tests, 13 repository gates, no skipped gates |
| Rendered measured archive | 20 checks passed under the generated CSP, including three CSV-derived archive regressions |
| Rendered synthetic demo | 17 checks passed under its matching CSP |
| Original evidence | 12 original response/judge/query/registration/label files match the starting commit byte-for-byte |
| Derived publication | Four published weeks verified against released inputs and recorded SHA-256 hashes; `publication-v3` |
| Browser bundle | 220,803 bytes; 58.3% smaller than the first integrated archive bundle; complete audit JSON retained |
| Static browser-data budget | Conservative maximum 415.3 KB, including latest and selected query-detail scripts |
| Actual demo HTTP readiness | Six served files returned HTTP 200 and matched local bytes; synthetic identity verified |
| Captured walkthrough | Eight real rendered scenes; H.264 MP4, 1440 × 1000, exactly 32 seconds; coupled manifest hash verified |

Chromium and Node 24.19.0 were used locally. CI is configured for Python 3.13 and Node 22, but this task did not dispatch a remote workflow. The existing test-only SQLite `ResourceWarning` and jsdom `scrollTo` notices remain nonfatal; no assertion or gate was skipped to obtain a pass.

The synthetic scenario persisted 360 provider envelopes, isolated one malformed response, retained 718 accepted judge scores on the first attempt, refused publication, made only 359 missing mock judge calls during recovery, and exported 359 complete panels. Actual API spend was $0. Original run identity, collection date, costs, and accepted scores were preserved.

Local generated assets are ignored by Git and reproducible with `make demo-build` and optional `make demo-video`:

- `.artifacts/release/vannaris-demo.mp4`
- `.artifacts/release/demo-cover.png`
- `.artifacts/release/capture.json` and its exact `demo-evidence.json`
- `.artifacts/release/preserved-evidence.json`
- `.artifacts/browser/archive/` and `.artifacts/browser/demo/`

No paid vendor/judge run, new human study, deployment, recording upload, LinkedIn post, remote artifact deletion, or environment publication was performed. Human labels and the active withheld registration remain unchanged. The real archive still ends on August 24, 2026.

The local website redesign uses shared light-theme tokens, simplified navigation and page introductions, a data-bound comparison, and expandable publication notes. Desktop, tablet, mobile, an open publication disclosure, keyboard query inspection, loading, unavailable, and archive states were inspected in Chromium. Final review captures are in `.artifacts/redesign/after/`; the original working-site reference is in `.artifacts/redesign/before/`. The structural snapshot was intentionally updated for the new homepage sections, shorter headings, and disclosure hierarchy. Original raw evidence hashes were rechecked after the redesign.
