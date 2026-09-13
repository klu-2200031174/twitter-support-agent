"""Reconstruct conversations, keep the chosen brand's, and define the task unit.

Two things happen here that matter for everything downstream.

1. Conversations. The raw file has no conversation id. We recover one by
   union-find over reply links (see src/data/threads.py for why undirected).

2. The unit of prediction. A "case" is the moment a customer opens a new
   support contact: the first customer turn of a thread that the brand went on
   to answer. That is the point where a real triage system has to act, and it
   is the only point where we can compare the agent's draft against a
   like-for-like human reply (the brand's first response).

   Choosing this unit excludes mid-conversation turns, where the right reply
   depends on state the agent has not been given. That is a scope decision, not
   an oversight -- it is recorded in the decision log and the report says what
   it costs.

Outputs
    data/processed/threads.jsonl   all AmazonHelp threads, ordered turns
    data/processed/cases.jsonl     one row per case (first ask + brand's reply)
    results/thread_stats.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data.threads import build_components, load_raw

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "twcs.csv"
PROC = REPO / "data" / "processed"
RESULTS = REPO / "results"

BRAND = "AmazonHelp"
HANDLE = re.compile(r"@\w+")
URL = re.compile(r"https?://\S+")
SIGNOFF = re.compile(r"[\^\*~]\s?[A-Za-z]{1,3}\s*$")


def is_english(text: str, threshold: float = 0.9) -> bool:
    """ASCII-ratio proxy. AmazonHelp answers Japanese customers on the same
    handle; we cannot hand-label what we cannot read, so those threads are
    excluded and counted."""
    if not text:
        return True
    return sum(ord(c) < 128 for c in text) / len(text) >= threshold


def clean(text: str) -> str:
    t = URL.sub(" <link> ", text or "")
    t = HANDLE.sub(" ", t)
    t = SIGNOFF.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    print("loading raw ...", flush=True)
    df = load_raw(RAW)
    print(f"  {len(df):,} tweets", flush=True)

    print("union-find over reply links ...", flush=True)
    df["conversation_id"] = build_components(df)
    n_conv = df["conversation_id"].nunique()
    print(f"  {n_conv:,} conversations", flush=True)

    # Keep only conversations AmazonHelp participates in.
    brand_convs = set(df.loc[df["author_id"] == BRAND, "conversation_id"].unique())
    sub = df[df["conversation_id"].isin(brand_convs)].copy()
    print(f"  {len(brand_convs):,} involve {BRAND} ({len(sub):,} tweets)", flush=True)

    sub["ts"] = pd.to_datetime(
        sub["created_at"], format="%a %b %d %H:%M:%S %z %Y", errors="coerce", utc=True
    )
    sub = sub.sort_values(["conversation_id", "ts", "tweet_id"], kind="stable")

    stats = {
        "raw_tweets": int(len(df)),
        "conversations_total": int(n_conv),
        "conversations_with_brand": int(len(brand_convs)),
        "brand": BRAND,
    }

    threads_path = PROC / "threads.jsonl"
    cases_path = PROC / "cases.jsonl"
    n_threads = n_cases = 0
    dropped = {"non_english": 0, "no_customer_open": 0, "no_brand_reply": 0,
               "multi_brand": 0, "empty_text": 0}
    turn_counts: list[int] = []

    with threads_path.open("w", encoding="utf-8") as ft, cases_path.open("w", encoding="utf-8") as fc:
        for conv_id, grp in sub.groupby("conversation_id", sort=False):
            authors = grp["author_id"].astype(str).tolist()
            texts = ["" if pd.isna(t) else str(t) for t in grp["text"].tolist()]
            flags = grp["inbound"].tolist()
            roles = [
                "customer" if (bool(f) if pd.notna(f) else a.isdigit()) else "brand"
                for f, a in zip(flags, authors)
            ]
            # Threads where another brand also participates are ambiguous about
            # who owns the case; drop them.
            other_brands = {
                a for a, r in zip(authors, roles) if r == "brand" and a != BRAND
            }
            if other_brands:
                dropped["multi_brand"] += 1
                continue

            turns = [
                {
                    "tweet_id": int(tid),
                    "role": role,
                    "created_at": None if pd.isna(ts) else ts.isoformat(),
                    "text": text,
                    "clean": clean(text),
                }
                for tid, role, ts, text in zip(grp["tweet_id"], roles, grp["ts"], texts)
            ]

            joined = " ".join(t["text"] for t in turns)
            if not is_english(joined):
                dropped["non_english"] += 1
                continue

            ft.write(json.dumps({"conversation_id": int(conv_id), "brand": BRAND,
                                 "n_turns": len(turns), "turns": turns},
                                ensure_ascii=False) + "\n")
            n_threads += 1
            turn_counts.append(len(turns))

            # --- carve the case out of the thread ---------------------------
            if turns[0]["role"] != "customer":
                dropped["no_customer_open"] += 1
                continue
            first_brand = next((i for i, t in enumerate(turns) if t["role"] == "brand"), None)
            if first_brand is None:
                dropped["no_brand_reply"] += 1
                continue
            # Everything the customer said before the brand first spoke is the
            # opening ask -- people often tweet twice before anyone answers.
            opening = [t for t in turns[:first_brand] if t["role"] == "customer"]
            ask = " ".join(t["clean"] for t in opening).strip()
            reply = turns[first_brand]["clean"]
            if not ask or not reply:
                dropped["empty_text"] += 1
                continue

            fc.write(json.dumps({
                "case_id": f"{BRAND}-{conv_id}",
                "conversation_id": int(conv_id),
                "created_at": turns[0]["created_at"],
                "customer_message": ask,
                "customer_message_raw": " ".join(t["text"] for t in opening).strip(),
                "brand_reply": reply,
                "brand_reply_raw": turns[first_brand]["text"],
                "n_turns": len(turns),
                "n_brand_turns": sum(1 for t in turns if t["role"] == "brand"),
                "n_customer_turns": sum(1 for t in turns if t["role"] == "customer"),
                "full_thread": [
                    {"role": t["role"], "text": t["clean"]} for t in turns
                ],
            }, ensure_ascii=False) + "\n")
            n_cases += 1

    import numpy as np

    stats.update({
        "threads_kept": n_threads,
        "cases": n_cases,
        "dropped": dropped,
        "turns_p50": float(np.median(turn_counts)) if turn_counts else 0,
        "turns_p90": float(np.percentile(turn_counts, 90)) if turn_counts else 0,
        "turns_max": int(max(turn_counts)) if turn_counts else 0,
    })
    (RESULTS / "thread_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(f"\nwrote {threads_path} and {cases_path}")


if __name__ == "__main__":
    main()
