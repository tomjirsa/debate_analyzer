"""Ollama-backed LLM analysis via LangChain over HTTP (e.g. localhost)."""

from __future__ import annotations

import os
import sys
from typing import Any

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

    raw_temp = os.environ.get("LLM_TEMPERATURE", "0.0").strip()
    try:
        temperature = float(raw_temp)
        temperature = max(0.0, min(2.0, temperature))
    except ValueError:
        temperature = 0.0

    print(
        f"[LLM] Using Ollama backend: {base_url} model={model} num_ctx={num_ctx} "
        f"temperature={temperature}",
        file=sys.stderr,
    )

    # num_ctx sets context window size (avoids "truncating input prompt" when >2048).
    # Per-call max output tokens go in ``options`` (``num_predict``). Using
    # ``llm.bind(num_predict=...)`` breaks with ollama>=0.6: Client.chat() no longer
    # accepts top-level generation kwargs; they must be under ``options``.
    llm = ChatOllama(
        base_url=base_url,
        model=model,
        temperature=temperature,
        num_ctx=num_ctx,
    )

    class OllamaBackend:
        def _invoke_kwargs(self, max_tokens: int, *, json_mode: bool) -> dict[str, Any]:
            out: dict[str, Any] = {
                "options": {
                    "num_ctx": num_ctx,
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            }
            if json_mode:
                out["format"] = "json"
            return out

        def generate(
            self, prompt: str, max_tokens: int = 2048, *, json_mode: bool = False
        ) -> str:
            """Invoke Ollama with ``num_predict=max_tokens`` in options; optional JSON mode."""
            kwargs = self._invoke_kwargs(max_tokens, json_mode=json_mode)
            if system_prompt:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt),
                ]
            else:
                messages = [HumanMessage(content=prompt)]
            response = llm.invoke(messages, **kwargs)
            content = getattr(response, "content", "")
            return (content or "").strip()

        def generate_batch(
            self,
            prompts: list[str],
            max_tokens: int = 2048,
            *,
            json_mode: bool = False,
        ) -> list[str]:
            """Sequential calls to Ollama (no HTTP batch API).

            Args:
                prompts: User prompts in order.
                max_tokens: Maps to Ollama ``num_predict``.
                json_mode: When True, sets Ollama ``format="json"`` for each call.
            """
            return [self.generate(p, max_tokens, json_mode=json_mode) for p in prompts]

    return OllamaBackend()
