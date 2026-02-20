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

### Transcribing Videos with Speaker Identification

Transcribe videos and identify speakers using state-of-the-art open-source models (faster-whisper + pyannote.audio):

**Setup Requirements:**
1. HuggingFace account and token (for speaker diarization):
   - Create account at [huggingface.co](https://huggingface.co)
   - Accept model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - Create access token at [settings/tokens](https://huggingface.co/settings/tokens)
   - Set environment variable: `export HF_TOKEN=your_token_here`

**CLI Usage:**

```bash
# Basic usage - transcribe with medium model
poetry run python -m debate_analyzer.transcriber video.mp4

# Specify output directory
poetry run python -m debate_analyzer.transcriber video.mp4 --output-dir transcripts

# Use different model size (tiny, base, small, medium, large)
poetry run python -m debate_analyzer.transcriber video.mp4 --model-size large

# Provide HuggingFace token directly
poetry run python -m debate_analyzer.transcriber video.mp4 --hf-token YOUR_TOKEN

# Specify language (for better accuracy)
poetry run python -m debate_analyzer.transcriber video.mp4 --language en
```

**Programmatic Usage:**

```python
from debate_analyzer.transcriber import transcribe_video

# Transcribe video
result = transcribe_video("data/videos/debate.mp4")

print(f"Found {result['speakers_count']} speakers")
print(f"Duration: {result['duration']:.2f} seconds")
print(f"Processing time: {result['processing_time']:.2f} seconds")

# Access transcription segments
for segment in result['transcription']:
    speaker = segment['speaker']
    text = segment['text']
    start = segment['start']
    print(f"[{start:.2f}s] {speaker}: {text}")
```

**Output Format:**

Transcriptions are saved as JSON files in `data/transcripts/` with the following structure:
```json
{
  "video_path": "path/to/video.mp4",
  "duration": 1234.56,
  "speakers_count": 3,
  "transcription": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Hello and welcome to the debate.",
      "speaker": "SPEAKER_00",
      "confidence": 0.95
    }
  ]
}
```

**Performance Notes:**
- First run downloads models (~5GB for Whisper medium, ~1GB for pyannote)
- Processing time: approximately 1-2x real-time (10-minute video = 10-20 minutes)
- Requires ~4GB RAM, ~3GB VRAM if GPU available
- Models are cached locally for subsequent runs

### Web App (speaker profiles and statistics)

A web app provides a database of speaker profiles, mapping to transcript speakers, and public statistics.

**Run locally (SQLite, no auth until you set env):**

```bash
# Optional: set admin credentials for /admin and /api/admin/*
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin

poetry run python -m debate_analyzer.api
# Open http://127.0.0.1:8000 (public speakers), http://127.0.0.1:8000/admin (admin)
```

- **Public:** `/` – speaker list; `/speakers/<id>` – speaker detail and stats.
- **Admin (HTTP Basic):** `/admin` – register transcripts (S3 or local path), open transcript → annotate speakers; `/admin/annotate?transcript_id=...` – assign speaker IDs to profiles.
- **API docs:** http://127.0.0.1:8000/docs

Use `DATABASE_URL` for PostgreSQL (e.g. in production). Deploy to AWS with [deploy/terraform-webapp/](deploy/terraform-webapp/README.md) (separate state from the Batch stack).

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
│       │   ├── video_downloader_conf.json
│       │   └── transcriber_conf.json
│       ├── video_downloader/        # Video downloader module
│       │   ├── __init__.py
│       │   ├── __main__.py
│       │   ├── cli.py              # Command-line interface
│       │   └── downloader.py       # Core downloader logic
│       ├── transcriber/            # Transcription & speaker diarization
│       │   ├── ...
│       ├── db/                      # Web app: DB models, repository
│       │   ├── models.py
│       │   ├── repository.py
│       │   └── base.py
│       └── api/                     # Web app: FastAPI, auth, loader
│           ├── app.py
│           ├── auth.py
│           ├── loader.py
│           └── static/              # Admin and public UI
├── deploy/terraform-webapp/        # Terraform for web app (separate state)
├── tests/            # Test files
├── doc/              # Documentation
├── data/             # Downloaded videos, subtitles, transcripts (generated)
│   ├── videos/
│   ├── subtitles/
│   └── transcripts/
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
