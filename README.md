# A support agent for @AmazonHelp, and an honest account of how good it isn't

Triage, draft and escalation for real customer-support tweets, built on the
[Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter)
dataset (2.8M tweets, 93 brands).

The system is the easy half. The evaluation is the point, and the evaluation's main finding is
that **the headline numbers overstate the system substantially** — in ways this repo measures
rather than asserts.

---

## Reproduce the headline results (~60 seconds, no API key, no data download)

```bash
git clone <this repo> && cd support-agent
pip install -r requirements.txt
make reproduce
```

That replays every number quoted in [`reports/REPORT.md`](reports/REPORT.md) from a committed,
content-addressed cache of model outputs. No credentials, no network, no 516MB download. A
cache miss is a hard error, so the run cannot quietly fall back to a stale figure.

```bash
make test    # 11 guards against the specific ways this kind of project goes wrong
```

How the cached model outputs were produced — and why that required care rather than just an
API key — is documented in [`docs/INFERENCE.md`](docs/INFERENCE.md). Read it before judging
the results.

---

## What it does

```
incoming tweet
     │
     ├─► TRIAGE      10 intents derived from the data · confidence · escalate? · which rule fired · why
     ├─► RETRIEVE    nearest historical AmazonHelp cases from before the eval cutoff
     └─► DRAFT       a reply, conditioned on the triage decision and that precedent
```

Two model calls, not one. Combining them scores slightly better and destroys the evaluation:
the model writes the reply first and back-fills a label that agrees with it, so escalation
becomes a rationalisation of a reply already written.

---

## Headline results

Everything below is **stratum A** — 120 uniformly random cases from held-out traffic. Intervals
are bootstrap 95%.

**Intent classification**

| system | macro-F1 | accuracy |
|---|---|---|
| trivial (majority class) | 0.033 | 0.200 |
| simple (TF-IDF + LogReg, out-of-fold) | 0.433 [0.32, 0.52] | 0.517 |
| **agent** | **0.797** [0.69, 0.87] | **0.850** [0.78, 0.91] |

**Escalation** — where missing one costs 10× escalating needlessly

| policy | recall | automated | **cost/100** |
|---|---|---|---|
| never escalate (trivial) | 0% | 100% | 533.3 |
| keyword rules (simple) | 42.2% | 65.8% | 320.0 |
| **always escalate — no automation at all** | 100% | 0% | **46.7** |
| **agent (tuned on held-out stratum B)** | **96.9%** | **21.7%** | **43.3** |

Read the third row. Under this cost model, **doing nothing beats the simple baseline by 7×**.
Automating badly is much worse than not automating, and the agent's margin over doing nothing
is 7%.

**Reply quality** — blinded LLM judge, four systems scored together, n=120

| system | overall | send-as-is |
|---|---|---|
| agent | 4.47 | 91% |
| reference (what AmazonHelp actually replied) | 3.62 | 26% |
| simple (nearest-neighbour real reply) | 3.08 | 11% |
| trivial (canned macro) | 2.92 | 1% |

---

## Three findings worth more than the table above

**1. The agent does not beat human support agents. The judge is biased, and the bias is
measured.** 30 cases were hand-scored blind, and written to disk *before* the judge ran:

| | agent − reference |
|---|---|
| the judge says | **+1.213** |
| a blind human says | **+0.273** |
| **judge inflation** | **+0.940** |

**~77% of the headline win is judge bias.** Note the judge has *high rank agreement* with the
human (QWK 0.789) and is badly *miscalibrated in magnitude* — correlation does not buy you
calibration, and magnitude is what drives the claim.

**2. The grounding does not ground anything.** The brief asks for replies grounded in brand
history. Built, then ablated — 40 paired cases, with retrieval vs without:

| | difference |
|---|---|
| overall | −0.095 [−0.32, +0.11] |
| **relevance** | **−0.500 [−0.88, −0.15]** |

Retrieval provides no measurable benefit and **significantly damages relevance**. The
mechanism is visible in the outputs: Amazon's historical replies are largely deflection
("please contact us here"), so grounding the drafter in them teaches deflection.

**3. The agent cannot find a safe slice of traffic to automate.** Ranking auto-handled cases by
the agent's own confidence, the first missed escalation appears after 9 cases (7.5% of
traffic). Maximum coverage holding a ≤2% miss rate: **6.7%**. That is not a business case.

**Recommendation: ship as a triage assistant, do not let it send anything.**

The full self-critique is [`reports/REPORT.md` §6](reports/REPORT.md) — including the
cost-ratio sensitivity that decides the deployment question, and why the win at 10:1 is partly
luck of the tuning split.

---

## The golden set

200 cases, hand-labelled, from traffic after the temporal cutoff. Two strata kept separate
permanently:

- **A (n=120), uniform random.** Unbiased. Every production claim comes from here alone.
- **B (n=80), keyword-probed for rare and high-stakes intents.** Biased by construction. Used
  for per-class reliability, operating-point tuning and error analysis. Never a headline.

The annotator saw the **whole resolved thread**; the agent sees only the opening message. That
asymmetry is the main structural defence against the golden set being a mirror of the system.

**53.3% of real traffic needs a human.** **36.5% of cases were flagged ambiguous at labelling
time** — all 73 are in [`data/golden/ADJUDICATION.md`](data/golden/ADJUDICATION.md) for
second-opinion review. Sampling and labelling protocol:
[`scripts/05_sample_golden.py`](scripts/05_sample_golden.py).

---

## Layout

```
src/
  taxonomy.py          10 intents + 9 escalation rules. Single source of truth: the
                       annotation guide and the classifier prompt are rendered from it,
                       so they cannot drift apart.
  llm.py               cached, content-addressed client (record / offline / live modes)
  data/langid.py       function-word language filter (ASCII-ratio failed silently)
  data/threads.py      union-find conversation reconstruction over inconsistent reply links
  agent/               prompts, retrieval, two-stage pipeline
  baselines/           trivial + simple, plus the keyword escalation rules
  evaluation/          metrics with bootstrap CIs, blinded judge, agreement statistics
scripts/               01-15, numbered in pipeline order
reports/REPORT.md      the writeup, incl. "what is misleading about my headline number"
reports/DECISIONS.md   21 non-obvious decisions and what each cost
docs/INFERENCE.md      how the cached model outputs were produced, and the caveats
results/*.json         machine-readable output behind every figure in the report
```

## Rebuilding from source

```bash
# put twcs.csv in data/raw/ (Kaggle, 516MB, not redistributed here)
make data     # ~4 min: brand selection, threading, clustering, splits, golden set
```

## Running live against the API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make live
```

Different completions, so slightly different numbers — expected, and the comparison against
the committed cache is itself a useful check (see `docs/INFERENCE.md`).

---

## Known limitations

- First customer message only; 62% of threads continue past one exchange.
- English only; 16% of AmazonHelp traffic on this handle is other languages, and the filter
  still leaks on very short all-caps text.
- Text only; some cases carry their meaning entirely in an attached image.
- Single annotator. Every accuracy figure substantially measures agreement with one person's
  reading of a taxonomy that same person wrote.
- n=120 for every production claim. The macro-F1 interval spans 18 points.
- Data is October–December 2017.
