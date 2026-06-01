"""Central configuration for the local meeting-minutes tool.

Everything is overridable via environment variables so the same code runs on
the prototype Mac and on the Windows work machine without edits. Nothing here
points at a cloud service — transcription and summarisation are fully local.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# --- Privacy: kill pyannote.audio's phone-home telemetry BEFORE it is imported.
# pyannote.audio 4.x ships with metrics ENABLED by default, POSTing usage
# metadata (file duration, speaker count, a session UUID, library version) to
# https://otel.pyannote.ai on every diarization. No audio/transcript content is
# sent, but for a fully-local clinical tool no outbound call is acceptable.
# config.py is imported before anything pulls in whisperx/pyannote, so setting
# this here disables it. setdefault => the user can still opt in by exporting
# PYANNOTE_METRICS_ENABLED=true themselves.
os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "false")
# Belt-and-suspenders: disable the OpenTelemetry SDK globally too.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("MM_DATA_DIR", BASE_DIR / "recordings"))
OUTPUT_DIR = Path(os.getenv("MM_OUTPUT_DIR", BASE_DIR / "minutes"))


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # ---- Audio capture ----
    # Target sample rate fed to Whisper. 16 kHz mono is what the model wants;
    # capturing straight to it avoids a separate resample step.
    sample_rate: int = int(os.getenv("MM_SAMPLE_RATE", "16000"))
    # Capture the local microphone (your own voice) in addition to system
    # audio (everyone else in the call). Both are mixed into one track.
    capture_mic: bool = _bool("MM_CAPTURE_MIC", True)
    capture_system: bool = _bool("MM_CAPTURE_SYSTEM", True)

    # ---- Transcription (WhisperX) ----
    # large-v3 = best accuracy on clinical terms; "medium" is ~2x faster and
    # lighter if the machine struggles. "small"/"base" for quick tests.
    whisper_model: str = os.getenv("MM_WHISPER_MODEL", "large-v3")
    # None = auto-detect. Set "en" or "de" to pin it (faster, more reliable
    # for a known-language institute).
    language: str | None = os.getenv("MM_LANGUAGE") or None
    # "int8" runs on CPU and is the safe default. Use "float16" only on an
    # NVIDIA GPU; "int8_float16" is a good GPU/CPU hybrid.
    compute_type: str = os.getenv("MM_COMPUTE_TYPE", "int8")
    device: str = os.getenv("MM_DEVICE", "cpu")  # "cuda" if she has an NVIDIA GPU

    # ---- Speaker diarization (pyannote, via WhisperX) ----
    diarize: bool = _bool("MM_DIARIZE", True)
    # pyannote's pretrained models are gated on Hugging Face: create a free
    # account, accept the terms for pyannote/speaker-diarization-3.1 and
    # pyannote/segmentation-3.0, then put your token here or in MM_HF_TOKEN.
    # Without it the tool still works — it just won't label speakers.
    hf_token: str | None = os.getenv("MM_HF_TOKEN") or None
    # Which pyannote pipeline to use. whisperx 3.8 + pyannote.audio 4.x require
    # "speaker-diarization-community-1" (even loading the older "3.1" pipeline
    # pulls a community-1 asset under pyannote 4.x). Accept its terms at
    # https://hf.co/pyannote/speaker-diarization-community-1. Override if needed.
    diarize_model: str = os.getenv(
        "MM_DIARIZE_MODEL", "pyannote/speaker-diarization-community-1"
    )
    min_speakers: int | None = (
        int(os.environ["MM_MIN_SPEAKERS"]) if os.getenv("MM_MIN_SPEAKERS") else None
    )
    max_speakers: int | None = (
        int(os.environ["MM_MAX_SPEAKERS"]) if os.getenv("MM_MAX_SPEAKERS") else None
    )

    # ---- Summarisation (local LLM via Ollama) ----
    ollama_host: str = os.getenv("MM_OLLAMA_HOST", "http://localhost:11434")
    # Summarising a transcript is an easy task — a general 7B model does it
    # well. On the 8GB prototype Mac only qwen2.5-coder:3b is installed, so
    # that's the fallback default; override on the work machine.
    summary_model: str = os.getenv("MM_SUMMARY_MODEL", "qwen2.5-coder:3b")

    glossary_path: Path = field(
        default_factory=lambda: Path(os.getenv("MM_GLOSSARY", BASE_DIR / "glossary.txt"))
    )

    def glossary(self) -> str:
        try:
            return self.glossary_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""

    def glossary_terms(self) -> list[str]:
        """Glossary as a flat list of terms (one per non-comment line)."""
        terms: list[str] = []
        for line in self.glossary().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
        return terms


def load() -> Config:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return Config()
