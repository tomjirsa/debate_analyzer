# Development Guide

## Getting Started

### Setting Up Your Development Environment

1. **Install System Requirements**:
   
   **ffmpeg** (required for video processing):
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```
   
   Verify installation:
   ```bash
   ffmpeg -version
   ```

2. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd debate_analyzer
   ```

4. **Install Python dependencies** (transcribe pipeline + web app; required for tests):
   ```bash
   poetry install --extras transcribe --extras webapp
   ```

5. **Activate the virtual environment**:
   ```bash
   poetry shell
   ```

### Using the Makefile

The project includes a Makefile with common development tasks:

#### Reset Virtual Environment
```bash
make reset_venv
```
This will:
- Remove the existing virtual environment
- Reinstall all dependencies from scratch
- Useful when dependencies are corrupted or need a clean slate

#### Run Tests
```bash
make test
```
This will:
- Run the full test suite with pytest
- Generate coverage reports
- Display results in the terminal

#### Deploy
```bash
make deploy
```
This will:
- Run tests to ensure everything passes
- Build the package
- Publish to PyPI (configure credentials first)

### Running the stats job locally

The speaker-stats batch task can be run against a **local directory** of transcript JSONs (no AWS required). Use this when developing or testing after running the transcriber locally.

1. Ensure the directory contains `*_transcription.json` files (e.g. from `python -m debate_analyzer.transcriber`).
2. Set `TRANSCRIPTS_PREFIX` (or `TRANSCRIPTS_S3_PREFIX`) to that directory path or a `file://` URI.
3. Run the stats job module; it will write `<stem>_speaker_stats.parquet` next to each transcript JSON.

```bash
# Example: transcripts in data/transcripts/
export TRANSCRIPTS_PREFIX=./data/transcripts
python -m debate_analyzer.batch.stats_job

# Or use the Makefile target
make stats-local PREFIX=./data/transcripts
```

On AWS Batch, the same code uses `TRANSCRIPTS_S3_PREFIX=s3://bucket/...`; the job detects S3 vs local from the prefix value.

## Code Quality Standards

### Code Formatting
We use **black** for consistent code formatting:
```bash
poetry run black src/ tests/
```

Configuration is in `pyproject.toml`:
- Line length: 88 characters
- Target: Python 3.9+

### Linting
We use **ruff** for fast Python linting:
```bash
poetry run ruff check src/ tests/
```

Fix auto-fixable issues:
```bash
poetry run ruff check --fix src/ tests/
```

### Type Checking
We use **mypy** for static type checking:
```bash
poetry run mypy src/
```

All functions should have type hints:
```python
def process_data(input_data: str) -> dict[str, any]:
    """Process input data and return results."""
    # implementation
```

## Testing Guidelines

### Writing Tests

Tests are located in the `/tests` folder. Follow these conventions:

1. **File naming**: `test_<module_name>.py`
2. **Function naming**: `test_<function_description>()`
3. **Class naming**: `Test<ClassName>`

Example test structure:
```python
"""Tests for the example module."""

import pytest
from debate_analyzer.example import ExampleClass


def test_simple_function() -> None:
    """Test a simple function."""
    result = simple_function("input")
    assert result == "expected"


class TestExampleClass:
    """Tests for ExampleClass."""
    
    def test_method(self) -> None:
        """Test a class method."""
        obj = ExampleClass()
        assert obj.method() == "expected"
```

### Running Tests

Run all tests:
```bash
poetry run pytest
```

Run with coverage:
```bash
poetry run pytest --cov
```

Run specific test file:
```bash
poetry run pytest tests/test_example.py
```

Run specific test function:
```bash
poetry run pytest tests/test_example.py::test_version
```

## Adding Dependencies

### Production Dependencies
```bash
poetry add <package-name>
```

### Development Dependencies
```bash
poetry add --group dev <package-name>
```

## Git Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and code quality checks
4. Commit with clear, descriptive messages
5. Push and create a pull request

### Pre-commit Checklist
- [ ] Tests pass (`make test`)
- [ ] Code is formatted (`poetry run black src/ tests/`)
- [ ] Linting passes (`poetry run ruff check src/ tests/`)
- [ ] Type checking passes (`poetry run mypy src/`)
- [ ] Documentation is updated if needed

## Project Structure Best Practices

### Source Code (`/src`)
- Keep all application code in `/src/debate_analyzer/`
- Use submodules for organization (`core/`, `models/`, `utils/`, etc.)
- Each module should have a clear, single responsibility

### Tests (`/tests`)
- Mirror the structure of `/src` in your tests
- Use fixtures for common test data
- Keep tests isolated and independent

### Documentation (`/doc`)
- Update documentation when adding features
- Include code examples in documentation
- Keep the main README focused on quick setup

## Troubleshooting

### Virtual Environment Issues
If you encounter virtual environment issues:
```bash
make reset_venv
```

### Dependency Conflicts
1. Check `poetry.lock` for conflicts
2. Try updating dependencies: `poetry update`
3. If needed, reset: `make reset_venv`

### Test Failures
1. Run tests in verbose mode: `pytest -vv`
2. Check test isolation: run failing test alone
3. Clear pytest cache: `rm -rf .pytest_cache`
