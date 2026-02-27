"""GPU-backed inference for LLM analysis using Hugging Face Transformers."""

from __future__ import annotations

import os
import sys
import time

from debate_analyzer.analysis.backend import LLMBackend


def get_transformers_gpu_backend(
    model_id: str | None = None,
    max_model_len: int | None = None,
) -> LLMBackend:
    """
    Return an LLMBackend that uses Transformers for GPU (CUDA) inference.

    Requires transformers and torch with CUDA. Used by the LLM batch job when
    LLM_USE_GPU=1 and running on a GPU node (e.g. AWS Batch with 1 GPU).

    Args:
        model_id: Hugging Face model id (e.g. Qwen/Qwen2-1.5B-Instruct).
            Default from env LLM_MODEL_ID.
        max_model_len: Max context length. Default from env LLM_MAX_MODEL_LEN (8192).

    Returns:
        Object implementing generate(prompt, max_tokens) -> str.

    Raises:
        ImportError: If transformers or torch is not installed.
        RuntimeError: If CUDA is not available.
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "Transformers and torch are required for GPU inference. "
            "Install with: pip install transformers torch (CUDA build)."
        ) from e

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. Run on a GPU node or use CPU backend."
        )

    model_id = model_id or os.environ.get("LLM_MODEL_ID", "Qwen/Qwen2-1.5B-Instruct")
    if max_model_len is None:
        raw = os.environ.get("LLM_MAX_MODEL_LEN", "8192")
        max_model_len = int(raw)

    device = torch.device("cuda")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    print(
        f"[LLM] Loading model {model_id} on GPU (first run may download from HF)...",
        file=sys.stderr,
    )
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map="cuda",
        trust_remote_code=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"[LLM] Model loaded on GPU in {elapsed:.1f}s.", file=sys.stderr)

    class TransformersGPUBackend:
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

    return TransformersGPUBackend()
