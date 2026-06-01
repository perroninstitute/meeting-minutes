"""Local audio capture for meetings you are attending.

Strategy: you join the Teams call normally. This records two things at once
and mixes them into one mono 16 kHz WAV:

  * System audio (loopback) — everyone else in the call, i.e. whatever your
    speakers play. On Windows this is a WASAPI loopback of the default output.
  * Your microphone — your own voice, which is NOT in the system audio.

Nothing is sent anywhere; we just write a .wav to disk.

We use the `soundcard` library because its loopback API is clean on Windows
(`include_loopback=True`) and it resamples to our target rate for us. If
`soundcard` or a device is unavailable the error messages explain what to do.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

try:
    import soundcard as sc
except Exception as e:  # pragma: no cover - import guard
    sc = None
    _IMPORT_ERROR = e


class _StreamRecorder(threading.Thread):
    """Records one device (mic or loopback) into a list of float32 frames."""

    def __init__(self, mic, sample_rate: int, label: str):
        super().__init__(daemon=True)
        self._mic = mic
        self._sr = sample_rate
        self.label = label
        self._frames: list[np.ndarray] = []
        # NB: must NOT be named `_stop` — that shadows threading.Thread._stop,
        # which join() calls internally, raising "'Event' object is not callable".
        self._stop_event = threading.Event()
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            # numframes=None → return whatever is available each loop; keeps
            # latency low and avoids blocking on a fixed block size.
            with self._mic.recorder(samplerate=self._sr, channels=1) as rec:
                while not self._stop_event.is_set():
                    data = rec.record(numframes=self._sr // 10)  # ~100ms chunks
                    self._frames.append(data.copy())
        except Exception as e:  # surface device errors to the caller
            self.error = e

    def stop(self) -> np.ndarray:
        self._stop_event.set()
        self.join(timeout=5)
        if not self._frames:
            return np.zeros((0, 1), dtype=np.float32)
        return np.concatenate(self._frames, axis=0)


def _default_loopback_mic():
    """The default speaker, opened as a loopback capture device."""
    speaker = sc.default_speaker()
    # get_microphone with include_loopback finds the matching loopback device.
    return sc.get_microphone(speaker.name, include_loopback=True)


def record(
    out_path: str | Path,
    sample_rate: int = 16000,
    capture_mic: bool = True,
    capture_system: bool = True,
    stop_event: threading.Event | None = None,
) -> Path:
    """Record until `stop_event` is set (or Enter is pressed if it's None).

    Returns the path to the written WAV.
    """
    if sc is None:
        raise RuntimeError(
            "The 'soundcard' package is not available "
            f"({_IMPORT_ERROR!r}).\nInstall it with:  pip install soundcard"
        )

    out_path = Path(out_path)
    recorders: list[_StreamRecorder] = []

    if capture_system:
        try:
            recorders.append(
                _StreamRecorder(_default_loopback_mic(), sample_rate, "system")
            )
        except Exception as e:
            raise RuntimeError(
                "Could not open the system-audio loopback device.\n"
                "On Windows this needs a real default speaker selected.\n"
                f"Underlying error: {e}"
            )

    if capture_mic:
        try:
            recorders.append(
                _StreamRecorder(sc.default_microphone(), sample_rate, "mic")
            )
        except Exception as e:
            print(f"  ! Microphone unavailable, recording system audio only ({e})")

    if not recorders:
        raise RuntimeError("Nothing to record: both mic and system capture are off.")

    print(f"  Recording from: {', '.join(r.label for r in recorders)}")
    for r in recorders:
        r.start()

    # Wait for the stop signal.
    if stop_event is None:
        try:
            input("  ▶ Recording… press Enter to stop.\n")
        except (KeyboardInterrupt, EOFError):
            pass
    else:
        while not stop_event.is_set():
            time.sleep(0.2)

    tracks = []
    for r in recorders:
        audio = r.stop()
        if r.error:
            print(f"  ! {r.label} stream error: {r.error}")
        if audio.size:
            tracks.append(audio.reshape(-1))

    if not tracks:
        raise RuntimeError("No audio was captured. Check device permissions.")

    # Mix: pad all tracks to the same length, sum, then guard against clipping.
    length = max(len(t) for t in tracks)
    mix = np.zeros(length, dtype=np.float32)
    for t in tracks:
        mix[: len(t)] += t
    peak = np.max(np.abs(mix)) or 1.0
    if peak > 1.0:
        mix /= peak  # normalise only if we actually clipped

    sf.write(str(out_path), mix, sample_rate, subtype="PCM_16")
    secs = length / sample_rate
    print(f"  ✓ Saved {secs:0.1f}s of audio → {out_path}")
    return out_path


if __name__ == "__main__":
    import config

    cfg = config.load()
    ts = time.strftime("%Y%m%d-%H%M%S")
    record(
        config.DATA_DIR / f"meeting-{ts}.wav",
        sample_rate=cfg.sample_rate,
        capture_mic=cfg.capture_mic,
        capture_system=cfg.capture_system,
    )
