# Vannaris — final design QA

**Findings:** No actionable P0/P1/P2 issues remain. The implementation passes against the existing working site and the simplified brief. This is a deliberate redesign, not pixel reproduction or approval of any rejected ImageGen mockup. No deployment occurred.

**[P3] Optional mobile scroll hint.** At 390px, the homepage matrix shows part of the six-category comparison, as in the source. The new right-edge fade suggests more content. A brief “Scroll to compare all six categories” hint could improve discovery; scrolling remains usable and this does not block acceptance.

## Comparison target and evidence

Intentional differences: warm off-white surfaces, white panels, pine accents, an upright headline, concise introductions, the main comparison below the intro, publication metadata in native disclosures, and engineering-demo links below the measured study. Data, withholding, archive controls, and evidence access remain intact. Different theme, content order, page height, and fold position are expected.

Paths are repository-relative. Captures exclude browser chrome/device frames. DPR is 1; no resampling or density normalization was used.

| Evidence | Pixels | CSS viewport / state |
| --- | --- | --- |
| `.artifacts/redesign/before/home.png` — source truth | 1440 × 1953 | 1440 × 1000, full page, original dark site, latest snapshot |
| `.artifacts/redesign/after/home-full.png` — implementation | 1440 × 2943 | 1440 × 1000, full page, same snapshot, disclosure closed |
| `.artifacts/redesign/before/home-mobile.png` | 390 × 2812 | Full page at 390px width; original viewport height is not recorded in the image |
| `.artifacts/redesign/after/home-mobile.png` | 390 × 4210 | 390 × 844, full page, disclosure closed |
| `.artifacts/redesign/after/home-preview.png` | 1440 × 1230 | Supplemental taller preview showing the complete figure |
| `.artifacts/redesign/after/home-mobile-viewport.png` | 390 × 844 | First viewport, menu closed |
| `.artifacts/redesign/after/home-tablet.png` | 768 × 1024 | First viewport |
| `.artifacts/redesign/after/results.png`, `methodology.png`, `data.png`, `vendor.png` | Each 1440 × 1150 | Current latest snapshot, disclosures closed; vendor is Exa |
| `.artifacts/redesign/after/publication-notes-open.png` | 1440 × 1150 | Results disclosure open |
| `.artifacts/redesign/after/mobile-menu.png` | 390 × 844 | Homepage menu open |

**Full-view comparison:** source `before/home.png` and implementation `after/home-full.png` were opened together in one comparison input. The two mobile full-page captures were likewise opened together. Matched width/density support comparison of wrapping and alignment; mobile vertical pixel fidelity is not claimed.

**Focused comparison:** source desktop capture and final `home-preview.png` were opened together to inspect title/navigation typography, category labels, score ink, withheld cells, and caption. The full-page pair also exposes the unranked roster row. The taller preview is supplemental, not a match to the original 1000px fold.

**Superseded captures:** early methodology/data screenshots did not reflect the current picker/disclosure. Fresh Chromium confirmed served HTML equals current source and both controls are visibly rendered. Canonical `after/methodology.png` and `after/data.png` were refreshed; `.artifacts/redesign/qa/data-final.png` preserves the verification capture. This was an evidence-state discrepancy, not a remaining product defect.

## Five required fidelity surfaces

- **Fonts/typography — passed.** Local Geist/Geist Mono remain sharp and coherent. The upright headline, shorter decks, tabular measurements, optical weights, wrapping, and heading hierarchy are readable across desktop/mobile without collisions or truncation.
- **Spacing/layout — passed.** The 1160px shell aligns intro, figure, roster, and supporting links. Spacing, restrained radii, white panels, and section rhythm form one system. Tablet remains legible; mobile stacks sections and keeps controls within the viewport. Comparison placement below the intro is intentional.
- **Colors/tokens — passed.** Warm light/pine replaces dark/red deliberately. The sequential mint-to-pine ramp and contrast-aware ink remain readable; all 28 published matrix labels exceed 4.5:1 (minimum observed 5.81:1). Withheld cells have explicit text and neutral treatment.
- **Image quality/assets — passed for reviewed pages.** The source has no required photographic hero or illustration. The existing letter mark and functional vector/data charts remain sharp; no invented imagery, fake data, or replacement product illustrations were introduced. Social-share cards are outside screenshot acceptance scope.
- **Copy/content — passed.** Actual date, historical-study framing, visible coverage, and honest withholding remain coherent. Supporting pages use concise task introductions; named disclosures retain provenance/methodology details. The explicitly synthetic engineering demo stays separate from measured performance.

## Iteration history

| Earlier finding | Fix | Post-fix evidence |
| --- | --- | --- |
| [P2] Unranked/provider and withheld score/cost crowding, visible in the source roster | Wider roster tracks and separated placements | `after/home-full.png` and `after/home-mobile.png`: Perplexity label/name/score/cost separated |
| [P1] Static measurement link lacked an accessible name before dynamic filling | Meaningful fallback link text | Final preview/mobile date link and passing accessibility checks; initial defect was diagnosed by implementation checks rather than archived visually |
| [P2] Results metadata delayed the first figure | Native disclosure; visible coverage metrics and selector retained | Earlier `/workspace/reviews/vannaris/after-results.html.png`; final `after/results.png` and `publication-notes-open.png` |

Final comparisons required no further source edits.

## Runtime and interaction verification

Team gates passed: **414 tests / 13 repository gates; 20 measured-site browser checks; 17 synthetic-site browser checks**. Coverage includes actual security headers, rendered WCAG, console errors, mobile overflow, archive URLs, filters/paging/empty states, keyboard/touch dialogs, Escape/focus return, nullable scores, and missing-bundle recovery.

Independent archive checks compare chart tables/SVG labels to public CSV bins. Delayed detail shows loading without latest-run data; released detail draws the selected archive; blocked detail shows unavailability/recovery. Disagreement uses complete three-judge panels. Additional fresh Chromium captures verified visible method/data/vendor selectors/disclosures and zero page exceptions. Menu, native disclosure, tablet, and supporting-page states were visually inspected.

## Review limits and checklist

No blocking questions remain. Safari-specific rendering, exhaustive enlarged-text captures, social-card redesign, and pixel reproduction are not claimed. The user still needs to review the concrete local result.

- [x] Source and implementation opened together; full-view and focused comparisons completed.
- [x] Five fidelity surfaces, desktop/tablet/mobile, and key rendered states reviewed.
- [x] Earlier substantive fixes confirmed with revised evidence; stale captures superseded.
- [x] Archive correctness, accessible controls, missingness, and runtime gates verified.
- [ ] Optional P3 mobile scroll hint; no acceptance-blocking fix required.

final result: passed
