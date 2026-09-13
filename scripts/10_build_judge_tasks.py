"""Assemble every system's replies and write the blinded judging task.

Four candidates per case:
    agent      the system under test
    simple     nearest-neighbour copy of a real historical AmazonHelp reply
    trivial    one canned macro, identical for every case
    reference  what AmazonHelp actually replied to THIS customer

`reference` is the control that makes the judge auditable. It is a real human
support reply, and it is judged blind in the same batch under the same rubric.
Three things become measurable because it is there:

  * whether the judge can tell quality apart at all (a human reply should beat
    a canned macro; if it does not, the judge is broken)
  * how far the agent is from the human bar, on a like-for-like scale
  * self-preference: if the judge systematically ranks machine text above the
    human's, the gap is the bias, and it is reported rather than assumed absent

`simple` is deliberately a real Amazon reply too -- just one retrieved for a
DIFFERENT customer. So agent-vs-simple isolates "did it fit THIS case",
holding brand voice constant, which is the comparison that actually matters.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.retrieve import HistoryIndex
from src.baselines.models import CANNED_REPLY, SimpleBaseline
from src.evaluation.judge import blind_cases, judge_system, judge_user, write_blinded

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"


def main() -> None:
    gold = [json.loads(l) for l in (REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8")]
    A = [g for g in gold if g["stratum"] == "A_random"]
    agent = {p["case_id"]: p for p in (
        json.loads(l) for l in (RUNS / "predictions_agent_A.jsonl").open(encoding="utf-8"))}

    print(f"{len(A)} stratum-A cases | {len(agent)} agent predictions")
    index = HistoryIndex.from_jsonl(REPO / "data/processed/retrieval_slim.jsonl")
    simple = SimpleBaseline(index=index)

    replies = {
        "agent": {g["golden_id"]: agent[g["golden_id"]]["reply"] for g in A if g["golden_id"] in agent},
        "simple": {g["golden_id"]: simple.nn_reply(g["customer_message"]) for g in A},
        "trivial": {g["golden_id"]: CANNED_REPLY for g in A},
        "reference": {g["golden_id"]: g["reference_reply"] for g in A},
    }
    for k, v in replies.items():
        missing = [g["golden_id"] for g in A if not v.get(g["golden_id"])]
        print(f"  {k:10s} {len(v)} replies, {len(missing)} missing")

    blinded = blind_cases(A, replies)
    write_blinded(blinded, RUNS / "judge_task.jsonl", RUNS / "judge_key.jsonl")
    (RUNS / "judge_system.txt").write_text(judge_system(), encoding="utf-8")

    # Human-agreement subset: the judge's scores are only worth as much as
    # their agreement with a person, so a fixed subset is set aside to be
    # scored by hand FIRST, without the judge's answers visible.
    subset = blinded[:60]
    with (RUNS / "human_scoring_task.jsonl").open("w", encoding="utf-8") as fh:
        for c in subset:
            fh.write(json.dumps({
                "golden_id": c.golden_id, "message": c.message, "candidates": c.letters,
            }, ensure_ascii=False) + "\n")

    print(f"\nwrote {RUNS/'judge_task.jsonl'} ({len(blinded)} cases x 4 candidates)")
    print(f"wrote {RUNS/'judge_key.jsonl'} (de-anonymisation key, not read by judging)")
    print(f"wrote {RUNS/'human_scoring_task.jsonl'} ({len(subset)} cases for hand scoring)")
    print("\n--- sample judging prompt ---")
    print(judge_user(blinded[0])[:1200])


if __name__ == "__main__":
    main()
