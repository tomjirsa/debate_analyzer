"""vLLM-backed inference for LLM analysis. Optional: install vllm in the LLM image."""

from __future__ import annotations

import os

from debate_analyzer.analysis.backend import LLMBackend


def get_vllm_backend(
    model_id: str | None = None,
    max_model_len: int | None = None,
    gpu_memory_utilization: float | None = None,
) -> LLMBackend:
    """
    Return an LLMBackend that uses vLLM for inference.

    Requires vllm to be installed. Typically used in the dedicated LLM Docker image.

    Args:
        model_id: Hugging Face model id (e.g. Qwen/Qwen2-7B-Instruct).
            Default from env LLM_MODEL_ID.
        max_model_len: Max context length. Default from env LLM_MAX_MODEL_LEN (8192).
            For 16 GB T4 (g4dn.2xlarge) use 8192 or 4096. For 32k context use a 24 GB+
            GPU (e.g. g5.xlarge).
        gpu_memory_utilization: Fraction of GPU memory to use (0.0–1.0). Default from
            env LLM_GPU_MEMORY_UTILIZATION (0.85). Lower values leave headroom and
            reduce OOM on 16 GB GPUs.

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
    if max_model_len is None:
        raw = os.environ.get("LLM_MAX_MODEL_LEN", "8192")
        max_model_len = int(raw)
    if gpu_memory_utilization is None:
        raw = os.environ.get("LLM_GPU_MEMORY_UTILIZATION", "0.85")
        gpu_memory_utilization = float(raw)
    # enforce_eager=True avoids torch.compile/Triton JIT, so no C compiler or Python.h needed in the container
    llm = LLM(
        model=model_id,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=True,
    )

    class VLLMBackend:
        def generate(self, prompt: str, max_tokens: int = 2048) -> str:
            from vllm import SamplingParams

            sampling_params = SamplingParams(max_tokens=max_tokens, temperature=0.2)
            outputs = llm.generate([prompt], sampling_params)
            if not outputs or not outputs[0].outputs:
                return ""
            return outputs[0].outputs[0].text or ""

    return VLLMBackend()
