"""Local meeting-minutes tool — CLI entry point.

Subcommands:
  record               Record a meeting (mic + system audio) to a WAV.
  process <audio>      Transcribe + diarize + summarize an existing WAV/MP3.
  run                  Record now, then process it when you stop. (Full flow.)

Everything runs locally. See README.md for setup and the consent notice.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import config


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _process(audio: Path, cfg, out: Path | None) -> Path:
    import transcriber
    import summarizer

    print(f"[1/3] Transcribing {audio.name} …")
    turns = transcriber.transcribe(audio, cfg)
    if not turns:
        print("  ! No speech found in the audio.")
        sys.exit(1)
    transcript = transcriber.format_transcript(turns)

    # Always keep the raw transcript next to the minutes — useful for review
    # and for re-summarising later without re-transcribing.
    transcript_path = config.OUTPUT_DIR / (audio.stem + ".transcript.txt")
    transcript_path.write_text(transcript, encoding="utf-8")
    print(f"  ✓ Transcript → {transcript_path}")

    print(f"[2/3] Summarizing with '{cfg.summary_model}' …")
    minutes = summarizer.summarize(transcript, cfg, date=time.strftime("%Y-%m-%d"))

    print("[3/3] Writing minutes …")
    out = out or (config.OUTPUT_DIR / (audio.stem + ".minutes.md"))
    out.write_text(minutes, encoding="utf-8")
    print(f"  ✓ Minutes → {out}")
    return out


def cmd_record(args, cfg) -> None:
    import recorder

    out = Path(args.output) if args.output else config.DATA_DIR / f"meeting-{_timestamp()}.wav"
    recorder.record(
        out,
        sample_rate=cfg.sample_rate,
        capture_mic=cfg.capture_mic,
        capture_system=cfg.capture_system,
    )


def cmd_process(args, cfg) -> None:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"File not found: {audio}")
        sys.exit(1)
    _process(audio, cfg, Path(args.output) if args.output else None)


def cmd_run(args, cfg) -> None:
    import recorder

    audio = config.DATA_DIR / f"meeting-{_timestamp()}.wav"
    print("=== Record ===")
    recorder.record(
        audio,
        sample_rate=cfg.sample_rate,
        capture_mic=cfg.capture_mic,
        capture_system=cfg.capture_system,
    )
    print("\n=== Process ===")
    _process(audio, cfg, Path(args.output) if args.output else None)


def main() -> None:
    cfg = config.load()
    parser = argparse.ArgumentParser(description="Local meeting-minutes tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_rec = sub.add_parser("record", help="Record a meeting to a WAV")
    p_rec.add_argument("-o", "--output", help="Output WAV path")
    p_rec.set_defaults(func=cmd_record)

    p_proc = sub.add_parser("process", help="Transcribe + summarize an audio file")
    p_proc.add_argument("audio", help="Path to a WAV/MP3 recording")
    p_proc.add_argument("-o", "--output", help="Output minutes .md path")
    p_proc.set_defaults(func=cmd_process)

    p_run = sub.add_parser("run", help="Record now, then process when stopped")
    p_run.add_argument("-o", "--output", help="Output minutes .md path")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args, cfg)


if __name__ == "__main__":
    main()
