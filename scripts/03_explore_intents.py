"""Discover candidate intents from the data instead of inventing them.

Method: TF-IDF over customer opening messages -> KMeans -> read the clusters.
Clustering is used as a *reading aid*, not as the taxonomy. k=24 is deliberately
larger than the taxonomy we expect to end up with, because over-clustering and
merging by hand is safer than under-clustering and never seeing a rare-but-
distinct intent (e.g. account-security cases, which are ~1% of volume but are
exactly the ones that must never be auto-answered).

Prints per cluster: size, distinctive terms, and sampled real messages, plus
what the brand actually replied -- because how the brand responds is often what
separates two intents that look similar in the customer's words.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "data" / "processed" / "cases.jsonl"
RESULTS = REPO / "results"

SEED = 20260910


def load_cases() -> pd.DataFrame:
    rows = [json.loads(l) for l in CASES.open(encoding="utf-8")]
    return pd.DataFrame(rows)


def main(k: int = 24, sample: int = 30000, per_cluster: int = 6) -> None:
    RESULTS.mkdir(exist_ok=True)
    df = load_cases()
    print(f"{len(df):,} cases")

    df["ts"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    print("date range:", df["ts"].min(), "->", df["ts"].max())
    print("\nmonthly volume:")
    print(df["ts"].dt.to_period("M").value_counts().sort_index().to_string())

    print("\nmessage length (chars):",
          df["customer_message"].str.len().describe(percentiles=[.1, .5, .9]).round(1).to_dict())
    print("thread turns:", df["n_turns"].describe(percentiles=[.5, .9]).round(1).to_dict())

    work = df.sample(min(sample, len(df)), random_state=SEED)
    vec = TfidfVectorizer(
        max_features=30000, ngram_range=(1, 2), min_df=5, max_df=0.4,
        stop_words="english", sublinear_tf=True,
    )
    X = vec.fit_transform(work["customer_message"])
    km = MiniBatchKMeans(n_clusters=k, random_state=SEED, n_init=10, batch_size=2048)
    labels = km.fit_predict(X)
    work = work.assign(cluster=labels)

    terms = np.array(vec.get_feature_names_out())
    centroids = km.cluster_centers_
    out_lines: list[str] = []

    order = pd.Series(labels).value_counts().index
    for c in order:
        grp = work[work.cluster == c]
        top = terms[np.argsort(centroids[c])[::-1][:12]]
        head = f"\n{'='*100}\nCLUSTER {c}  n={len(grp)} ({len(grp)/len(work):.1%})\n  terms: {', '.join(top)}"
        print(head)
        out_lines.append(head)
        for _, r in grp.sample(min(per_cluster, len(grp)), random_state=SEED).iterrows():
            block = (f"  C: {r.customer_message[:230]}\n"
                     f"  A: {r.brand_reply[:200]}\n"
                     f"     [turns={r.n_turns} brand_turns={r.n_brand_turns}]")
            print(block)
            out_lines.append(block)

    (RESULTS / "cluster_exploration.txt").write_text("\n".join(out_lines), encoding="utf-8")
    work[["case_id", "cluster", "customer_message", "brand_reply"]].to_csv(
        RESULTS / "clustered_sample.csv", index=False)
    print(f"\nwrote {RESULTS/'cluster_exploration.txt'}")


if __name__ == "__main__":
    main()
