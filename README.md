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
├── tests/            # Test files
├── doc/              # Documentation
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
