"""Video downloader implementation."""

import json
import os
import re
from pathlib import Path
from typing import Any, Union

import yt_dlp  # type: ignore[import-untyped]


class VideoDownloadError(Exception):
    """Exception raised when video download fails."""

    pass


class VideoDownloader:
    """Downloads YouTube videos and subtitles using yt-dlp."""

    def __init__(
        self, output_dir: Union[str, Path], config_path: Union[str, Path, None] = None
    ) -> None:
        """
        Initialize the video downloader.

        Args:
            output_dir: Directory where videos and subtitles will be saved
            config_path: Path to configuration JSON file (optional)
        """
        self.output_dir = Path(output_dir)
        self.videos_dir = self.output_dir / "videos"
        self.subtitles_dir = self.output_dir / "subtitles"

        # Create directories if they don't exist
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_config(config_path)

    def _load_config(
        self, config_path: Union[str, Path, None] = None
    ) -> dict[str, Any]:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file. If None, uses default config.

        Returns:
            Configuration dictionary
        """
        if config_path is None:
            # Use default config path
            config_path = (
                Path(__file__).parent.parent / "conf" / "video_downloader_conf.json"
            )
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise VideoDownloadError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)

        # Remove description field if present (it's for documentation only)
        config.pop("description", None)

        return config

    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is a valid YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if valid YouTube URL, False otherwise
        """
        youtube_regex = re.compile(
            r"(https?://)?(www\.)?"
            r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
            r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        return bool(youtube_regex.match(url))

    def download(self, url: str, download_subtitles: bool = True) -> dict[str, Any]:
        """
        Download video and subtitles from YouTube URL.

        Args:
            url: YouTube video URL
            download_subtitles: Whether to download subtitles (default: True)

        Returns:
            Dictionary containing metadata about the downloaded files:
                - video_id: YouTube video ID
                - title: Video title
                - video_path: Path to downloaded video file
                - subtitle_paths: List of paths to downloaded subtitle files
                - duration: Video duration in seconds
                - uploader: Channel name

        Raises:
            VideoDownloadError: If URL is invalid or download fails

        Note:
            If the environment variable ``YT_COOKIES_FILE`` is set and points to an
            existing file, that file is used as the cookie file for yt-dlp (e.g. to
            work around YouTube bot checks on datacenter IPs).
        """
        if not self.validate_url(url):
            raise VideoDownloadError(f"Invalid YouTube URL: {url}")

        # Start with base configuration
        ydl_opts = self.config.copy()

        # Add output templates (title first, then id)
        ydl_opts["outtmpl"] = {
            "default": str(self.videos_dir / "%(title)s_%(id)s.%(ext)s"),
            "subtitle": str(self.subtitles_dir / "%(title)s_%(id)s.%(ext)s"),
        }

        # Override subtitle settings if specified
        if not download_subtitles:
            ydl_opts["writesubtitles"] = False
            ydl_opts["writeautomaticsub"] = False
            ydl_opts["subtitleslangs"] = []
            ydl_opts["subtitlesformat"] = None

        # Optional cookies file for YouTube (e.g. bot check on datacenter IPs)
        cookies_path = os.environ.get("YT_COOKIES_FILE", "").strip()
        if cookies_path:
            path = Path(cookies_path)
            if path.exists() and path.is_file():
                ydl_opts["cookiefile"] = str(path)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info and download
                info = ydl.extract_info(url, download=True)

                if info is None:
                    raise VideoDownloadError(
                        f"Failed to extract video info from: {url}"
                    )

                # Collect video metadata
                video_id = info.get("id", "unknown")
                title = info.get("title", "unknown")
                duration = info.get("duration", 0)
                uploader = info.get("uploader", "unknown")

                # Find downloaded video file (title_id.ext; title may be sanitized by yt-dlp)
                video_ext = info.get("ext", "mp4")
                video_matches = list(self.videos_dir.glob(f"*_{video_id}.{video_ext}"))
                video_path = (
                    self.videos_dir / f"{title}_{video_id}.{video_ext}"
                    if not video_matches
                    else video_matches[0]
                )

                # Find subtitle files (filename is title_id.ext)
                subtitle_paths = list(self.subtitles_dir.glob(f"*_{video_id}.srt"))
                subtitle_paths.extend(self.subtitles_dir.glob(f"*_{video_id}.vtt"))

                metadata = {
                    "video_id": video_id,
                    "title": title,
                    "video_path": str(video_path),
                    "subtitle_paths": [str(p) for p in subtitle_paths],
                    "duration": duration,
                    "uploader": uploader,
                    "url": url,
                }

                # Save metadata to JSON file
                metadata_path = self.videos_dir / f"{video_id}_metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)

                return metadata

        except yt_dlp.utils.DownloadError as e:
            raise VideoDownloadError(f"Failed to download video: {e}") from e
        except Exception as e:
            raise VideoDownloadError(f"Unexpected error during download: {e}") from e


def download_video(
    url: str,
    output_dir: Union[str, Path] = "data",
    download_subtitles: bool = True,
    config_path: Union[str, Path, None] = None,
) -> dict[str, Any]:
    """
    Download a YouTube video and its subtitles.

    This is a convenience function that creates a VideoDownloader instance
    and downloads the video.

    Args:
        url: YouTube video URL
        output_dir: Directory where videos will be saved (default: "data")
        download_subtitles: Whether to download subtitles (default: True)
        config_path: Path to custom configuration file (optional)

    Returns:
        Dictionary containing metadata about the downloaded files

    Raises:
        VideoDownloadError: If URL is invalid or download fails

    Example:
        >>> metadata = download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> print(f"Downloaded: {metadata['title']}")
    """
    downloader = VideoDownloader(output_dir, config_path=config_path)
    return downloader.download(url, download_subtitles=download_subtitles)
