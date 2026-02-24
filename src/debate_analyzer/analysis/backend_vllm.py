"""vLLM-backed inference for LLM analysis. Optional: install vllm in the LLM image."""

from __future__ import annotations

import os

from debate_analyzer.analysis.backend import LLMBackend


def get_vllm_backend(
    model_id: str | None = None,
    max_model_len: int = 32768,
) -> LLMBackend:
    """
    Return an LLMBackend that uses vLLM for inference.

    Requires vllm to be installed. Typically used in the dedicated LLM Docker image.

    Args:
        model_id: Hugging Face model id (e.g. Qwen/Qwen2-7B-Instruct).
            Default from env LLM_MODEL_ID.
        max_model_len: Max context length. Default 32k; requires 32 GB GPU (e.g. g4dn.2xlarge).

    Returns:
        Object implementing generate(prompt, max_tokens) -> str.

    Raises:
        ImportError: If vllm is not installed.
    """
    try:
        from vllm import LLM
    except ImportError as e:
        raise ImportError(
            "vLLM is not installed. Install with: pip install vllm. "
            "Use the dedicated LLM Docker image for Batch jobs."
        ) from e

    model_id = model_id or os.environ.get("LLM_MODEL_ID", "Qwen/Qwen2-7B-Instruct")
    # enforce_eager=True avoids torch.compile/Triton JIT, so no C compiler or Python.h needed in the container
    llm = LLM(model=model_id, max_model_len=max_model_len, enforce_eager=True)

    class VLLMBackend:
        def generate(self, prompt: str, max_tokens: int = 2048) -> str:
            from vllm import SamplingParams

            sampling_params = SamplingParams(max_tokens=max_tokens, temperature=0.2)
            outputs = llm.generate([prompt], sampling_params)
            if not outputs or not outputs[0].outputs:
                return ""
            return outputs[0].outputs[0].text or ""

    return VLLMBackend()
