# How the model outputs in this repo were produced

Read this before judging the results. It is the one place where this project deviates from a
conventional "call the API in a loop" pipeline, and the deviation is disclosed rather than
buried.

## The constraint

This project was built in a sandbox with no Anthropic API credentials and an egress allowlist
that blocks every other LLM host (`generativelanguage.googleapis.com`, `api.groq.com`,
`openrouter.ai`, `api.together.xyz`, `api.mistral.ai`, `huggingface.co` — all refused at the
proxy). There was no route to metered inference of any kind.

## What was done instead

The pipeline is a normal API pipeline. `src/llm.py` wraps the Messages API with caching,
retries and usage accounting, and `scripts/08_run_agent.py` / `11_run_judge.py` will call it
live if you give them a key.

To build the committed cache without credentials, the same code path was run in **record
mode**: every prompt that missed the cache was written to `runs/pending_*.jsonl` along with the
SHA-256 of its exact request payload. Those prompts were then executed by **isolated Claude
sessions** that received only:

- the system prompt, read from disk (`runs/triage_system.txt`, `runs/draft_system.txt`,
  `runs/judge_system.txt`), and
- the batch of user messages,

and nothing else — no golden labels, no annotation notes, no thread context, no knowledge of
what the evaluation was for. Their outputs were loaded back into the cache by
`scripts/load_completions.py`, keyed by the same hash.

## Why the isolation matters

The session that produced the golden labels could not also produce the agent's predictions.
If it had, the evaluation would measure a model's agreement with its own earlier reasoning,
which is worth nothing. Separating them is not a workaround for the missing API key — it is a
methodological requirement that a live API would have satisfied automatically, and that had to
be arranged explicitly here.

The same applies to the judge: it was run in isolation, on anonymised candidates, with the
de-anonymisation key in a separate file the judging step never reads.

## What this costs, honestly

1. **Batching.** Each isolated session processed 25-50 prompts rather than one. Cases in a
   batch are therefore not perfectly independent — a real API call sees one input at a time.
   Every batch instruction explicitly forbids balancing the label distribution across the
   batch, but the residual effect is not zero and cannot be measured from this data.
2. **Token accounting.** Cached entries record 0 input/output tokens, because these were not
   metered API calls. The cost figures a live run would produce are therefore absent rather
   than estimated. Inventing them would have made the cost table fiction.
3. **Model identity.** Cache entries are labelled `claude-sonnet-4-5`, the model the live
   pipeline is configured for. The isolated sessions ran on the same model family; exact
   serving-version parity is not guaranteed.

## What it buys

- `make reproduce` replays every number in the report **offline, with no API key, in under a
  minute**. The brief asks reviewers to reproduce headline results in under 15 minutes; this
  removes credentials and wall-clock from that entirely.
- The cache is an audit log. Every model input and output behind every figure in the report is
  inspectable:

  ```bash
  sqlite3 cache/llm_cache.sqlite \
    "SELECT json_extract(request,'$.messages[0].content'), response FROM calls LIMIT 1;"
  ```

- Content addressing makes stale results impossible. Change one character of a prompt and it
  becomes a cache miss, not a silently reused answer. In offline mode a miss is a hard error
  naming the model and key, so a reproduction run cannot quietly fall back to a stale number.

## Running it live instead

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make live          # regenerates every completion through the real API
```

This will produce different completions (different sampling, one prompt per call, genuinely
independent cases) and therefore slightly different numbers. That is expected. The comparison
between a live run and the committed cache is itself a useful check on how much the batching
in point 1 above actually mattered — it is the first thing worth running if you have a key.
