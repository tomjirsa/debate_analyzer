"""Audio extraction from video files using FFmpeg."""

import subprocess
import tempfile
from pathlib import Path
from typing import Union


class AudioExtractionError(Exception):
    """Exception raised when audio extraction fails."""

    pass


class AudioExtractor:
    """Extracts audio from video files using FFmpeg."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        """
        Initialize the audio extractor.

        Args:
            sample_rate: Output audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
        """
        self.sample_rate = sample_rate
        self.channels = channels

    def check_ffmpeg_available(self) -> bool:
        """
        Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def is_audio_file(self, file_path: Path) -> bool:
        """
        Check if the file is already an audio file.

        Args:
            file_path: Path to the file

        Returns:
            True if the file is an audio file, False otherwise
        """
        audio_extensions = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wma"}
        return file_path.suffix.lower() in audio_extensions

    def extract_audio(
        self, video_path: Union[str, Path], output_path: Union[str, Path, None] = None
    ) -> Path:
        """
        Extract audio from video file using FFmpeg.

        If the input is already an audio file, it will be re-encoded to ensure
        consistent format (WAV, 16kHz, mono).

        Args:
            video_path: Path to input video or audio file
            output_path: Path for output audio file. If None, creates temp file.

        Returns:
            Path to the extracted audio file (WAV format)

        Raises:
            AudioExtractionError: If FFmpeg is not available or extraction fails
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise AudioExtractionError(f"Input file not found: {video_path}")

        if not self.check_ffmpeg_available():
            raise AudioExtractionError(
                "FFmpeg is not installed or not available in PATH. "
                "Please install FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                "  Windows: Download from https://ffmpeg.org/download.html"
            )

        # Create output path if not provided
        if output_path is None:
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="debate_audio_"
            )
            output_path = Path(temp_file.name)
            temp_file.close()
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # FFmpeg command to extract audio
            # -i: input file
            # -ar: audio sample rate
            # -ac: audio channels (1 = mono)
            # -c:a: audio codec (pcm_s16le = uncompressed 16-bit PCM)
            # -y: overwrite output file if exists
            command = [
                "ffmpeg",
                "-i",
                str(video_path),
                "-ar",
                str(self.sample_rate),
                "-ac",
                str(self.channels),
                "-c:a",
                "pcm_s16le",
                "-y",
                str(output_path),
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                raise AudioExtractionError(
                    f"FFmpeg failed with return code {result.returncode}:\n"
                    f"{result.stderr}"
                )

            if not output_path.exists():
                raise AudioExtractionError(
                    "Audio extraction completed but output file not found"
                )

            return output_path

        except subprocess.SubprocessError as e:
            raise AudioExtractionError(f"Failed to run FFmpeg: {e}") from e
        except Exception as e:
            # Clean up output file if extraction failed
            if output_path.exists():
                output_path.unlink()
            raise AudioExtractionError(
                f"Unexpected error during extraction: {e}"
            ) from e


def extract_audio(
    video_path: Union[str, Path],
    output_path: Union[str, Path, None] = None,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """
    Extract audio from a video file.

    This is a convenience function that creates an AudioExtractor instance
    and extracts the audio.

    Args:
        video_path: Path to input video file
        output_path: Path for output audio file (optional)
        sample_rate: Output audio sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1 for mono)

    Returns:
        Path to the extracted audio file

    Raises:
        AudioExtractionError: If extraction fails

    Example:
        >>> audio_path = extract_audio("debate.mp4")
        >>> print(f"Audio extracted to: {audio_path}")
    """
    extractor = AudioExtractor(sample_rate=sample_rate, channels=channels)
    return extractor.extract_audio(video_path, output_path)
