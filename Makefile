.PHONY: help setup reproduce data agent judge live clean test

PY ?= python3

help:
	@echo "make setup      install dependencies"
	@echo "make reproduce  replay every headline number offline, no API key   (~60s)"
	@echo "make test       sanity checks on the committed artifacts"
	@echo ""
	@echo "make data       rebuild from the Kaggle CSV (needs data/raw/twcs.csv)  (~4 min)"
	@echo "make live       regenerate all model outputs via the API (needs ANTHROPIC_API_KEY)"
	@echo "make clean      remove derived artifacts (keeps the cache and golden set)"

setup:
	$(PY) -m pip install -r requirements.txt

# ---------------------------------------------------------------------------
# The headline path. No API key, no network, no raw data download.
# Every number quoted in reports/REPORT.md is produced here.
# ---------------------------------------------------------------------------
reproduce:
	@echo "=== [1/6] baselines: trivial + simple + degenerate policies ==="
	$(PY) scripts/07_run_baselines.py
	@echo ""
	@echo "=== [2/6] agent triage (replayed from committed cache) ==="
	LLM_OFFLINE=1 $(PY) scripts/08_run_agent.py --offline --triage-only
	@echo ""
	@echo "=== [3/6] escalation operating point + cost-ratio sensitivity ==="
	$(PY) scripts/09_operating_point.py
	@echo ""
	@echo "=== [4/6] judge: agreement with the blind human, then system scores ==="
	$(PY) scripts/12_analyse_judge.py
	@echo ""
	@echo "=== [5/6] interrogating the headline result ==="
	$(PY) scripts/13_interrogate_result.py
	@echo ""
	@echo "=== [6/6] retrieval: quality, and whether it helps at all ==="
	$(PY) scripts/14_eval_retrieval.py
	$(PY) scripts/15_retrieval_ablation.py
	@echo ""
	@echo "Done. JSON for every figure is in results/."

test:
	$(PY) -m pytest tests/ -q

# ---------------------------------------------------------------------------
# Rebuilding from source data. Requires the Kaggle file; see README.
# ---------------------------------------------------------------------------
data: data/raw/twcs.csv
	$(PY) scripts/01_select_brand.py
	$(PY) scripts/02_build_threads.py
	$(PY) scripts/03_explore_intents.py
	$(PY) scripts/04_build_splits.py
	$(PY) scripts/05_sample_golden.py
	$(PY) scripts/06_finalise_golden.py data/golden/raw_annotations.jsonl

data/raw/twcs.csv:
	@echo "data/raw/twcs.csv not found."
	@echo "Download from kaggle.com/datasets/thoughtvector/customer-support-on-twitter"
	@echo "and unzip twcs.csv into data/raw/. Not redistributed here (516MB, Kaggle terms)."
	@exit 1

# ---------------------------------------------------------------------------
# Live inference. Produces different completions; see docs/INFERENCE.md.
# ---------------------------------------------------------------------------
live:
	@test -n "$$ANTHROPIC_API_KEY" || (echo "ANTHROPIC_API_KEY is not set" && exit 1)
	$(PY) scripts/08_run_agent.py
	$(PY) scripts/10_build_judge_tasks.py
	$(PY) scripts/11_run_judge.py
	$(PY) scripts/12_analyse_judge.py

clean:
	rm -f results/*.json results/*.csv results/*.txt
	rm -f runs/predictions_*.jsonl runs/pending_*.jsonl
	rm -rf runs/chunks
	@echo "Kept: cache/, data/golden/, runs/human_scores.jsonl, runs/judge_*.jsonl"
