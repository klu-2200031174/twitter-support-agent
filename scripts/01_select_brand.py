"""Choose the brand to build for, from evidence rather than name recognition.

The intuitive choice is the highest-volume brand. That is a trap. A support
agent that drafts replies "grounded in how the brand historically resolved
similar issues" needs a history that contains resolutions. Several of the
largest accounts in this dataset almost never resolve anything in-channel --
they redirect to DM, phone or a help page. Grounding a drafter in that history
teaches it to write "please DM us" with high fidelity, which is a working
system that is worth nothing.

So we score candidate brands on four things:

  volume        enough threads to retrieve from and to sample an eval set out of
  deflection    fraction of replies that redirect instead of helping (lower better)
  substance     replies that survive stripping handles/URLs/sign-offs (higher better)
  english       we have to hand-label this; we can only label what we can read

Deflection is measured in three separate forms, because brands differ in how
they punt: Apple says "DM us", Amazon posts a phone/chat link, UPS posts a
tracking-page link. Counting only the first form -- which is the obvious regex
to write -- makes Amazon look 50x cleaner than Apple when it is not.

Output: results/brand_selection.csv + a short justification printed to stdout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "twcs.csv"
OUT = REPO / "results"

# --- deflection, in its three observed forms -------------------------------
DM_PUNT = re.compile(
    r"\b(dm\b|dms\b|direct message|private message|pm us|inbox us|"
    r"send us a (dm|private|message)|via dm|shoot us a dm|slide into)", re.I
)
CHANNEL_PUNT = re.compile(
    r"\b(call us|give us a call|phone (us|our)|reach (us|out to us) by phone|"
    r"contact (us )?(via|by|through) (phone|chat)|live chat|chat with us|"
    r"chat here|by phone or chat|customer (service|care) (team )?(on|at)\s*[\d+]|"
    r"our (support|help|contact) (page|centre|center|team) (here|at|via))", re.I
)
LINK_ONLY = re.compile(r"https?://\S+")
HANDLE = re.compile(r"@\w+")
# Agent sign-offs: "^AG", "^TN", "*JD", "- Miriam ^MM"
SIGNOFF = re.compile(r"[\^\*~]\s?[A-Z]{2,3}\b|\B[\^\*]\w{1,3}\s*$")


def substantive_text(s: pd.Series) -> pd.Series:
    """What is left of a reply once boilerplate is removed."""
    t = s.fillna("")
    t = t.str.replace(HANDLE, " ", regex=True)
    t = t.str.replace(LINK_ONLY, " ", regex=True)
    t = t.str.replace(SIGNOFF, " ", regex=True)
    return t.str.replace(r"\s+", " ", regex=True).str.strip()


def ascii_ratio(s: pd.Series) -> pd.Series:
    """Crude language proxy: fraction of characters in the ASCII range.

    Good enough to separate an English-language support account from one that
    handles a lot of Japanese or Arabic. Not a language detector, and not
    claimed to be one.
    """
    return s.fillna("").map(
        lambda x: (sum(ord(c) < 128 for c in x) / len(x)) if x else 1.0
    )


def main(min_replies: int = 8000) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"reading {RAW} ...", flush=True)
    df = pd.read_csv(
        RAW,
        usecols=["tweet_id", "author_id", "inbound", "text", "in_response_to_tweet_id"],
        dtype={"author_id": "string", "text": "string"},
        low_memory=False,
    )
    brand = df[df["inbound"] == False].copy()  # noqa: E712
    print(f"  {len(df):,} tweets, {len(brand):,} from brands", flush=True)

    brand["sub"] = substantive_text(brand["text"])
    brand["is_dm_punt"] = brand["text"].str.contains(DM_PUNT, na=False)
    brand["is_channel_punt"] = brand["text"].str.contains(CHANNEL_PUNT, na=False)
    brand["has_link"] = brand["text"].str.contains(LINK_ONLY, na=False)
    brand["sub_len"] = brand["sub"].str.len()
    # A reply is "thin" if, after stripping boilerplate, there is barely a
    # sentence left -- e.g. "Sorry about that!" plus a link.
    brand["is_thin"] = brand["sub_len"] < 40
    brand["ascii"] = ascii_ratio(brand["text"])

    g = brand.groupby("author_id", observed=True)
    stats = pd.DataFrame(
        {
            "replies": g.size(),
            "customers": g["in_response_to_tweet_id"].nunique(),
            "dm_punt": g["is_dm_punt"].mean(),
            "channel_punt": g["is_channel_punt"].mean(),
            "link_rate": g["has_link"].mean(),
            "thin_rate": g["is_thin"].mean(),
            "median_sub_len": g["sub_len"].median(),
            "english": g["ascii"].mean(),
        }
    )
    stats["any_punt"] = (
        brand.assign(p=brand["is_dm_punt"] | brand["is_channel_punt"])
        .groupby("author_id", observed=True)["p"]
        .mean()
    )
    stats = stats[stats["replies"] >= min_replies].copy()

    # Substance = replies that are neither a redirect nor near-empty.
    stats["substantive"] = 1 - (
        brand.assign(bad=lambda d: d["is_dm_punt"] | d["is_channel_punt"] | d["is_thin"])
        .groupby("author_id", observed=True)["bad"]
        .mean()
    )

    # Composite score. Volume enters as a log so that a 4x volume advantage
    # cannot buy a brand out of a bad substance rate; substance is what the
    # drafter actually learns from, so it carries the most weight.
    import numpy as np

    v = np.log10(stats["replies"]) / np.log10(stats["replies"].max())
    stats["score"] = (
        0.30 * v
        + 0.50 * stats["substantive"]
        + 0.20 * (stats["english"] > 0.95).astype(float)
    )

    stats = stats.sort_values("score", ascending=False)
    stats.round(4).to_csv(OUT / "brand_selection.csv")

    pd.set_option("display.width", 220)
    cols = ["replies", "dm_punt", "channel_punt", "thin_rate", "substantive",
            "english", "median_sub_len", "score"]
    print("\n=== brand selection (top 20 by score) ===")
    print(stats[cols].head(20).round(3).to_string())
    print("\n=== the high-volume names, for contrast ===")
    big = stats.sort_values("replies", ascending=False).head(10)
    print(big[cols].round(3).to_string())
    print(f"\nwrote {OUT/'brand_selection.csv'}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
