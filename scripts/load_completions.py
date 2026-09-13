"""Load generated completions into the content-addressed cache.

Each completion is keyed by the SHA-256 of its exact request payload, so a
completion can only ever be served for the prompt that produced it. Change a
prompt by one character and it becomes a cache miss rather than silently
reusing a stale answer.

Usage:
    python scripts/load_completions.py runs/chunks/A_1_out.jsonl [more...]

Input lines: {"key": "...", "completion": "..."} plus whatever else.
The pending file supplies the model and request payload for each key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm import _Cache, DEFAULT_CACHE

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"


def load_pending() -> dict[str, dict]:
    """key -> the recorded request, across every pending file."""
    out: dict[str, dict] = {}
    for p in sorted(RUNS.glob("pending_*.jsonl")):
        for line in p.open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            out[r["key"]] = r
    return out


def main(paths: list[str]) -> None:
    pending = load_pending()
    cache = _Cache(DEFAULT_CACHE)
    added = skipped = unknown = 0

    for path in paths:
        for line in Path(path).open(encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            key, text = row["key"], row["completion"]
            req = pending.get(key)
            if req is None:
                unknown += 1
                continue
            if cache.get(key) is not None:
                skipped += 1
                continue
            payload = {
                "model": req["model"],
                "system": req["system"],
                "messages": [{"role": "user", "content": req["prompt"]}],
                "max_tokens": req["max_tokens"],
                "temperature": req["temperature"],
                "stop_sequences": None,
            }
            # Token counts are recorded as 0: these completions did not come
            # from a metered API call, and inventing usage numbers would make
            # the cost table in the report a fiction.
            cache.put(key, req["model"], payload, text, 0, 0)
            added += 1

    print(f"added={added} already_cached={skipped} unknown_key={unknown}")
    print(f"cache now holds {cache.size()} completions at {DEFAULT_CACHE}")
    if unknown:
        print("!! unknown keys mean the prompt changed since recording; re-record and regenerate.")


if __name__ == "__main__":
    main(sys.argv[1:])
