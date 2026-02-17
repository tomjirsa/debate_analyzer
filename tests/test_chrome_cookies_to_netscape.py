"""Tests for deploy/scripts/chrome_cookies_to_netscape.py cookie converter."""

import subprocess
import sys
from pathlib import Path

import pytest

# Script path from repo root (tests/ is at root)
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "deploy" / "scripts" / "chrome_cookies_to_netscape.py"


def _run_script(
    stdin: str | None = None,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the converter script with optional stdin and extra args."""
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestChromeCookiesToNetscape:
    """Tests for Chrome-to-Netscape cookie conversion."""

    def test_json_chrome_style_produces_netscape_lines(self) -> None:
        """Chrome-style JSON produces correct Netscape lines."""
        json_input = """[
            {"name": "SID", "value": "secret123", "domain": ".youtube.com",
             "path": "/", "secure": true, "expirationDate": 2000000000},
            {"name": "HSID", "value": "abc", "domain": ".youtube.com",
             "path": "/", "secure": false, "expirationDate": 0}
        ]"""
        result = _run_script(stdin=json_input)
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert len(lines) == 3  # header + 2 cookies
        # First cookie: .youtube.com, TRUE, /, TRUE, 2000000000, SID, secret123
        parts1 = lines[1].split("\t")
        assert len(parts1) == 7
        assert parts1[0] == ".youtube.com"
        assert parts1[1] == "TRUE"
        assert parts1[2] == "/"
        assert parts1[3] == "TRUE"
        assert parts1[4] == "2000000000"
        assert parts1[5] == "SID"
        assert parts1[6] == "secret123"
        # Session cookie: expiration 0
        parts2 = lines[2].split("\t")
        assert parts2[4] == "0"
        assert parts2[5] == "HSID"
        assert parts2[6] == "abc"

    def test_json_minimal_defaults_applied(self) -> None:
        """Minimal JSON with only name/value gets default domain, path, expiry."""
        json_input = '[{"name": "a", "value": "b"}]'
        result = _run_script(stdin=json_input)
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "# Netscape HTTP Cookie File"
        parts = lines[1].split("\t")
        assert parts[0] == ".youtube.com"
        assert parts[2] == "/"
        assert parts[3] == "TRUE"
        assert int(parts[4]) > 0  # default far-future expiry applied
        assert parts[5] == "a"
        assert parts[6] == "b"

    def test_cookie_header_two_cookies(self) -> None:
        """Cookie header (name1=val1; name2=val2) produces two Netscape lines."""
        result = _run_script(stdin="name1=val1; name2=val2")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert len(lines) == 3
        parts1 = lines[1].split("\t")
        parts2 = lines[2].split("\t")
        assert parts1[0] == ".youtube.com" and parts2[0] == ".youtube.com"
        assert (parts1[5], parts1[6]) == ("name1", "val1")
        assert (parts2[5], parts2[6]) == ("name2", "val2")

    def test_cookie_header_with_hash_treat_as_header(self) -> None:
        """Input starting with # is treated as cookie header (not JSON)."""
        result = _run_script(stdin="# Netscape HTTP Cookie File\nfoo=bar")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert len(lines) >= 2

    def test_empty_input_exit_nonzero(self) -> None:
        """Empty input exits with non-zero and error message."""
        result = _run_script(stdin="")
        assert result.returncode != 0
        assert "empty" in result.stderr.lower()

    def test_output_to_file(self, tmp_path: Path) -> None:
        """-o FILE writes Netscape content to file."""
        out_file = tmp_path / "cookies.txt"
        result = _run_script(
            stdin='[{"name": "x", "value": "y"}]', args=["-o", str(out_file)]
        )
        assert result.returncode == 0
        assert result.stdout == ""
        content = out_file.read_text()
        assert content.startswith("# Netscape HTTP Cookie File")
        assert "x" in content and "y" in content

    def test_domain_path_overrides_for_header(self) -> None:
        """--domain and --path override defaults for Cookie header input."""
        result = _run_script(
            stdin="sess=abc",
            args=["--domain", ".example.com", "--path", "/api"],
        )
        assert result.returncode == 0
        parts = result.stdout.strip().split("\n")[1].split("\t")
        assert parts[0] == ".example.com"
        assert parts[2] == "/api"
        assert (parts[5], parts[6]) == ("sess", "abc")

    def test_netscape_output_acceptable_by_ytdlp(self, tmp_path: Path) -> None:
        """Netscape file produced by the script is accepted by yt-dlp (no cookie error)."""
        cookies_file = tmp_path / "cookies.txt"
        result = _run_script(
            stdin='[{"name": "test", "value": "val", "domain": ".youtube.com"}]',
            args=["-o", str(cookies_file)],
        )
        assert result.returncode == 0
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--cookies",
                str(cookies_file),
                "--skip-download",
                "--no-warnings",
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        # yt-dlp must not fail due to cookie file format (e.g. "Unable to parse cookies")
        err = (proc.stderr or "").lower()
        assert "unable to parse cookies" not in err

    def test_ytdlp_accepts_deploy_cookies_txt_if_present(self) -> None:
        """If deploy/cookies.txt exists, yt-dlp accepts it (no cookie-format error)."""
        cookies_file = REPO_ROOT / "deploy" / "cookies.txt"
        if not cookies_file.is_file():
            pytest.skip("deploy/cookies.txt not present")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--cookies",
                str(cookies_file),
                "--skip-download",
                "--no-warnings",
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        err = (proc.stderr or "").lower()
        assert "unable to parse cookies" not in err
