"""Measure the retriever, because "grounded" is only a claim until it is.

There is no relevance-labelled retrieval set here, so a proxy is used and named
as a proxy: for each golden case, does the top-k retrieved historical case
carry the SAME hand-labelled intent? Intent match is weaker than topical
relevance -- two delivery_delayed cases can be about different carriers and
different promises -- so this is an upper bound on how useful the evidence is,
not a measure of it.

The number that matters more is the similarity distribution. If the best match
for a typical case scores 0.2 on a 0-1 cosine, the "precedent" shown to the
drafter is barely related to the case, and any claim that the reply is grounded
in brand history is doing very little work.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.agent.retrieve import HistoryIndex
from src.evaluation import metrics as M

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


def main() -> None:
    gold = [json.loads(l) for l in (REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8")]
    preds = {p["case_id"]: p for p in (
        json.loads(l) for l in (REPO / "runs/predictions_agent_A.jsonl").open(encoding="utf-8"))}
    index = HistoryIndex.from_jsonl(REPO / "data/processed/retrieval_slim.jsonl")
    print(f"retrieval corpus: {len(index.cases):,} historical cases")

    top1, topk_mean, n_empty = [], [], 0
    for g in gold:
        hits = index.search(g["customer_message"], k=4)
        if not hits:
            n_empty += 1
            top1.append(0.0)
            topk_mean.append(0.0)
            continue
        top1.append(hits[0].score)
        topk_mean.append(float(np.mean([h.score for h in hits])))

    sim = {
        "n": len(gold),
        "cases_with_no_match_above_threshold": n_empty,
        "top1_similarity": {
            "mean": round(float(np.mean(top1)), 4),
            "p10": round(float(np.percentile(top1, 10)), 4),
            "p50": round(float(np.percentile(top1, 50)), 4),
            "p90": round(float(np.percentile(top1, 90)), 4),
        },
        "share_top1_below_0.30": round(float(np.mean([s < 0.30 for s in top1])), 4),
        "share_top1_below_0.20": round(float(np.mean([s < 0.20 for s in top1])), 4),
    }

    # Proxy relevance: does the retrieved neighbour share the gold intent?
    # Neighbour intents are not labelled, so they are approximated by the
    # agent's own classifier -- a noisy proxy on top of a proxy, flagged as
    # such rather than reported as recall.
    from src.baselines.models import SimpleBaseline

    texts = [g["customer_message"] for g in gold]
    intents = [g["label_intent"] for g in gold]
    clf = SimpleBaseline().fit(texts, intents)

    match_at1, match_atk = [], []
    for g in gold:
        hits = index.search(g["customer_message"], k=4)
        if not hits:
            match_at1.append(False)
            match_atk.append(False)
            continue
        pred_intents = clf.clf.predict([h.customer_message for h in hits])
        match_at1.append(pred_intents[0] == g["label_intent"])
        match_atk.append(g["label_intent"] in set(pred_intents))

    rel = {
        "intent_match_at_1": round(float(np.mean(match_at1)), 4),
        "intent_match_at_4": round(float(np.mean(match_atk)), 4),
        "caveat": ("Neighbour intents come from a TF-IDF classifier fitted on the golden "
                   "labels, not from human annotation. Treat as indicative only."),
    }

    # Does better retrieval actually produce better replies? Correlate the
    # top-1 similarity with the judge's overall score for the agent.
    corr = None
    judge_path = RESULTS / "judge_analysis.json"
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        from importlib import import_module
        mod = import_module("12_analyse_judge")
        judge = mod.load_judge()
        key = {json.loads(l)["golden_id"]: json.loads(l)
               for l in (REPO / "runs/judge_key.jsonl").open(encoding="utf-8")}
        from src.evaluation.judge import DIMENSIONS
        xs, ys = [], []
        for g in gold:
            gid = g["golden_id"]
            if gid not in judge or gid not in preds:
                continue
            inv = {v: k for k, v in key[gid]["mapping"].items()}
            s = judge[gid]["scores"].get(inv.get("agent"))
            if not s:
                continue
            retr = preds[gid].get("retrieved") or []
            best = max([r["score"] for r in retr], default=0.0)
            xs.append(best)
            ys.append(float(np.mean([s[d] for d in DIMENSIONS])))
        if len(xs) > 10:
            corr = {
                "n": len(xs),
                "spearman_top1sim_vs_judge_score": round(M.spearman(xs, ys), 4),
                "interpretation": ("If this is near zero, the retrieved evidence is not what "
                                   "is driving reply quality -- the model's own prior is."),
            }
    except Exception as exc:  # noqa: BLE001
        corr = {"error": str(exc)[:200]}

    out = {"similarity": sim, "proxy_relevance": rel, "does_retrieval_help": corr}
    M.dump(out, RESULTS / "retrieval_eval.json")

    print("\n=== similarity of the best historical match ===")
    print(f"  mean {sim['top1_similarity']['mean']:.3f} | "
          f"p10 {sim['top1_similarity']['p10']:.3f} | "
          f"median {sim['top1_similarity']['p50']:.3f} | "
          f"p90 {sim['top1_similarity']['p90']:.3f}")
    print(f"  share of cases whose BEST match scores below 0.30: {sim['share_top1_below_0.30']:.1%}")
    print(f"  share below 0.20: {sim['share_top1_below_0.20']:.1%}")
    print("\n=== proxy relevance ===")
    print(f"  intent match @1: {rel['intent_match_at_1']:.1%} | @4: {rel['intent_match_at_4']:.1%}")
    if corr and "spearman_top1sim_vs_judge_score" in corr:
        print("\n=== does retrieval quality predict reply quality? ===")
        print(f"  Spearman(top-1 similarity, judge score) = "
              f"{corr['spearman_top1sim_vs_judge_score']:+.3f}  (n={corr['n']})")
    print(f"\nwrote {RESULTS/'retrieval_eval.json'}")


if __name__ == "__main__":
    main()
