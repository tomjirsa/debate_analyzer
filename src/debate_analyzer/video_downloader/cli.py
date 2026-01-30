"""Command-line interface for video downloader."""

import argparse
import sys

from .downloader import VideoDownloadError, download_video


def main() -> int:
    """
    Command-line interface for video downloader.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        prog="python -m debate_analyzer.video_downloader",
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

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration file (optional)",
    )

    args = parser.parse_args()

    try:
        print(f"Downloading video from: {args.url}")
        print(f"Output directory: {args.output_dir}")
        if args.config:
            print(f"Using config: {args.config}")
        print("-" * 60)

        metadata = download_video(
            args.url,
            args.output_dir,
            download_subtitles=not args.no_subtitles,
            config_path=args.config,
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
