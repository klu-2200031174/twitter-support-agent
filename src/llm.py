"""Cached, concurrent Anthropic client.

Every model call is keyed by a hash of (model, system, messages, decoding params)
and written to an on-disk cache that is committed to the repo. Consequences:

  * `make reproduce` replays every number in the report with no API key and no
    network, in well under 15 minutes.
  * Re-running an experiment after changing one prompt only pays for the calls
    that actually changed.
  * The cache doubles as an audit log: every model input/output pair that
    produced a number in the report is inspectable in `cache/`.

Cache entries are content-addressed, so a changed prompt is a cache miss by
construction -- there is no way to silently serve a stale answer for a new
prompt.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO_ROOT / "cache" / "llm_cache.sqlite"

# Published per-million-token prices, used only for the cost figures in the
# report. Update if pricing changes; nothing in the pipeline depends on these.
PRICES_PER_MTOK = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5": (5.00, 25.00),
}


def _price(model: str) -> tuple[float, float]:
    for key, val in PRICES_PER_MTOK.items():
        if model.startswith(key):
            return val
    return (0.0, 0.0)


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, model: str, in_tok: int, out_tok: int) -> None:
        pin, pout = _price(model)
        with self._lock:
            self.calls += 1
            self.input_tokens += in_tok
            self.output_tokens += out_tok
            self.cost_usd += in_tok / 1e6 * pin + out_tok / 1e6 * pout

    def hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def summary(self) -> dict[str, Any]:
        return {
            "live_calls": self.calls,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 4),
        }


class _Cache:
    """SQLite-backed content-addressed cache. Thread-safe, one connection per thread."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.Lock()
        with self._conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS calls ("
                " key TEXT PRIMARY KEY,"
                " model TEXT, request TEXT, response TEXT,"
                " input_tokens INT, output_tokens INT, created_at REAL)"
            )

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT response, input_tokens, output_tokens FROM calls WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return None
        return {"text": row[0], "input_tokens": row[1], "output_tokens": row[2]}

    def put(self, key: str, model: str, request: dict, text: str, in_tok: int, out_tok: int) -> None:
        with self._write_lock:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?)",
                (key, model, json.dumps(request, sort_keys=True), text, in_tok, out_tok, time.time()),
            )
            conn.commit()

    def size(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM calls").fetchone()[0]


class LLM:
    """Thin wrapper over the Messages API with caching, retries and accounting.

    Parameters
    ----------
    offline:
        When True, a cache miss raises instead of hitting the network. This is
        what `make reproduce` uses: it guarantees the committed numbers came
        from the committed cache and cannot be quietly regenerated.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5",
        cache_path: Path | str = DEFAULT_CACHE,
        offline: bool | None = None,
        max_retries: int = 6,
        record_misses_to: Path | str | None = None,
    ):
        self.model = model
        self.cache = _Cache(Path(cache_path))
        self.usage = Usage()
        self.max_retries = max_retries
        if offline is None:
            offline = os.environ.get("LLM_OFFLINE", "0") == "1"
        self.offline = offline
        self._client = None
        self._client_lock = threading.Lock()
        # Miss-recording mode: instead of calling the API (or failing), write
        # the exact prompt and its cache key to a file so the completions can
        # be produced out of band and loaded back in. This is how the committed
        # cache in this repo was built without API credentials; see
        # docs/INFERENCE.md.
        self.record_misses_to = Path(record_misses_to) if record_misses_to else None
        self._recorded: set[str] = set()
        self._record_lock = threading.Lock()
        if self.record_misses_to:
            self.record_misses_to.parent.mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    import anthropic

                    self._client = anthropic.Anthropic(max_retries=0)
        return self._client

    @staticmethod
    def _key(payload: dict) -> str:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        prefill: str | None = None,
        stop_sequences: Sequence[str] | None = None,
        model: str | None = None,
    ) -> str:
        model = model or self.model
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        if prefill:
            messages.append({"role": "assistant", "content": prefill})
        payload = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop_sequences": list(stop_sequences) if stop_sequences else None,
        }
        key = self._key(payload)

        cached = self.cache.get(key)
        if cached is not None:
            self.usage.hit()
            return cached["text"]

        if self.record_misses_to is not None:
            with self._record_lock:
                if key not in self._recorded:
                    self._recorded.add(key)
                    with self.record_misses_to.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({
                            "key": key, "model": model, "system": system,
                            "prompt": prompt, "max_tokens": max_tokens,
                            "temperature": temperature,
                        }, ensure_ascii=False) + "\n")
            return ""  # caller must tolerate empty output during a recording pass

        if self.offline:
            raise RuntimeError(
                "LLM cache miss in offline mode.\n"
                f"  model={model} key={key[:12]}\n"
                "  The committed cache does not contain this call. Either a prompt "
                "changed, or you are running a step that needs live inference.\n"
                "  Re-run with ANTHROPIC_API_KEY set and LLM_OFFLINE=0."
            )

        text, in_tok, out_tok = self._call_with_retries(payload)
        if prefill:
            text = prefill + text
        self.usage.add(model, in_tok, out_tok)
        self.cache.put(key, model, payload, text, in_tok, out_tok)
        return text

    def _call_with_retries(self, payload: dict) -> tuple[str, int, int]:
        kwargs = {k: v for k, v in payload.items() if v is not None}
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.messages.create(**kwargs)
                text = "".join(b.text for b in resp.content if b.type == "text")
                return text, resp.usage.input_tokens, resp.usage.output_tokens
            except Exception as exc:  # noqa: BLE001 - retry on anything transient
                last_err = exc
                status = getattr(exc, "status_code", None)
                if status is not None and status < 500 and status not in (408, 409, 429):
                    raise
                time.sleep(min(2**attempt + random.random(), 30))
        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts: {last_err}")

    def map(
        self,
        fn: Callable[[Any], Any],
        items: Iterable[Any],
        workers: int = 8,
        desc: str = "",
    ) -> list[Any]:
        """Run `fn` over items concurrently, preserving input order.

        Concurrency is bounded because the cache is the common case: a warm run
        is IO against SQLite, not the network.
        """
        items = list(items)
        if not items:
            return []
        from concurrent.futures import as_completed

        out: list[Any] = [None] * len(items)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
            done = 0
            for fut in as_completed(futures):
                idx = futures[fut]
                out[idx] = fut.result()
                done += 1
                if desc and (done % 25 == 0 or done == len(items)):
                    print(f"  {desc}: {done}/{len(items)}", flush=True)
        return out


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model response.

    Models occasionally wrap JSON in prose or fences even when told not to.
    Failing loudly here beats silently mislabelling an example, so the caller
    sees a ValueError with the raw text attached.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in response: {text[:300]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"unbalanced JSON in response: {text[:300]!r}")
