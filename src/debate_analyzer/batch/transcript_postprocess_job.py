"""
Run LLM post-processing on transcript(s): correct grammar/ASR errors only.

Reads *_transcription_raw.json (from transcriber), writes *_transcription.json.
Environment:
- TRANSCRIPT_S3_URI: Single raw file (s3:// or file:// or path).
  Writes <stem>_transcription.json alongside.
- TRANSCRIPTS_S3_PREFIX: S3 prefix listing *_transcription_raw.json;
  processes each, writes _transcription.json per file.

Backend: MOCK_LLM=1 for tests. Otherwise Ollama (same as llm_analysis_job).
Install with: poetry install --extras llm
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from debate_analyzer.analysis.backend import MockLLMBackend
from debate_analyzer.analysis.prompts import SYSTEM_PROMPT_RESPONSE_LANGUAGE
from debate_analyzer.analysis.transcript_postprocess import run_correction

_MAX_TOKENS_PER_REPLY = 1024


def _log(msg: str) -> None:
    """Emit progress message to stderr with [LLM] prefix."""
    print(f"[LLM] {msg}", file=sys.stderr)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Return (bucket, key) for s3:// URI."""
    if not uri.startswith("s3://") or len(uri) < 8:
        raise ValueError(f"Invalid S3 URI: {uri}")
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key


def _get_backend():
    """Return generate_batch callable: mock when MOCK_LLM=1, else Ollama backend."""
    if os.environ.get("MOCK_LLM", "").strip() in ("1", "true", "yes"):
        backend = MockLLMBackend()
        return backend.generate_batch, "mock"
    try:
        from debate_analyzer.analysis.backend_ollama import get_ollama_backend

        backend = get_ollama_backend(system_prompt=SYSTEM_PROMPT_RESPONSE_LANGUAGE)
        return backend.generate_batch, "ollama"
    except ImportError as e:
        print(
            "Error: Ollama backend requires langchain-ollama. "
            "Install with: poetry install --extras llm",
            file=sys.stderr,
        )
        raise SystemExit(1) from e


def _write_result_s3(result: dict, bucket: str, key: str) -> None:
    """Write result JSON to S3."""
    import boto3

    client = boto3.client("s3")
    body = json.dumps(result, ensure_ascii=False, indent=2)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )


def _write_result_file(result: dict, path: Path) -> None:
    """Write result JSON to local file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_one(source_uri: str, generate_batch, model_label: str) -> bool:
    """Load raw transcript, run correction, write _transcription.json."""
    from debate_analyzer.api.loader import load_transcript_payload

    try:
        payload = load_transcript_payload(source_uri)
    except Exception as e:
        print(f"Error loading {source_uri}: {e}", file=sys.stderr)
        return False

    result = run_correction(
        payload,
        generate_batch,
        max_tokens_per_reply=_MAX_TOKENS_PER_REPLY,
        postprocess_model_label=model_label,
    )

    if source_uri.startswith("s3://"):
        bucket, key = _parse_s3_uri(source_uri)
        if "_transcription_raw.json" in key:
            out_key = key.replace("_transcription_raw.json", "_transcription.json")
        else:
            out_key = (
                key.rstrip("/").removesuffix("_transcription_raw")
                + "_transcription.json"
            )
        _write_result_s3(result, bucket, out_key)
        print(f"Wrote s3://{bucket}/{out_key}")
    else:
        path = Path(source_uri.replace("file://", ""))
        if "_transcription_raw.json" in path.name:
            out_path = path.parent / path.name.replace(
                "_transcription_raw.json", "_transcription.json"
            )
        else:
            stem = path.stem.removesuffix("_transcription_raw")
            out_path = path.parent / (stem + "_transcription.json")
        _write_result_file(result, out_path)
        print(f"Wrote {out_path}")

    return True


def run(prefix_or_uri: str) -> int:
    """
    Run post-processing on one transcript (URI) or all under a prefix (S3 only).

    Args:
        prefix_or_uri: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX.

    Returns:
        Number of _transcription.json files written.
    """
    job_start = time.perf_counter()
    s = prefix_or_uri.strip()

    if "_transcription_raw.json" in s:
        _log(f"Processing single file: {s}")
        _log("Loading model...")
        t0 = time.perf_counter()
        generate_batch, model_label = _get_backend()
        _log(f"Model ready in {time.perf_counter() - t0:.1f}s.")
        _log(f"Correcting transcript: {s}")
        ok = _run_one(s, generate_batch, model_label)
        if ok:
            _log("Completed transcript.")
        else:
            _log("Failed transcript.")
        elapsed = time.perf_counter() - job_start
        _log(f"Job finished: {1 if ok else 0} succeeded (total {elapsed:.1f}s).")
        return 1 if ok else 0

    if not s.startswith("s3://"):
        print(
            "Error: TRANSCRIPTS_S3_PREFIX must be an S3 URI (s3://...)",
            file=sys.stderr,
        )
        return 0

    import boto3

    _log(f"Processing prefix: {s}")
    bucket, prefix_key = _parse_s3_uri(s)
    if not prefix_key.endswith("/"):
        prefix_key += "/"
    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    uris: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_key):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            if not key.endswith("_transcription_raw.json"):
                continue
            uris.append(f"s3://{bucket}/{key}")
    _log(f"Found {len(uris)} transcript(s) under prefix.")
    if not uris:
        _log("Job finished: 0 transcript(s) processed.")
        return 0

    _log("Loading model...")
    t0 = time.perf_counter()
    generate_batch, model_label = _get_backend()
    _log(f"Model ready in {time.perf_counter() - t0:.1f}s.")
    n = len(uris)
    succeeded = 0
    failed = 0
    for i, uri in enumerate(uris):
        short_key = uri.split("/")[-1] if "/" in uri else uri
        _log(f"Processing transcript {i + 1}/{n}: {short_key}")
        ok = _run_one(uri, generate_batch, model_label)
        if ok:
            succeeded += 1
            _log(f"Completed transcript {i + 1}/{n}.")
        else:
            failed += 1
            _log(f"Failed transcript {i + 1}/{n}.")
    elapsed = time.perf_counter() - job_start
    if failed:
        _log(f"Job finished: {succeeded} ok, {failed} failed (total {elapsed:.1f}s).")
    else:
        _log(f"Job finished: {succeeded} transcript(s) written ({elapsed:.1f}s).")
    return succeeded


def main() -> None:
    """Entry point: read TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX from env."""
    uri = os.environ.get("TRANSCRIPT_S3_URI", "").strip()
    prefix = os.environ.get("TRANSCRIPTS_S3_PREFIX", "").strip()
    if uri:
        n = run(uri)
    elif prefix:
        n = run(prefix)
    else:
        print(
            "Error: TRANSCRIPT_S3_URI or TRANSCRIPTS_S3_PREFIX must be set",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Done. Wrote {n} transcript file(s).")


if __name__ == "__main__":
    main()
