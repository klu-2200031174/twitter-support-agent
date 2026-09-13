"""Turn 2.8M loose tweets into ordered conversations for one brand.

The raw file is a flat tweet table with two link columns: `in_response_to_tweet_id`
(parent) and `response_tweet_id` (comma-separated children). Neither is a
conversation id, and neither is fully consistent -- there are dangling parents,
self-loops, and children listed that do not exist in the file.

Rather than trust either column alone, we treat every observed link as an
undirected edge and take connected components as conversations. That is robust
to the inconsistencies: a thread survives even if one direction of a link is
missing, and a missing parent cannot silently split a conversation in two.
Within a component we order by timestamp, which is what a support agent
actually sees.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import pandas as pd

RAW_COLUMNS = [
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "response_tweet_id",
    "in_response_to_tweet_id",
]

# Handles in this dataset are either an anonymised numeric id (a customer) or a
# screen name (a brand). `inbound` tells us the same thing but is occasionally
# wrong; we cross-check with the id shape.
_NUMERIC = re.compile(r"^\d+$")


class DSU:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype={
            "tweet_id": "int64",
            "author_id": "string",
            "inbound": "boolean",
            "created_at": "string",
            "text": "string",
            "response_tweet_id": "string",
            "in_response_to_tweet_id": "string",
        },
        low_memory=False,
    )
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"raw file missing columns {missing}; got {list(df.columns)}")
    return df


def build_components(df: pd.DataFrame) -> pd.Series:
    """Assign every tweet a conversation id via union-find over reply links."""
    known = set(df["tweet_id"].tolist())
    dsu = DSU()
    for tid in known:
        dsu.find(tid)

    parents = df["in_response_to_tweet_id"]
    for tid, par in zip(df["tweet_id"], parents):
        if pd.isna(par):
            continue
        try:
            pid = int(float(par))
        except (TypeError, ValueError):
            continue
        if pid in known and pid != tid:
            dsu.union(tid, pid)

    children = df["response_tweet_id"]
    for tid, kids in zip(df["tweet_id"], children):
        if pd.isna(kids):
            continue
        for k in str(kids).split(","):
            k = k.strip()
            if not k:
                continue
            try:
                kid = int(float(k))
            except ValueError:
                continue
            if kid in known and kid != tid:
                dsu.union(tid, kid)

    return df["tweet_id"].map(dsu.find)


def brand_of(authors: list[str], inbounds: list[bool]) -> str | None:
    """The brand handle in a conversation, or None if there isn't exactly one."""
    brands = {
        a
        for a, inb in zip(authors, inbounds)
        if a is not None and not _NUMERIC.match(str(a)) and not bool(inb)
    }
    if len(brands) == 1:
        return brands.pop()
    return None


def iter_threads(df: pd.DataFrame) -> Iterator[dict]:
    """Yield one dict per conversation, turns ordered by time then tweet id."""
    df = df.copy()
    df["conversation_id"] = build_components(df)
    df["ts"] = pd.to_datetime(df["created_at"], format="%a %b %d %H:%M:%S %z %Y", errors="coerce")
    bad_ts = int(df["ts"].isna().sum())
    if bad_ts:
        # Fall back to a permissive parse only for the stragglers.
        fix = df["ts"].isna()
        df.loc[fix, "ts"] = pd.to_datetime(df.loc[fix, "created_at"], errors="coerce", utc=True)

    df = df.sort_values(["conversation_id", "ts", "tweet_id"], kind="stable")

    for conv_id, grp in df.groupby("conversation_id", sort=False):
        authors = grp["author_id"].tolist()
        # `inbound` is authoritative when present; when it is null we fall back
        # to the shape of the author id (customers are anonymised to digits).
        inbounds = [
            bool(flag) if pd.notna(flag) else bool(_NUMERIC.match(str(author)))
            for flag, author in zip(grp["inbound"].tolist(), authors)
        ]
        brand = brand_of(authors, inbounds)
        turns = []
        for tid, author, inb, ts, text in zip(
            grp["tweet_id"], authors, inbounds, grp["ts"], grp["text"]
        ):
            turns.append(
                {
                    "tweet_id": int(tid),
                    "author_id": str(author),
                    "role": "customer" if bool(inb) else "brand",
                    "created_at": None if pd.isna(ts) else ts.isoformat(),
                    "text": "" if pd.isna(text) else str(text),
                }
            )
        yield {
            "conversation_id": int(conv_id),
            "brand": brand,
            "n_turns": len(turns),
            "turns": turns,
        }


def write_threads(df: pd.DataFrame, out_path: Path, brand: str | None = None) -> dict:
    """Write threads to JSONL. If `brand` is given, keep only that brand's threads."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = defaultdict(int)
    with out_path.open("w", encoding="utf-8") as fh:
        for thread in iter_threads(df):
            stats["threads_total"] += 1
            if brand is not None and thread["brand"] != brand:
                continue
            if thread["brand"] is None:
                stats["threads_no_brand"] += 1
                if brand is not None:
                    continue
            stats["threads_written"] += 1
            stats["turns_written"] += thread["n_turns"]
            fh.write(json.dumps(thread, ensure_ascii=False) + "\n")
    return dict(stats)


def read_threads(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
