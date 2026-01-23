"""Command-line interface for debate_analyzer."""

import sys


def main() -> int:
    """
    Main entry point for the debate_analyzer package.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print("Debate Analyzer")
    print("=" * 60)
    print("\nAvailable commands:")
    print("  python -m debate_analyzer.download_video URL  - Download YouTube video")
    print("\nFor more information, see the documentation in doc/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
