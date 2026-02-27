"""CPU-backed inference for LLM analysis using Hugging Face Transformers."""

from __future__ import annotations

import os
import sys
import time

from debate_analyzer.analysis.backend import LLMBackend


def get_transformers_cpu_backend(
    model_id: str | None = None,
    max_model_len: int | None = None,
) -> LLMBackend:
    """
    Return an LLMBackend that uses Transformers for CPU inference.

    Requires transformers and torch to be installed. Used by the LLM batch job
    when running on CPU (no GPU/vLLM).

    Args:
        model_id: Hugging Face model id (e.g. Qwen/Qwen2-1.5B-Instruct).
            Default from env LLM_MODEL_ID.
        max_model_len: Max context length. Default from env LLM_MAX_MODEL_LEN (8192).
            Used to cap input length for CPU memory.

    Returns:
        Object implementing generate(prompt, max_tokens) -> str.

    Raises:
        ImportError: If transformers or torch is not installed.
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "Transformers and torch are required for CPU inference. "
            "Install with: pip install transformers torch."
        ) from e

    model_id = model_id or os.environ.get("LLM_MODEL_ID", "Qwen/Qwen2-1.5B-Instruct")
    if max_model_len is None:
        raw = os.environ.get("LLM_MAX_MODEL_LEN", "8192")
        max_model_len = int(raw)

    print(
        f"[LLM] Loading model {model_id} (first run may download from Hugging Face)...",
        file=sys.stderr,
    )
    t0 = time.perf_counter()
    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float32,
        device_map=None,
        trust_remote_code=True,
    )
    model = model.to(device)
    elapsed = time.perf_counter() - t0
    print(f"[LLM] Model loaded in {elapsed:.1f}s.", file=sys.stderr)

    class TransformersCPUBackend:
        def generate(self, prompt: str, max_tokens: int = 2048) -> str:
            messages = [{"role": "user", "content": prompt}]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            model_inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_model_len,
            ).to(device)
            with torch.inference_mode():
                generated_ids = model.generate(
                    **model_inputs,
                    max_new_tokens=max_tokens,
                    do_sample=True,
                    temperature=0.2,
                    pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                )
            input_len = model_inputs.input_ids.shape[1]
            new_ids = generated_ids[:, input_len:]
            response = tokenizer.decode(new_ids[0], skip_special_tokens=True)
            return response.strip() or ""

    return TransformersCPUBackend()
