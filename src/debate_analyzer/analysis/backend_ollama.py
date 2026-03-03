"""Ollama-backed LLM analysis via LangChain over HTTP (e.g. localhost)."""

from __future__ import annotations

import os
import sys

from debate_analyzer.analysis.backend import LLMBackend


def get_ollama_backend(
    base_url: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> LLMBackend:
    """
    Return an LLMBackend using Ollama via LangChain (HTTP; localhost or OLLAMA_HOST).

    Requires langchain-ollama. Used when LLM_BACKEND=ollama. Ollama must be running
    (e.g. on the same instance); pull the model first (e.g. ollama pull qwen2.5:7b).

    Args:
        base_url: Ollama API base URL. Default: OLLAMA_HOST or http://localhost:11434.
        model: Ollama model name. Default: OLLAMA_MODEL or LLM_MODEL_ID or qwen2.5:7b.
        system_prompt: Optional system message (e.g. response language). Prepended to
            each request when set.

    Returns:
        Object with generate() and generate_batch() (same order as input).

    Raises:
        ImportError: If langchain_ollama is not installed.
        Exception: If Ollama is unreachable (connection refused, timeout).
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_ollama import ChatOllama
    except ImportError as e:
        raise ImportError(
            "langchain-ollama is required for the Ollama backend. "
            "Install with: poetry install --extras llm"
        ) from e

    base_url = (
        base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    )
    model = (
        model
        or os.environ.get("OLLAMA_MODEL", "").strip()
        or os.environ.get("LLM_MODEL_ID", "qwen2.5:7b").strip()
    )

    raw_ctx = os.environ.get("LLM_MAX_MODEL_LEN", "8192").strip()
    try:
        num_ctx = max(1024, int(raw_ctx))
    except ValueError:
        num_ctx = 8192

    print(
        f"[LLM] Using Ollama backend: {base_url} model={model} num_ctx={num_ctx}",
        file=sys.stderr,
    )

    # Do not pass num_predict: ollama expects it in options={}, not top-level.
    # Rely on model default max output length (or OLLAMA_NUM_PREDICT if needed).
    # num_ctx sets context window size (avoids "truncating input prompt" when >2048).
    llm = ChatOllama(
        base_url=base_url,
        model=model,
        temperature=0.2,
        num_ctx=num_ctx,
    )

    class OllamaBackend:
        def generate(self, prompt: str, max_tokens: int = 2048) -> str:
            bound = llm
            if system_prompt:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt),
                ]
            else:
                messages = [HumanMessage(content=prompt)]
            response = bound.invoke(messages)
            content = getattr(response, "content", "")
            return (content or "").strip()

        def generate_batch(
            self, prompts: list[str], max_tokens: int = 2048
        ) -> list[str]:
            """Sequential calls to Ollama (no HTTP batch API)."""
            return [self.generate(p, max_tokens) for p in prompts]

    return OllamaBackend()
