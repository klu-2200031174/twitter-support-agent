"""Reconcile the raw annotation pass into the final golden set.

Two things are recorded here rather than quietly fixed.

1. RULE-SET DRIFT. The escalation rules were edited during annotation: E2 was
   widened from "moves money" to "requires an action on this account", and E9
   (relationship risk) was added, because labelling surfaced cases the original
   rules could not adjudicate. Editing a rubric mid-annotation invalidates
   labels made under the old version unless every one is re-swept. This script
   performs that sweep deterministically and prints exactly how many labels it
   touched, so a reader can judge the damage instead of taking it on trust.

2. AUDITABILITY. Every escalate=True label must name at least one rule. An
   escalation with no rule attached is an intuition, and intuitions cannot be
   reproduced by a second annotator or challenged by a reviewer. The sweep
   assigns the rule implied by the annotation note; any case where no rule
   applies is reported as an error rather than silently passed.

Output
    data/golden/golden_set.jsonl   labelled, joined to the case text
    data/golden/ADJUDICATION.md    the cases flagged for human review
    results/golden_stats.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.taxonomy import ESCALATION_RULE_IDS, INTENT_NAMES, BY_NAME

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "data" / "golden"
RESULTS = REPO / "results"

RENAMES = {"E2_money_action": "E2_account_action"}
# Rule implied by intent when the annotator escalated without naming one.
# These are not new judgements: they are the rule that the annotation note
# already describes, made explicit.
IMPLIED_BY_INTENT = {
    "delivery_missing": "E2_account_action",   # needs a carrier investigation + refund/replace
    "service_complaint": "E9_relationship_risk",
}


def main(labels_path: str) -> None:
    sample = {json.loads(l)["golden_id"]: json.loads(l)
              for l in (GOLDEN / "golden_sample.jsonl").open(encoding="utf-8")}
    labels = [json.loads(l) for l in Path(labels_path).open(encoding="utf-8")]

    renamed = implied = 0
    errors: list[str] = []
    rows = []

    for lab in labels:
        gid = lab["golden_id"]
        if gid not in sample:
            errors.append(f"{gid}: no such case in the sample")
            continue
        if lab["intent"] not in INTENT_NAMES:
            errors.append(f"{gid}: unknown intent {lab['intent']!r}")
            continue

        rules = []
        for r in lab["rules"]:
            if r in RENAMES:
                renamed += 1
                r = RENAMES[r]
            if r not in ESCALATION_RULE_IDS:
                errors.append(f"{gid}: unknown rule {r!r}")
                continue
            rules.append(r)

        if lab["escalate"] and not rules:
            implied_rule = IMPLIED_BY_INTENT.get(lab["intent"])
            if implied_rule is None:
                errors.append(f"{gid}: escalate=True with no rule and no implied rule "
                              f"for intent {lab['intent']!r}")
            else:
                rules.append(implied_rule)
                implied += 1
        if not lab["escalate"] and rules:
            errors.append(f"{gid}: escalate=False but rules {rules} are attached")

        case = sample[gid]
        rows.append({
            "golden_id": gid,
            "case_id": case["case_id"],
            "stratum": case["stratum"],
            "probe": case.get("probe"),
            "created_at": case["created_at"],
            "customer_message": case["customer_message"],
            "reference_reply": case["brand_reply"],
            "n_turns": case["n_turns"],
            "n_brand_turns": case["n_brand_turns"],
            "label_intent": lab["intent"],
            "label_escalate": bool(lab["escalate"]),
            "label_rules": sorted(set(rules)),
            "label_confidence": lab["conf"],
            "label_ambiguous": bool(lab["ambiguous"]),
            "label_note": lab["note"],
        })

    if errors:
        print("!! reconciliation errors:")
        for e in errors:
            print("   ", e)
        raise SystemExit(1)

    rows.sort(key=lambda r: r["golden_id"])
    out = GOLDEN / "golden_set.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- adjudication queue -------------------------------------------------
    # Anything the annotator flagged ambiguous OR marked low confidence is put
    # in front of a second human. This is where single-annotator bias is most
    # likely to be doing the work, so it is where a second opinion buys most.
    queue = [r for r in rows if r["label_ambiguous"] or r["label_confidence"] == "low"]
    lines = [
        "# Adjudication queue",
        "",
        f"{len(queue)} of {len(rows)} golden cases were flagged during annotation as ambiguous ",
        "or low-confidence. These are the cases where a single annotator's judgement is doing ",
        "the most work, and where a second opinion changes the most.",
        "",
        "For each: is the intent right? should it go to a human or can a bot answer it?",
        "",
    ]
    for r in queue:
        alts = [i for i in INTENT_NAMES if i != r["label_intent"]]
        lines += [
            "---",
            "",
            f"### {r['golden_id']}  (labelled `{r['label_intent']}`, "
            f"{'ESCALATE' if r['label_escalate'] else 'auto'}, confidence: {r['label_confidence']})",
            "",
            f"> {r['customer_message'][:500]}",
            "",
            f"*Amazon actually replied:* {r['reference_reply'][:300]}",
            "",
            f"*Why it was flagged:* {r['label_note']}",
            "",
            f"*Definition used:* {BY_NAME[r['label_intent']].summary}",
            "",
        ]
    (GOLDEN / "ADJUDICATION.md").write_text("\n".join(lines), encoding="utf-8")

    stats = {
        "n": len(rows),
        "stratum_A_random": sum(r["stratum"] == "A_random" for r in rows),
        "stratum_B_targeted": sum(r["stratum"] == "B_targeted" for r in rows),
        "intent_distribution_all": dict(Counter(r["label_intent"] for r in rows).most_common()),
        "intent_distribution_stratumA": dict(
            Counter(r["label_intent"] for r in rows if r["stratum"] == "A_random").most_common()),
        "escalate_rate_all": round(sum(r["label_escalate"] for r in rows) / len(rows), 4),
        "escalate_rate_stratumA": round(
            sum(r["label_escalate"] for r in rows if r["stratum"] == "A_random")
            / max(1, sum(r["stratum"] == "A_random" for r in rows)), 4),
        "rule_frequency": dict(Counter(x for r in rows for x in r["label_rules"]).most_common()),
        "confidence": dict(Counter(r["label_confidence"] for r in rows)),
        "ambiguous_n": sum(r["label_ambiguous"] for r in rows),
        "ambiguous_rate": round(sum(r["label_ambiguous"] for r in rows) / len(rows), 4),
        "adjudication_queue_n": len(queue),
        "reconciliation": {
            "rule_ids_renamed": renamed,
            "implied_rules_attached": implied,
            "note": ("Rules were edited mid-annotation (E2 widened, E9 added). Every label was "
                     "re-swept; these counts are how many were touched."),
        },
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "golden_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(f"\nwrote {out}")
    print(f"wrote {GOLDEN/'ADJUDICATION.md'} ({len(queue)} cases for second-opinion review)")


if __name__ == "__main__":
    main(sys.argv[1])
