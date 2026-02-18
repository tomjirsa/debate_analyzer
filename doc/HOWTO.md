# How-To Guides

This document contains step-by-step guides for common tasks in the Debate Analyzer project.

## Table of Contents
- [How to Download YouTube Videos](#how-to-download-youtube-videos)
- [How to Transcribe Videos with Speaker Identification](#how-to-transcribe-videos-with-speaker-identification)
- [How to Annotate Speaker Names](#how-to-annotate-speaker-names)
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

## How to Transcribe Videos with Speaker Identification

The transcriber module provides state-of-the-art speech-to-text transcription with automatic speaker identification using open-source models (faster-whisper + pyannote.audio).

### Prerequisites

1. **FFmpeg** (required for audio extraction):
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # Verify installation
   ffmpeg -version
   ```

2. **HuggingFace Account and Token** (required for speaker diarization):
   
   a. Create a free account at [huggingface.co](https://huggingface.co)
   
   b. Accept the model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   
   c. Create an access token at [settings/tokens](https://huggingface.co/settings/tokens)
   
   d. Set the environment variable:
   ```bash
   export HF_TOKEN=your_token_here
   
   # Or add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
   echo 'export HF_TOKEN=your_token_here' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **Install Dependencies**:
   ```bash
   poetry install
   ```

### Using the Command-Line Interface

**Basic Usage:**

```bash
# Transcribe a video (uses medium Whisper model)
poetry run python -m debate_analyzer.transcriber video.mp4

# Specify output directory
poetry run python -m debate_analyzer.transcriber video.mp4 --output-dir my_transcripts

# Use different Whisper model size
# Available: tiny, base, small, medium, large, large-v2, large-v3
poetry run python -m debate_analyzer.transcriber video.mp4 --model-size large

# Provide HuggingFace token directly (if not in environment)
poetry run python -m debate_analyzer.transcriber video.mp4 --hf-token YOUR_TOKEN

# Specify language for better accuracy (auto-detected if not specified)
poetry run python -m debate_analyzer.transcriber video.mp4 --language en

# Force CPU processing (even if GPU is available)
poetry run python -m debate_analyzer.transcriber video.mp4 --device cpu
```

**Model Size Selection:**

Choose based on your needs:
- `tiny`: Fastest, lowest accuracy (~1GB RAM, ~0.5x real-time)
- `base`: Fast, good for simple speech (~1GB RAM, ~0.7x real-time)
- `small`: Balanced for basic use (~2GB RAM, ~1x real-time)
- `medium`: Recommended for most use cases (~5GB RAM, ~2x real-time) **[DEFAULT]**
- `large`: Best accuracy, slower (~10GB RAM, ~3x real-time)
- `large-v2`, `large-v3`: Latest versions of large model

### Using Python Code

**Option 1: Simple Transcription**

```python
from debate_analyzer.transcriber import transcribe_video

# Basic usage with defaults
result = transcribe_video("data/videos/debate.mp4")

print(f"Found {result['speakers_count']} speakers")
print(f"Duration: {result['duration']:.2f} seconds")
print(f"Processing time: {result['processing_time']:.2f} seconds")

# Access transcription segments
for segment in result['transcription']:
    speaker = segment['speaker']
    text = segment['text']
    start = segment['start']
    end = segment['end']
    confidence = segment['confidence']
    
    print(f"[{start:.2f}s - {end:.2f}s] {speaker} (conf: {confidence:.2f}): {text}")
```

**Option 2: Custom Configuration**

```python
from debate_analyzer.transcriber import transcribe_video

result = transcribe_video(
    video_path="data/videos/debate.mp4",
    output_dir="custom_transcripts",
    model_size="large",  # Use large model for best accuracy
    device="cuda",       # Force GPU usage
    language="en",       # Specify English
    hf_token="your_hf_token_if_not_in_env"
)

# Save specific speaker's text to file
speaker_0_text = [
    seg['text'] for seg in result['transcription']
    if seg['speaker'] == 'SPEAKER_00'
]

with open('speaker_0_transcript.txt', 'w') as f:
    f.write('\n'.join(speaker_0_text))
```

**Option 3: Processing Multiple Videos**

```python
from pathlib import Path
from debate_analyzer.transcriber import transcribe_video

video_dir = Path("data/videos")
output_dir = Path("data/transcripts")

for video_file in video_dir.glob("*.mp4"):
    print(f"Processing: {video_file.name}")
    
    try:
        result = transcribe_video(
            video_path=video_file,
            output_dir=output_dir,
            model_size="medium"
        )
        print(f"  ✓ Completed: {result['speakers_count']} speakers found")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
```

### Output Format

Transcriptions are saved as JSON files in the output directory:

**File Structure:**
```
output_dir/
├── video_name_audio.wav         # Extracted audio (16kHz mono WAV)
└── video_name_transcription.json # Transcription with speakers
```

**JSON Format:**
```json
{
  "video_path": "data/videos/debate.mp4",
  "audio_path": "data/transcripts/debate_audio.wav",
  "duration": 1234.56,
  "processing_time": 892.12,
  "model": {
    "whisper": "medium",
    "diarization": "pyannote/speaker-diarization-3.1"
  },
  "speakers_count": 3,
  "transcription": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Hello and welcome to the debate.",
      "speaker": "SPEAKER_00",
      "confidence": 0.95
    },
    {
      "start": 3.8,
      "end": 8.2,
      "text": "Thank you for having me here today.",
      "speaker": "SPEAKER_01",
      "confidence": 0.92
    }
  ]
}
```

### Working with Output Data

**Load and Analyze Transcription:**

```python
import json
from collections import Counter

# Load transcription
with open('data/transcripts/debate_transcription.json') as f:
    data = json.load(f)

# Count words per speaker
speaker_words = Counter()
for segment in data['transcription']:
    speaker = segment['speaker']
    word_count = len(segment['text'].split())
    speaker_words[speaker] += word_count

print("Words spoken by each speaker:")
for speaker, count in speaker_words.most_common():
    print(f"  {speaker}: {count} words")

# Find all segments from a specific speaker
speaker_0_segments = [
    seg for seg in data['transcription']
    if seg['speaker'] == 'SPEAKER_00'
]

# Calculate total speaking time per speaker
from collections import defaultdict
speaking_time = defaultdict(float)

for segment in data['transcription']:
    duration = segment['end'] - segment['start']
    speaking_time[segment['speaker']] += duration

print("\nSpeaking time per speaker:")
for speaker, time in sorted(speaking_time.items()):
    print(f"  {speaker}: {time:.2f} seconds ({time/60:.2f} minutes)")
```

### Performance Considerations

**First Run:**
- Downloads Whisper model (~5GB for medium)
- Downloads pyannote models (~1GB)
- Models are cached for subsequent runs

**Processing Time:**
- Approximately 1-2x real-time with medium model
- Example: 10-minute video = 10-20 minutes processing
- GPU can speed up by 2-3x

**Resource Requirements:**
- **RAM**: 4-8GB depending on model size
- **VRAM** (GPU): 3-6GB if using CUDA
- **Disk Space**: Original video + extracted audio + JSON (~1MB per hour)

### Troubleshooting

**Error: HuggingFace token required**

Solution:
```bash
# Set environment variable
export HF_TOKEN=your_token_here

# Or provide directly in code
result = transcribe_video("video.mp4", hf_token="your_token")
```

**Error: FFmpeg not found**

Solution:
```bash
# Install FFmpeg
brew install ffmpeg  # macOS
sudo apt-get install ffmpeg  # Linux

# Verify installation
ffmpeg -version
```

**Error: CUDA out of memory**

Solutions:
1. Use smaller model: `--model-size small` or `--model-size base`
2. Force CPU: `--device cpu`
3. Close other GPU applications

**Error: Authentication failed with HuggingFace**

Solutions:
1. Verify token is valid at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Accept model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Create new token if needed

**Poor Transcription Quality**

Solutions:
1. Use larger model: `--model-size large`
2. Specify language: `--language en`
3. Ensure audio quality is good (check input video)
4. Try different model version: `--model-size large-v3`

**Speaker Identification Issues**

Notes:
- Speaker IDs (SPEAKER_00, SPEAKER_01, etc.) are arbitrary
- Same person might get different IDs in different videos
- Accuracy depends on:
  - Audio quality
  - Speaker voice differences
  - Background noise levels
  - Overlapping speech

**Slow Processing**

Solutions:
1. Use smaller model: `--model-size base` or `--model-size small`
2. Use GPU if available (automatic with `--device auto`)
3. Process multiple videos in parallel (separate processes)
4. Consider extracting key segments first

### Advanced Usage

**Custom Configuration File:**

Create `custom_config.json`:
```json
{
  "whisper": {
    "model_size": "large",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en"
  },
  "pyannote": {
    "pipeline": "pyannote/speaker-diarization-3.1",
    "min_speakers": 2,
    "max_speakers": 4
  },
  "audio_extraction": {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav"
  }
}
```

Use it:
```bash
poetry run python -m debate_analyzer.transcriber video.mp4 --config custom_config.json
```

**Extract Audio Only:**

```python
from debate_analyzer.transcriber import AudioExtractor

extractor = AudioExtractor(sample_rate=16000, channels=1)
audio_path = extractor.extract_audio("video.mp4", "output_audio.wav")
print(f"Audio extracted to: {audio_path}")
```

**Transcribe Without Diarization:**

```python
from debate_analyzer.transcriber import WhisperTranscriber, AudioExtractor

# Extract audio
extractor = AudioExtractor()
audio_path = extractor.extract_audio("video.mp4")

# Transcribe only (no speaker identification)
transcriber = WhisperTranscriber(model_size="medium")
segments = transcriber.transcribe(audio_path)

for seg in segments:
    print(f"[{seg.start:.2f}s] {seg.text}")
```

## How to Annotate Speaker Names

After transcribing a video, speaker IDs are generic (e.g. `SPEAKER_00`, `SPEAKER_01`). To assign real names, use the **speaker annotator** — a single HTML tool that runs in your browser (no server required).

1. **Open the tool**: Open [tool/speaker_annotator.html](../tool/speaker_annotator.html) in your browser (e.g. double-click the file or use `file://`).
2. **Load transcript and video**: Use the file inputs to select your transcript JSON (from the transcriber) and the corresponding video file.
3. **Assign names**: For each speaker ID, type the display name in the text field. The transcript list updates as you type.
4. **Use the transcript**: Click a segment to jump the video to that time. The current segment is highlighted as the video plays.
5. **Save the mapping**: Click **Save speaker mapping (download JSON)** to download a JSON file with the `speaker_mapping`. Save it next to your transcript (e.g. `debate_transcription_speaker_metadata.json`). In Chrome/Edge you can use **Save as…** to choose the path.

The metadata JSON has this structure:

```json
{
  "speaker_mapping": {
    "SPEAKER_00": "Alice",
    "SPEAKER_01": "Bob"
  },
  "updated_at": "2025-02-18T12:00:00.000Z"
}
```

You can use this file downstream to replace speaker IDs with display names when displaying or exporting the transcript.

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
