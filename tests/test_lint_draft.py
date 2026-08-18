from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_LINT_PATH = _REPO / "skills" / "siftline-research" / "scripts" / "lint_draft.py"


@pytest.fixture(scope="module")
def lint_module():
    spec = importlib.util.spec_from_file_location("lint_draft_v422", _LINT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lint_self_test_passes(lint_module) -> None:
    """The linter's own self-test must stay green (regression gate)."""
    assert lint_module.self_test() == 0


def test_lint_margin_exceeded(lint_module) -> None:
    text = lint_module.AUDIT_DRAFT_VALID
    total = lint_module._doc_length(text)
    errors = lint_module.lint(text, max_chars=total, profile="audit")
    codes = {c for c, _, _ in errors}
    assert lint_module.CODE_MARGIN in codes


def test_lint_margin_within_headroom(lint_module) -> None:
    text = lint_module.AUDIT_DRAFT_VALID
    total = lint_module._doc_length(text)
    errors = lint_module.lint(text, max_chars=total * 2, profile="audit")
    codes = {c for c, _, _ in errors}
    assert lint_module.CODE_MARGIN not in codes


def test_lint_margin_requires_max_chars(lint_module) -> None:
    assert lint_module._margin_contract_error("audit", None, 8) is not None
    assert lint_module._margin_contract_error("audit", 500, 8) is None


def test_lint_code_verified_requires_surface(lint_module) -> None:
    errors = lint_module.lint("The seed loop is code-verified.")
    codes = {c for c, _, _ in errors}
    assert lint_module.CODE_VERIFIED in codes

    clean = lint_module.lint("The loop is code-verified: I ran npm test -- src/loop.test.ts.")
    assert not clean


def test_lint_code_verified_negation_exempt(lint_module) -> None:
    text = "The build passed but playability stays documented, not code-verified."
    assert not lint_module.lint(text)
