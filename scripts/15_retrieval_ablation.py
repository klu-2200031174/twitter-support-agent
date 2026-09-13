"""Score the retrieval ablation: agent WITH vs WITHOUT historical evidence.

The brief asks for replies "grounded in how that brand has historically
resolved similar issues". This is the experiment that asks whether that
grounding does anything, rather than assuming it does because it was built.

Paired and blinded: the same 40 stratum-A cases, both variants judged side by
side under the same rubric, presentation order shuffled, system identity in a
separate key file the judging step never read.

Reads completions from the committed cache so a clean checkout reproduces it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.evaluation import metrics as M
from src.evaluation.judge import BlindedCase, DIMENSIONS, judge_user, parse_scores
from src.llm import DEFAULT_CACHE, LLM, _Cache

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
RESULTS = REPO / "results"


def main() -> None:
    tasks = [json.loads(l) for l in (RUNS / "ablation_task.jsonl").open(encoding="utf-8")]
    key = {json.loads(l)["golden_id"]: json.loads(l)["mapping"]
           for l in (RUNS / "ablation_key.jsonl").open(encoding="utf-8")}
    system = (RUNS / "judge_system.txt").read_text(encoding="utf-8")
    cache = _Cache(DEFAULT_CACHE)

    pairs, dims, best = [], {d: [] for d in DIMENSIONS}, {"with_retrieval": 0, "no_retrieval": 0}
    missing = 0
    for t in tasks:
        case = BlindedCase(golden_id=t["golden_id"], message=t["message"],
                           letters=t["candidates"], mapping={}, order=list(t["candidates"]))
        payload = {"model": "claude-sonnet-4-5", "system": system,
                   "messages": [{"role": "user", "content": judge_user(case)}],
                   "max_tokens": 700, "temperature": 0.0, "stop_sequences": None}
        hit = cache.get(LLM._key(payload))
        if hit is None:
            missing += 1
            continue
        parsed = parse_scores(hit["text"])
        m = key[t["golden_id"]]
        inv = {v: k for k, v in m.items()}
        a = parsed["scores"].get(inv["with_retrieval"])
        b = parsed["scores"].get(inv["no_retrieval"])
        if not a or not b:
            continue
        pairs.append((float(np.mean([a[d] for d in DIMENSIONS])),
                      float(np.mean([b[d] for d in DIMENSIONS]))))
        for d in DIMENSIONS:
            dims[d].append((a[d], b[d]))
        if parsed["best"] in m:
            best[m[parsed["best"]]] += 1

    if missing:
        raise SystemExit(f"{missing} ablation judgements missing from cache")

    overall = M.paired_bootstrap_diff(pairs, lambda v: float(np.mean(v)))
    by_dim = {d: M.paired_bootstrap_diff(v, lambda x: float(np.mean(x))) for d, v in dims.items()}

    out = {"n": len(pairs), "overall": overall, "best_picks": best, "by_dimension": by_dim,
           "interpretation": (
               "Negative diff means retrieval HURTS. Amazon's historical replies are "
               "heavily deflection-shaped, so grounding the drafter in them teaches "
               "deflection, which the rubric scores as less relevant.")}
    M.dump(out, RESULTS / "retrieval_ablation.json")

    print("=" * 74)
    print(f"RETRIEVAL ABLATION (n={len(pairs)} paired, blinded)  with - without")
    print("=" * 74)
    print(f"  overall: with={overall['a']:.3f}  without={overall['b']:.3f}  "
          f"diff={overall['diff']:+.3f}  CI[{overall['ci_lo']:+.3f},{overall['ci_hi']:+.3f}]")
    print(f"  P(retrieval better) = {overall['p_a_better']:.2f}")
    print(f"  judge picked best:  with={best['with_retrieval']}  without={best['no_retrieval']}")
    print("\n  by dimension:")
    for d, r in by_dim.items():
        flag = "  <- significant" if r["ci_hi"] < 0 or r["ci_lo"] > 0 else ""
        print(f"    {d:<12} {r['diff']:+.3f}  CI[{r['ci_lo']:+.2f},{r['ci_hi']:+.2f}]{flag}")
    print(f"\nwrote {RESULTS/'retrieval_ablation.json'}")


if __name__ == "__main__":
    main()
