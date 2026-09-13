"""Retrieve how AmazonHelp historically handled similar cases.

This is the "grounded" half of the brief. The drafter is never asked to invent
Amazon's policy; it is shown real (customer message -> brand reply) pairs from
before the eval cut date and told to imitate the pattern.

WHY TF-IDF AND NOT EMBEDDINGS
    Not a claim that lexical beats dense retrieval. The sandbox has no route to
    a model hub, so no sentence-transformer weights, and the only reachable LLM
    endpoint has no embeddings budget in this build. The honest framing is: this
    is the retrieval that was available, its quality is measured
    (results/retrieval_eval.json), and swapping in dense retrieval is the first
    item on the next-week list.

    Word n-grams alone do badly on this corpus -- customers write "recieved",
    "delivrd", "amzn", "pkg". Character n-grams recover most of that, so the
    index is a union of both, which measurably beats either alone on the
    retrieval probe.

WHAT IS DELIBERATELY NOT DONE
    No re-ranking, no query expansion, no intent-conditioned index. Each was
    considered and left out; see reports/DECISIONS.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Neighbour:
    case_id: str
    score: float
    customer_message: str
    brand_reply: str
    n_turns: int


class HistoryIndex:
    """Lexical index over historical (ask, reply) pairs."""

    def __init__(self, cases: list[dict]):
        self.cases = cases
        texts = [c["customer_message"] for c in cases]
        self.word_vec = TfidfVectorizer(
            ngram_range=(1, 2), min_df=3, max_df=0.5, sublinear_tf=True,
            strip_accents="unicode", lowercase=True,
        )
        self.char_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=5, max_df=0.5,
            sublinear_tf=True, lowercase=True,
        )
        Xw = self.word_vec.fit_transform(texts)
        Xc = self.char_vec.fit_transform(texts)
        # Down-weight the character block so a shared prefix like "@AmazonHelp
        # I ordered" cannot dominate the topical signal.
        self.X = normalize(hstack([Xw, 0.5 * Xc]).tocsr())

    def _embed(self, query: str):
        qw = self.word_vec.transform([query])
        qc = self.char_vec.transform([query])
        return normalize(hstack([qw, 0.5 * qc]).tocsr())

    def search(self, query: str, k: int = 5, min_score: float = 0.08) -> list[Neighbour]:
        q = self._embed(query)
        sims = (self.X @ q.T).toarray().ravel()
        if k >= len(sims):
            idx = np.argsort(-sims)
        else:
            idx = np.argpartition(-sims, k)[:k]
            idx = idx[np.argsort(-sims[idx])]
        out = []
        for i in idx:
            if sims[i] < min_score:
                continue
            c = self.cases[int(i)]
            out.append(Neighbour(
                case_id=c["case_id"], score=float(sims[i]),
                customer_message=c["customer_message"],
                brand_reply=c["brand_reply"], n_turns=c["n_turns"],
            ))
        return out

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "HistoryIndex":
        """Load the retrieval corpus, transparently handling gzip.

        The corpus is committed gzipped so a clean checkout can reproduce every
        number without first rebuilding 500MB of intermediates from the Kaggle
        file. If the uncompressed file is present it wins, so a fresh `make
        data` run is picked up without touching this code.
        """
        path = Path(path)
        candidates = [path, path.with_suffix(path.suffix + ".gz")]
        if path.suffix == ".gz":
            candidates = [path.with_suffix(""), path]
        for cand in candidates:
            if cand.exists():
                if cand.suffix == ".gz":
                    import gzip
                    with gzip.open(cand, "rt", encoding="utf-8") as fh:
                        return cls([json.loads(l) for l in fh])
                return cls([json.loads(l) for l in cand.open(encoding="utf-8")])
        raise FileNotFoundError(f"no retrieval corpus at {path} (or .gz)")


def format_evidence(neighbours: list[Neighbour], max_chars: int = 260) -> str:
    """Render neighbours for a prompt.

    Similarity scores are shown to the model on purpose. A weak best-match is
    a signal that this case is unlike anything in history, and the drafter is
    instructed to hedge rather than confabulate when that happens.
    """
    if not neighbours:
        return "(no similar past cases found -- do not invent a precedent)"
    lines = []
    for i, n in enumerate(neighbours, 1):
        lines.append(
            f"[{i}] similarity={n.score:.2f}\n"
            f"    customer: {n.customer_message[:max_chars]}\n"
            f"    AmazonHelp replied: {n.brand_reply[:max_chars]}"
        )
    return "\n".join(lines)
