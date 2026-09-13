"""Metrics, with intervals attached to everything.

Every headline number in this project comes from at most 120 unbiased
examples. A bare point estimate at that sample size invites false precision:
the difference between 71% and 76% macro-F1 on 120 cases is not a result. So
every scalar reported here carries a bootstrap interval, and comparisons
between systems are done as a paired bootstrap on the difference rather than by
eyeballing two point estimates.

The escalation metrics are deliberately not symmetric. Accuracy on a
53%-positive problem is close to meaningless, and F1 treats both errors alike
when the whole design premise is that they are not alike. What matters
operationally is:

  missed escalations   auto-replied to a case that needed a human (expensive)
  needless escalations sent a human a case a bot could close (cheap)
  automation rate      share of traffic the bot handles at all (the business case)
  expected cost        the two error types combined at their stated ratio
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score

from src.taxonomy import COST_MISSED_ESCALATION, COST_NEEDLESS_ESCALATION, INTENT_NAMES

RNG_SEED = 20260910


def bootstrap_ci(
    values: Sequence,
    stat: Callable[[Sequence], float],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = RNG_SEED,
) -> tuple[float, float, float]:
    """Percentile bootstrap. Returns (point, lo, hi)."""
    rng = np.random.default_rng(seed)
    values = list(values)
    n = len(values)
    point = stat(values)
    if n == 0:
        return (float("nan"),) * 3
    idx = rng.integers(0, n, size=(n_boot, n))
    stats = np.array([stat([values[i] for i in row]) for row in idx])
    lo, hi = np.percentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(point), float(lo), float(hi)


def paired_bootstrap_diff(
    pairs: Sequence[tuple],
    stat: Callable[[Sequence], float],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = RNG_SEED,
) -> dict:
    """Bootstrap the difference between two systems on the SAME cases.

    Paired, because the systems are scored on identical examples and the
    case-to-case variance is shared. An unpaired comparison here would widen
    the interval for no reason and hide real differences.

    `pairs` is a sequence of (a_item, b_item); `stat` maps a list of items to a
    scalar. Returns the difference (a - b) with an interval and the fraction of
    resamples in which a beats b.
    """
    rng = np.random.default_rng(seed)
    pairs = list(pairs)
    n = len(pairs)
    a_point = stat([p[0] for p in pairs])
    b_point = stat([p[1] for p in pairs])
    idx = rng.integers(0, n, size=(n_boot, n))
    diffs = np.array([
        stat([pairs[i][0] for i in row]) - stat([pairs[i][1] for i in row])
        for row in idx
    ])
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "a": round(a_point, 4),
        "b": round(b_point, 4),
        "diff": round(a_point - b_point, 4),
        "ci_lo": round(float(lo), 4),
        "ci_hi": round(float(hi), 4),
        "p_a_better": round(float((diffs > 0).mean()), 4),
    }


# --------------------------------------------------------------------------
# intent
# --------------------------------------------------------------------------
def macro_f1(pairs: Sequence[tuple[str, str]]) -> float:
    """pairs of (gold, pred). Labels fixed to the full taxonomy so that a
    system which never predicts a class is penalised for it rather than having
    the class quietly dropped from the average."""
    if not pairs:
        return float("nan")
    gold = [p[0] for p in pairs]
    pred = [p[1] for p in pairs]
    return float(f1_score(gold, pred, labels=list(INTENT_NAMES),
                          average="macro", zero_division=0))


def accuracy(pairs: Sequence[tuple[str, str]]) -> float:
    if not pairs:
        return float("nan")
    return float(np.mean([g == p for g, p in pairs]))


def per_class_report(pairs: Sequence[tuple[str, str]]) -> dict:
    gold = [p[0] for p in pairs]
    pred = [p[1] for p in pairs]
    support = Counter(gold)
    out = {}
    for label in INTENT_NAMES:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if g != label and p == label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[label] = {
            "support": support.get(label, 0),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            # Flagged so the report never quotes a per-class F1 from 4 examples
            # without saying so.
            "unreliable_small_support": support.get(label, 0) < 10,
        }
    return out


def confusion(pairs: Sequence[tuple[str, str]]) -> dict:
    gold = [p[0] for p in pairs]
    pred = [p[1] for p in pairs]
    m = confusion_matrix(gold, pred, labels=list(INTENT_NAMES))
    return {"labels": list(INTENT_NAMES), "matrix": m.tolist()}


def top_confusions(pairs: Sequence[tuple[str, str]], n: int = 8) -> list[dict]:
    c = Counter((g, p) for g, p in pairs if g != p)
    return [{"gold": g, "pred": p, "count": n_}
            for (g, p), n_ in c.most_common(n)]


# --------------------------------------------------------------------------
# escalation
# --------------------------------------------------------------------------
@dataclass
class EscalationOutcome:
    gold: bool
    pred: bool


def escalation_stats(items: Sequence[EscalationOutcome]) -> dict:
    tp = sum(1 for i in items if i.gold and i.pred)
    fp = sum(1 for i in items if not i.gold and i.pred)
    fn = sum(1 for i in items if i.gold and not i.pred)
    tn = sum(1 for i in items if not i.gold and not i.pred)
    n = max(1, len(items))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "n": len(items),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        # The two numbers that actually matter operationally.
        "missed_escalation_rate": round(fn / n, 4),
        "needless_escalation_rate": round(fp / n, 4),
        # Share of traffic the bot answers without a human.
        "automation_rate": round((tn + fn) / n, 4),
        # Of what the bot auto-answers, how much should have gone to a human.
        "auto_handled_error_rate": round(fn / max(1, tn + fn), 4),
        "expected_cost_per_100": round(
            100 * (fn * COST_MISSED_ESCALATION + fp * COST_NEEDLESS_ESCALATION) / n, 2),
    }


def escalation_cost(items: Sequence[EscalationOutcome]) -> float:
    """Scalar for bootstrapping: cost per case, lower is better."""
    if not items:
        return float("nan")
    fn = sum(1 for i in items if i.gold and not i.pred)
    fp = sum(1 for i in items if not i.gold and i.pred)
    return (fn * COST_MISSED_ESCALATION + fp * COST_NEEDLESS_ESCALATION) / len(items)


def escalation_recall(items: Sequence[EscalationOutcome]) -> float:
    tp = sum(1 for i in items if i.gold and i.pred)
    fn = sum(1 for i in items if i.gold and not i.pred)
    return tp / (tp + fn) if tp + fn else float("nan")


# --------------------------------------------------------------------------
# agreement (used for judge validation and for label reliability)
# --------------------------------------------------------------------------
def cohen_kappa(a: Sequence, b: Sequence) -> float:
    """Unweighted kappa for nominal labels."""
    a, b = list(a), list(b)
    if not a:
        return float("nan")
    labels = sorted(set(a) | set(b))
    idx = {l: i for i, l in enumerate(labels)}
    n = len(a)
    m = np.zeros((len(labels), len(labels)))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    po = np.trace(m) / n
    pe = float((m.sum(axis=0) / n) @ (m.sum(axis=1) / n))
    if pe == 1:
        return float("nan")
    return float((po - pe) / (1 - pe))


def quadratic_weighted_kappa(a: Sequence[int], b: Sequence[int],
                             min_rating: int = 1, max_rating: int = 5) -> float:
    """For ordinal scores (the judge's 1-5 rubric dimensions).

    Unweighted kappa treats a 4-vs-5 disagreement as identical to 1-vs-5, which
    badly understates agreement on an ordinal scale and would make the judge
    look worse than it is.
    """
    a, b = list(a), list(b)
    if not a:
        return float("nan")
    n_r = max_rating - min_rating + 1
    O = np.zeros((n_r, n_r))
    for x, y in zip(a, b):
        O[int(x) - min_rating, int(y) - min_rating] += 1
    W = np.zeros((n_r, n_r))
    for i in range(n_r):
        for j in range(n_r):
            W[i, j] = ((i - j) ** 2) / ((n_r - 1) ** 2)
    ha = np.bincount([int(x) - min_rating for x in a], minlength=n_r)
    hb = np.bincount([int(x) - min_rating for x in b], minlength=n_r)
    E = np.outer(ha, hb).astype(float)
    E = E * (O.sum() / E.sum())
    denom = (W * E).sum()
    if denom == 0:
        return float("nan")
    return float(1 - (W * O).sum() / denom)


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    from scipy.stats import spearmanr
    if len(set(a)) < 2 or len(set(b)) < 2:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def dump(obj, path) -> None:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
