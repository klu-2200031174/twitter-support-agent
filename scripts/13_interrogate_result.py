"""Attack the headline result.

The judge says the agent beats real AmazonHelp replies by +0.85 (P=1.00). A
system that outscores the humans whose behaviour it was trained to imitate is
usually measuring an artefact. Four candidate explanations are testable here.

H1  MY OWN PREPROCESSING CRIPPLED THE BASELINE.
    Cleaning replaced every URL with the literal token "<link>". 60% of real
    AmazonHelp replies contain one; the agent was instructed never to emit
    links, so 11% of its replies do. Half of Amazon's actual answer -- the help
    page it points to -- was deleted by me before judging, and the judge then
    scored the remains as unhelpful. Test: re-run the comparison on only those
    cases where the reference reply contains no link.

H2  SELF-PREFERENCE.
    Judge and agent are the same model family. Test: compare the judge's
    ranking against the blind human scores collected before the judge ran. If
    the human also ranks the agent first, self-preference is not the whole
    story; if the gap is much smaller for the human, it is part of it.

H3  THE RUBRIC REWARDS WHAT THE AGENT DOES.
    The rubric prizes acknowledging specifics and asking one precise question.
    That is exactly the shape the drafting prompt was written to produce, and
    it is NOT what Amazon's agents optimise for -- they optimise for moving the
    customer into a channel where they can actually see the order. Test:
    decompose the gap by dimension and check whether it concentrates in the
    dimensions the prompt targets.

H4  THE COMPARISON IS UNFAIR IN KIND.
    Amazon's reply is a real action in a real workflow with consequences; the
    agent's is a draft nobody sent. Not testable from this data. Stated as a
    limitation, not resolved.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.evaluation import metrics as M
from src.evaluation.judge import DIMENSIONS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from importlib import import_module

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
RESULTS = REPO / "results"


def main() -> None:
    mod = import_module("12_analyse_judge")
    judge = mod.load_judge()
    key = {json.loads(l)["golden_id"]: json.loads(l)
           for l in (RUNS / "judge_key.jsonl").open(encoding="utf-8")}
    tasks = {json.loads(l)["golden_id"]: json.loads(l)
             for l in (RUNS / "judge_task.jsonl").open(encoding="utf-8")}
    human = {json.loads(l)["golden_id"]: json.loads(l)
             for l in (RUNS / "human_scores.jsonl").open(encoding="utf-8")}

    def score_of(gid, system, source):
        mapping = key[gid]["mapping"]
        inv = {v: k for k, v in mapping.items()}
        letter = inv.get(system)
        if letter is None:
            return None
        s = (source.get(gid) or {}).get("scores", {}).get(letter)
        if not s:
            return None
        return float(np.mean([s[d] for d in DIMENSIONS])), s

    out = {}

    # ---- H1: the <link> artefact -----------------------------------------
    with_link, without_link = [], []
    for gid in judge:
        mapping = key[gid]["mapping"]
        inv = {v: k for k, v in mapping.items()}
        ref_text = tasks[gid]["candidates"].get(inv.get("reference"), "")
        a = score_of(gid, "agent", judge)
        r = score_of(gid, "reference", judge)
        if not a or not r:
            continue
        (with_link if "<link>" in ref_text else without_link).append((a[0], r[0]))

    h1 = {
        "all_cases": M.paired_bootstrap_diff(with_link + without_link, lambda v: float(np.mean(v))),
        "reference_contains_link": M.paired_bootstrap_diff(with_link, lambda v: float(np.mean(v))),
        "reference_has_no_link": M.paired_bootstrap_diff(without_link, lambda v: float(np.mean(v))),
        "n_with_link": len(with_link),
        "n_without_link": len(without_link),
    }
    out["H1_link_artefact"] = h1

    # ---- H2: self-preference, judge vs blind human -----------------------
    h2_pairs_judge, h2_pairs_human = [], []
    for gid in human:
        if gid not in judge:
            continue
        aj, rj = score_of(gid, "agent", judge), score_of(gid, "reference", judge)
        ah, rh = score_of(gid, "agent", human), score_of(gid, "reference", human)
        if aj and rj:
            h2_pairs_judge.append((aj[0], rj[0]))
        if ah and rh:
            h2_pairs_human.append((ah[0], rh[0]))
    out["H2_self_preference"] = {
        "judge_gap_on_hand_scored_subset": M.paired_bootstrap_diff(
            h2_pairs_judge, lambda v: float(np.mean(v))),
        "human_gap_on_same_subset": M.paired_bootstrap_diff(
            h2_pairs_human, lambda v: float(np.mean(v))),
        "n": len(h2_pairs_human),
    }

    # ---- H3: where does the gap live? ------------------------------------
    per_dim = {}
    for d in DIMENSIONS:
        pairs = []
        for gid in judge:
            a, r = score_of(gid, "agent", judge), score_of(gid, "reference", judge)
            if a and r:
                pairs.append((a[1][d], r[1][d]))
        per_dim[d] = M.paired_bootstrap_diff(pairs, lambda v: float(np.mean(v)))
    out["H3_gap_by_dimension"] = per_dim

    # ---- context: escalation-conditioned quality --------------------------
    # A holding reply for an escalated case and a resolving reply for an
    # auto-handled case are different jobs. Scoring them together hides which
    # one the agent is actually good at.
    gold = {json.loads(l)["golden_id"]: json.loads(l)
            for l in (REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8")}
    split = defaultdict(list)
    for gid in judge:
        a = score_of(gid, "agent", judge)
        r = score_of(gid, "reference", judge)
        if not a or not r:
            continue
        bucket = "gold_escalate" if gold[gid]["label_escalate"] else "gold_auto"
        split[bucket].append((a[0], r[0]))
    out["quality_by_gold_routing"] = {
        k: {**M.paired_bootstrap_diff(v, lambda x: float(np.mean(x))), "n": len(v)}
        for k, v in split.items()
    }

    M.dump(out, RESULTS / "result_interrogation.json")

    print("=== H1: is the agent's win an artefact of my own preprocessing? ===")
    print(f"  all cases                       agent-reference = {h1['all_cases']['diff']:+.3f}")
    print(f"  reference HAS a <link> (n={h1['n_with_link']:>3})   "
          f"= {h1['reference_contains_link']['diff']:+.3f}  "
          f"CI[{h1['reference_contains_link']['ci_lo']:+.2f},{h1['reference_contains_link']['ci_hi']:+.2f}]")
    print(f"  reference has NO link  (n={h1['n_without_link']:>3})   "
          f"= {h1['reference_has_no_link']['diff']:+.3f}  "
          f"CI[{h1['reference_has_no_link']['ci_lo']:+.2f},{h1['reference_has_no_link']['ci_hi']:+.2f}]")

    print("\n=== H2: self-preference (same 30 cases, judge vs blind human) ===")
    j = out["H2_self_preference"]["judge_gap_on_hand_scored_subset"]
    h = out["H2_self_preference"]["human_gap_on_same_subset"]
    print(f"  judge says agent - reference = {j['diff']:+.3f}  CI[{j['ci_lo']:+.2f},{j['ci_hi']:+.2f}]")
    print(f"  human says agent - reference = {h['diff']:+.3f}  CI[{h['ci_lo']:+.2f},{h['ci_hi']:+.2f}]")
    print(f"  inflation attributable to the judge: {j['diff']-h['diff']:+.3f}")

    print("\n=== H3: where the gap lives ===")
    for d, v in per_dim.items():
        print(f"  {d:<12} {v['diff']:+.3f}  CI[{v['ci_lo']:+.2f},{v['ci_hi']:+.2f}]")

    print("\n=== agent vs reference, split by whether the case needed a human ===")
    for k, v in out["quality_by_gold_routing"].items():
        print(f"  {k:<16} n={v['n']:>3}  diff={v['diff']:+.3f}  "
              f"CI[{v['ci_lo']:+.2f},{v['ci_hi']:+.2f}]")
    print(f"\nwrote {RESULTS/'result_interrogation.json'}")


if __name__ == "__main__":
    main()
