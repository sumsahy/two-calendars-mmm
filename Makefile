# One-command entry points. Everything is reproducible from config/scenarios.yaml (fixed seeds).
PY := PYTHONPATH=src python3

.PHONY: install test data validate eval fit sweep sweep-equal replicate report all demo-bad-drop llm-live

install:            ## install dependencies
	pip install -e ".[dev]"

test:               ## 37+ unit and integration tests (no API key needed)
	$(PY) -m pytest -q -p no:warnings

data:               ## generate all synthetic worlds into data/<scenario>/
	$(PY) -c "from tcmmm.generator import load_scenarios, write_scenario; [write_scenario(n, c) for n, c in load_scenarios().items()]"

validate: data      ## refresh gate on the main scenario's vendor drop (exit 2 = BLOCK)
	$(PY) -m tcmmm.validation.run --vendor-dir data/main/vendor

eval:               ## score the LLM spec reader on 12 labelled specs
	$(PY) -m tcmmm.validation.eval

fit:                ## main scenario, all four TV versions, main (spend-share) prior
	$(PY) -m tcmmm.pipeline --scenario main --prior spend_share

sweep:              ## all scenarios, spend-share prior (main analysis)
	$(PY) -m tcmmm.pipeline --all --prior spend_share --draws 600 --tune 800

sweep-equal:        ## all scenarios, equal prior (sensitivity)
	$(PY) -m tcmmm.pipeline --all

replicate:          ## extra random worlds for the two decisive scenarios
	$(PY) -m tcmmm.replicate --scenarios main tv_clearly_better --seeds 3 --prior spend_share
	$(PY) -m tcmmm.replicate --scenarios main tv_clearly_better --seeds 3

report:             ## build reports/before_after.html from results
	$(PY) -m tcmmm.report.build_html

all: test validate eval sweep sweep-equal replicate report

demo-bad-drop: data ## simulate a vendor silently switching to week-ending dates; gate must BLOCK
	rm -rf data/drops/week_ending && mkdir -p data/drops && cp -r data/main/vendor data/drops/week_ending
	$(PY) -c "import pandas as pd; p='data/drops/week_ending/tv_media_weekly.csv'; d=pd.read_csv(p, parse_dates=['week_start']); d['week_start']=(d['week_start']+pd.Timedelta(days=6)).dt.strftime('%Y-%m-%d'); d.to_csv(p, index=False)"
	-$(PY) -m tcmmm.validation.run --vendor-dir data/drops/week_ending --out reports/validation/bad_drop

llm-live:           ## needs GROQ_API_KEY: record Groq readings, then score them
	$(PY) -c "from pathlib import Path; from tcmmm.validation.llm_spec_reader import record_live; record_live(sorted(Path('specs/vendor').glob('*.md')) + sorted(Path('specs/eval').glob('*.md')))"
	LLM_FIXTURE_DIR=specs/llm_fixtures_groq LLM_MODE=recorded $(PY) -m tcmmm.validation.eval
