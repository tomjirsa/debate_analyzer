"""Tests for Ollama LLM backend (mocked; no running Ollama required)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip(
    "langchain_ollama", reason="langchain-ollama not installed (extras llm)"
)


def test_ollama_backend_generate_returns_content():
    """get_ollama_backend().generate returns the mocked invoke content."""
    mock_invoke_return = MagicMock()
    mock_invoke_return.content = '{"main_topics": [{"id": "t1", "title": "Test"}]}'
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_invoke_return

    with (
        patch("langchain_ollama.ChatOllama", return_value=mock_llm),
        patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434"}, clear=False),
    ):
        from debate_analyzer.analysis.backend_ollama import get_ollama_backend

        backend = get_ollama_backend(base_url="http://localhost:11434", model="test")
        out = backend.generate("List topics", max_tokens=512)
    assert "main_topics" in out
    mock_llm.invoke.assert_called_once()


def test_ollama_backend_generate_batch_order():
    """generate_batch returns one response per prompt in order."""
    mock_invoke_return = MagicMock()
    mock_invoke_return.content = '{"summary": "ok"}'
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_invoke_return

    with (
        patch("langchain_ollama.ChatOllama", return_value=mock_llm),
        patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434"}, clear=False),
    ):
        from debate_analyzer.analysis.backend_ollama import get_ollama_backend

        backend = get_ollama_backend(base_url="http://localhost:11434", model="test")
        prompts = ["First", "Second", "Third"]
        results = backend.generate_batch(prompts, max_tokens=100)
    assert len(results) == 3
    assert all("summary" in r for r in results)
    assert mock_llm.invoke.call_count == 3


def test_llm_job_get_backend_returns_ollama_when_not_mock():
    """_get_backend() returns Ollama backend generate_batch when MOCK_LLM is not set."""
    from debate_analyzer.analysis.backend import MockLLMBackend

    mock_backend = MockLLMBackend()
    with (
        patch.dict(os.environ, {"MOCK_LLM": ""}, clear=False),
        patch(
            "debate_analyzer.analysis.backend_ollama.get_ollama_backend",
            return_value=mock_backend,
        ),
    ):
        from debate_analyzer.batch import llm_analysis_job

        generate_batch = llm_analysis_job._get_backend()
    out = generate_batch(["hello"], max_tokens=10)
    assert len(out) == 1
    assert mock_backend.call_count == 1
