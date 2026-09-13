"""Baselines the agent has to beat to justify its cost.

TRIVIAL
    Always predict the most frequent intent. Never escalate. Send one canned
    reply to everybody. This exists to expose the majority-class illusion: on a
    skewed problem it can post a respectable accuracy while being worthless,
    and any headline accuracy that does not clear it by a wide margin is noise.

SIMPLE
    TF-IDF -> logistic regression for intent, keyword rules for escalation,
    nearest-neighbour copy for the reply. No LLM anywhere.

    The simple baseline is handed an advantage the agent never gets: it is
    fitted on the golden labels themselves, out-of-fold. It therefore learns
    this annotator's idiosyncratic boundaries -- exactly the thing the agent has
    to infer from a written taxonomy. Any margin the agent wins under that
    handicap is a conservative estimate of the real margin.

    Reported metrics for this baseline are out-of-fold (5-fold stratified), so
    it is never scored on a case it was fitted on.

NEAREST-NEIGHBOUR REPLY
    The reply baseline copies, verbatim, the historical AmazonHelp reply from
    the most similar past case. This is the strongest cheap answer to "why not
    just retrieve?" and it is a genuinely hard baseline to beat on tone,
    because it IS the brand's voice. Where it fails is specificity: it answers
    the case it was written for, not this one.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import normalize

from src.agent.retrieve import HistoryIndex

# The single most common shape of AmazonHelp reply in the training period:
# apologise, ask for detail, warn off posting personal information.
CANNED_REPLY = (
    "I'm sorry for the trouble! Without sharing any personal or account "
    "information, could you tell us a little more about what's happened?"
)

# Keyword escalation rules. Written by reading the training period only, and
# deliberately kept crude -- this is the "what a sensible engineer does in an
# afternoon" bar that the LLM policy has to clear.
ESCALATION_KEYWORDS = {
    "E1_account_security": r"hack|unauthori[sz]ed|fraud|phish|scam|locked out|can'?t log ?in|"
                           r"password|compromis|someone (else )?(used|accessed)",
    "E2_account_action": r"refund|money back|reimburse|compensat|credit|charge[ds]?|billed|"
                         r"cancel (my|the) order|replacement|missing|never (arrived|received)|"
                         r"not received|marked as delivered|says delivered",
    "E3_legal_regulatory_media": r"lawyer|solicitor|legal|small claims|ombudsman|trading standards|"
                                 r"watchdog|consumer rights|sue |press|journalist",
    "E4_safety_harm": r"injur|burn|fire|hazard|dangerous|unsafe|recall|electrocut|hurt",
    "E5_repeat_failure": r"\b(again|third|3rd|fourth|4th|fifth|5th|second time|twice|"
                         r"multiple times|every time|each time)\b|already (called|contacted|"
                         r"reported|spoke)|no (one|body) (has )?(replied|responded|helped)|"
                         r"still (no|waiting)|keep (being|getting)",
    "E6_vulnerability_distress": r"my (son|daughter|child|kid|mum|mother|dad|father)|"
                                 r"hospital|medical|disab|funeral|died|passed away|carer",
    "E7_high_value_or_bulk": r"seller ?central|business account|bulk|wholesale|"
                             r"[£$₹]\s?\d{3,}|\d{4,}\s?(inr|rupees|rs)",
    "E9_relationship_risk": r"cancel(ling|ing)? my prime|never (shop|order|use|buying)|"
                            r"worst|useless|disgrace|pathetic|shame|joke|lie[sd]?|lying|"
                            r"switching to|taking my business",
}


@dataclass
class BaselinePrediction:
    case_id: str
    intent: str
    escalate: bool
    rules: list[str]
    reply: str
    confidence: float = 0.0


class TrivialBaseline:
    """Majority intent, never escalate, one canned reply."""

    def __init__(self, majority_intent: str, always_escalate: bool = False):
        self.majority_intent = majority_intent
        self.always_escalate = always_escalate

    @classmethod
    def fit(cls, intents: list[str]) -> "TrivialBaseline":
        return cls(Counter(intents).most_common(1)[0][0])

    def predict(self, cases: list[dict]) -> list[BaselinePrediction]:
        return [
            BaselinePrediction(
                case_id=c.get("golden_id", c.get("case_id", "?")),
                intent=self.majority_intent,
                escalate=self.always_escalate,
                rules=[],
                reply=CANNED_REPLY,
                confidence=1.0,
            )
            for c in cases
        ]


class SimpleBaseline:
    """TF-IDF + logistic regression, keyword escalation, nearest-neighbour reply."""

    def __init__(self, index: HistoryIndex | None = None, seed: int = 20260910):
        self.index = index
        self.seed = seed
        self.clf = None

    @staticmethod
    def _make_clf():
        return make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                            strip_accents="unicode", lowercase=True),
            LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0),
        )

    def fit(self, texts: list[str], intents: list[str]) -> "SimpleBaseline":
        self.clf = self._make_clf()
        self.clf.fit(texts, intents)
        return self

    def predict_intents_oof(self, texts: list[str], intents: list[str],
                            n_splits: int = 5) -> tuple[list[str], list[float]]:
        """Out-of-fold intent predictions, so the baseline is never scored on a
        case it was fitted on."""
        y = np.array(intents)
        X = np.array(texts, dtype=object)
        preds = np.empty(len(y), dtype=object)
        confs = np.zeros(len(y))
        # Classes with fewer members than n_splits cannot be stratified; fold
        # them into the split by their own count.
        counts = Counter(intents)
        min_count = min(counts.values())
        splits = max(2, min(n_splits, min_count))
        skf = StratifiedKFold(n_splits=splits, shuffle=True, random_state=self.seed)
        for tr, te in skf.split(X, y):
            clf = self._make_clf()
            clf.fit(list(X[tr]), list(y[tr]))
            p = clf.predict(list(X[te]))
            proba = clf.predict_proba(list(X[te])).max(axis=1)
            preds[te] = p
            confs[te] = proba
        return list(preds), list(confs)

    @staticmethod
    def escalation_rules(text: str) -> list[str]:
        import re
        hits = []
        for rule, pattern in ESCALATION_KEYWORDS.items():
            if re.search(pattern, text, re.I):
                hits.append(rule)
        return hits

    def nn_reply(self, text: str) -> str:
        if self.index is None:
            return CANNED_REPLY
        hits = self.index.search(text, k=1)
        return hits[0].brand_reply if hits else CANNED_REPLY

    def predict(self, cases: list[dict], intents: list[str] | None = None,
                confs: list[float] | None = None) -> list[BaselinePrediction]:
        out = []
        for i, c in enumerate(cases):
            text = c["customer_message"]
            rules = self.escalation_rules(text)
            out.append(BaselinePrediction(
                case_id=c.get("golden_id", c.get("case_id", "?")),
                intent=intents[i] if intents else (self.clf.predict([text])[0] if self.clf else "other"),
                escalate=bool(rules),
                rules=rules,
                reply=self.nn_reply(text),
                confidence=confs[i] if confs else 0.0,
            ))
        return out
