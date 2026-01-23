# How-To Guides

This document contains step-by-step guides for common tasks in the Debate Analyzer project.

## Table of Contents
- [How to Download YouTube Videos](#how-to-download-youtube-videos)
- [How to Add a New Feature](#how-to-add-a-new-feature)
- [How to Write Tests](#how-to-write-tests)
- [How to Debug Issues](#how-to-debug-issues)
- [How to Add Dependencies](#how-to-add-dependencies)
- [How to Release a New Version](#how-to-release-a-new-version)

## How to Download YouTube Videos

### Prerequisites

Ensure **ffmpeg** is installed (required for video processing):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
```

### Using the Command-Line Interface

Download a video with subtitles:

```bash
# Using default output directory (data/)
poetry run python -m debate_analyzer.download_video "https://www.youtube.com/watch?v=VIDEO_ID"

# Using custom output directory
poetry run python -m debate_analyzer.download_video "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir my_videos
```

### Using Python Code

**Option 1: Convenience Function**

```python
from debate_analyzer.video_downloader import download_video

metadata = download_video("https://www.youtube.com/watch?v=VIDEO_ID")
print(f"Downloaded: {metadata['title']}")
print(f"Video: {metadata['video_path']}")
print(f"Subtitles: {metadata['subtitle_paths']}")
```

**Option 2: Using the Class**

```python
from debate_analyzer.video_downloader import VideoDownloader

downloader = VideoDownloader(output_dir="my_videos")

# Validate URL first (optional)
if downloader.validate_url("https://www.youtube.com/watch?v=VIDEO_ID"):
    metadata = downloader.download("https://www.youtube.com/watch?v=VIDEO_ID")
    print(f"Downloaded: {metadata['title']}")
```

### Downloaded Files

The downloader creates the following structure:

```
output_dir/
├── videos/
│   ├── VIDEO_ID_TITLE.mp4
│   └── VIDEO_ID_metadata.json
└── subtitles/
    └── VIDEO_ID_TITLE.en.srt
```

### Troubleshooting

**Error: ffmpeg not found**
- Install ffmpeg using the commands above
- Verify installation: `ffmpeg -version`

**Error: Format not available**
- The video may have restricted formats
- Check if the video is available in your region
- Try a different video URL

## How to Add a New Feature

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Add your code in `/src/debate_analyzer/`**:
   - Create a new module or add to existing one
   - Include type hints on all functions
   - Add docstrings (Google style)

3. **Write tests in `/tests/`**:
   - Create corresponding test file: `test_<module>.py`
   - Test all functionality
   - Aim for high coverage

4. **Run code quality checks**:
   ```bash
   make all  # Runs format, lint, typecheck, and test
   ```

5. **Update documentation**:
   - Update API.md if adding public APIs
   - Update ARCHITECTURE.md if changing design
   - Update README.md if changing setup

6. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat: description of your feature"
   git push origin feature/your-feature-name
   ```

## How to Write Tests

### Basic Test Structure

```python
"""Tests for the example module."""

import pytest
from debate_analyzer.module import function_to_test


def test_basic_functionality() -> None:
    """Test basic functionality."""
    result = function_to_test("input")
    assert result == "expected"
```

### Using Fixtures

```python
import pytest


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}


def test_with_fixture(sample_data: dict) -> None:
    """Test using fixture."""
    assert sample_data["key"] == "value"
```

### Testing Exceptions

```python
import pytest


def test_exception_handling() -> None:
    """Test that function raises correct exception."""
    with pytest.raises(ValueError, match="expected error message"):
        function_that_raises()
```

### Parametrized Tests

```python
import pytest


@pytest.mark.parametrize("input,expected", [
    ("test1", "result1"),
    ("test2", "result2"),
    ("test3", "result3"),
])
def test_multiple_cases(input: str, expected: str) -> None:
    """Test multiple cases with parametrize."""
    assert process(input) == expected
```

## How to Debug Issues

### Run Specific Test
```bash
# Run single test file
poetry run pytest tests/test_example.py

# Run single test function
poetry run pytest tests/test_example.py::test_function

# Run with verbose output
poetry run pytest -vv

# Run with print statements shown
poetry run pytest -s
```

### Debug with pdb
```python
def test_with_debugging() -> None:
    """Test with breakpoint."""
    import pdb; pdb.set_trace()
    result = function_to_test()
    assert result == "expected"
```

### Check Type Errors
```bash
# Run mypy on specific file
poetry run mypy src/debate_analyzer/module.py

# Get detailed output
poetry run mypy --show-error-codes src/
```

### Check Linting Issues
```bash
# Check specific file
poetry run ruff check src/debate_analyzer/module.py

# Get detailed explanation
poetry run ruff check --show-fixes src/
```

## How to Add Dependencies

### Production Dependency
```bash
poetry add package-name
```

### Development Dependency
```bash
poetry add --group dev package-name
```

### With Version Constraints
```bash
poetry add "package-name>=1.0,<2.0"
```

### Update Dependencies
```bash
# Update all dependencies
poetry update

# Update specific package
poetry update package-name
```

### Check for Outdated Packages
```bash
poetry show --outdated
```

## How to Release a New Version

1. **Ensure all tests pass**:
   ```bash
   make all
   ```

2. **Update version in `pyproject.toml`**:
   ```toml
   [tool.poetry]
   version = "0.2.0"  # Update this
   ```

3. **Update version in `src/debate_analyzer/__init__.py`**:
   ```python
   __version__ = "0.2.0"
   ```

4. **Update CHANGELOG** (create if needed):
   Document changes in this release

5. **Commit version bump**:
   ```bash
   git add .
   git commit -m "chore: bump version to 0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```

6. **Deploy**:
   ```bash
   make deploy
   ```

## How to Set Up Pre-commit Hooks

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running pre-commit checks..."
make all
if [ $? -ne 0 ]; then
    echo "Pre-commit checks failed. Commit aborted."
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## How to Generate Documentation

### Using pdoc (optional)
```bash
poetry add --group dev pdoc

# Generate HTML docs
poetry run pdoc src/debate_analyzer -o docs/html

# Serve docs locally
poetry run pdoc src/debate_analyzer
```

## Troubleshooting Common Issues

### Poetry Lock Issues
```bash
poetry lock --no-update
```

### Virtual Environment Corruption
```bash
make reset_venv
```

### Import Errors in Tests
Ensure you're running tests through Poetry:
```bash
poetry run pytest  # Correct
pytest            # May not work if venv not activated
```

### Coverage Not Working
```bash
# Clear coverage data
rm -rf .coverage htmlcov/

# Run tests again
make test
```
