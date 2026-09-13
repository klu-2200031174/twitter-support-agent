"""The agent: triage -> retrieve -> draft.

Two model calls per case, deliberately not one.

A single call that emits intent, escalation and reply together is cheaper and
scores slightly better on reply quality, because the model writes the reply
first and back-fills a label that agrees with it. That coupling is exactly what
makes the system unevaluable: you can no longer tell whether a good reply came
from correct triage or in spite of incorrect triage, and the escalation
decision quietly becomes a post-hoc rationalisation of a reply already written.

Splitting them costs about 2x the tokens and buys an auditable decision: the
triage output is fixed before the drafter sees anything, retrieval is
conditioned on it, and a wrong route produces a visibly wrong draft instead of
a plausible one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.agent import prompts
from src.agent.retrieve import HistoryIndex, format_evidence
from src.llm import LLM, extract_json
from src.taxonomy import ESCALATION_RULE_IDS, INTENT_NAMES


@dataclass
class Prediction:
    case_id: str
    intent: str
    confidence: float
    escalate: bool
    rules: list[str]
    reason: str
    reply: str
    retrieved: list[dict] = field(default_factory=list)
    triage_raw: str = ""
    parse_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# When the model returns something unparseable we do NOT retry with a nudge and
# we do NOT silently pick a default. A malformed triage output is a real
# failure of the system, and the safe behaviour for a support agent is to route
# to a human. Hiding these behind a retry loop would make the reported
# escalation numbers better than the system deserves.
PARSE_FAILURE = {
    "intent": "other",
    "confidence": 0.0,
    "escalate": True,
    "rules": ["E8_unclassifiable"],
    "reason": "Triage output could not be parsed; routed to a human by default.",
}


class SupportAgent:
    def __init__(
        self,
        llm: LLM,
        index: HistoryIndex | None,
        k: int = 4,
        confidence_threshold: float = 0.55,
        use_retrieval: bool = True,
    ):
        self.llm = llm
        self.index = index
        self.k = k
        # Below this confidence, E8 fires regardless of what the model said.
        # The threshold is a policy dial, tuned on train-period cases only and
        # reported as a sweep rather than a single tuned number.
        self.confidence_threshold = confidence_threshold
        self.use_retrieval = use_retrieval

    # -- stage 1 ------------------------------------------------------------
    def triage(self, message: str) -> dict[str, Any]:
        raw = self.llm.complete(
            prompt=prompts.triage_user(message),
            system=prompts.triage_system(),
            max_tokens=300,
            temperature=0.0,
        )
        if not raw:
            return {**PARSE_FAILURE, "_raw": "", "_error": "empty (recording pass)"}
        try:
            obj = extract_json(raw)
        except ValueError as exc:
            return {**PARSE_FAILURE, "_raw": raw, "_error": str(exc)[:200]}

        intent = obj.get("intent")
        if intent not in INTENT_NAMES:
            return {**PARSE_FAILURE, "_raw": raw,
                    "_error": f"intent {intent!r} not in taxonomy"}

        try:
            conf = float(obj.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = min(max(conf, 0.0), 1.0)

        rules = [r for r in (obj.get("rules") or []) if r in ESCALATION_RULE_IDS]
        escalate = bool(obj.get("escalate", False))

        # Policy override, applied after the model, not inside it: a model that
        # is unsure is escalated whatever it claimed. Keeping this in code
        # rather than in the prompt makes the threshold auditable and sweepable.
        if conf < self.confidence_threshold:
            escalate = True
            if "E8_unclassifiable" not in rules:
                rules.append("E8_unclassifiable")

        reason = str(obj.get("reason", ""))[:300]
        if escalate and not rules:
            rules = ["E8_unclassifiable"]
        if not escalate:
            rules = []

        return {"intent": intent, "confidence": conf, "escalate": escalate,
                "rules": rules, "reason": reason, "_raw": raw, "_error": None}

    # -- stage 2 ------------------------------------------------------------
    def draft(self, message: str, triage: dict[str, Any]) -> tuple[str, list[dict]]:
        neighbours = []
        if self.use_retrieval and self.index is not None:
            neighbours = self.index.search(message, k=self.k)
        evidence = format_evidence(neighbours) if self.use_retrieval else (
            "(retrieval disabled for this run -- rely on general knowledge of the brand)"
        )
        reply = self.llm.complete(
            prompt=prompts.draft_user(
                message=message, intent=triage["intent"], escalate=triage["escalate"],
                reason=triage["reason"], evidence=evidence,
            ),
            system=prompts.draft_system(),
            max_tokens=220,
            temperature=0.0,
        )
        return reply.strip(), [
            {"case_id": n.case_id, "score": round(n.score, 4),
             "customer_message": n.customer_message, "brand_reply": n.brand_reply}
            for n in neighbours
        ]

    # -- both ---------------------------------------------------------------
    def run(self, case: dict) -> Prediction:
        msg = case["customer_message"]
        t = self.triage(msg)
        reply, retrieved = self.draft(msg, t)
        return Prediction(
            case_id=case.get("case_id", case.get("golden_id", "?")),
            intent=t["intent"], confidence=t["confidence"], escalate=t["escalate"],
            rules=t["rules"], reason=t["reason"], reply=reply, retrieved=retrieved,
            triage_raw=t.get("_raw", ""), parse_error=t.get("_error"),
        )

    def run_all(self, cases: list[dict], workers: int = 6, desc: str = "agent") -> list[Prediction]:
        return self.llm.map(self.run, cases, workers=workers, desc=desc)


def load_index(path: Path | str) -> HistoryIndex:
    return HistoryIndex.from_jsonl(path)


def write_predictions(preds: list[Prediction], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for p in preds:
            fh.write(json.dumps(p.to_json(), ensure_ascii=False) + "\n")
