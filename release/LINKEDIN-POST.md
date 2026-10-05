# LinkedIn post draft

Unpublished draft for the portfolio engineering release. Review the final release location before posting. The previously deployed website does not automatically contain local changes.

---

I built Vannaris to make search-API comparisons inspectable.

Five vendors. An authored 150-question set. Judges from three model families. Public scores, latency, costs, and the missing data behind the result.

The most interesting engineering problem was recovery: retrieval can succeed, cost money, and then lose its judge result to a quota error or interrupted process. The pipeline stores run-specific questions and responses, checkpoints accepted judge calls, and resumes missing work while preserving the original run identity.

A credential-free demo injects a failure and shows recovery through the actual local pipeline. Its data is clearly synthetic and stays separate from the real measurements.

The evaluation also challenged the original idea. Small differences and judge sensitivity made the quality-routing story weaker than the table first suggested. The project preserves those findings, publishes uncertainty, and treats incomplete categories as missing evidence rather than an invitation to print a confident overall score.

The real archive ends on August 24, 2026. This release improves implementation and recomputes analysis from released measurements; it does not claim a new live run. One blinded human calibration supports a limited pairwise finding on one sample. Independent human agreement and absolute-score validation remain open.

If you build evaluation pipelines or backend systems for AI tools, I would value a concrete challenge to the methodology or a reproducible correction to the numbers.

Code and engineering case study: https://github.com/feruzkarimovv/vannaris

Local demo: clone the repository, run `make setup`, then `make demo`.

---

## Publication notes

This is a draft, not a posted message. It claims no traffic, customers, realized savings, deployment, or additional human study. Add a screenshot or short recording only after following [DEMO-WALKTHROUGH.md](DEMO-WALKTHROUGH.md) against the validated release. Keep mock results labelled and historical dates visible. Update concrete claims if implementation or scope changes before posting.
