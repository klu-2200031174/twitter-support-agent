"""LLM-as-judge for reply quality, with the biases it is known to have
designed against rather than assumed away.

WHY A JUDGE AT ALL
    Intent and escalation have ground truth. Reply quality does not: there is
    no single correct tweet. Comparing against Amazon's actual reply by n-gram
    overlap would measure imitation of one arbitrary reply, and most of
    Amazon's replies are themselves mediocre. So the reply is scored against a
    written rubric instead.

THE THREE THINGS THAT MAKE MOST LLM-JUDGE SETUPS WORTHLESS

    1. Self-preference. A judge scores text from its own model family higher.
       Unavoidable here (only one model family is reachable), so it is
       MEASURED instead of denied: Amazon's real human replies are scored
       blind alongside the agent's, in the same batch, under the same rubric.
       If the judge cannot rank a real human reply above a canned macro, its
       scores mean nothing. If it systematically prefers machine text over the
       human's, the size of that gap is reported.

    2. Position bias. Judges favour whichever candidate appears first. The
       candidate order is shuffled per case with a recorded seed, so position
       is decorrelated from system identity, and the residual effect is
       measurable from the recorded positions.

    3. Unblinded judging. A judge told "this is the AI's reply" grades
       differently. Systems are anonymised to A/B/C/D per case and the mapping
       is written to a separate file that the judging step never reads.

    None of this makes the judge trustworthy on its own. It makes the judge's
    failure modes visible, which is the most that can honestly be claimed.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

RUBRIC = """Score each candidate reply on five dimensions, 1 to 5.

GROUNDED (1-5)
  5 = every claim is consistent with how this brand demonstrably handles such cases;
      offers nothing it has no basis to offer
  3 = broadly plausible but includes at least one detail with no support
  1 = invents policy, entitlements, timeframes or facts about the customer's order

RELEVANT (1-5)
  5 = addresses the specific problem the customer actually described
  3 = addresses the general category but misses what makes this case particular
  1 = generic filler that could be pasted under any complaint

ACTIONABLE (1-5)
  5 = the customer knows exactly what happens next, or is asked precisely the one
      question needed to move forward
  3 = a next step exists but is vague or asks for something already provided
  1 = no next step, or sends the customer in a circle

TONE (1-5)
  5 = warm, human, proportionate to how upset this customer is; apologises once at
      most and only if warranted
  3 = serviceable but stiff, over-apologetic, or too cheerful for the situation
  1 = tone-deaf: chirpy at a furious customer, or cold at a distressed one

SAFE (1-5)
  5 = promises no outcome it cannot deliver, confirms nothing about account state,
      neither requests nor repeats personal data
  3 = borderline: hints at an outcome, or nudges toward sharing details
  1 = promises a refund/replacement/investigation, or solicits or echoes personal
      data in a public channel

Then:
SEND_AS_IS: yes or no -- would a support lead let this go out unedited?
BEST: the single letter of the reply you would actually send.
"""

JUDGE_SYSTEM = """You are evaluating candidate replies for a brand's public support \
account on Twitter. You are given the customer's original message and several candidate \
replies, labelled by letter.

The candidates come from different sources, which are not disclosed to you and which you \
should not try to guess. Some may be written by people, some by software. Judge only what \
is on the page.

{rubric}

Scoring discipline:
- Use the full range. If a reply is generic filler, RELEVANT is 1 or 2, not 3.
- A fluent, warm reply that answers the wrong problem scores high on TONE and low on
  RELEVANT. Do not let one dimension pull the others.
- A reply that correctly refuses to solve something in public and hands off cleanly is
  a GOOD reply, not an unhelpful one. Judge it on whether the hand-off is well made.
- Length is not quality. A short reply that asks the one right question beats a long
  one that asks three wrong ones.

Output strict JSON only, no prose, no code fences:
{{"scores": {{"A": {{"grounded": 0, "relevant": 0, "actionable": 0, "tone": 0, "safe": 0, "send_as_is": "no"}}, ...}}, "best": "A", "note": "<= 20 words on what separated them"}}"""


JUDGE_USER = """Customer message:
---
{message}
---

Candidate replies:
{candidates}

JSON:"""


@dataclass
class BlindedCase:
    golden_id: str
    message: str
    letters: dict[str, str]      # letter -> reply text
    mapping: dict[str, str]      # letter -> system name  (kept OUT of the prompt)
    order: list[str]             # letters in presentation order, for position-bias analysis


def blind_cases(
    cases: list[dict],
    replies_by_system: dict[str, dict[str, str]],
    seed: int = 20260910,
) -> list[BlindedCase]:
    """Anonymise and shuffle system replies per case.

    `replies_by_system[system][golden_id] -> reply`
    """
    rng = random.Random(seed)
    systems = sorted(replies_by_system)
    letters = "ABCDEFGH"
    out: list[BlindedCase] = []
    for c in cases:
        gid = c["golden_id"]
        present = [s for s in systems if replies_by_system[s].get(gid)]
        order = present[:]
        rng.shuffle(order)
        mapping = {letters[i]: s for i, s in enumerate(order)}
        letter_replies = {letters[i]: replies_by_system[s][gid] for i, s in enumerate(order)}
        out.append(BlindedCase(
            golden_id=gid, message=c["customer_message"],
            letters=letter_replies, mapping=mapping,
            order=[letters[i] for i in range(len(order))],
        ))
    return out


def judge_system() -> str:
    return JUDGE_SYSTEM.format(rubric=RUBRIC)


def judge_user(case: BlindedCase) -> str:
    cands = "\n".join(f"[{l}] {t}" for l, t in case.letters.items())
    return JUDGE_USER.format(message=case.message.strip(), candidates=cands)


DIMENSIONS = ("grounded", "relevant", "actionable", "tone", "safe")


def parse_scores(raw: str) -> dict:
    from src.llm import extract_json
    obj = extract_json(raw)
    scores = obj.get("scores", {})
    clean: dict[str, dict] = {}
    for letter, s in scores.items():
        row = {}
        for d in DIMENSIONS:
            try:
                v = int(round(float(s.get(d, 0))))
            except (TypeError, ValueError):
                v = 0
            row[d] = min(max(v, 1), 5) if v else 0
        sai = str(s.get("send_as_is", "no")).strip().lower()
        row["send_as_is"] = sai in ("yes", "true", "y")
        clean[str(letter).strip().upper()] = row
    return {"scores": clean, "best": str(obj.get("best", "")).strip().upper(),
            "note": str(obj.get("note", ""))[:200]}


def write_blinded(cases: list[BlindedCase], task_path: Path, key_path: Path) -> None:
    """Write the judging task and, separately, the de-anonymisation key.

    Two files on purpose. The judging step reads only the task file, so there
    is no path by which system identity can leak into a score.
    """
    task_path.parent.mkdir(parents=True, exist_ok=True)
    with task_path.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps({
                "golden_id": c.golden_id, "message": c.message, "candidates": c.letters,
            }, ensure_ascii=False) + "\n")
    with key_path.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps({
                "golden_id": c.golden_id, "mapping": c.mapping, "order": c.order,
            }, ensure_ascii=False) + "\n")
