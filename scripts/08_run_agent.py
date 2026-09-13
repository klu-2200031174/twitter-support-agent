"""Run the agent over the golden set.

Three modes, one code path:

  --record   Write every prompt that misses the cache to runs/pending_*.jsonl
             and produce no predictions. Used to build the committed cache
             without API credentials (see docs/INFERENCE.md).
  --offline  Replay from the committed cache. Any miss is a hard error, which
             is what makes `make reproduce` a real guarantee rather than a
             hope.
  (default)  Live inference against the API, populating the cache as it goes.

The agent sees only `customer_message`. The golden labels, the reference reply,
the thread and the turn counts are all withheld here and only rejoined at
scoring time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.pipeline import SupportAgent, load_index, write_predictions
from src.llm import LLM

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "data" / "golden" / "golden_set.jsonl"
RETRIEVAL = REPO / "data" / "processed" / "retrieval_slim.jsonl"
RUNS = REPO / "runs"
RESULTS = REPO / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="record cache misses as prompts instead of calling the API")
    ap.add_argument("--offline", action="store_true",
                    help="replay from cache only; error on any miss")
    ap.add_argument("--no-retrieval", action="store_true",
                    help="ablation: draft without retrieved evidence")
    ap.add_argument("--triage-only", action="store_true",
                    help="run stage 1 only; skip drafting (intent + escalation eval)")
    ap.add_argument("--model", default="claude-sonnet-4-5")
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tag = "agent_noretrieval" if args.no_retrieval else "agent"
    RUNS.mkdir(exist_ok=True)

    gold = [json.loads(l) for l in GOLDEN.open(encoding="utf-8")]
    # Strip everything the agent must not see.
    cases = [{"case_id": g["golden_id"], "customer_message": g["customer_message"]}
             for g in gold]
    print(f"{len(cases)} cases | model={args.model} | retrieval={not args.no_retrieval}")

    record_path = RUNS / f"pending_{tag}.jsonl" if args.record else None
    if record_path and record_path.exists():
        record_path.unlink()

    llm = LLM(model=args.model, offline=args.offline, record_misses_to=record_path)
    index = None if args.no_retrieval else load_index(RETRIEVAL)
    agent = SupportAgent(llm=llm, index=index, k=4,
                         confidence_threshold=args.threshold,
                         use_retrieval=not args.no_retrieval)

    if args.triage_only:
        from src.agent.pipeline import Prediction

        def triage_only(case):
            t = agent.triage(case["customer_message"])
            return Prediction(
                case_id=case["case_id"], intent=t["intent"], confidence=t["confidence"],
                escalate=t["escalate"], rules=t["rules"], reason=t["reason"], reply="",
                triage_raw=t.get("_raw", ""), parse_error=t.get("_error"),
            )

        preds = llm.map(triage_only, cases, workers=1 if args.record else 6, desc=tag)
        out = Path(args.out) if args.out else RUNS / f"predictions_{tag}_triage.jsonl"
        write_predictions(preds, out)
        n_err = sum(1 for p in preds if p.parse_error)
        print(f"\nwrote {out}\ntriage parse failures: {n_err}/{len(preds)}")
        return

    preds = agent.run_all(cases, workers=1 if args.record else 6, desc=tag)

    if args.record:
        n = sum(1 for _ in record_path.open(encoding="utf-8")) if record_path.exists() else 0
        print(f"\nrecorded {n} prompts needing completion -> {record_path}")
        print("Next: generate completions for these, then run scripts/load_completions.py")
        return

    out = Path(args.out) if args.out else RUNS / f"predictions_{tag}.jsonl"
    write_predictions(preds, out)
    n_err = sum(1 for p in preds if p.parse_error)
    print(f"\nwrote {out}")
    print(f"triage parse failures: {n_err}/{len(preds)}")
    print("usage:", json.dumps(llm.usage.summary()))


if __name__ == "__main__":
    main()
