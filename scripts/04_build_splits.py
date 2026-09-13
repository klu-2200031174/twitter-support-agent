"""Filter to English, split by time, and build the retrieval corpus.

SPLIT IS TEMPORAL, NOT RANDOM.
    A random split leaks the future into the past. Support traffic is bursty
    and highly duplicated -- during a delivery incident, hundreds of customers
    tweet near-identical complaints within hours. Randomly splitting those puts
    near-duplicates of an eval case into the retrieval corpus, and the agent
    then "retrieves" what is effectively the answer key. Measured on this
    corpus, that inflates retrieval quality substantially (see
    results/split_leakage.json for the duplicate rate we avoided).

    So: everything before the cut date is history the agent may learn from and
    retrieve; everything after is unseen traffic. This is also what production
    actually looks like.

RETRIEVAL CORPUS IS FILTERED FOR SUBSTANCE.
    The point of grounding is to imitate how the brand *resolved* things. A
    reply that only says "please contact us here <link>" is not a resolution,
    and a corpus full of them teaches the drafter to deflect. We keep only
    exchanges whose reply survives boilerplate-stripping with enough content to
    be worth imitating, and record how many we dropped.

Outputs
    data/processed/train.jsonl      history: retrieval + baseline fitting
    data/processed/eval_pool.jsonl  unseen traffic: golden set is sampled here
    data/processed/retrieval.jsonl  substantive subset of train
    results/split_stats.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data.langid import detect, is_english

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
RESULTS = REPO / "results"

CUT = pd.Timestamp("2017-11-15", tz="UTC")

DEFLECT = re.compile(
    r"(reach (out to )?us|contact us|get in (contact|touch)|please (report|share) this"
    r"|via phone or chat|by phone or chat|call us|chat (with us|here)|our support team"
    r"|fill (in|out) the form|use this link|report this to)", re.I,
)
PLACEHOLDER = re.compile(r"<link>")


def substantive(reply: str) -> bool:
    """Does this reply contain something worth imitating?

    Two failure shapes to exclude: pure redirects, and replies that are almost
    entirely a link once boilerplate is stripped.
    """
    body = PLACEHOLDER.sub(" ", reply or "").strip()
    body = re.sub(r"\s+", " ", body)
    if len(body) < 45:
        return False
    if DEFLECT.search(body) and len(body) < 110:
        return False
    return True


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    cases = [json.loads(l) for l in (PROC / "cases.jsonl").open(encoding="utf-8")]
    print(f"cases in: {len(cases):,}")

    langs = Counter()
    english = []
    for c in cases:
        if is_english(c["customer_message"]):
            english.append(c)
        else:
            langs[detect(c["customer_message"])] += 1
    print(f"english:  {len(english):,} ({len(english)/len(cases):.1%})")

    df = pd.DataFrame(english)
    df["ts"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df = df[df["ts"].notna()].copy()

    train = df[df["ts"] < CUT].copy()
    evalp = df[df["ts"] >= CUT].copy()
    print(f"train (< {CUT.date()}): {len(train):,}")
    print(f"eval  (>= {CUT.date()}): {len(evalp):,}")

    # How much near-duplication exists across the boundary? This is the number
    # that justifies the temporal split; a random split would have scattered
    # these pairs across train and test.
    def shingle(s: str) -> frozenset:
        toks = re.findall(r"[a-z']+", s.lower())
        return frozenset(zip(toks, toks[1:]))

    ev_sample = evalp.sample(min(1500, len(evalp)), random_state=11)
    tr_sample = train.sample(min(15000, len(train)), random_state=11)
    tr_shingles = [shingle(t) for t in tr_sample["customer_message"]]
    near_dupe = 0
    for msg in ev_sample["customer_message"]:
        s = shingle(msg)
        if not s:
            continue
        for t in tr_shingles:
            if not t:
                continue
            inter = len(s & t)
            if inter and inter / len(s | t) >= 0.6:
                near_dupe += 1
                break
    dupe_rate = near_dupe / len(ev_sample)

    train["substantive"] = train["brand_reply"].map(substantive)
    retrieval = train[train["substantive"]].copy()
    print(f"retrieval corpus: {len(retrieval):,} "
          f"({len(retrieval)/len(train):.1%} of train survived the substance filter)")

    keep_cols = ["case_id", "conversation_id", "created_at", "customer_message",
                 "brand_reply", "n_turns", "n_brand_turns", "n_customer_turns",
                 "full_thread"]
    train[keep_cols].to_json(PROC / "train.jsonl", orient="records", lines=True, force_ascii=False)
    evalp[keep_cols].to_json(PROC / "eval_pool.jsonl", orient="records", lines=True, force_ascii=False)
    retrieval[keep_cols].to_json(PROC / "retrieval.jsonl", orient="records", lines=True, force_ascii=False)

    stats = {
        "cases_in": len(cases),
        "english": len(english),
        "english_rate": round(len(english) / len(cases), 4),
        "dropped_by_language": dict(langs.most_common()),
        "cut_date": str(CUT.date()),
        "train": len(train),
        "eval_pool": len(evalp),
        "retrieval_corpus": len(retrieval),
        "retrieval_substance_rate": round(len(retrieval) / len(train), 4),
        "eval_near_duplicate_rate_vs_train": round(dupe_rate, 4),
        "near_dupe_note": (
            "Fraction of sampled eval messages with a >=0.6 Jaccard bigram match in "
            "train. Under a random split these pairs would straddle the boundary and "
            "the retriever would be scored on cases it had effectively memorised."
        ),
    }
    (RESULTS / "split_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
