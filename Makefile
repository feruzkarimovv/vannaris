VANNARIS_PYTHON ?= .venv/bin/python
VANNARIS_PORT ?= 8000
VANNARIS_BIND ?= 127.0.0.1

.PHONY: setup setup-browser check check-browser check-demo-browser verify serve demo demo-build demo-video recompute headers

setup:
	bash scripts/setup.sh

setup-browser:
	npx playwright install chromium

check:
	VANNARIS_PYTHON="$(VANNARIS_PYTHON)" bash scripts/check-all.sh

check-browser:
	node scripts/check-browser.mjs site

check-demo-browser: demo-build
	node scripts/check-browser.mjs .demo/site --demo

verify: check check-browser check-demo-browser

serve:
	$(VANNARIS_PYTHON) -m http.server $(VANNARIS_PORT) --bind $(VANNARIS_BIND) --directory site

demo-build:
	$(VANNARIS_PYTHON) -m src.demo --out .demo

demo: demo-build
	$(VANNARIS_PYTHON) -m http.server $(VANNARIS_PORT) --bind $(VANNARIS_BIND) --directory .demo/site

demo-video: demo-build
	node scripts/record-demo.mjs

recompute:
	$(VANNARIS_PYTHON) scripts/recompute_publication.py --site-root site --in-place

headers:
	$(VANNARIS_PYTHON) scripts/update_site_headers.py
