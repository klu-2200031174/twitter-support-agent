"""Render a batch of golden cases for annotation.

The annotator sees the WHOLE resolved thread: the opening ask, what AmazonHelp
actually replied, how many turns it took, and how it ended. The agent under
evaluation sees only the opening customer message.

That asymmetry is intentional and is the main defence against the golden set
being a mirror of the system. Labels made with hindsight -- knowing that a
case ran 26 turns and ended in a refund -- encode information the agent cannot
copy from its own reasoning. It is closer to how a QA lead labels resolved
tickets than to how a triage bot guesses.

Usage: python scripts/labeling_view.py <start> <count>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "data" / "golden" / "golden_sample.jsonl"


def main(start: int = 0, count: int = 40, max_turns: int = 7) -> None:
    rows = [json.loads(l) for l in SAMPLE.open(encoding="utf-8")]
    rows.sort(key=lambda r: r["order"])
    for r in rows[start : start + count]:
        print(f"\n{'#'*94}")
        print(f"{r['golden_id']}  [{r['stratum']}"
              + (f"/{r['probe']}" if r.get("probe") else "")
              + f"]  turns={r['n_turns']} brand_turns={r['n_brand_turns']}")
        print(f"ASK: {r['customer_message'][:420]}")
        thread = r["full_thread"][:max_turns]
        for t in thread[1:]:
            tag = "CUST" if t["role"] == "customer" else "AMZN"
            print(f"  {tag}: {t['text'][:230]}")
        if len(r["full_thread"]) > max_turns:
            print(f"  ... (+{len(r['full_thread'])-max_turns} more turns)")


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    main(a, b)
