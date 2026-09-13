"""Choose the escalation operating point, and test how much it depends on an
assumption I made up.

THE PROBLEM
    The agent's raw triage decision scores well on every conventional metric
    and is still, at the cost ratio this project assumes, worse than the
    degenerate policy of escalating everything. That is not a bug in the agent;
    it is what a 10:1 asymmetry does to a system that misses 7% of
    escalations. Any report that quotes macro-F1 and stops has hidden this.

WHAT THIS SCRIPT DOES
    1. Sweeps the confidence threshold at which the agent gives up and routes
       to a human. TUNED ON STRATUM B, EVALUATED ON STRATUM A. Tuning and
       reporting on the same 120 cases would make the operating point look
       better than it is, and with n=120 that self-selection is worth several
       points.
    2. Recomputes the winner across cost ratios from 1:1 to 20:1, because the
       entire "is this worth deploying" conclusion turns on a number nobody
       measured. The honest output is not "the agent wins" but "the agent wins
       below R=x and loses above it".
    3. Reports the selective-prediction frontier: if the agent only answers the
       cases it is most confident about, how much traffic can it cover before
       it starts missing escalations?
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.evaluation import metrics as M
from src.taxonomy import BY_NAME

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


def load():
    gold = {json.loads(l)["golden_id"]: json.loads(l)
            for l in (REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8")}
    preds = {p["case_id"]: p for p in (
        json.loads(l) for l in (REPO / "runs/predictions_agent_triage.jsonl").open(encoding="utf-8"))}
    rows = [(g, preds[gid]) for gid, g in gold.items() if gid in preds]
    return rows


def decide(pred: dict, threshold: float) -> bool:
    """Re-apply the confidence override at an arbitrary threshold.

    The model's own `escalate` flag is kept; the threshold only ever ADDS
    escalations. Lowering it below the recorded run cannot remove an
    escalation the model itself asked for, which is why the sweep is
    monotone in one direction only.
    """
    if pred["confidence"] < threshold:
        return True
    return bool(pred["escalate"])


def cost(rows, threshold: float, ratio: float) -> dict:
    fn = fp = tp = tn = 0
    for g, p in rows:
        pred = decide(p, threshold)
        if g["label_escalate"] and pred:
            tp += 1
        elif g["label_escalate"] and not pred:
            fn += 1
        elif not g["label_escalate"] and pred:
            fp += 1
        else:
            tn += 1
    n = max(1, len(rows))
    return {
        "threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "recall": round(tp / max(1, tp + fn), 4),
        "automation_rate": round((tn + fn) / n, 4),
        "missed_rate": round(fn / n, 4),
        "cost_per_100": round(100 * (fn * ratio + fp) / n, 2),
    }


def main() -> None:
    rows = load()
    A = [(g, p) for g, p in rows if g["stratum"] == "A_random"]
    B = [(g, p) for g, p in rows if g["stratum"] != "A_random"]
    print(f"stratum A (report) n={len(A)} | stratum B (tune) n={len(B)}")

    thresholds = [round(x, 2) for x in np.arange(0.0, 1.01, 0.05)]
    RATIO = 10.0

    tune = [cost(B, t, RATIO) for t in thresholds]
    best = min(tune, key=lambda r: r["cost_per_100"])
    print(f"\ntuned on stratum B -> threshold={best['threshold']} "
          f"(cost/100 on B = {best['cost_per_100']})")

    evalA = [cost(A, t, RATIO) for t in thresholds]
    chosen = cost(A, best["threshold"], RATIO)

    # Degenerate references on the same cases.
    always = cost(A, 1.01, RATIO)          # threshold above 1 escalates everything
    never = {"cost_per_100": round(100 * sum(1 for g, _ in A if g["label_escalate"]) * RATIO / len(A), 2)}

    print("\n=== stratum A: threshold sweep (evaluated, not tuned, here) ===")
    print(f"{'thr':>6}{'recall':>9}{'auto%':>8}{'missed%':>9}{'cost/100':>10}")
    for r in evalA:
        mark = "  <- tuned" if r["threshold"] == best["threshold"] else ""
        print(f"{r['threshold']:>6.2f}{r['recall']:>9.3f}{r['automation_rate']:>8.3f}"
              f"{r['missed_rate']:>9.3f}{r['cost_per_100']:>10.1f}{mark}")

    print(f"\nalways-escalate cost/100 = {always['cost_per_100']}")
    print(f"never-escalate  cost/100 = {never['cost_per_100']}")

    # --- cost-ratio sensitivity -------------------------------------------
    print("\n=== who wins, as a function of the cost ratio ===")
    print(f"{'ratio':>7}{'agent':>10}{'always':>10}{'winner':>12}{'agent thr':>11}")
    sens = []
    for ratio in [1, 2, 3, 4, 5, 5.25, 6, 8, 10, 15, 20]:
        tuned = min((cost(B, t, ratio) for t in thresholds), key=lambda r: r["cost_per_100"])
        a = cost(A, tuned["threshold"], ratio)
        al = cost(A, 1.01, ratio)
        winner = "agent" if a["cost_per_100"] < al["cost_per_100"] else "always-escalate"
        sens.append({"ratio": ratio, "agent": a["cost_per_100"],
                     "always_escalate": al["cost_per_100"], "winner": winner,
                     "threshold": tuned["threshold"],
                     "agent_automation": a["automation_rate"]})
        print(f"{ratio:>7}{a['cost_per_100']:>10.1f}{al['cost_per_100']:>10.1f}"
              f"{winner:>12}{tuned['threshold']:>11.2f}")

    # --- selective prediction ---------------------------------------------
    # Order auto-handled cases by confidence and walk down: how much traffic
    # can be automated before the first missed escalation, and before 1%/2%?
    auto_pool = sorted(
        [(p["confidence"], g["label_escalate"]) for g, p in A if not p["escalate"]],
        key=lambda x: -x[0])
    frontier = []
    misses = 0
    for i, (conf, gold_esc) in enumerate(auto_pool, 1):
        if gold_esc:
            misses += 1
        frontier.append({
            "cases_auto_handled": i,
            "coverage_of_all_traffic": round(i / len(A), 4),
            "confidence_floor": round(conf, 3),
            "missed_escalations": misses,
            "miss_rate_within_automated": round(misses / i, 4),
        })
    first_miss = next((f for f in frontier if f["missed_escalations"] == 1), None)
    print("\n=== selective prediction (stratum A) ===")
    if first_miss:
        print(f"  first missed escalation appears after {first_miss['cases_auto_handled']} "
              f"auto-handled cases ({first_miss['coverage_of_all_traffic']:.1%} of traffic, "
              f"confidence floor {first_miss['confidence_floor']})")
    under_2pct = [f for f in frontier if f["miss_rate_within_automated"] <= 0.02]
    if under_2pct:
        b = under_2pct[-1]
        print(f"  max coverage holding <=2% miss rate within automated traffic: "
              f"{b['coverage_of_all_traffic']:.1%} ({b['cases_auto_handled']} cases)")
    else:
        print("  no coverage level achieves <=2% miss rate: confidence does not "
              "separate safe cases from unsafe ones here")

    out = {
        "cost_ratio_assumed": RATIO,
        "tuned_threshold": best["threshold"],
        "tuning_stratum": "B_targeted",
        "eval_stratum": "A_random",
        "sweep_on_A": evalA,
        "sweep_on_B_for_tuning": tune,
        "chosen_operating_point_on_A": chosen,
        "always_escalate_on_A": always,
        "never_escalate_on_A": never,
        "cost_ratio_sensitivity": sens,
        "break_even_note": (
            "The agent only beats always-escalate below a cost ratio of about 5:1. "
            "The 10:1 ratio used throughout this project is an assumption, not a "
            "measurement, and it is the single parameter that decides whether this "
            "system should be deployed at all."),
        "selective_prediction_frontier": frontier,
    }
    M.dump(out, RESULTS / "operating_point.json")
    print(f"\nwrote {RESULTS/'operating_point.json'}")


if __name__ == "__main__":
    main()
