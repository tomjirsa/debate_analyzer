"""Tests for video_downloader module."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yt_dlp
from debate_analyzer.video_downloader import (
    VideoDownloader,
    VideoDownloadError,
    download_video,
)


class TestVideoDownloader:
    """Tests for VideoDownloader class."""

    def test_init_creates_directories(self, tmp_path: Path) -> None:
        """Test that VideoDownloader creates necessary directories."""
        output_dir = tmp_path / "test_output"
        downloader = VideoDownloader(output_dir)

        assert downloader.output_dir == output_dir
        assert downloader.videos_dir.exists()
        assert downloader.subtitles_dir.exists()
        assert downloader.videos_dir == output_dir / "videos"
        assert downloader.subtitles_dir == output_dir / "subtitles"

    def test_init_with_existing_directories(self, tmp_path: Path) -> None:
        """Test that VideoDownloader works with existing directories."""
        output_dir = tmp_path / "existing"
        output_dir.mkdir(parents=True)
        (output_dir / "videos").mkdir()
        (output_dir / "subtitles").mkdir()

        downloader = VideoDownloader(output_dir)

        assert downloader.videos_dir.exists()
        assert downloader.subtitles_dir.exists()

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
            ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", True),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", True),
            ("https://www.example.com/video", False),
            ("not a url", False),
            ("https://vimeo.com/123456", False),
            ("", False),
            ("https://www.youtube.com/watch?v=invalid", False),
        ],
    )
    def test_validate_url(self, tmp_path: Path, url: str, expected: bool) -> None:
        """Test URL validation for various YouTube URL formats."""
        downloader = VideoDownloader(tmp_path)
        assert downloader.validate_url(url) == expected

    def test_download_with_invalid_url(self, tmp_path: Path) -> None:
        """Test that download raises error for invalid URL."""
        downloader = VideoDownloader(tmp_path)

        with pytest.raises(VideoDownloadError, match="Invalid YouTube URL"):
            downloader.download("https://www.example.com/video")

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_success(self, mock_ytdl_class: MagicMock, tmp_path: Path) -> None:
        """Test successful video download with metadata."""
        # Mock yt-dlp instance
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl

        # Mock video info
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "duration": 212,
            "uploader": "Test Channel",
            "ext": "mp4",
        }
        mock_ytdl.extract_info.return_value = mock_info

        # Create downloader and download
        downloader = VideoDownloader(tmp_path)

        # Create mock video file (downloader uses template title_id.ext)
        video_file = downloader.videos_dir / "Test Video_dQw4w9WgXcQ.mp4"
        video_file.touch()

        # Create mock subtitle file (downloader globs *_video_id.srt)
        subtitle_file = downloader.subtitles_dir / "Test Video_dQw4w9WgXcQ.srt"
        subtitle_file.touch()

        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch("builtins.open", mock_open()) as mock_file:
            metadata = downloader.download(url)

        # Verify yt-dlp was called correctly
        mock_ytdl.extract_info.assert_called_once_with(url, download=True)

        # Verify metadata
        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["title"] == "Test Video"
        assert metadata["duration"] == 212
        assert metadata["uploader"] == "Test Channel"
        assert metadata["url"] == url
        assert "Test Video_dQw4w9WgXcQ.mp4" in metadata["video_path"]

        # Verify metadata file was written
        mock_file.assert_called_once()
        call_args = mock_file.call_args
        assert "dQw4w9WgXcQ_metadata.json" in str(call_args[0][0])

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_extract_info_returns_none(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that download handles None response from extract_info."""
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
        mock_ytdl.extract_info.return_value = None

        downloader = VideoDownloader(tmp_path)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with pytest.raises(VideoDownloadError, match="Failed to extract video info"):
            downloader.download(url)

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_handles_download_error(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that download handles yt-dlp DownloadError."""
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
        mock_ytdl.extract_info.side_effect = yt_dlp.utils.DownloadError("Network error")

        downloader = VideoDownloader(tmp_path)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with pytest.raises(VideoDownloadError, match="Failed to download video"):
            downloader.download(url)

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_handles_unexpected_error(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that download handles unexpected exceptions."""
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl
        mock_ytdl.extract_info.side_effect = RuntimeError("Unexpected error")

        downloader = VideoDownloader(tmp_path)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with pytest.raises(
            VideoDownloadError, match="Unexpected error during download"
        ):
            downloader.download(url)

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_collects_subtitle_files(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that download collects all subtitle files."""
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl

        video_id = "dQw4w9WgXcQ"
        mock_info = {
            "id": video_id,
            "title": "Test",
            "duration": 100,
            "uploader": "Tester",
            "ext": "mp4",
        }
        mock_ytdl.extract_info.return_value = mock_info

        downloader = VideoDownloader(tmp_path)

        # Create mock subtitle files (downloader globs *_video_id.srt / *_video_id.vtt)
        (downloader.subtitles_dir / f"en_{video_id}.srt").touch()
        (downloader.subtitles_dir / f"es_{video_id}.srt").touch()
        (downloader.subtitles_dir / f"fr_{video_id}.vtt").touch()

        # Create mock video file (downloader uses template title_id.ext)
        (downloader.videos_dir / f"Test_{video_id}.mp4").touch()

        url = f"https://www.youtube.com/watch?v={video_id}"

        with patch("builtins.open", mock_open()):
            metadata = downloader.download(url)

        # Should find all 3 subtitle files
        assert len(metadata["subtitle_paths"]) == 3
        assert any(f"en_{video_id}.srt" in path for path in metadata["subtitle_paths"])
        assert any(f"es_{video_id}.srt" in path for path in metadata["subtitle_paths"])
        assert any(f"fr_{video_id}.vtt" in path for path in metadata["subtitle_paths"])

    @patch("debate_analyzer.video_downloader.downloader.yt_dlp.YoutubeDL")
    def test_download_handles_missing_optional_fields(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that download handles missing optional metadata fields."""
        mock_ytdl = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_ytdl

        # Minimal info dict
        mock_info: dict[str, str] = {}
        mock_ytdl.extract_info.return_value = mock_info

        downloader = VideoDownloader(tmp_path)

        # Create mock video file with default names
        (downloader.videos_dir / "unknown_unknown.mp4").touch()

        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch("builtins.open", mock_open()):
            metadata = downloader.download(url)

        # Should use default values
        assert metadata["video_id"] == "unknown"
        assert metadata["title"] == "unknown"
        assert metadata["duration"] == 0
        assert metadata["uploader"] == "unknown"


class TestDownloadVideoFunction:
    """Tests for the download_video convenience function."""

    @patch("debate_analyzer.video_downloader.downloader.VideoDownloader")
    def test_download_video_with_defaults(
        self, mock_downloader_class: MagicMock
    ) -> None:
        """Test download_video function with default parameters."""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download.return_value = {"video_id": "test123"}

        url = "https://www.youtube.com/watch?v=test123"
        result = download_video(url)

        mock_downloader_class.assert_called_once_with("data", config_path=None)
        mock_downloader.download.assert_called_once_with(url, download_subtitles=True)
        assert result == {"video_id": "test123"}

    @patch("debate_analyzer.video_downloader.downloader.VideoDownloader")
    def test_download_video_with_custom_output_dir(
        self, mock_downloader_class: MagicMock
    ) -> None:
        """Test download_video function with custom output directory."""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download.return_value = {"video_id": "test123"}

        url = "https://www.youtube.com/watch?v=test123"
        output_dir = "/custom/path"
        result = download_video(url, output_dir)

        mock_downloader_class.assert_called_once_with(output_dir, config_path=None)
        mock_downloader.download.assert_called_once_with(url, download_subtitles=True)
        assert result == {"video_id": "test123"}

    @patch("debate_analyzer.video_downloader.downloader.VideoDownloader")
    def test_download_video_propagates_errors(
        self, mock_downloader_class: MagicMock
    ) -> None:
        """Test that download_video propagates errors from VideoDownloader."""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download.side_effect = VideoDownloadError("Test error")

        url = "https://www.youtube.com/watch?v=test123"

        with pytest.raises(VideoDownloadError, match="Test error"):
            download_video(url)
