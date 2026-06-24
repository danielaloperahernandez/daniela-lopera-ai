"""Prompts must load, expose a version, and render their placeholders."""

from __future__ import annotations

import pytest

from ai_core import load_prompt


def test_rag_prompt_renders() -> None:
    prompt = load_prompt("rag_answer")
    assert prompt.version
    system, user = prompt.render(context="CTX", question="Q?")
    assert "CTX" in user
    assert "Q?" in user
    assert "ONLY" in system  # the grounding instruction is present


def test_unknown_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")
