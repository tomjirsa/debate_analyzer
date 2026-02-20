# Project Setup Checklist

Use this checklist to set up the Debate Analyzer project. For detailed development workflow and code standards, see [DEVELOPMENT.md](DEVELOPMENT.md). For quick install and usage, see the root [README.md](../README.md).

## System Requirements

- **Python 3.9+**
- **Poetry** — [install](https://python-poetry.org/docs/#installation)
- **ffmpeg** — Required for video download and transcribe
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: [ffmpeg.org](https://ffmpeg.org/download.html)
- *(Optional for transcribe)* **HuggingFace token** — For speaker diarization; see [TRANSCRIBE.md](TRANSCRIBE.md)

## Project Structure

- **Source:** `/src/debate_analyzer/` — `video_downloader/`, `transcriber/`, `db/`, `api/`, `conf/`
- **Tests:** `/tests/` at repo root (pytest)
- **Docs:** `/doc/` (this folder)
- **Deploy:** `/deploy/terraform/` (Batch), `/deploy/terraform-webapp/` (Web app)

## Setup Steps

1. **Clone and enter repo**
   ```bash
   git clone <repository-url>
   cd debate_analyzer
   ```

2. **Install dependencies**
   ```bash
   poetry install --extras transcribe --extras webapp
   ```
   Omit extras if you only need core, transcribe, or webapp.

3. **Verify ffmpeg**
   ```bash
   ffmpeg -version
   ```

4. **Activate shell (optional)**
   ```bash
   poetry shell
   ```

5. **Run checks**
   ```bash
   make all   # format, lint, typecheck, test
   ```

## Quality Checklist

- [ ] `poetry install` completes without errors
- [ ] `make test` passes
- [ ] `make format` runs (black)
- [ ] `make lint` runs (ruff)
- [ ] `make typecheck` runs (mypy)
- [ ] `make all` passes

## See Also

- [README.md](../README.md) — Quick setup and usage
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development workflow, code quality, testing
- [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture and project layout
- [TRANSCRIBE.md](TRANSCRIBE.md) — Transcribe module setup
- [WEBAPP.md](WEBAPP.md) — Web app and run locally
