"""Local meeting-minutes tool — CLI entry point.

Subcommands:
  record               Record a meeting (mic + system audio) to a WAV.
  process <audio>      Transcribe + diarize + summarize an existing WAV/MP3.
  run                  Record now, then process it when you stop. (Full flow.)
  summarise            Summarise an existing transcription.

Everything runs locally. See README.md for setup and the consent notice.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import config


def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _stop_after(seconds: int | None) -> "threading.Event | None":
    """Return a stop_event that fires after `seconds` (None => stop on Enter)."""
    if not seconds or seconds <= 0:
        return None
    ev = threading.Event()

    def _timer() -> None:
        time.sleep(seconds)
        print(f"  ⏱ Reached {seconds}s limit — stopping.")
        ev.set()

    threading.Thread(target=_timer, daemon=True).start()
    print(f"  Recording for a fixed {seconds}s…")
    return ev


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
    minutes = summarizer.summarize(transcript, cfg, date=time.strftime("%d/%m/%Y"))

    print("[3/3] Writing minutes …")
    out = out or (config.OUTPUT_DIR / (audio.stem + ".minutes.md"))
    out.write_text(minutes, encoding="utf-8")
    print(f"  ✓ Minutes → {out}")
    return out
  
def _summarise(transcript_path: Path, cfg, out: Path | None):
    import summarizer
    
    transcript = transcript_path.read_text(encoding="utf-8")
    print(f"[1/2] Summarizing with '{cfg.summary_model}' …")
    minutes = summarizer.summarize(transcript, cfg, date=time.strftime("%d/%m/%Y"))

    print("[2/2] Writing minutes …")
    out = out or (config.OUTPUT_DIR / (transcript_path.stem + ".minutes.md"))
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
        stop_event=_stop_after(args.duration),
    )


def cmd_process(args, cfg) -> None:
    audio = Path(args.audio)
    if not audio.exists():
        print(f"File not found: {audio}")
        sys.exit(1)
    _process(audio, cfg, Path(args.output) if args.output else None)
    
def cmd_summarise(args, cfg) -> None:
    transcript = Path(args.transcript)
    if not transcript.exists():
        print(f"File not found: {transcript}")
        sys.exit(1)
    _summarise(transcript, cfg, Path(args.output) if args.output else None)


def cmd_run(args, cfg) -> None:
    import recorder

    audio = config.DATA_DIR / f"meeting-{_timestamp()}.wav"
    print("=== Record ===")
    recorder.record(
        audio,
        sample_rate=cfg.sample_rate,
        capture_mic=cfg.capture_mic,
        capture_system=cfg.capture_system,
        stop_event=_stop_after(args.duration),
    )
    print("\n=== Process ===")
    _process(audio, cfg, Path(args.output) if args.output else None)


def main() -> None:
    cfg = config.load()
    parser = argparse.ArgumentParser(description="Local meeting-minutes tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_rec = sub.add_parser("record", help="Record a meeting to a WAV")
    p_rec.add_argument("-o", "--output", help="Output WAV path")
    p_rec.add_argument(
        "-d", "--duration", type=int, default=None,
        help="Record for a fixed number of seconds, then stop automatically "
             "(default: record until you press Enter).",
    )
    p_rec.set_defaults(func=cmd_record)

    p_proc = sub.add_parser("process", help="Transcribe + summarize an audio file")
    p_proc.add_argument("audio", help="Path to a WAV/MP3 recording")
    p_proc.add_argument("-o", "--output", help="Output minutes .md path")
    p_proc.set_defaults(func=cmd_process)

    p_run = sub.add_parser("run", help="Record now, then process when stopped")
    p_run.add_argument("-o", "--output", help="Output minutes .md path")
    p_run.add_argument(
        "-d", "--duration", type=int, default=None,
        help="Record for a fixed number of seconds before processing "
             "(default: record until you press Enter).",
    )
    p_run.set_defaults(func=cmd_run)
    p_sum = sub.add_parser("summarise", help="Summarise an existing transcript")
    p_sum.add_argument("transcript", help="Path to .transcript.txt file")
    p_sum.add_argument("-o", "--output", help="Output minutes .md path")
    p_sum.set_defaults(func=cmd_summarise)

    args = parser.parse_args()
    args.func(args, cfg)


if __name__ == "__main__":
    main()
