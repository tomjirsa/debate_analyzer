"""Load transcript JSON from S3 URI or local file path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import boto3


def load_transcript_payload(source_uri: str) -> dict[str, Any]:
    """
    Load transcript JSON from source_uri.
    - s3://bucket/key -> fetch via boto3.
    - file:///path or /path -> read from filesystem.
    - Otherwise treat as local path.

    Returns:
        Parsed JSON dict (transcription list, duration, etc.).

    Raises:
        FileNotFoundError: Local file does not exist.
        ValueError: Unsupported scheme or invalid JSON.
    """
    source_uri = source_uri.strip()
    if source_uri.startswith("s3://"):
        return _load_from_s3(source_uri)
    if source_uri.startswith("file://"):
        path = Path(source_uri[7:])
    else:
        path = Path(source_uri)
    return _load_from_file(path)


def _load_from_s3(uri: str) -> dict[str, Any]:
    """Parse s3://bucket/key and get object content as JSON."""
    if not uri.startswith("s3://") or len(uri) < 8:
        raise ValueError(f"Invalid S3 URI: {uri}")
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ValueError(f"Invalid S3 key: {uri}")
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def _load_from_file(path: Path) -> dict[str, Any]:
    """Read JSON from local file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
