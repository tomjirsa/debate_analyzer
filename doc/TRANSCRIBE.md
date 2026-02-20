# Transcribe Module

The transcriber module provides **speech-to-text** (faster-whisper) and **speaker diarization** (pyannote.audio) for video files. It produces a JSON transcript with segments and speaker IDs (e.g. `SPEAKER_00`, `SPEAKER_01`).

For annotating speaker IDs with real names or speaker profiles (first name, surname; standalone tool or web app), see [HOWTO.md](HOWTO.md#how-to-annotate-speaker-names) and [WEBAPP.md](WEBAPP.md). For running transcription on AWS Batch, see [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md) and [AWS_SETUP.md](AWS_SETUP.md).

---

## Prerequisites

1. **FFmpeg** — Required for audio extraction from video.
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt-get install ffmpeg`
   - Verify: `ffmpeg -version`

2. **HuggingFace account and token** — Required for pyannote speaker diarization.
   - Create account at [huggingface.co](https://huggingface.co).
   - Accept model terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1).
   - Create access token at [settings/tokens](https://huggingface.co/settings/tokens).
   - Set: `export HF_TOKEN=your_token_here` (or pass `--hf-token` to the CLI).

3. **Install dependencies** — Install the transcribe extra:
   ```bash
   poetry install --extras transcribe
   ```

---

## CLI Usage

Run the transcriber as a module:

```bash
# Basic usage (medium model, auto device)
poetry run python -m debate_analyzer.transcriber video.mp4

# Output directory
poetry run python -m debate_analyzer.transcriber video.mp4 --output-dir my_transcripts

# Model size: tiny, base, small, medium, large, large-v2, large-v3
poetry run python -m debate_analyzer.transcriber video.mp4 --model-size large

# Device: auto, cpu, cuda
poetry run python -m debate_analyzer.transcriber video.mp4 --device cuda

# HuggingFace token (if not in HF_TOKEN env)
poetry run python -m debate_analyzer.transcriber video.mp4 --hf-token YOUR_TOKEN

# Language (e.g. en, es, fr); auto-detected if omitted
poetry run python -m debate_analyzer.transcriber video.mp4 --language en

# Custom config file
poetry run python -m debate_analyzer.transcriber video.mp4 --config path/to/config.json
```

---

## Python API

**Main function: `transcribe_video()`**

```python
from debate_analyzer.transcriber import transcribe_video

result = transcribe_video(
    video_path="path/to/video.mp4",
    output_dir="data/transcripts",
    model_size="medium",
    device="auto",
    hf_token=None,       # or set HF_TOKEN env
    config_path=None,
    language=None,       # e.g. "en" for English
)

# result keys: video_path, audio_path, duration, processing_time, model,
#              speakers_count, transcription, output_path
print(f"Speakers: {result['speakers_count']}, Duration: {result['duration']:.2f}s")
for seg in result["transcription"]:
    print(f"[{seg['start']:.2f}s] {seg['speaker']}: {seg['text']}")
```

**Lower-level components** (for custom pipelines):

- `AudioExtractor` — Extract audio from video to WAV.
- `WhisperTranscriber` — Speech-to-text only (no diarization).
- `SpeakerDiarizer` — Speaker diarization (pyannote).
- `TranscriptMerger` — Merge Whisper segments with diarization.

Example: transcribe without diarization (Whisper only):

```python
from debate_analyzer.transcriber import AudioExtractor, WhisperTranscriber

extractor = AudioExtractor(sample_rate=16000, channels=1)
audio_path = extractor.extract_audio("video.mp4", "output.wav")

transcriber = WhisperTranscriber(model_size="medium")
segments = transcriber.transcribe(audio_path)
for seg in segments:
    print(f"[{seg.start:.2f}s] {seg.text}")
```

---

## Output Format

**Output directory layout:**

```
output_dir/
├── <basename>_audio.wav           # Extracted audio (16 kHz mono WAV)
└── <basename>_transcription.json  # Transcription with speakers
```

**JSON structure:**

- `video_path` — Input video path.
- `audio_path` — Path to extracted audio WAV.
- `duration` — Video/audio duration in seconds.
- `processing_time` — Total processing time in seconds.
- `model` — e.g. `{"whisper": "medium", "diarization": "pyannote/speaker-diarization-3.1"}`.
- `speakers_count` — Number of unique speakers.
- `transcription` — List of segments; each segment:
  - `start`, `end` — Time range in seconds.
  - `text` — Transcribed text.
  - `speaker` — Speaker ID (e.g. `SPEAKER_00`).
  - `confidence` — Optional confidence score.
- `output_path` — Path to the saved JSON file (in the returned dict).

---

## Performance

- **First run:** Downloads Whisper model (~5 GB for medium) and pyannote models (~1 GB); cached for later runs.
- **Processing time:** Roughly 1–2× real time with the medium model (e.g. 10 min video ≈ 10–20 min).
- **Resources:** ~4–8 GB RAM; if using GPU, ~3–6 GB VRAM.
- **Model sizes:** `tiny` (fastest, least accurate) through `large` / `large-v3` (slowest, best accuracy). Default is `medium`.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| HuggingFace token required | Set `HF_TOKEN` or pass `--hf-token`. Accept pyannote model terms at the link above. |
| FFmpeg not found | Install ffmpeg; verify with `ffmpeg -version`. |
| CUDA out of memory | Use `--model-size small` or `--device cpu`. |
| Poor quality | Try `--model-size large`, `--language en`, and ensure good audio. |
| Speaker IDs arbitrary | Speaker IDs are not stable across videos. Use the web app or standalone annotator to map them to speaker profiles (first name, surname) or names; see [HOWTO](HOWTO.md#how-to-annotate-speaker-names). |

---

## See Also

- [HOWTO.md](HOWTO.md) — Download videos, annotate speaker names, add features, tests.
- [WEBAPP.md](WEBAPP.md) — Web app and admin annotation at `/admin/annotate`.
- [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md) — Run transcribe job on AWS Batch.
- [AWS_SETUP.md](AWS_SETUP.md) — Full AWS setup guide.
