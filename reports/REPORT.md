# An AI support agent for @AmazonHelp — and how much to trust it

**TL;DR.** The agent classifies intent at 0.80 macro-F1 and catches 97% of cases that need a
human. It also, at the cost ratio this report argues for, barely beats the strategy of
employing no automation at all; its apparent 0.85-point win over real human replies is
~77% judge bias; and the retrieval component the brief specifically asks for — grounding
replies in brand history — **measurably makes replies worse**. The recommendation is to
ship it as a triage assistant for human agents and not to let it send anything.

---

## 1. Problem framing

### The brand, chosen on evidence

I scored all 93 brands on volume, deflection rate, reply substance and language
(`scripts/01_select_brand.py`). The intuitive pick is **AppleSupport** — the biggest
consumer name in the dataset. It is a trap:

| brand | replies | "DM us" | phone/chat punt | substantive |
|---|---|---|---|---|
| **AmazonHelp** | 169,840 | 0.7% | 4.8% | **89.8%** |
| AppleSupport | 106,860 | 52.5% | 0.0% | 46.7% |
| TMobileHelp | 34,317 | 82.8% | 0.1% | 16.2% |
| comcastcares | 33,031 | 71.5% | 0.0% | 27.1% |

Over half of Apple's replies are "DM us". An agent grounded in that history learns to say
"DM us" with high fidelity — a working system worth nothing. AmazonHelp has 1.6× the volume
and 89.8% substantive replies, so **AmazonHelp**.

Note the first version of this measurement only counted DM deflections and made Amazon look
50× cleaner than it is. Amazon deflects to *phone/chat links* instead. Measuring one form of
a behaviour and concluding it is absent is the easiest mistake in this dataset.

### What "good" means here

Not accuracy. The governing fact is an asymmetry: **auto-replying to a case that needed a
human is far more expensive than escalating one a bot could have closed.** A missed
escalation on a fraud report or a furious customer is a public brand failure; an unnecessary
escalation costs a few minutes of agent time. I set that ratio at **10:1** and — critically —
report what happens as it varies, because it is an assumption, not a measurement, and it
decides the entire deployment conclusion (§6).

So "good" is: *maximise the traffic handled automatically, subject to almost never
auto-handling something that needed a person.*

### Scope: what I chose not to build

- **Multi-turn state.** The agent acts only on the first customer message of a thread. Mid-
  conversation turns depend on state (what was already asked, what the customer answered)
  that would need a dialogue manager. 62% of threads run past one exchange, so this is a real
  limitation, not a rounding error.
- **Non-English.** 16% of AmazonHelp's English-handle traffic is French, Spanish, German,
  Portuguese, Italian or Japanese. Filtered out. I cannot hand-label what I cannot read, and
  pretending otherwise would corrupt the golden set.
- **Images.** Several cases carry their meaning entirely in an attached screenshot. Text-only
  pipeline; these are unreachable by construction and show up in the failure analysis.
- **Actually resolving anything.** The agent has no order lookup, no account access, no
  refund authority. It drafts and routes. Everything downstream of that is out of scope.
- **Fine-tuning.** 41k training cases exist, but the golden set is the only labelled data, and
  200 examples is not a fine-tuning corpus — it is a test set, and spending it on training
  would leave nothing to measure with.

---

## 2. What was built

```
incoming tweet
     │
     ├─► TRIAGE (LLM, structured JSON)
     │     intent ∈ 10 labels · confidence · escalate · rule IDs · one-line reason
     │     └─ confidence < threshold ⇒ escalate regardless (policy in code, not prompt)
     │
     ├─► RETRIEVE (TF-IDF word+char n-grams over 33,359 pre-cutoff resolved cases)
     │
     └─► DRAFT (LLM, conditioned on triage + retrieved precedent)
```

Two model calls, not one. A single call that emits label and reply together scores slightly
better and is unevaluable: the model writes the reply first and back-fills a label that
agrees with it, so the escalation decision becomes a post-hoc rationalisation. Splitting
them costs ~2× the tokens and buys an auditable decision.

**The intent taxonomy** (10 labels) was derived bottom-up: TF-IDF → k-means at k=24 over 30k
opening messages, then reading every cluster alongside what Amazon actually replied. k=24 is
deliberately larger than the target so rare-but-expensive intents (account security, ~1% of
volume) surfaced separately instead of being absorbed. Boundaries were drawn on an
operational test — *would the support desk do something different?* — not a semantic one.
"Parcel is late" and "tracking says delivered but it isn't here" cluster together and are
separate intents, because one is expectation-setting and the other opens a carrier
investigation.

**The escalation policy** is nine written rules (E1 account security … E9 relationship risk),
fixed before labelling so that escalation labels are auditable rather than intuitive. Every
escalate=True label in the golden set names the rule that fired.

---

## 3. The golden set

200 cases, hand-labelled, sampled from traffic **after** the temporal cutoff.

**Two strata, kept separate forever:**

- **Stratum A (n=120), uniform random.** Unbiased. Every number in this report that claims to
  describe production traffic comes from A and only A.
- **Stratum B (n=80), keyword-probed for rare/high-stakes intents.** Biased by construction.
  Used for per-class reliability, for tuning the operating point, and for error analysis —
  never for a headline.

A single sample cannot do both jobs: random leaves rare classes with 3-5 examples, stratified
destroys any production claim. Reporting both, and never silently averaging them, is the
point.

**Labelling protocol.** The annotator saw the *whole resolved thread* — the opening ask, what
Amazon actually replied, how many turns it took, how it ended. The agent sees only the opening
message. That asymmetry is deliberate: labels made with hindsight encode information the agent
cannot reproduce from its own reasoning, which is the main defence against the golden set
being a mirror of the system.

**What the labels look like:**

| | stratum A |
|---|---|
| delivery_delayed | 20.0% |
| service_complaint | 15.8% |
| billing_account | 13.3% |
| digital_service | 12.5% |
| delivery_missing | 12.5% |
| item_problem | 6.7% |
| feedback_other / presales_info | 5.8% each |
| return_refund | 4.2% |
| other | 3.3% |
| **needs a human** | **53.3%** |

**36.5% of cases were flagged ambiguous at labelling time.** That is not annotator weakness;
it is the data. `data/golden/ADJUDICATION.md` contains all 73 for second-opinion review.

**Two honest caveats on the labels.** (i) The escalation rules were edited *during*
annotation — E2 widened, E9 added — because labelling surfaced cases the original rules could
not adjudicate. Every label was then re-swept uniformly (`scripts/06_finalise_golden.py`
reports it touched 9 renames + 13 implied rules). A rubric edited mid-annotation is a real
threat to validity; the mitigation is to say so and re-apply it. (ii) Single annotator.
See §6.

---

## 4. Results

### Intent classification (stratum A, n=120)

| system | macro-F1 | accuracy |
|---|---|---|
| trivial (majority class) | 0.033 | 0.200 |
| simple (TF-IDF + LogReg, out-of-fold) | 0.433 [0.32, 0.52] | 0.517 |
| **agent** | **0.797** [0.69, 0.87] | **0.850** [0.78, 0.91] |

The simple baseline is *handed an advantage the agent never gets*: it is fitted on the golden
labels themselves (out-of-fold), so it learns this annotator's idiosyncratic boundaries — the
exact thing the agent must infer from a written taxonomy. The agent wins under that handicap.

Accuracy decomposes sharply by label difficulty:

| | n | accuracy |
|---|---|---|
| cases I marked unambiguous | 127 | **0.945** |
| cases I marked ambiguous | 73 | **0.616** |

### Escalation (stratum A, threshold tuned on stratum B)

| policy | recall | automated | missed | **cost/100** |
|---|---|---|---|---|
| never escalate (trivial) | 0% | 100% | 53.3% | 533.3 |
| keyword rules (simple) | 42.2% | 65.8% | 30.8% | 320.0 |
| agent, untuned (t=0.55) | 87.5% | 41.7% | 6.7% | 78.3 |
| **always escalate — no automation at all** | **100%** | **0%** | **0%** | **46.7** |
| **agent, tuned (t=0.75)** | **96.9%** | **21.7%** | **1.7%** | **43.3** |

**Read the fourth row.** Under a 10:1 asymmetry, *doing nothing* beats the simple baseline by
7× and beats the untuned agent. Automating badly is much worse than not automating. The tuned
agent beats no-automation — by 7%, while automating only 21.7% of traffic.

### Reply quality (blinded LLM judge, n=120, four systems scored together)

| system | overall | grounded | relevant | actionable | tone | safe | send-as-is |
|---|---|---|---|---|---|---|---|
| **agent** | **4.47** | 4.31 | 4.65 | 4.18 | 4.47 | 4.75 | 91% |
| reference (real AmazonHelp) | 3.62 | 3.70 | 3.50 | 3.42 | 3.12 | 4.34 | 26% |
| simple (nearest-neighbour) | 3.08 | 3.29 | 2.40 | 2.54 | 2.60 | 4.55 | 11% |
| trivial (canned macro) | 2.92 | 4.00 | 1.33 | 1.92 | 2.39 | 5.00 | 1% |

Paired bootstrap, agent vs reference: **+0.853** [+0.71, +0.99], P(agent better) = 1.00.

The agent appears to beat professional human support agents. **It does not.** See §6.

### Is the judge trustworthy?

30 cases × 4 replies were hand-scored **blind, and written to disk before the judge ran**.

| dimension | QWK | Spearman | within ±1 |
|---|---|---|---|
| relevant | 0.860 | 0.891 | 97% |
| tone | 0.845 | 0.847 | 99% |
| actionable | 0.734 | 0.821 | 94% |
| grounded | 0.435 | 0.473 | 95% |
| **safe** | **0.100** | 0.025 | 90% |
| **all pooled** | **0.789** | 0.784 | 95% |

send-as-is: Cohen's κ = 0.599 (81% raw). Best-pick agreement 0.63 vs 0.25 chance.

So: **the judge is reliable on relevance, tone and actionability; unreliable on groundedness;
and meaningless on safety.** The safety κ is near zero because both raters score nearly
everything 4-5 — there is no variance to agree about, so that dimension carries no
information and should not be quoted.

### Does grounding in brand history help? (the ablation)

The brief asks specifically for replies "grounded in how that brand has historically resolved
similar issues". I built that, then tested it. 40 cases, agent with retrieval vs without,
blinded and paired:

| | with retrieval | without | difference |
|---|---|---|---|
| overall | 4.235 | 4.330 | **−0.095** [−0.32, +0.11] |
| relevant | — | — | **−0.500** [−0.88, −0.15] |

**Retrieval provides no measurable benefit overall and significantly damages relevance.**
Corroborating evidence: Spearman(top-1 retrieval similarity, judge score) = **−0.067** across
all 120 cases — retrieval quality is unrelated to reply quality.

The mechanism is visible in the outputs. Grounded in Amazon's history, the agent learns
Amazon's habit — redirect to phone/chat. Ungrounded, it answers:

> **Customer:** Livestream from my LG v30 to my new fire stick is very choppy. Works fine on
> my Roku. Any firmware update to fix this?
> **With retrieval:** "…this looks Fire Stick-specific. Have you contacted Customer Service to
> help troubleshoot this?"
> **Without retrieval:** "Try moving your Fire Stick and router closer together, restart both,
> and check for a software update under Settings > My Fire TV > About."

Retrieval is also weak on its own terms: **64.5%** of cases have a best historical match below
0.30 cosine. The "precedent" shown to the drafter is usually barely related.

---

## 5. Failure analysis — top 5

All 12 missed escalations (stratum A + B) were read individually. Five patterns, in order of
cost.

**F1 — "No action was explicitly requested" (5 of 12 misses).** The agent classifies
`delivery_missing` correctly, then declines to fire E2 because the customer did not *ask* for
anything.

> G013: *"got an 'attempted delivery' email today but my office reception is manned 24/7.
> Strange"* → intent `delivery_missing` ✓, confidence 0.80, **escalate = false**.
> Agent's reason: *"…matching a false delivery attempt."* It identified the problem exactly
> and still routed it to a bot.

**Hypothesis:** a rule-wording defect, not a reasoning defect. E2 reads "issuing or chasing a
refund", which the model interprets as requiring a customer request. The rule should be
stated in terms of *what closing the case requires*, not what the customer asked for. This is
my bug, and it is cheap to fix.

**F2 — Complaint-with-recovery reads as closed (3 of 12).** The customer got their item but is
angry about how. The agent treats a resolved artefact as a resolved relationship.

> G021: *"thanks for AMZL leaving my packages unsecured outside of the CLOSED leasing office…
> I had to go on a hunt to find my damn packages"* → `service_complaint` ✓, **escalate =
> false**, reason: *"…a carrier-conduct complaint after recovering them."*

**Hypothesis:** E9 (relationship risk) is the newest and least-specified rule, added
mid-annotation. The agent under-applies it exactly where it was added to apply.

**F3 — Vulnerability signals not weighted.** G173 contains *"my son is still waiting for his
gift"* alongside a falsified carrier report; the agent routed it to auto as a routine delay.
E6 fired in my labels and not in the model's. **Hypothesis:** E6's examples are all explicit
(bereavement, medical, disability) and the model does not generalise to implicit dependency.

**F4 — Goal buried under a technical symptom.** G176 reports a 404 on a sign-in page; the
actual goal is *"i need to reset my 2FA"*. The agent classified the surface symptom
(`digital_service`, correct) and missed the account-security goal underneath. **Hypothesis:**
triage classifies the topic rather than the objective; these come apart whenever a customer
narrates a workaround instead of the aim.

**F5 — Artefacts of my own pipeline.** Two distinct self-inflicted failures:
- G053 (*"ACORDEI E 2 MINUTOS DEPOIS CHEGARAM OS MEUS LIVROS! OBRIGADA"*) is Portuguese that
  slipped my language filter — all-caps with few function words. The agent read it correctly
  and confidently (0.85) and was marked wrong for doing so, because my scope says non-English
  is out of scope.
- G186 (*"Shout out to"*) is meaningless because my own cleaning stripped the @handle.

**Hypothesis:** preprocessing built for the median case silently destroys short messages, and
short messages are ~10% of traffic.

**Also notable (not an escalation miss):** the largest intent confusions are
`feedback_other → other` (4), `presales_info → digital_service` (4) and
`item_problem → return_refund` (3). The last is arguably not an error at all — "my item is
broken" and "I want to return my broken item" are the same ticket at different moments, and
my taxonomy forces a choice the data does not support.

---

## 6. What is misleading about my headline number

**The headline: "0.80 macro-F1, 97% escalation recall, and it beats human replies by 0.85."**
Here is everything wrong with that sentence.

### 6.1 The agent does not beat human support agents. The judge is biased, and I measured it.

The same 30 cases, scored by the blinded judge and by a blind human rater:

| | agent − reference |
|---|---|
| judge says | **+1.213** [+0.95, +1.45] |
| blind human says | **+0.273** [+0.05, +0.49] |
| **inflation attributable to the judge** | **+0.940** |

**Roughly 77% of the headline win is judge bias.** The real gap is +0.27 with a confidence
interval that nearly touches zero. Any reply-quality claim in §4 should be read with that
discount applied.

Note the subtlety: the judge has *high rank agreement* with the human (QWK 0.79) and is still
badly *miscalibrated in magnitude*. Correlation does not buy you calibration, and it is
magnitude that drives the headline.

I tested an alternative explanation first and it was wrong. My cleaning replaced URLs with
`<link>`, mangling 60% of real Amazon replies before judging — I expected that to explain the
gap. It does not: restricted to cases where the reference contains no link, the gap *widens*
to +0.963. Good hypothesis, refuted by the data.

### 6.2 The deployment conclusion rests on a number I invented

Everything in §4 assumes missed escalations cost 10× needless ones. Nobody measured that. Vary
it:

| cost ratio | agent | always-escalate | winner |
|---|---|---|---|
| 1:1 | 18.3 | 46.7 | agent |
| 3:1 | 36.7 | 46.7 | agent |
| **5:1** | **46.7** | **46.7** | **tie** |
| 8:1 | 61.7 | 46.7 | always-escalate |
| 10:1 | 43.3 | 46.7 | agent |
| 15:1 | 51.7 | 46.7 | always-escalate |
| 20:1 | 60.0 | 46.7 | always-escalate |

Two things to take from this. First, **the agent only reliably beats no-automation below about
5:1** — and the whole design premise of this project is that the ratio is *higher* than that.
Second, the non-monotonicity (loses at 8:1, wins at 10:1, loses at 15:1) is **not a real
effect**. It is the threshold being re-tuned on 80 stratum-B cases at each ratio and
overfitting. The win at 10:1 is partly luck of the tuning split, and I would not defend it.

### 6.3 The agent cannot identify a safe slice of traffic

The deployment case depends on automating the easy cases and escalating the rest. Ranking
auto-handled cases by the agent's own confidence:

- The **first missed escalation appears after only 9 auto-handled cases** (7.5% of traffic).
- **Maximum coverage holding ≤2% miss rate: 6.7% of traffic.**

Confidence barely separates safe from unsafe. Automating 6.7% of traffic is not a business
case.

### 6.4 The measurement measures agreement with me

The golden labels, the taxonomy, the escalation rules, the prompts and the judge rubric were
all written by the same mind. 0.85 accuracy substantially means *"the agent agrees with my
opinions about my own taxonomy."* Two things partially mitigate and neither fixes it: labels
were made with hindsight the agent does not have, and agent predictions were generated in
isolated sessions that never saw the labels. The `ADJUDICATION.md` queue exists so a second
person can attack the 73 most contestable labels; until they do, treat every number as
provisional.

### 6.5 n = 120

Every production claim rests on 120 examples. The macro-F1 interval is [0.69, 0.87] — a span
of 18 points. Differences smaller than that are not results. Per-class F1 for `other` (n=4)
and `return_refund` (n=5) is noise and is flagged as such in the output.

### 6.6 The grounding does not ground anything

The component the brief specifically asks for is inert at best and harmful to relevance at
worst (§4). If you strip retrieval out, the numbers barely move. Whatever the agent is doing
well, it is not "learning from brand history."

### 6.7 The data is from October–December 2017

Nine years old. Every policy, carrier, product and support workflow referenced has changed.
This measures whether the approach works, not whether this agent would work today.

### 6.8 Mediocre reference, easy target

26% of real AmazonHelp replies in the sample were judged send-as-is. Beating this baseline is
not the same as being good — it partly reflects that Twitter support in 2017 was largely a
deflection channel.

---

## 7. What I'd do with one more week

In priority order, each aimed at a specific finding above.

1. **Fix F1/F2 and re-measure (½ day).** Rewrite E2 in terms of what closing the case requires
   rather than what the customer asked for; add explicit recovered-but-angry exemplars to E9.
   These two patterns are 8 of 12 misses and the fix is prompt-level. This is the single
   highest-value change here.
2. **Get a second annotator onto ADJUDICATION.md (1 day).** 73 contestable labels, one
   afternoon of a second person's time, and then §6.4 becomes a measured inter-annotator κ
   rather than a confession. Everything downstream inherits the credibility.
3. **Replace the judge with a human-anchored one (1 day).** Given §6.1, calibrate the judge
   against the blind human scores — fit the offset, or switch to pairwise-only judging, which
   is far less prone to magnitude drift than absolute scoring.
4. **Kill or fix retrieval (1 day).** Dense embeddings over the resolved corpus, plus filtering
   the index to *non-deflecting* replies only — the current corpus teaches deflection. If a
   properly-built retriever still fails the ablation, delete the component and say so.
5. **Buy escalation recall with a cheap second opinion (1 day).** The failure modes are
   recall failures on a policy the model already understands. A second triage pass on
   auto-handled cases only (21.7% of traffic — so nearly free) targeting §6.3 directly.
6. **Extend to multi-turn (2 days).** 62% of threads continue past the first exchange, and
   the highest-value automation may be mid-thread, not at the front door.
7. **Widen the golden set to 500 and stratify by ambiguity (1 day).** §6.5 is a sample-size
   problem and sample size is purchasable.

**What I would tell a decision-maker today:** do not let this system send replies. Deploy it
as a triage assistant — it routes correctly 85% of the time, catches 97% of cases needing a
human, and its drafts are a reasonable starting point for an agent to edit. The automation
case does not survive the cost analysis, and the honest number for auto-handling is 6.7% of
traffic, not 21.7%.
