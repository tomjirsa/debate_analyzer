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
