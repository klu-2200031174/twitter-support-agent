"""Run the blinded LLM judge over all four systems.

Reads only runs/judge_task.jsonl (anonymised candidates). Never reads
runs/judge_key.jsonl -- system identity is rejoined afterwards, at scoring
time, so it cannot influence a score.

Modes mirror the agent runner: --record writes prompts for out-of-band
completion, --offline replays from the committed cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.judge import BlindedCase, judge_system, judge_user, parse_scores
from src.llm import LLM

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"


def load_tasks() -> list[BlindedCase]:
    out = []
    for line in (RUNS / "judge_task.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        out.append(BlindedCase(golden_id=r["golden_id"], message=r["message"],
                               letters=r["candidates"], mapping={}, order=list(r["candidates"])))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--model", default="claude-sonnet-4-5")
    ap.add_argument("--seed-tag", default="", help="suffix to force distinct cache keys "
                                                   "for a repeat run (self-consistency check)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tasks = load_tasks()
    print(f"{len(tasks)} judging tasks")

    tag = f"judge{args.seed_tag}"
    record_path = RUNS / f"pending_{tag}.jsonl" if args.record else None
    if record_path and record_path.exists():
        record_path.unlink()

    llm = LLM(model=args.model, offline=args.offline, record_misses_to=record_path)
    system = judge_system()

    def run(case: BlindedCase):
        user = judge_user(case)
        if args.seed_tag:
            # A trivial, semantically inert marker so a repeat run is a
            # genuinely separate cache entry rather than a replay of the first.
            user = f"{user}\n\n(pass {args.seed_tag})"
        raw = llm.complete(prompt=user, system=system, max_tokens=700, temperature=0.0)
        if not raw:
            return {"golden_id": case.golden_id, "raw": "", "parsed": None}
        try:
            return {"golden_id": case.golden_id, "raw": raw, "parsed": parse_scores(raw)}
        except Exception as exc:  # noqa: BLE001
            return {"golden_id": case.golden_id, "raw": raw, "parsed": None,
                    "error": str(exc)[:200]}

    results = llm.map(run, tasks, workers=1 if args.record else 6, desc=tag)

    if args.record:
        n = sum(1 for _ in record_path.open(encoding="utf-8")) if record_path.exists() else 0
        (RUNS / "judge_system.txt").write_text(system, encoding="utf-8")
        print(f"recorded {n} judge prompts -> {record_path}")
        return

    out = Path(args.out) if args.out else RUNS / f"{tag}_scores.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    bad = sum(1 for r in results if not r.get("parsed"))
    print(f"wrote {out} | unparsed: {bad}/{len(results)}")


if __name__ == "__main__":
    main()
