# Decision log

Non-obvious calls, why they were made, and what each cost. Ordered roughly by how much
they shaped the result.

---

**1. Brand chosen by deflection rate, not volume or name recognition.**
AppleSupport is the obvious pick and 52.5% of its replies are "DM us" — grounding a drafter in
that history teaches it to deflect fluently. AmazonHelp has 1.6× the volume and 89.8%
substantive replies. *Cost:* Amazon is multilingual on one handle, so 16% of traffic had to be
dropped.

**2. Deflection measured in three forms, after the first measurement was wrong.**
My initial regex caught only DM deflections and made Amazon look 50× cleaner than Apple. Amazon
deflects to *phone/chat links* instead. Measuring one form of a behaviour and concluding it is
absent is the easiest error in this dataset — the corrected measure drives decision 1.

**3. Conversations reconstructed by union-find over reply links, not by following parent
pointers.** `in_response_to_tweet_id` and `response_tweet_id` are both incomplete and mutually
inconsistent (dangling parents, children that do not exist). Treating every observed link as an
undirected edge and taking connected components means a missing link in one direction cannot
silently split a conversation in two. Recovered 82,556 AmazonHelp threads from 2.8M loose
tweets.

**4. The unit of prediction is the first customer message of a thread.**
That is where a triage system must act, and the only point where the agent's draft can be
compared like-for-like against a human reply. *Cost:* 62% of threads continue past one exchange
and are out of scope. This is the largest deliberate scope cut in the project.

**5. Language filtered with a hand-rolled function-word detector, after ASCII-ratio failed
silently.** The first filter removed Japanese and kept French, Spanish and German — Latin-script
languages are ~97% ASCII. That left ~11% of the "English" corpus in languages the annotator
cannot read, which would have quietly corrupted both the taxonomy and the golden set. Model
hubs are unreachable from this sandbox, so the detector is 6 function-word lists. It is a
filter, not a language detector, and it still leaks on very short all-caps text (see G053).

**6. Temporal split, kept even after the evidence for it came out weak.**
I split at 2017-11-15 expecting heavy near-duplication across a random split (support traffic
is bursty; hundreds tweet the same complaint during an incident). Measured near-duplicate rate:
**0.33%** — far lower than assumed. Kept the temporal split anyway because it matches
production, but the leakage argument I would have made for it does not hold, and saying so
matters more than keeping a tidy justification.

**7. Ten intents, knowing 200 examples cannot measure ten classes well.**
Boundaries drawn on an operational test — *would the desk do something different?* — not a
semantic one. `delivery_delayed` and `delivery_missing` look similar and are separate because
one is expectation-setting and the other opens a carrier investigation. `damaged` and `wrong
item` feel different and are one class because both enter the same returns flow. *Cost:* rare
classes land 4-5 examples in stratum A; per-class F1 there is noise and is flagged as unreliable
in the output rather than quoted.

**8. Two golden strata, never averaged into one headline.**
Random-only leaves rare classes unmeasurable; stratified-only destroys any production claim.
Both were drawn and kept separate: **A (120, random)** produces every production number,
**B (80, probed)** does per-class reliability, operating-point tuning and error analysis. The
probes deliberately over-generate — they choose what gets *looked at*, never what the label is.

**9. Labelled with hindsight the agent is denied.**
The annotator saw the whole resolved thread; the agent sees only the opening message. Labels
therefore encode information the agent cannot reproduce from its own reasoning. This is the
main structural defence against the golden set being a mirror of the system — and it is a
partial defence, not a solution (see REPORT §6.4).

**10. Escalation rules written before labelling — then edited during it, and re-swept.**
Fixing rules first makes escalation labels auditable instead of intuitive. But labelling
surfaced cases the rules could not adjudicate, so E2 was widened and E9 added mid-annotation.
A rubric edited mid-annotation invalidates earlier labels unless every one is re-applied;
`scripts/06_finalise_golden.py` performs that sweep and prints what it touched (9 renames, 13
implied rules). Recording the drift beats hiding it.

**11. Cost ratio set at 10:1 — and treated as the main threat to the conclusion.**
Missed escalation vs needless escalation. Nobody measured this; I chose it. So the report
sweeps it from 1:1 to 20:1 and shows the agent only reliably beats no-automation below ~5:1.
The single most load-bearing assumption in the project is an assumption, and the honest output
is a break-even point rather than a verdict.

**12. Escalation threshold tuned on stratum B, evaluated on stratum A.**
Tuning and reporting on the same 120 cases would inflate the operating point by several points.
*Cost:* tuning on 80 biased cases is noisy — visible as non-monotonic winners in the cost-ratio
sweep — and that instability is reported rather than smoothed.

**13. Two model calls (triage, then draft) instead of one.**
One combined call is cheaper and scores slightly better on reply quality, because the model
writes the reply first and back-fills a label agreeing with it. That makes the system
unevaluable: escalation becomes a rationalisation of a reply already written. ~2× tokens for an
auditable decision.

**14. Unparseable triage output routes to a human. No retry, no default label.**
Retrying with a nudge until the JSON parses would make reported escalation numbers better than
the system deserves. A malformed output is a real failure and the safe behaviour is a human.
(It never fired — 0/200 parse failures — but the numbers are honest because of the policy, not
because of the outcome.)

**15. The simple baseline is deliberately advantaged.**
It is fitted on the golden labels out-of-fold, so it learns this annotator's idiosyncratic
boundaries — the exact thing the agent has to infer from a written taxonomy. Any margin the
agent wins under that handicap understates the true margin.

**16. Real human replies judged blind in the same batch as the systems.**
Without a human control, a reply-quality leaderboard is unfalsifiable. With it, three things
become measurable: whether the judge can tell quality apart at all, how far the agent is from
the human bar, and — via the pre-registered blind human scores — the size of the judge's
self-preference bias. That control is what turned "+0.85 over humans" into "+0.27, and +0.94 of
judge bias."

**17. Human scores written to disk before the judge ran.**
Obvious in principle, easy to violate in practice. Scoring after seeing the judge's answers
would make the agreement statistic meaningless.

**18. The safety dimension is reported and then disqualified.**
Judge-human QWK on `safe` is 0.100 — near zero, because both raters score nearly everything
4-5. There is no variance to agree about, so the dimension carries no information. Reporting
the number and then saying it should not be quoted is more useful than dropping it.

**19. Retrieval was built, ablated, and found harmful — and the finding was kept.**
The brief asks specifically for grounding in brand history. It was built, then tested: no
overall benefit, and a significant **−0.50 hit to relevance**. The mechanism is that Amazon's
history is largely deflection, so grounding teaches deflection. The convenient move was to
report retrieval as a feature and never ablate it.

**20. Inference recorded, not live-called.**
No API credentials were available and every non-Anthropic LLM host is firewalled from this
sandbox. Completions were produced by isolated Claude sessions given only the prompt, then
written into a content-addressed cache keyed by SHA-256 of the exact request. Consequences:
`make reproduce` replays every number offline in seconds with no key, and the cache doubles as
an audit log of every model input/output behind every figure. Documented in `docs/INFERENCE.md`.
*Cost:* generations were batched (30-50 prompts per session), so cases were not perfectly
independent of one another — disclosed, and the reason each batch prompt forbids
distribution-balancing.

**21. Agent predictions generated in sessions that never saw the labels.**
The session that wrote the golden labels could not also write the agent's predictions without
the evaluation measuring nothing. Isolated sessions received only the system prompt and the raw
tweets. *Cost:* ~4× the token spend of doing it inline, and one failed attempt that hit a rate
limit and had to be re-chunked.
