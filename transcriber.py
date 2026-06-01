"""Local transcription + speaker diarization with WhisperX.

Pipeline (all on-device, no network except a one-time model download):
  1. faster-whisper transcribes the audio.
  2. wav2vec alignment gives accurate word timestamps.
  3. pyannote diarization labels who spoke when.
  4. Words are assigned to speakers and grouped into a readable transcript.

Diarization needs a free Hugging Face token (see config.py). Without one the
tool still transcribes — it just won't separate speakers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Turn:
    speaker: str
    text: str
    start: float
    end: float


def _initial_prompt(terms: list[str]) -> str | None:
    """Bias Whisper toward domain vocabulary so it spells rare terms right."""
    if not terms:
        return None
    # Whisper's initial_prompt is just context text; a comma list of the
    # expected jargon measurably reduces phonetic mis-transcriptions.
    return "Clinical neurology meeting. Terms may include: " + ", ".join(terms) + "."


def transcribe(audio_path: str | Path, cfg) -> list[Turn]:
    try:
        import whisperx
    except Exception as e:
        raise RuntimeError(
            "WhisperX is not installed.\n"
            "Install it with:  pip install whisperx\n"
            f"(import error: {e})"
        )

    audio_path = str(audio_path)
    print(f"  Loading Whisper model '{cfg.whisper_model}' on {cfg.device}…")

    asr_options = {}
    prompt = _initial_prompt(cfg.glossary_terms())
    if prompt:
        asr_options["initial_prompt"] = prompt

    model = whisperx.load_model(
        cfg.whisper_model,
        device=cfg.device,
        compute_type=cfg.compute_type,
        language=cfg.language,
        asr_options=asr_options or None,
    )

    audio = whisperx.load_audio(audio_path)
    print("  Transcribing…")
    result = model.transcribe(audio, batch_size=8)
    language = result.get("language", cfg.language or "en")

    # --- word-level alignment (improves diarization accuracy) ---
    try:
        align_model, meta = whisperx.load_align_model(
            language_code=language, device=cfg.device
        )
        result = whisperx.align(
            result["segments"], align_model, meta, audio, cfg.device,
            return_char_alignments=False,
        )
    except Exception as e:
        print(f"  ! Alignment skipped ({e}); using segment-level timings.")

    # --- diarization ---
    if cfg.diarize and cfg.hf_token:
        try:
            print("  Identifying speakers…")
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=cfg.hf_token, device=cfg.device
            )
            diarize_segments = diarize_model(
                audio, min_speakers=cfg.min_speakers, max_speakers=cfg.max_speakers
            )
            result = whisperx.assign_word_speakers(diarize_segments, result)
        except Exception as e:
            print(f"  ! Diarization failed ({e}); continuing without speaker labels.")
    elif cfg.diarize and not cfg.hf_token:
        print("  ! No MM_HF_TOKEN set — skipping speaker labels (transcript only).")

    return _to_turns(result.get("segments", []))


def _to_turns(segments: list[dict]) -> list[Turn]:
    """Collapse consecutive same-speaker segments into readable turns."""
    turns: list[Turn] = []
    for seg in segments:
        speaker = seg.get("speaker", "Speaker ?")
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if turns and turns[-1].speaker == speaker:
            turns[-1].text += " " + text
            turns[-1].end = end
        else:
            turns.append(Turn(speaker, text, start, end))
    return turns


def format_transcript(turns: list[Turn]) -> str:
    """Plain-text, speaker-labelled transcript for the summariser + archive."""
    lines = []
    for t in turns:
        stamp = f"[{int(t.start)//60:02d}:{int(t.start)%60:02d}]"
        lines.append(f"{stamp} {t.speaker}: {t.text}")
    return "\n".join(lines)
