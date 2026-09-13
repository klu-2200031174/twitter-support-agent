"""Run both baselines on the golden set and record their numbers.

Also runs two diagnostics that are not baselines but change how the agent's
results should be read:

  INTENT-ONLY ESCALATION
      Predict escalation from the GOLD intent alone, using each intent's most
      common escalation outcome. If the agent's escalation policy cannot beat
      this, then all the rule reasoning is decoration and escalation is just
      intent classification wearing a hat.

  ALWAYS-ESCALATE / NEVER-ESCALATE
      The two degenerate policies. Always-escalate has perfect recall and zero
      automation; never-escalate has perfect automation and catches nothing.
      They bracket the achievable range, and any escalation number should be
      read against them rather than against 0 or 1.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.retrieve import HistoryIndex
from src.baselines.models import SimpleBaseline, TrivialBaseline
from src.evaluation import metrics as M

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "data" / "golden" / "golden_set.jsonl"
RETRIEVAL = REPO / "data" / "processed" / "retrieval_slim.jsonl"
RESULTS = REPO / "results"


def load_golden() -> list[dict]:
    return [json.loads(l) for l in GOLDEN.open(encoding="utf-8")]


def score(name: str, gold: list[dict], preds: list, stratum: str | None = None) -> dict:
    rows = list(zip(gold, preds))
    if stratum:
        rows = [(g, p) for g, p in rows if g["stratum"] == stratum]
    if not rows:
        return {}
    intent_pairs = [(g["label_intent"], p.intent) for g, p in rows]
    esc = [M.EscalationOutcome(gold=g["label_escalate"], pred=p.escalate) for g, p in rows]

    f1_pt, f1_lo, f1_hi = M.bootstrap_ci(intent_pairs, M.macro_f1)
    acc_pt, acc_lo, acc_hi = M.bootstrap_ci(intent_pairs, M.accuracy)
    rec_pt, rec_lo, rec_hi = M.bootstrap_ci(esc, M.escalation_recall)
    cost_pt, cost_lo, cost_hi = M.bootstrap_ci(esc, M.escalation_cost)

    return {
        "system": name,
        "stratum": stratum or "ALL",
        "n": len(rows),
        "intent": {
            "macro_f1": round(f1_pt, 4), "macro_f1_ci": [round(f1_lo, 4), round(f1_hi, 4)],
            "accuracy": round(acc_pt, 4), "accuracy_ci": [round(acc_lo, 4), round(acc_hi, 4)],
            "per_class": M.per_class_report(intent_pairs),
            "top_confusions": M.top_confusions(intent_pairs),
        },
        "escalation": {
            **M.escalation_stats(esc),
            "recall_ci": [round(rec_lo, 4), round(rec_hi, 4)],
            "cost_per_case": round(cost_pt, 4),
            "cost_per_case_ci": [round(cost_lo, 4), round(cost_hi, 4)],
        },
    }


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    gold = load_golden()
    texts = [g["customer_message"] for g in gold]
    intents = [g["label_intent"] for g in gold]
    stratum_a = [g for g in gold if g["stratum"] == "A_random"]

    print(f"golden: {len(gold)} ({len(stratum_a)} in stratum A)")

    # --- trivial ----------------------------------------------------------
    # Majority class taken from stratum A only: it is the only unbiased
    # estimate of what "most frequent" means in production traffic.
    trivial = TrivialBaseline.fit([g["label_intent"] for g in stratum_a])
    print(f"trivial majority intent: {trivial.majority_intent}")
    trivial_preds = trivial.predict(gold)

    # --- simple -----------------------------------------------------------
    print("building retrieval index ...", flush=True)
    index = HistoryIndex.from_jsonl(RETRIEVAL)
    simple = SimpleBaseline(index=index)
    oof_intents, oof_confs = simple.predict_intents_oof(texts, intents)
    simple_preds = simple.predict(gold, intents=oof_intents, confs=oof_confs)

    out = {"systems": {}, "diagnostics": {}}
    for name, preds in [("trivial", trivial_preds), ("simple", simple_preds)]:
        out["systems"][name] = {
            "stratum_A": score(name, gold, preds, "A_random"),
            "all": score(name, gold, preds, None),
        }

    # --- diagnostics ------------------------------------------------------
    # Intent-only escalation, fitted on stratum A, applied everywhere.
    by_intent = defaultdict(list)
    for g in stratum_a:
        by_intent[g["label_intent"]].append(g["label_escalate"])
    intent_policy = {k: (sum(v) / len(v)) >= 0.5 for k, v in by_intent.items()}
    esc_io = [
        M.EscalationOutcome(gold=g["label_escalate"],
                            pred=intent_policy.get(g["label_intent"], True))
        for g in stratum_a
    ]
    out["diagnostics"]["escalation_from_gold_intent_only"] = {
        "policy": intent_policy,
        **M.escalation_stats(esc_io),
        "note": ("Upper bound on what escalation looks like if it is nothing more than "
                 "intent classification. Uses GOLD intents, so no real system can do "
                 "better by this route."),
    }
    for name, val in [("always_escalate", True), ("never_escalate", False)]:
        e = [M.EscalationOutcome(gold=g["label_escalate"], pred=val) for g in stratum_a]
        out["diagnostics"][name] = M.escalation_stats(e)

    # Keyword-rule escalation on its own, separated from the simple baseline's
    # intent model, so the two halves can be judged independently.
    esc_kw = [
        M.EscalationOutcome(gold=g["label_escalate"],
                            pred=bool(SimpleBaseline.escalation_rules(g["customer_message"])))
        for g in stratum_a
    ]
    out["diagnostics"]["keyword_rules_only"] = M.escalation_stats(esc_kw)

    M.dump(out, RESULTS / "baselines.json")

    # --- console summary --------------------------------------------------
    print("\n" + "=" * 78)
    print(f"{'system':<28}{'macroF1':>9}{'acc':>8}{'escRec':>9}{'auto%':>8}{'cost/100':>10}")
    print("-" * 78)
    for name in ("trivial", "simple"):
        s = out["systems"][name]["stratum_A"]
        print(f"{name+' (stratum A)':<28}{s['intent']['macro_f1']:>9.3f}"
              f"{s['intent']['accuracy']:>8.3f}{s['escalation']['recall']:>9.3f}"
              f"{s['escalation']['automation_rate']:>8.3f}"
              f"{s['escalation']['expected_cost_per_100']:>10.1f}")
    print("-" * 78)
    for k in ("always_escalate", "never_escalate", "keyword_rules_only",
              "escalation_from_gold_intent_only"):
        d = out["diagnostics"][k]
        print(f"{k:<28}{'':>9}{'':>8}{d['recall']:>9.3f}"
              f"{d['automation_rate']:>8.3f}{d['expected_cost_per_100']:>10.1f}")
    print("=" * 78)
    print(f"\nwrote {RESULTS/'baselines.json'}")


if __name__ == "__main__":
    main()
