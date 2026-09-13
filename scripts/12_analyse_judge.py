"""De-anonymise the judge's scores and check whether the judge can be trusted.

Order matters here. The judge's scores are only evidence if the judge agrees
with a person, so this script reports agreement FIRST and system rankings
second. A reply-quality leaderboard produced by an unvalidated judge is
decoration.

Four things get measured:

  1. JUDGE vs HUMAN. 30 cases x 4 replies were hand-scored blind, and the hand
     scores were written to disk BEFORE the judge ran. Quadratic-weighted kappa
     per dimension (the scale is ordinal, so unweighted kappa would understate
     agreement), plus Spearman, plus agreement on the binary send_as_is call
     and on which candidate is best.

  2. SELF-PREFERENCE. `reference` is a real human AmazonHelp reply, judged
     blind in the same batch. If the judge ranks machine text above the human's
     systematically, that gap is the bias.

  3. POSITION BIAS. Candidates were shuffled per case. Mean score by slot
     position shows whether the judge favours whatever it reads first.

  4. A CONFOUND I COULD NOT REMOVE. Real Amazon replies frequently contain the
     token "<link>" (URLs were replaced during cleaning); the agent was
     instructed never to emit links. So "<link>" is a partial tell for system
     identity, visible to both the judge and the human scorer. The rate is
     reported per system so the reader can discount accordingly.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.evaluation import metrics as M
from src.evaluation.judge import DIMENSIONS, parse_scores

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
RESULTS = REPO / "results"


def load_judge() -> dict[str, dict]:
    """golden_id -> parsed judge output, read straight from the committed cache.

    Completions are looked up by recomputing the exact cache key from the task,
    not by matching text. An earlier version matched on a prompt prefix and
    silently linked only 34 of 120 cases, quietly shrinking every downstream
    sample; recomputing the key makes that class of bug impossible, because a
    mismatch raises instead of dropping a row.

    Reading from the cache rather than from per-run scratch files is what lets
    a clean checkout reproduce these numbers -- the cache is committed, the
    scratch is not.
    """
    from src.evaluation.judge import BlindedCase, judge_user
    from src.llm import _Cache, DEFAULT_CACHE, LLM

    tasks = [json.loads(l) for l in (RUNS / "judge_task.jsonl").open(encoding="utf-8")]
    system = (RUNS / "judge_system.txt").read_text(encoding="utf-8")
    cache = _Cache(DEFAULT_CACHE)

    out, missing, unparsed = {}, [], 0
    for t in tasks:
        case = BlindedCase(golden_id=t["golden_id"], message=t["message"],
                           letters=t["candidates"], mapping={}, order=list(t["candidates"]))
        payload = {
            "model": "claude-sonnet-4-5",
            "system": system,
            "messages": [{"role": "user", "content": judge_user(case)}],
            "max_tokens": 700,
            "temperature": 0.0,
            "stop_sequences": None,
        }
        hit = cache.get(LLM._key(payload))
        if hit is None:
            missing.append(t["golden_id"])
            continue
        try:
            out[t["golden_id"]] = parse_scores(hit["text"])
        except Exception:
            unparsed += 1
    if missing or unparsed:
        print(f"!! judge cache misses={len(missing)} unparsed={unparsed}")
        if missing:
            raise SystemExit(
                f"{len(missing)} judge completions are not in the cache "
                f"(first: {missing[:3]}). Run: python scripts/11_run_judge.py --record")
    return out


def main() -> None:
    key = {json.loads(l)["golden_id"]: json.loads(l)
           for l in (RUNS / "judge_key.jsonl").open(encoding="utf-8")}
    judge = load_judge()
    human = {json.loads(l)["golden_id"]: json.loads(l)
             for l in (RUNS / "human_scores.jsonl").open(encoding="utf-8")}
    tasks = {json.loads(l)["golden_id"]: json.loads(l)
             for l in (RUNS / "judge_task.jsonl").open(encoding="utf-8")}
    print(f"judged {len(judge)}/{len(key)} cases | hand-scored {len(human)} cases")

    out: dict = {}

    # ---- 1. judge vs human ------------------------------------------------
    paired = defaultdict(lambda: ([], []))
    send_h, send_j, best_match, n_best = [], [], 0, 0
    for gid, h in human.items():
        j = judge.get(gid)
        if not j:
            continue
        for letter, hs in h["scores"].items():
            js = j["scores"].get(letter)
            if not js:
                continue
            for d in DIMENSIONS:
                paired[d][0].append(hs[d])
                paired[d][1].append(js[d])
            send_h.append(bool(hs["send_as_is"]))
            send_j.append(bool(js["send_as_is"]))
        if j.get("best"):
            n_best += 1
            best_match += int(j["best"] == h["best"])

    agreement = {}
    for d in DIMENSIONS:
        a, b = paired[d]
        agreement[d] = {
            "n": len(a),
            "qwk": round(M.quadratic_weighted_kappa(a, b), 4),
            "spearman": round(M.spearman(a, b), 4),
            "mean_human": round(float(np.mean(a)), 3),
            "mean_judge": round(float(np.mean(b)), 3),
            "judge_minus_human": round(float(np.mean(b) - np.mean(a)), 3),
            "exact_match": round(float(np.mean([x == y for x, y in zip(a, b)])), 3),
            "within_one": round(float(np.mean([abs(x - y) <= 1 for x, y in zip(a, b)])), 3),
        }
    allh = [v for d in DIMENSIONS for v in paired[d][0]]
    allj = [v for d in DIMENSIONS for v in paired[d][1]]
    agreement["ALL_DIMENSIONS"] = {
        "n": len(allh),
        "qwk": round(M.quadratic_weighted_kappa(allh, allj), 4),
        "spearman": round(M.spearman(allh, allj), 4),
        "within_one": round(float(np.mean([abs(x - y) <= 1 for x, y in zip(allh, allj)])), 3),
    }
    agreement["send_as_is"] = {
        "n": len(send_h),
        "cohen_kappa": round(M.cohen_kappa(send_h, send_j), 4),
        "raw_agreement": round(float(np.mean([x == y for x, y in zip(send_h, send_j)])), 3),
        "human_yes_rate": round(float(np.mean(send_h)), 3),
        "judge_yes_rate": round(float(np.mean(send_j)), 3),
    }
    agreement["best_pick"] = {
        "n": n_best,
        "agreement": round(best_match / max(1, n_best), 3),
        "chance": 0.25,
    }
    out["judge_vs_human"] = agreement

    # ---- 2. per-system scores --------------------------------------------
    by_system = defaultdict(lambda: defaultdict(list))
    send_by_system = defaultdict(list)
    best_counts = defaultdict(int)
    for gid, j in judge.items():
        mapping = key[gid]["mapping"]
        for letter, s in j["scores"].items():
            sysname = mapping.get(letter)
            if not sysname:
                continue
            for d in DIMENSIONS:
                by_system[sysname][d].append(s[d])
            by_system[sysname]["overall"].append(float(np.mean([s[d] for d in DIMENSIONS])))
            send_by_system[sysname].append(bool(s["send_as_is"]))
        if j.get("best") and j["best"] in mapping:
            best_counts[mapping[j["best"]]] += 1

    systems = {}
    for sysname, dims in by_system.items():
        row = {}
        for d in list(DIMENSIONS) + ["overall"]:
            vals = dims[d]
            pt, lo, hi = M.bootstrap_ci(vals, lambda v: float(np.mean(v)))
            row[d] = {"mean": round(pt, 3), "ci": [round(lo, 3), round(hi, 3)]}
        row["send_as_is_rate"] = round(float(np.mean(send_by_system[sysname])), 3)
        row["judge_picked_best"] = best_counts.get(sysname, 0)
        row["n"] = len(dims["overall"])
        systems[sysname] = row
    out["systems"] = systems

    # paired comparisons on the same cases
    comparisons = {}
    gids = sorted(judge)
    for other in ("simple", "trivial", "reference"):
        pairs = []
        for gid in gids:
            mapping = key[gid]["mapping"]
            inv = {v: k for k, v in mapping.items()}
            ja, jb = judge[gid]["scores"].get(inv.get("agent")), judge[gid]["scores"].get(inv.get(other))
            if not ja or not jb:
                continue
            pairs.append((float(np.mean([ja[d] for d in DIMENSIONS])),
                          float(np.mean([jb[d] for d in DIMENSIONS]))))
        comparisons[f"agent_vs_{other}"] = M.paired_bootstrap_diff(
            pairs, lambda v: float(np.mean(v)))
    out["paired_comparisons"] = comparisons

    # ---- 3. position bias -------------------------------------------------
    pos = defaultdict(list)
    for gid, j in judge.items():
        letters = sorted(j["scores"])
        for i, letter in enumerate(letters):
            s = j["scores"][letter]
            pos[i].append(float(np.mean([s[d] for d in DIMENSIONS])))
    out["position_bias"] = {
        f"slot_{i}": {"mean": round(float(np.mean(v)), 3), "n": len(v)}
        for i, v in sorted(pos.items())
    }

    # ---- 4. the <link> confound ------------------------------------------
    link_rate = defaultdict(list)
    for gid, t in tasks.items():
        mapping = key[gid]["mapping"]
        for letter, text in t["candidates"].items():
            sysname = mapping.get(letter)
            if sysname:
                link_rate[sysname].append("<link>" in text)
    out["link_token_confound"] = {
        s: round(float(np.mean(v)), 3) for s, v in link_rate.items()
    }

    M.dump(out, RESULTS / "judge_analysis.json")

    # ---- console ----------------------------------------------------------
    print("\n=== 1. DOES THE JUDGE AGREE WITH A HUMAN? (30 cases x 4 replies) ===")
    print(f"{'dimension':<14}{'QWK':>8}{'rho':>8}{'within1':>9}{'human':>8}{'judge':>8}{'delta':>8}")
    for d in DIMENSIONS:
        a = agreement[d]
        print(f"{d:<14}{a['qwk']:>8.3f}{a['spearman']:>8.3f}{a['within_one']:>9.2f}"
              f"{a['mean_human']:>8.2f}{a['mean_judge']:>8.2f}{a['judge_minus_human']:>+8.2f}")
    al = agreement["ALL_DIMENSIONS"]
    print(f"{'ALL':<14}{al['qwk']:>8.3f}{al['spearman']:>8.3f}{al['within_one']:>9.2f}")
    s = agreement["send_as_is"]
    print(f"\nsend-as-is:  kappa={s['cohen_kappa']:.3f}  raw={s['raw_agreement']:.2f}  "
          f"(human says yes {s['human_yes_rate']:.0%}, judge {s['judge_yes_rate']:.0%})")
    b = agreement["best_pick"]
    print(f"best-pick agreement: {b['agreement']:.2f} (chance {b['chance']:.2f}, n={b['n']})")

    print("\n=== 2. REPLY QUALITY BY SYSTEM (judge, blind, n=120) ===")
    print(f"{'system':<12}{'overall':>9}{'ground':>8}{'relev':>8}{'action':>8}{'tone':>7}{'safe':>7}"
          f"{'send%':>8}{'best':>6}")
    for sysname in ("agent", "reference", "simple", "trivial"):
        if sysname not in systems:
            continue
        r = systems[sysname]
        print(f"{sysname:<12}{r['overall']['mean']:>9.2f}{r['grounded']['mean']:>8.2f}"
              f"{r['relevant']['mean']:>8.2f}{r['actionable']['mean']:>8.2f}"
              f"{r['tone']['mean']:>7.2f}{r['safe']['mean']:>7.2f}"
              f"{r['send_as_is_rate']:>8.0%}{r['judge_picked_best']:>6}")

    print("\n=== 3. AGENT vs OTHERS (paired bootstrap on overall score) ===")
    for k, v in comparisons.items():
        print(f"  {k:<22} diff={v['diff']:+.3f}  95% CI [{v['ci_lo']:+.3f},{v['ci_hi']:+.3f}]  "
              f"P(agent better)={v['p_a_better']:.2f}")

    print("\n=== 4. BIAS CHECKS ===")
    print("  position:", {k: v["mean"] for k, v in out["position_bias"].items()})
    print("  '<link>' token rate by system:", out["link_token_confound"])
    print(f"\nwrote {RESULTS/'judge_analysis.json'}")


if __name__ == "__main__":
    main()
