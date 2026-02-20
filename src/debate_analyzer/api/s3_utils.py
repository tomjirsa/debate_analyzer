"""S3 helpers: parse S3 URIs and generate presigned URLs."""

from __future__ import annotations


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """
    Parse an s3://bucket/key URI into bucket and key.

    Args:
        uri: URI like s3://bucket-name/path/to/object.

    Returns:
        Tuple of (bucket, key).

    Raises:
        ValueError: If uri is not a valid S3 URI or key is empty.
    """
    uri = uri.strip()
    if not uri.startswith("s3://") or len(uri) < 8:
        raise ValueError(f"Invalid S3 URI: {uri}")
    rest = uri[5:]
    parts = rest.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    if not key:
        raise ValueError(f"Invalid S3 key: {uri}")
    return bucket, key


def generate_presigned_get_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a presigned GET URL for an S3 object.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        expires_in: URL validity in seconds (default 1 hour).

    Returns:
        Presigned URL string.
    """
    import boto3

    client = boto3.client("s3")
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
