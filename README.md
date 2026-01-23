# Debate Analyzer

A Python project for debate analysis built with Poetry.

## Quick Setup

### Prerequisites
- Python 3.9 or higher
- Poetry (install via `curl -sSL https://install.python-poetry.org | python3 -`)
- ffmpeg (required for video processing)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd debate_analyzer
```

2. Install dependencies:
```bash
poetry install
```

3. Verify ffmpeg is installed:
```bash
ffmpeg -version
```

4. Activate the virtual environment:
```bash
poetry shell
```

### Quick Start with Make

This project includes a Makefile for common tasks:

```bash
# Reset and recreate virtual environment
make reset_venv

# Run tests
make test

# Deploy (build and publish)
make deploy
```

## Usage

### Downloading YouTube Videos

Download YouTube videos for debate analysis with optimized settings (high audio quality, reduced video size):

```bash
# Basic usage - downloads video with subtitles
poetry run python -m debate_analyzer.video_downloader "https://www.youtube.com/watch?v=VIDEO_ID"

# Specify output directory
poetry run python -m debate_analyzer.video_downloader "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir my_videos

# Skip subtitles
poetry run python -m debate_analyzer.video_downloader "https://www.youtube.com/watch?v=VIDEO_ID" --no-subtitles

# Use custom configuration
poetry run python -m debate_analyzer.video_downloader "https://www.youtube.com/watch?v=VIDEO_ID" --config path/to/config.json
```

**Download Configuration:**
- Audio: Best available quality (important for speech analysis)
- Video: Limited to 480p (optimized for smaller file sizes)
- Format: MP4 container with automatic subtitle download
- Configuration file: `src/debate_analyzer/conf/video_downloader_conf.json`

**Programmatic Usage:**

```python
from debate_analyzer.video_downloader import download_video

# Download video
metadata = download_video(
    url="https://www.youtube.com/watch?v=VIDEO_ID",
    output_dir="data",
    download_subtitles=True
)

print(f"Downloaded: {metadata['title']}")
print(f"Video path: {metadata['video_path']}")
print(f"Subtitles: {metadata['subtitle_paths']}")
```

## Development

### Running Tests
```bash
poetry run pytest
# or with coverage
poetry run pytest --cov
```

### Code Formatting
```bash
poetry run black src/ tests/
```

### Linting
```bash
poetry run ruff check src/ tests/
```

### Type Checking
```bash
poetry run mypy src/
```

## Project Structure

```
debate_analyzer/
├── src/              # Source code
│   └── debate_analyzer/
│       ├── conf/                    # Configuration files
│       │   └── video_downloader_conf.json
│       ├── video_downloader/        # Video downloader module
│       │   ├── __init__.py
│       │   ├── __main__.py
│       │   ├── cli.py              # Command-line interface
│       │   └── downloader.py       # Core downloader logic
│       └── video_downloader.py     # (Deprecated - kept for compatibility)
├── tests/            # Test files
├── doc/              # Documentation
├── data/             # Downloaded videos and subtitles (generated)
│   ├── videos/
│   └── subtitles/
├── pyproject.toml    # Poetry configuration
├── Makefile          # Common tasks automation
└── README.md         # This file
```

## Documentation

For detailed documentation, see the [doc](./doc) folder:
- [Architecture](./doc/ARCHITECTURE.md) - System architecture and design
- [Development Guide](./doc/DEVELOPMENT.md) - Development workflow and guidelines
- [API Reference](./doc/API.md) - API documentation

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]
