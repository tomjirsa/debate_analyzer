"""
Video downloader module for downloading YouTube videos and subtitles.

DEPRECATED: This module has been refactored into a package.
Please import from debate_analyzer.video_downloader instead.

This file is kept for backward compatibility.
"""

# Re-export everything from the new video_downloader package
from .video_downloader import (
    VideoDownloader,
    VideoDownloadError,
    download_video,
    main,
)

__all__ = ["VideoDownloader", "VideoDownloadError", "download_video", "main"]


if __name__ == "__main__":
    import sys

    sys.exit(main())
