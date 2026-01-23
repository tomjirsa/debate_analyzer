"""Video downloader module for downloading YouTube videos and subtitles."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Union

import yt_dlp  # type: ignore[import-untyped]


class VideoDownloadError(Exception):
    """Exception raised when video download fails."""

    pass


class VideoDownloader:
    """Downloads YouTube videos and subtitles using yt-dlp."""

    def __init__(self, output_dir: Union[str, Path]) -> None:
        """
        Initialize the video downloader.

        Args:
            output_dir: Directory where videos and subtitles will be saved
        """
        self.output_dir = Path(output_dir)
        self.videos_dir = self.output_dir / "videos"
        self.subtitles_dir = self.output_dir / "subtitles"

        # Create directories if they don't exist
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)

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
        """
        if not self.validate_url(url):
            raise VideoDownloadError(f"Invalid YouTube URL: {url}")

        # Configure yt-dlp options
        ydl_opts = {
            # Prioritize audio quality while limiting video to 480p to reduce file size
            # Format explanation:
            # - bestvideo[height<=480]: Best video quality up to 480p (saves space)
            # - bestaudio: Best available audio quality (important for speech analysis)
            # - fallback to best[height<=480] if separate streams not available
            "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            "merge_output_format": "mp4",  # Merge into mp4 container
            "outtmpl": {
                "default": str(self.videos_dir / "%(id)s_%(title)s.%(ext)s"),
                "subtitle": str(self.subtitles_dir / "%(id)s_%(title)s.%(ext)s"),
            },
            "writesubtitles": download_subtitles,
            "writeautomaticsub": download_subtitles,
            "subtitleslangs": ["en"] if download_subtitles else [],
            "subtitlesformat": "srt" if download_subtitles else None,
            "skip_download": False,
            "ignoreerrors": True,  # Continue if subtitle download fails
            "no_warnings": False,
            "fragment_retries": 2,  # Retry fragments up to 10 times
            "skip_unavailable_fragments": False,  # Skip fragments that can't be downloaded
            "extractor_retries": 3,  # Retry extraction up to 3 times
            "retries": 3,  # Retry failed downloads
            "http_chunk_size": 10485760,  # 10MB chunks to reduce load
            "prefer_ffmpeg": True,  # Use ffmpeg for better audio/video merging
            # "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading first to get metadata
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

                # Find downloaded video file
                video_ext = info.get("ext", "mp4")
                video_filename = f"{video_id}_{title}.{video_ext}"
                video_path = self.videos_dir / video_filename

                # Find subtitle files
                subtitle_paths = list(self.subtitles_dir.glob(f"{video_id}_*.srt"))
                subtitle_paths.extend(self.subtitles_dir.glob(f"{video_id}_*.vtt"))

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
    url: str, output_dir: Union[str, Path] = "data", download_subtitles: bool = True
) -> dict[str, Any]:
    """
    Download a YouTube video and its subtitles.

    This is a convenience function that creates a VideoDownloader instance
    and downloads the video.

    Args:
        url: YouTube video URL
        output_dir: Directory where videos will be saved (default: "data")
        download_subtitles: Whether to download subtitles (default: True)

    Returns:
        Dictionary containing metadata about the downloaded files

    Raises:
        VideoDownloadError: If URL is invalid or download fails

    Example:
        >>> metadata = download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> print(f"Downloaded: {metadata['title']}")
    """
    downloader = VideoDownloader(output_dir)
    return downloader.download(url, download_subtitles=download_subtitles)


def main() -> int:
    """
    Command-line interface for video downloader.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        prog="python -m debate_analyzer.download_video",
        description="Download YouTube videos and subtitles for debate analysis",
    )

    parser.add_argument(
        "url",
        type=str,
        help="YouTube video URL to download",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Directory to save downloaded videos (default: data)",
    )

    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Skip downloading subtitles",
    )

    args = parser.parse_args()

    try:
        print(f"Downloading video from: {args.url}")
        print(f"Output directory: {args.output_dir}")
        print("-" * 60)

        metadata = download_video(
            args.url, args.output_dir, download_subtitles=not args.no_subtitles
        )

        print("\n" + "=" * 60)
        print("Download completed successfully!")
        print("=" * 60)
        print(f"Video ID: {metadata['video_id']}")
        print(f"Title: {metadata['title']}")
        print(f"Uploader: {metadata['uploader']}")
        print(f"Duration: {metadata['duration']} seconds")
        print(f"Video file: {metadata['video_path']}")

        if metadata["subtitle_paths"]:
            print(f"Subtitles: {len(metadata['subtitle_paths'])} file(s)")
            for subtitle_path in metadata["subtitle_paths"]:
                print(f"  - {subtitle_path}")
        else:
            print("Subtitles: None found")

        return 0

    except VideoDownloadError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
