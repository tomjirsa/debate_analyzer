# API Reference

## Overview

This document provides API reference documentation for the Debate Analyzer project.

## System Requirements

Some components require system-level dependencies:

- **ffmpeg**: Required by `video_downloader` module for processing and merging video/audio streams
  - Installation: See [README.md](../README.md#prerequisites) for platform-specific instructions
  - Verify: Run `ffmpeg -version` to confirm installation

## Modules

### debate_analyzer

Main package module.

#### Attributes

- `__version__`: Package version string

## Core Modules

### video_downloader

Module for downloading YouTube videos and subtitles using yt-dlp.

#### Classes

##### VideoDownloader

Downloads YouTube videos and subtitles with automatic directory management.

**Constructor:**

```python
VideoDownloader(output_dir: str | Path) -> None
```

**Parameters:**
- `output_dir`: Directory where videos and subtitles will be saved. Creates `videos/` and `subtitles/` subdirectories automatically.

**Methods:**

`validate_url(url: str) -> bool`

Validates if a URL is a valid YouTube URL.

- **Args:**
  - `url`: URL string to validate
- **Returns:** `True` if valid YouTube URL, `False` otherwise
- **Supported formats:**
  - `https://www.youtube.com/watch?v=VIDEO_ID`
  - `https://youtu.be/VIDEO_ID`
  - `https://www.youtube.com/embed/VIDEO_ID`
  - `https://www.youtube-nocookie.com/embed/VIDEO_ID`

`download(url: str) -> dict[str, Any]`

Downloads video and subtitles from a YouTube URL.

- **Args:**
  - `url`: YouTube video URL
- **Returns:** Dictionary containing:
  - `video_id`: YouTube video ID
  - `title`: Video title
  - `video_path`: Path to downloaded video file
  - `subtitle_paths`: List of paths to downloaded subtitle files
  - `duration`: Video duration in seconds
  - `uploader`: Channel name
  - `url`: Original URL
- **Raises:**
  - `VideoDownloadError`: If URL is invalid or download fails

**Example:**

```python
from debate_analyzer.video_downloader import VideoDownloader

downloader = VideoDownloader("my_data")
metadata = downloader.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(f"Downloaded: {metadata['title']}")
print(f"Video saved to: {metadata['video_path']}")
print(f"Subtitles: {metadata['subtitle_paths']}")
```

#### Functions

##### download_video

Convenience function for downloading YouTube videos.

```python
download_video(url: str, output_dir: str | Path = "data") -> dict[str, Any]
```

**Parameters:**
- `url`: YouTube video URL
- `output_dir`: Directory where videos will be saved (default: `"data"`)

**Returns:** Same dictionary as `VideoDownloader.download()`

**Raises:**
- `VideoDownloadError`: If URL is invalid or download fails

**Example:**

```python
from debate_analyzer.video_downloader import download_video

# Download to default data/ directory
metadata = download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Download to custom directory
metadata = download_video(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="custom_folder"
)
```

#### Exceptions

##### VideoDownloadError

Exception raised when video download fails.

**Inherits from:** `Exception`

**Common causes:**
- Invalid YouTube URL
- Network connectivity issues
- Video unavailable or private
- Geographically restricted content
- Age-restricted content without authentication

#### Download Behavior

The video downloader:
1. Creates `videos/` and `subtitles/` subdirectories in the output directory
2. Downloads video in best available quality (prefers MP4 format)
3. Downloads English subtitles (native or auto-generated)
4. Converts subtitles to SRT format
5. Saves metadata to JSON file (`VIDEO_ID_metadata.json`)
6. Uses filename template: `VIDEO_ID_TITLE.EXT`

#### CLI Usage

Download videos via command line:

```bash
# Download to default data/ directory
python -m debate_analyzer.download_video "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download to custom directory
python -m debate_analyzer.download_video "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output-dir ./my_videos
```

### transcriber

Module for transcribing videos with speaker identification using faster-whisper and pyannote.audio.

#### Classes

##### AudioExtractor

Extracts audio from video files using FFmpeg.

**Constructor:**

```python
AudioExtractor(sample_rate: int = 16000, channels: int = 1) -> None
```

**Parameters:**
- `sample_rate`: Output audio sample rate in Hz (default: 16000)
- `channels`: Number of audio channels, 1 for mono, 2 for stereo (default: 1)

**Methods:**

`extract_audio(video_path: str | Path, output_path: str | Path | None = None) -> Path`

Extracts audio from video file using FFmpeg.

- **Args:**
  - `video_path`: Path to input video or audio file
  - `output_path`: Path for output audio file (optional, creates temp file if None)
- **Returns:** Path to the extracted audio file (WAV format)
- **Raises:**
  - `AudioExtractionError`: If FFmpeg is not available or extraction fails

##### WhisperTranscriber

Transcribes audio using faster-whisper.

**Constructor:**

```python
WhisperTranscriber(
    model_size: str = "medium",
    device: str = "auto",
    compute_type: str = "float16",
    language: str | None = None
) -> None
```

**Parameters:**
- `model_size`: Whisper model size (tiny, base, small, medium, large, large-v2, large-v3)
- `device`: Device to use ('auto', 'cpu', or 'cuda')
- `compute_type`: Computation type ('float16', 'int8', 'float32')
- `language`: Language code (e.g., 'en', 'es'). None for auto-detection.

**Methods:**

`transcribe(audio_path: str | Path) -> list[TranscriptSegment]`

Transcribes audio file to text with timestamps.

- **Args:**
  - `audio_path`: Path to audio file
- **Returns:** List of transcript segments with start/end times and text
- **Raises:**
  - `TranscriptionError`: If transcription fails

##### SpeakerDiarizer

Identifies speakers in audio using pyannote.audio.

**Constructor:**

```python
SpeakerDiarizer(
    hf_token: str | None = None,
    pipeline_name: str = "pyannote/speaker-diarization-3.1",
    min_speakers: int | None = None,
    max_speakers: int | None = None
) -> None
```

**Parameters:**
- `hf_token`: HuggingFace access token (reads from HF_TOKEN env var if None)
- `pipeline_name`: Name of the pyannote pipeline to use
- `min_speakers`: Minimum number of speakers (optional constraint)
- `max_speakers`: Maximum number of speakers (optional constraint)

**Methods:**

`diarize(audio_path: str | Path) -> list[SpeakerSegment]`

Performs speaker diarization on audio file.

- **Args:**
  - `audio_path`: Path to audio file
- **Returns:** List of speaker segments with start/end times and speaker IDs
- **Raises:**
  - `DiarizationError`: If diarization fails or HF token is invalid

##### TranscriptMerger

Merges transcription segments with speaker labels.

**Methods:**

`merge(transcript_segments: list[TranscriptSegment], speaker_segments: list[SpeakerSegment]) -> list[TranscriptWithSpeaker]`

Merges transcription with speaker labels based on timestamp overlap.

- **Args:**
  - `transcript_segments`: List of transcript segments from Whisper
  - `speaker_segments`: List of speaker segments from pyannote
- **Returns:** List of merged segments with both text and speaker labels

#### Functions

##### transcribe_video

Main API function for transcribing videos with speaker identification.

```python
transcribe_video(
    video_path: str | Path,
    output_dir: str | Path = "data/transcripts",
    model_size: str = "medium",
    device: str = "auto",
    hf_token: str | None = None,
    config_path: str | Path | None = None,
    language: str | None = None
) -> dict[str, Any]
```

**Parameters:**
- `video_path`: Path to video file
- `output_dir`: Directory to save outputs (default: "data/transcripts")
- `model_size`: Whisper model size (default: "medium")
- `device`: Device to use ('auto', 'cpu', or 'cuda')
- `hf_token`: HuggingFace token for pyannote (or use HF_TOKEN env var)
- `config_path`: Path to custom configuration file (optional)
- `language`: Language code for transcription (e.g., 'en', 'es'). Auto-detected if None.

**Returns:** Dictionary containing:
- `video_path`: Path to input video
- `audio_path`: Path to extracted audio
- `duration`: Duration in seconds
- `processing_time`: Total processing time in seconds
- `model`: Dictionary with model information
- `speakers_count`: Number of unique speakers detected
- `transcription`: List of transcript segments with speaker labels
- `output_path`: Path to output JSON file

**Raises:**
- `TranscriptionError`: If transcription fails

**Example:**

```python
from debate_analyzer.transcriber import transcribe_video

# Basic usage
result = transcribe_video("data/videos/debate.mp4")

print(f"Found {result['speakers_count']} speakers")
print(f"Duration: {result['duration']:.2f} seconds")

# Access transcription segments
for segment in result['transcription']:
    print(f"[{segment['start']:.2f}s] {segment['speaker']}: {segment['text']}")
```

#### Data Models

##### TranscriptSegment

A segment of transcribed text with timestamps.

**Attributes:**
- `start`: float - Start time in seconds
- `end`: float - End time in seconds
- `text`: str - Transcribed text

##### SpeakerSegment

A segment identified with a speaker label.

**Attributes:**
- `start`: float - Start time in seconds
- `end`: float - End time in seconds
- `speaker_id`: str - Speaker identifier (e.g., "SPEAKER_00")

##### TranscriptWithSpeaker

A transcribed segment with speaker identification.

**Attributes:**
- `start`: float - Start time in seconds
- `end`: float - End time in seconds
- `text`: str - Transcribed text
- `speaker`: str - Speaker identifier
- `confidence`: float - Confidence score (0.0-1.0)

#### Exceptions

##### AudioExtractionError

Exception raised when audio extraction fails.

**Inherits from:** `Exception`

**Common causes:**
- FFmpeg not installed or not in PATH
- Invalid video file format
- Corrupted video file
- Insufficient disk space

##### TranscriptionError

Exception raised when transcription fails.

**Inherits from:** `Exception`

**Common causes:**
- Whisper model download failed
- Invalid audio file
- Insufficient memory
- CUDA errors (if using GPU)

##### DiarizationError

Exception raised when speaker diarization fails.

**Inherits from:** `Exception`

**Common causes:**
- Missing or invalid HuggingFace token
- Model terms not accepted
- Network issues during model download
- Invalid audio file format

#### Setup Requirements

**HuggingFace Token:**

Speaker diarization requires a HuggingFace account and token:

1. Create account at [huggingface.co](https://huggingface.co)
2. Accept model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Create access token at [settings/tokens](https://huggingface.co/settings/tokens)
4. Set environment variable: `export HF_TOKEN=your_token_here`

#### CLI Usage

Transcribe videos via command line:

```bash
# Basic usage
python -m debate_analyzer.transcriber video.mp4

# Specify output directory
python -m debate_analyzer.transcriber video.mp4 --output-dir transcripts

# Use different model size
python -m debate_analyzer.transcriber video.mp4 --model-size large

# Provide HuggingFace token
python -m debate_analyzer.transcriber video.mp4 --hf-token YOUR_TOKEN

# Specify language
python -m debate_analyzer.transcriber video.mp4 --language en
```

### Example Module Structure

```python
"""
module_name
-----------

Brief description of the module.

Functions:
    function_name: Brief description

Classes:
    ClassName: Brief description
"""
```

## Usage Examples

### Basic Usage

```python
from debate_analyzer import example

# Example usage here
```

## API Conventions

### Type Hints
All public functions and methods use type hints:

```python
def process_data(input_data: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Process input data with optional configuration.
    
    Args:
        input_data: The data to process
        options: Optional configuration dictionary
        
    Returns:
        Dictionary containing processed results
        
    Raises:
        ValueError: If input_data is empty
    """
```

### Docstring Format
We use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief one-line description.
    
    Longer description if needed, explaining the purpose,
    behavior, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: Description of when this is raised
        
    Example:
        >>> function_name("test", 42)
        True
    """
```

## Error Handling

[Document common exceptions and error handling patterns]

## Best Practices

1. **Type Safety**: Always use type hints
2. **Documentation**: Document all public APIs
3. **Error Handling**: Use specific exceptions
4. **Validation**: Validate inputs early
5. **Immutability**: Prefer immutable data structures when possible
