"""
Run LLM analysis on transcript(s) and write results to S3 or local path.

Reads from environment:
- TRANSCRIPT_S3_URI: Single transcript JSON (s3:// or file:// or path).
  Writes <stem>_llm_analysis.json alongside.
- TRANSCRIPTS_S3_PREFIX: S3 prefix listing *_transcription.json;
  processes each, writes _llm_analysis.json per file.

Uses MOCK_LLM=1 for tests. Otherwise Transformers CPU backend (dedicated LLM image).
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from debate_analyzer.analysis.backend import MockLLMBackend
from debate_analyzer.analysis.runner import run_analysis


def _log(msg: str) -> None:
    """Emit progress message to stderr with [LLM] prefix for CloudWatch visibility."""
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
    """Return generate callable (mock or Transformers CPU backend)."""
    if os.environ.get("MOCK_LLM", "").strip() in ("1", "true", "yes"):
        backend = MockLLMBackend()
        return backend.generate
    try:
        from debate_analyzer.analysis.backend_transformers_cpu import (
            get_transformers_cpu_backend,
        )

        backend = get_transformers_cpu_backend()
        return backend.generate
    except ImportError as e:
        print(
            "Error: Transformers not available. Set MOCK_LLM=1 or use the LLM image.",
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


def _run_one(
    source_uri: str,
    generate,
    log_progress: Callable[[str], None] | None = None,
) -> bool:
    """Load transcript, run analysis, write result. Returns True on success."""
    from debate_analyzer.api.loader import load_transcript_payload

    try:
        payload = load_transcript_payload(source_uri)
    except Exception as e:
        print(f"Error loading {source_uri}: {e}", file=sys.stderr)
        return False

    result = run_analysis(payload, generate, log_progress=log_progress)

    if source_uri.startswith("s3://"):
        bucket, key = _parse_s3_uri(source_uri)
        if "_transcription.json" in key:
            out_key = key.replace("_transcription.json", "_llm_analysis.json")
        else:
            out_key = key.rstrip("/") + "_llm_analysis.json"
        _write_result_s3(result, bucket, out_key)
        print(f"Wrote s3://{bucket}/{out_key}")
    else:
        path = Path(source_uri.replace("file://", ""))
        if "_transcription.json" in path.name:
            out_path = path.parent / path.name.replace(
                "_transcription.json", "_llm_analysis.json"
            )
        else:
            out_path = path.parent / (path.stem + "_llm_analysis.json")
        _write_result_file(result, out_path)
        print(f"Wrote {out_path}")

    return True


def run(prefix_or_uri: str) -> int:
    """
    Run LLM analysis on one transcript (URI) or all under a prefix (S3 only).

    Args:
        prefix_or_uri: TRANSCRIPT_S3_URI (single file) or TRANSCRIPTS_S3_PREFIX.

    Returns:
        Number of _llm_analysis.json files written.
    """
    job_start = time.perf_counter()
    s = prefix_or_uri.strip()

    # Single file: URI or path that points to a transcript JSON
    if "_transcription.json" in s:
        _log(f"Processing single file: {s}")
        _log("Loading model (this may take a few minutes)...")
        t0 = time.perf_counter()
        generate = _get_backend()
        _log(f"Model ready in {time.perf_counter() - t0:.1f}s.")
        _log(f"Processing transcript: {s}")
        ok = _run_one(s, generate, log_progress=_log)
        if ok:
            _log("Completed transcript.")
        else:
            _log("Failed transcript.")
        elapsed = time.perf_counter() - job_start
        _log(f"Job finished: {1 if ok else 0} succeeded, {0 if ok else 1} failed (total {elapsed:.1f}s).")
        return 1 if ok else 0

    # S3 prefix: list *_transcription.json
    if not s.startswith("s3://"):
        print(
            "Error: TRANSCRIPTS_S3_PREFIX must be an S3 URI (s3://...)", file=sys.stderr
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
            if not key.endswith("_transcription.json"):
                continue
            uris.append(f"s3://{bucket}/{key}")
    _log(f"Found {len(uris)} transcript(s) under prefix.")
    if not uris:
        _log("Job finished: 0 transcript(s) analyzed.")
        return 0

    _log("Loading model (this may take a few minutes)...")
    t0 = time.perf_counter()
    generate = _get_backend()
    _log(f"Model ready in {time.perf_counter() - t0:.1f}s.")
    n = len(uris)
    succeeded = 0
    failed = 0
    for i, uri in enumerate(uris):
        short_key = uri.split("/")[-1] if "/" in uri else uri
        _log(f"Processing transcript {i + 1}/{n}: {short_key}")
        ok = _run_one(uri, generate, log_progress=_log)
        if ok:
            succeeded += 1
            _log(f"Completed transcript {i + 1}/{n}.")
        else:
            failed += 1
            _log(f"Failed transcript {i + 1}/{n}.")
    elapsed = time.perf_counter() - job_start
    if failed:
        _log(f"Job finished: {succeeded} succeeded, {failed} failed (total {elapsed:.1f}s).")
    else:
        _log(f"Job finished: {succeeded} transcript(s) analyzed (total {elapsed:.1f}s).")
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
    print(f"Done. Wrote {n} LLM analysis file(s).")


if __name__ == "__main__":
    main()
