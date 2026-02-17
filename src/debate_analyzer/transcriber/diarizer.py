"""Speaker diarization using pyannote.audio."""

import os
from pathlib import Path
from typing import Optional, Union

import soundfile as sf  # type: ignore[import-untyped]
import torch
from pyannote.audio import Pipeline  # type: ignore[import-untyped]

from debate_analyzer.transcriber.models import SpeakerSegment


class DiarizationError(Exception):
    """Exception raised when speaker diarization fails."""

    pass


class SpeakerDiarizer:
    """Identifies speakers in audio using pyannote.audio."""

    def __init__(
        self,
        hf_token: Optional[str] = None,
        pipeline_name: str = "pyannote/speaker-diarization-3.1",
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> None:
        """
        Initialize the speaker diarizer.

        Args:
            hf_token: HuggingFace access token. If None, reads from HF_TOKEN env var.
            pipeline_name: Name of the pyannote pipeline to use
            min_speakers: Minimum number of speakers (optional)
            max_speakers: Maximum number of speakers (optional)

        Raises:
            DiarizationError: If HF token is not provided or pipeline fails to load
        """
        # Get HuggingFace token
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")

        if not self.hf_token:
            raise DiarizationError(
                "HuggingFace token is required for speaker diarization.\n"
                "Please provide it via:\n"
                "  1. --hf-token argument, or\n"
                "  2. HF_TOKEN environment variable\n\n"
                "To get a token:\n"
                "  1. Create account at https://huggingface.co\n"
                "  2. Accept model terms at https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                "  3. Create access token at https://huggingface.co/settings/tokens\n"
                "  4. Export it: export HF_TOKEN=your_token_here"
            )

        self.pipeline_name = pipeline_name
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        try:
            # Load the pipeline
            self.pipeline = Pipeline.from_pretrained(
                pipeline_name,
                token=self.hf_token,
            )
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                raise DiarizationError(
                    f"Authentication failed with HuggingFace.\n"
                    f"Please check:\n"
                    f"  1. Your token is valid\n"
                    f"  2. You have accepted the model terms at:\n"
                    f"     https://huggingface.co/{pipeline_name}\n"
                    f"Original error: {e}"
                ) from e
            else:
                raise DiarizationError(
                    f"Failed to load diarization pipeline '{pipeline_name}': {e}"
                ) from e

    def diarize(self, audio_path: Union[str, Path]) -> list[SpeakerSegment]:
        """
        Perform speaker diarization on audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            List of speaker segments with timestamps

        Raises:
            DiarizationError: If diarization fails
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise DiarizationError(f"Audio file not found: {audio_path}")

        try:
            # Load audio into memory (workaround for torchcodec issues in pyannote 4.0)
            waveform, sample_rate = sf.read(str(audio_path))

            # Convert to torch tensor and ensure correct shape (channels, samples)
            if waveform.ndim == 1:
                # Mono audio - add channel dimension
                waveform = waveform[None, :]
            else:
                # Stereo or multi-channel - transpose to (channels, samples)
                waveform = waveform.T

            waveform_tensor = torch.from_numpy(waveform).float()

            # Create the audio dictionary format that pyannote expects
            audio_dict = {
                "waveform": waveform_tensor,
                "sample_rate": sample_rate,
            }

            # Run diarization
            diarization_params = {}
            if self.min_speakers is not None:
                diarization_params["min_speakers"] = self.min_speakers
            if self.max_speakers is not None:
                diarization_params["max_speakers"] = self.max_speakers

            diarization = self.pipeline(audio_dict, **diarization_params)

            # Convert to our data model
            speaker_segments = []

            # pyannote.audio 4.0 returns a DiarizeOutput object
            # The actual diarization is in the speaker_diarization attribute
            if hasattr(diarization, "speaker_diarization"):
                # Get the Annotation object from the DiarizeOutput
                annotation = diarization.speaker_diarization
                for turn, _, speaker in annotation.itertracks(yield_label=True):
                    speaker_segments.append(
                        SpeakerSegment(
                            start=turn.start,
                            end=turn.end,
                            speaker_id=speaker,
                        )
                    )
            elif hasattr(diarization, "segments"):
                # Alternative format with segments attribute
                for segment in diarization.segments:
                    speaker_segments.append(
                        SpeakerSegment(
                            start=segment.start,
                            end=segment.end,
                            speaker_id=segment.speaker,
                        )
                    )
            elif hasattr(diarization, "itertracks"):
                # Fallback for older API (direct Annotation object)
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    speaker_segments.append(
                        SpeakerSegment(
                            start=turn.start,
                            end=turn.end,
                            speaker_id=speaker,
                        )
                    )
            else:
                raise DiarizationError(
                    "Unsupported diarization output format. "
                    f"Available attributes: {dir(diarization)}"
                )

            # Sort by start time
            speaker_segments.sort(key=lambda x: x.start)

            return speaker_segments

        except Exception as e:
            raise DiarizationError(f"Failed to perform diarization: {e}") from e
