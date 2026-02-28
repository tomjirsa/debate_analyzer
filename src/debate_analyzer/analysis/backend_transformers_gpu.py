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
        Object implementing generate and generate_batch.

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
        dtype=dtype,
        device_map="cuda",
        trust_remote_code=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"[LLM] Model loaded on GPU in {elapsed:.1f}s.", file=sys.stderr)

    raw_batch_size = os.environ.get("LLM_BATCH_SIZE", "8").strip()
    try:
        max_batch_size = max(1, int(raw_batch_size))
    except ValueError:
        max_batch_size = 8
    pad_token_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    class TransformersGPUBackend:
        def generate(self, prompt: str, max_tokens: int = 2048) -> str:
            out = self.generate_batch([prompt], max_tokens)
            return out[0] if out else ""

        def generate_batch(
            self, prompts: list[str], max_tokens: int = 2048
        ) -> list[str]:
            if not prompts:
                return []
            results: list[str] = []
            for start in range(0, len(prompts), max_batch_size):
                batch_prompts = prompts[start : start + max_batch_size]
                batch_results = self._generate_batch_chunk(
                    batch_prompts, max_tokens, pad_token_id
                )
                results.extend(batch_results)
            return results

        def _generate_batch_chunk(
            self,
            prompts: list[str],
            max_tokens: int,
            pad_token_id: int,
        ) -> list[str]:
            messages_list = [[{"role": "user", "content": p}] for p in prompts]
            texts = [
                tokenizer.apply_chat_template(
                    msgs,
                    tokenize=False,
                    add_generation_prompt=True,
                )
                for msgs in messages_list
            ]
            old_padding_side = tokenizer.padding_side
            tokenizer.padding_side = "left"
            try:
                model_inputs = tokenizer(
                    texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=max_model_len,
                ).to(device)
            finally:
                tokenizer.padding_side = old_padding_side
            input_ids = model_inputs.input_ids
            attention_mask = model_inputs.attention_mask
            input_lengths = attention_mask.sum(dim=1)
            with torch.inference_mode():
                generated_ids = model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_tokens,
                    do_sample=True,
                    temperature=0.2,
                    pad_token_id=pad_token_id,
                )
            batch_size = input_ids.shape[0]
            out_list: list[str] = []
            for i in range(batch_size):
                start = input_lengths[i].item()
                new_ids = generated_ids[i, start:]
                response = tokenizer.decode(
                    new_ids, skip_special_tokens=True
                ).strip()
                out_list.append(response or "")
            return out_list

    return TransformersGPUBackend()
