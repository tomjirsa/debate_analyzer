"""Command-line interface for video transcription."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn, Optional


def main() -> NoReturn:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Transcribe videos with speaker identification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python -m debate_analyzer.transcriber video.mp4
  
  # Specify output directory
  python -m debate_analyzer.transcriber video.mp4 --output-dir transcripts
  
  # Use different model size
  python -m debate_analyzer.transcriber video.mp4 --model-size large
  
  # Provide HuggingFace token
  python -m debate_analyzer.transcriber video.mp4 --hf-token YOUR_TOKEN
        """,
    )

    parser.add_argument(
        "video_path",
        type=str,
        help="Path to video file to transcribe",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/transcripts",
        help="Directory to save transcription outputs (default: data/transcripts)",
    )

    parser.add_argument(
        "--model-size",
        type=str,
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        default="medium",
        help="Whisper model size (default: medium)",
    )

    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Device to use for processing (default: auto)",
    )

    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="HuggingFace token for pyannote models (or set HF_TOKEN env var)",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration file",
    )

    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code for transcription (e.g., 'en', 'es', 'fr'). If not specified, language is auto-detected.",
    )

    args = parser.parse_args()

    # Validate video path
    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    if not video_path.is_file():
        print(f"Error: Path is not a file: {video_path}", file=sys.stderr)
        sys.exit(1)

    try:
        # Import here to avoid slow imports when just showing help
        from debate_analyzer.transcriber import transcribe_video

        print(f"Transcribing: {video_path}")
        print(f"Model: {args.model_size}")
        print(f"Device: {args.device}")
        print(f"Output directory: {args.output_dir}")
        print()

        result = transcribe_video(
            video_path=video_path,
            output_dir=args.output_dir,
            model_size=args.model_size,
            device=args.device,
            hf_token=args.hf_token,
            config_path=args.config,
            language=args.language,
        )

        print("\n" + "=" * 60)
        print("Transcription Complete!")
        print("=" * 60)
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Processing time: {result['processing_time']:.2f} seconds")
        print(f"Speakers found: {result['speakers_count']}")
        print(f"Total segments: {len(result['transcription'])}")
        print(f"\nOutput saved to: {result['output_path']}")
        print()

        # Show first few segments as preview
        print("Preview (first 5 segments):")
        print("-" * 60)
        for segment in result["transcription"][:5]:
            speaker = segment["speaker"]
            text = segment["text"]
            start = segment["start"]
            print(f"[{start:>7.2f}s] {speaker}: {text}")
        
        if len(result["transcription"]) > 5:
            print(f"... and {len(result['transcription']) - 5} more segments")

        sys.exit(0)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
