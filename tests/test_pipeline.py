"""Sanity checks on the committed artifacts.

These are not unit tests of behaviour; they are guards against the specific
ways this kind of project silently produces wrong numbers. Each one corresponds
to a mistake that was actually made and caught during the build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.taxonomy import ESCALATION_RULE_IDS, INTENT_NAMES  # noqa: E402


@pytest.fixture(scope="module")
def golden():
    return [json.loads(l) for l in (REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8")]


def test_golden_set_size_and_strata(golden):
    assert len(golden) == 200
    assert sum(g["stratum"] == "A_random" for g in golden) == 120
    assert sum(g["stratum"] == "B_targeted" for g in golden) == 80


def test_every_label_is_in_the_taxonomy(golden):
    for g in golden:
        assert g["label_intent"] in INTENT_NAMES, g["golden_id"]
        for r in g["label_rules"]:
            assert r in ESCALATION_RULE_IDS, (g["golden_id"], r)


def test_every_escalation_names_a_rule(golden):
    """An escalation with no rule attached is an intuition, and intuitions are
    not reproducible by a second annotator. This caught 13 cases at build time."""
    for g in golden:
        if g["label_escalate"]:
            assert g["label_rules"], f"{g['golden_id']} escalates with no rule"
        else:
            assert not g["label_rules"], f"{g['golden_id']} has rules but does not escalate"


def test_golden_ids_unique(golden):
    ids = [g["golden_id"] for g in golden]
    assert len(set(ids)) == len(ids)


def test_agent_never_saw_the_labels():
    """The prompt builder must not leak anything from the golden record.

    Regression guard for the whole evaluation: if the agent's input ever
    includes the reference reply or the label, every number is meaningless.
    """
    from src.agent import prompts

    g = json.loads((REPO / "data/golden/golden_set.jsonl").open(encoding="utf-8").readline())
    user = prompts.triage_user(g["customer_message"])
    for leak in (g["reference_reply"], g["label_intent"], g["label_note"]):
        if leak and len(leak) > 12:
            assert leak not in user


def test_cache_is_content_addressed():
    """Changing a prompt by one character must miss the cache, not silently
    serve a stale completion."""
    from src.llm import LLM

    base = {"model": "m", "system": "s", "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 10, "temperature": 0.0, "stop_sequences": None}
    other = {**base, "messages": [{"role": "user", "content": "hellp"}]}
    assert LLM._key(base) != LLM._key(other)
    assert LLM._key(base) == LLM._key(dict(base))


def test_offline_mode_fails_loudly_on_a_miss(tmp_path):
    """A reproduction run must not be able to quietly skip an uncached call."""
    from src.llm import LLM

    llm = LLM(model="m", cache_path=tmp_path / "empty.sqlite", offline=True)
    with pytest.raises(RuntimeError, match="cache miss"):
        llm.complete(prompt="not cached", system=None)


def test_language_filter_rejects_latin_script_non_english():
    """The first version passed French/Spanish/German because they are ~97%
    ASCII. That leaked ~11% of the corpus past the filter."""
    from src.data.langid import is_english

    assert is_english("Where is my order? It was supposed to arrive yesterday and I paid extra")
    assert not is_english("Bonjour, je n'ai pas encore recu mon colis, pouvez-vous verifier")
    assert not is_english("Hola, mi pedido no ha llegado todavia y necesito saber que pasa")
    assert not is_english("Ich habe meine Bestellung nicht erhalten und brauche jetzt Hilfe")


def test_metrics_penalise_unpredicted_classes():
    """macro-F1 must be computed over the full taxonomy, so a system that never
    predicts a class is penalised rather than having it dropped."""
    from src.evaluation.metrics import macro_f1

    pairs = [("delivery_delayed", "delivery_delayed")] * 50
    assert macro_f1(pairs) < 0.2  # one class right, nine never predicted


def test_escalation_cost_is_asymmetric():
    from src.evaluation.metrics import EscalationOutcome, escalation_cost

    missed = [EscalationOutcome(gold=True, pred=False)]
    needless = [EscalationOutcome(gold=False, pred=True)]
    assert escalation_cost(missed) > escalation_cost(needless)


def test_headline_numbers_match_the_report():
    """Guards against the report drifting away from results/ after a re-run."""
    res = json.loads((REPO / "results/judge_analysis.json").read_text())
    assert res["judge_vs_human"]["ALL_DIMENSIONS"]["qwk"] > 0.7
    assert res["systems"]["agent"]["overall"]["mean"] > res["systems"]["reference"]["overall"]["mean"]

    interro = json.loads((REPO / "results/result_interrogation.json").read_text())
    judge_gap = interro["H2_self_preference"]["judge_gap_on_hand_scored_subset"]["diff"]
    human_gap = interro["H2_self_preference"]["human_gap_on_same_subset"]["diff"]
    # The central claim of the "what is misleading" section: the judge inflates
    # the agent's advantage over real human replies by a large margin.
    assert judge_gap > human_gap * 2
