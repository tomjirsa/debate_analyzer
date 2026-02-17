#!/usr/bin/env python3
"""
Convert Chrome DevTools cookies (JSON or Cookie header) to Netscape cookie format.

Reads cookies from a file or stdin, auto-detects JSON vs Cookie header format,
and writes a Netscape-format cookie file suitable for yt-dlp (e.g. YT_COOKIES_FILE).
"""

import argparse
import json
import sys
import time
from pathlib import Path

NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
DEFAULT_DOMAIN = ".youtube.com"
DEFAULT_PATH = "/"
DEFAULT_EXPIRY_YEARS = 10


def _sanitize(s: str) -> str:
    """Replace TAB and newline in cookie name/value to preserve Netscape format."""
    return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _cookie_to_netscape_line(
    domain: str,
    path: str,
    secure: bool,
    expiration: int,
    name: str,
    value: str,
) -> str:
    """Format a single cookie as a Netscape line (TAB-separated)."""
    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    secure_str = "TRUE" if secure else "FALSE"
    return "\t".join(
        [
            domain,
            include_subdomains,
            path,
            secure_str,
            str(int(expiration)),
            _sanitize(name),
            _sanitize(value),
        ]
    )


def _parse_json_cookies(data: str) -> list[dict]:
    """
    Parse JSON input into a list of cookie dicts with normalized keys.

    Accepts array of objects or single object. Chrome-style keys (expirationDate,
    domain, path, secure) are normalized. Missing fields get defaults.
    """
    raw = json.loads(data)
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("JSON must be an array of cookie objects or a single object")

    default_expiry = int(time.time()) + (
        DEFAULT_EXPIRY_YEARS * 365 * 24 * 60 * 60
    )
    cookies: list[dict] = []
    for i, obj in enumerate(raw):
        if not isinstance(obj, dict):
            raise ValueError(f"Cookie at index {i} is not an object")
        name = obj.get("name")
        value = obj.get("value")
        if name is None or value is None:
            raise ValueError(f"Cookie at index {i} missing 'name' or 'value'")
        raw_exp = obj.get("expirationDate")
        if raw_exp is None:
            raw_exp = obj.get("expiry")
        if raw_exp is None:
            raw_exp = obj.get("expires")
        if raw_exp is None:
            expiration = default_expiry
        elif isinstance(raw_exp, (int, float)) and raw_exp <= 0:
            expiration = 0  # session cookie
        else:
            expiration = int(float(raw_exp))
        cookies.append(
            {
                "domain": obj.get("domain") or DEFAULT_DOMAIN,
                "path": obj.get("path") or DEFAULT_PATH,
                "secure": bool(obj.get("secure", True)),
                "expiration": expiration,
                "name": str(name),
                "value": str(value),
            }
        )
    return cookies


def _parse_cookie_header(
    line: str,
    default_domain: str = DEFAULT_DOMAIN,
    default_path: str = DEFAULT_PATH,
    default_expiry: int | None = None,
) -> list[dict]:
    """
    Parse a Cookie header line (name1=value1; name2=value2) into cookie dicts.

    Uses default domain, path, and expiry for all cookies (header has no per-cookie
    meta).
    """
    if default_expiry is None:
        default_expiry = int(time.time()) + (
            DEFAULT_EXPIRY_YEARS * 365 * 24 * 60 * 60
        )
    cookies: list[dict] = []
    for part in line.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        cookies.append(
            {
                "domain": default_domain,
                "path": default_path,
                "secure": True,
                "expiration": default_expiry,
                "name": name,
                "value": value,
            }
        )
    return cookies


def _cookies_to_netscape(cookies: list[dict]) -> str:
    """Convert list of cookie dicts to Netscape format string."""
    lines = [NETSCAPE_HEADER]
    for c in cookies:
        lines.append(
            _cookie_to_netscape_line(
                domain=c["domain"],
                path=c["path"],
                secure=c["secure"],
                expiration=c["expiration"],
                name=c["name"],
                value=c["value"],
            )
        )
    return "\n".join(lines) + "\n"


def _read_input(path: str | None) -> str:
    """Read content from file or stdin. path '-' means stdin."""
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    """Run the converter: read input, detect format, write Netscape output."""
    parser = argparse.ArgumentParser(
        description="Convert Chrome DevTools cookies to Netscape format for yt-dlp."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input file path, or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=DEFAULT_DOMAIN,
        help=f"Default domain for Cookie header input (default: {DEFAULT_DOMAIN})",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=DEFAULT_PATH,
        help=f"Default path for Cookie header input (default: {DEFAULT_PATH})",
    )
    parser.add_argument(
        "--expiry",
        type=int,
        default=None,
        help="Default expiry (Unix sec) for Cookie header (default: 10y from now)",
    )
    args = parser.parse_args()

    try:
        content = _read_input(args.input)
    except OSError as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return 1

    content = content.strip().lstrip("\ufeff")
    if not content:
        print("Error: empty input", file=sys.stderr)
        return 1

    try:
        if content.startswith("[") or content.startswith("{"):
            cookies = _parse_json_cookies(content)
        else:
            default_expiry = args.expiry
            if default_expiry is None:
                default_expiry = int(time.time()) + (
                    DEFAULT_EXPIRY_YEARS * 365 * 24 * 60 * 60
                )
            cookies = _parse_cookie_header(
                content,
                default_domain=args.domain,
                default_path=args.path,
                default_expiry=default_expiry,
            )
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        return 1

    if not cookies:
        print("Error: no cookies found in input", file=sys.stderr)
        return 1

    out = _cookies_to_netscape(cookies)
    if args.output:
        try:
            Path(args.output).write_text(out, encoding="utf-8")
        except OSError as e:
            print(f"Error writing output: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
