"""Sample the 200-case golden set. Two strata, deliberately.

THE PROBLEM WITH ONE SAMPLE
    A purely random sample of 200 measures production reality but leaves the
    rare intents with 3-5 examples each -- per-class F1 on 4 examples is noise,
    and the rare classes here (billing_account, service_complaint) are exactly
    the ones where a mistake is expensive. A purely stratified sample fixes
    that but destroys any claim about production performance, because it
    over-represents rare classes by design.

    So we draw both and keep them separately labelled, forever:

      STRATUM A (n=120, uniform random from the eval pool)
        Unbiased. Every headline number that claims to describe production
        traffic is computed on A alone, and A alone.

      STRATUM B (n=80, targeted at rare and high-stakes intents)
        Biased by construction. Used only for per-class reliability and for
        error analysis, never for a headline number.

    Reporting both, and never mixing them into one average without saying so,
    is the point. The report's "what is misleading" section leans on this.

TARGETING FOR STRATUM B
    Rare intents are found with keyword probes rather than a model, so that
    the sample is not pre-filtered by the very classifier we intend to
    evaluate. Probes over-generate on purpose: they select candidates for a
    human to label, they do not assign labels. A probe that pulls in an
    irrelevant case is harmless -- it just gets labelled whatever it truly is.

Outputs
    data/golden/golden_sample.jsonl   200 unlabelled cases, with stratum tags
    results/golden_sampling.json
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
GOLDEN = REPO / "data" / "golden"
RESULTS = REPO / "results"

SEED = 20260910
N_RANDOM = 120
N_TARGETED = 80

# Probes are intentionally broad. They bias *what gets looked at*, never what
# the label ends up being.
PROBES: dict[str, str] = {
    "billing_account": r"\b(charge[ds]?|charging|billed|billing|unauthori[sz]ed|subscription|"
        r"membership|hacked|locked|log ?in|sign ?in|password|gift ?card|amazon pay|"
        r"prime fee|debited|direct debit)\b",
    "service_complaint": r"\b(customer (service|care)|3 different|three different|no one|nobody|"
        r"worst|useless|passed around|been on the phone|rude|driver|complain(t|ing)?|"
        r"cancel(ling)? my prime|never again)\b",
    "presales_info": r"\b(does it|do you (deliver|ship|sell|have)|can i (order|buy|get)|"
        r"is it possible|what (is|are) the|how (do|does|much|long)|will it|before i (buy|order)|"
        r"in stock|release date|available in)\b",
    "digital_service": r"\b(kindle|fire ?(tv|stick|tablet)|echo|alexa|prime video|amazon music|"
        r"audible|app (crash|keeps|won'?t)|website|checkout error|streaming|download)\b",
    "item_problem": r"\b(damaged|broken|faulty|defect(ive)?|wrong item|not as described|"
        r"missing (part|piece|item)|counterfeit|fake|cracked|smashed)\b",
    "other": r"^\s*(<link>|\W{0,4})\s*$|^.{0,25}$",
}


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8")]


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    rng = random.Random(SEED)

    pool = load(PROC / "eval_pool.jsonl")
    print(f"eval pool: {len(pool):,}")

    # --- Stratum A: uniform random ---------------------------------------
    shuffled = pool[:]
    rng.shuffle(shuffled)
    stratum_a = shuffled[:N_RANDOM]
    taken = {c["case_id"] for c in stratum_a}

    # --- Stratum B: probe-targeted ---------------------------------------
    remaining = [c for c in shuffled[N_RANDOM:]]
    per_probe = N_TARGETED // len(PROBES)
    stratum_b: list[dict] = []
    probe_counts: dict[str, int] = {}

    for intent, pattern in PROBES.items():
        rx = re.compile(pattern, re.I)
        hits = [c for c in remaining
                if c["case_id"] not in taken and rx.search(c["customer_message"])]
        rng.shuffle(hits)
        picked = hits[:per_probe]
        for c in picked:
            taken.add(c["case_id"])
            stratum_b.append({**c, "_probe": intent})
        probe_counts[intent] = len(picked)

    # Top up to exactly N_TARGETED if a probe under-delivered.
    while len(stratum_b) < N_TARGETED:
        c = remaining.pop()
        if c["case_id"] in taken:
            continue
        taken.add(c["case_id"])
        stratum_b.append({**c, "_probe": "topup"})
        probe_counts["topup"] = probe_counts.get("topup", 0) + 1

    rows = []
    for i, c in enumerate(stratum_a):
        rows.append({"golden_id": f"G{i+1:03d}", "stratum": "A_random", "probe": None, **c})
    for i, c in enumerate(stratum_b):
        probe = c.pop("_probe")
        rows.append({"golden_id": f"G{N_RANDOM+i+1:03d}", "stratum": "B_targeted",
                     "probe": probe, **c})

    # Present in shuffled order so that the annotator does not label all of one
    # probe in a row -- consecutive similar cases drag labels toward each other.
    rng.shuffle(rows)
    for n, r in enumerate(rows):
        r["order"] = n

    out = GOLDEN / "golden_sample.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {
        "seed": SEED,
        "eval_pool_size": len(pool),
        "n_total": len(rows),
        "stratum_A_random": N_RANDOM,
        "stratum_B_targeted": N_TARGETED,
        "probe_yield": probe_counts,
        "cut_date": "2017-11-15",
        "rule": ("Headline production metrics are computed on stratum A only. Stratum B is "
                 "used for per-class reliability and error analysis and is never averaged "
                 "into a production claim without an explicit reweighting."),
    }
    (RESULTS / "golden_sampling.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
