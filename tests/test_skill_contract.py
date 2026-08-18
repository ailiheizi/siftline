from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SKILL = _REPO / "skills" / "siftline-research" / "SKILL.md"
_REFERENCE = _REPO / "skills" / "siftline-research" / "references" / "evidence-integrity.md"

# Phrases that re-introduce the visible-skeleton / marker ceremony that made large
# single-turn runs fail. The Skill and its references must never contain them.
FORBIDDEN_CEREMONY_PHRASES = [
    "write skeleton block NOW",
    "Output a visible block",
    "skeleton refresh and the ledger read are the only mandated interim outputs",
    "next assistant-visible event",
    "zero-tool barrier",
    "refresh the skeleton with the exact case-sensitive",
    "refresh the literal-field skeleton block",
    "record a visible `issued_invocations=N` line immediately before",
    "skeleton must already exist",
]


def _skill_text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _reference_text() -> str:
    return _REFERENCE.read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", FORBIDDEN_CEREMONY_PHRASES)
def test_no_ceremony_contract_in_skill_or_reference(phrase: str) -> None:
    """The visible skeleton / visible issued_invocations ceremony must be gone."""
    assert phrase not in _skill_text()
    assert phrase not in _reference_text()


def test_explicit_user_budget_never_scaled_rule_exists() -> None:
    """An explicit user-given external budget is the shared cap and is never scaled."""
    text = _skill_text() + "\n" + _reference_text()
    assert "never scaled" in text
    assert "explicit user budget" in text
    assert "never rescale" in text


def test_freeze_formula_rule_exists() -> None:
    """Freeze = ceil(0.75 * B): B=8 -> 6, B=12 -> 9."""
    text = _skill_text() + "\n" + _reference_text()
    assert "ceil(0.75" in text
    assert "attempt 6" in text
    assert "attempt 9" in text


def test_no_mandated_interim_outputs_rule_exists() -> None:
    """After the freeze there are no mandated interim outputs (no skeleton, no ledger)."""
    text = _skill_text() + "\n" + _reference_text()
    assert "no mandated interim outputs" in text


def test_time_convergence_soft_stop_rule_exists() -> None:
    """Discovery soft stop = earliest of freeze attempt, 18 total tools, ~12 min."""
    text = _skill_text() + "\n" + _reference_text()
    assert "soft stop" in text
    assert "18 total tool" in text
    assert "32" in text
    assert "20 minutes" in text


def test_lint_never_preempts_delivery_rule_exists() -> None:
    """Lint runs only after the final answer is drafted; it never delays delivery."""
    text = _skill_text() + "\n" + _reference_text()
    assert "at most one" in text
    assert "lint" in text.lower()
    assert "manually-verified" in text
