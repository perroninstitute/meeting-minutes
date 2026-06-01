# Local Meeting Minutes

Record a meeting you're attending, transcribe it with speaker labels, and turn
it into structured clinical minutes — **100% on your own machine**. No audio,
transcript, or summary ever leaves the computer. Built for sensitive
(e.g. clinical / neurological) meetings where cloud services are not allowed.

```
record (mic + system audio)  →  WhisperX (transcribe + speaker labels)
                              →  local LLM via Ollama  →  minutes.md
```

---

## ⚠️ Consent & compliance — read first

This tool **records meetings**. Before using it for real:

- **Get participant consent.** Recording clinical/work meetings without the
  participants' knowledge is often illegal and against institutional policy.
  Announce that the meeting is being recorded.
- **Clear it with your institute's IT / data-protection officer.** A
  fully-local tool is the easiest kind to approve, but approval should still
  be obtained — especially on a work-issued machine.
- **Test with dummy audio**, never a real patient meeting, until it's running
  fully locally and verified.
- **Protect the files.** `recordings/` and `minutes/` contain sensitive data.
  Keep them on an encrypted disk (BitLocker / FileVault) and **out of any
  cloud-synced folder** (OneDrive, Dropbox, iCloud).

The tool is local by design, but *you* are responsible for how recordings are
captured, stored, and shared.

---

## What runs where

| Step | Tech | Local? |
|---|---|---|
| Capture system audio + mic | `soundcard` (WASAPI loopback on Windows) | ✅ |
| Transcribe + word timing | WhisperX / faster-whisper | ✅ (one-time model download) |
| Speaker labels (diarization) | pyannote via WhisperX | ✅ (one-time model download) |
| Summarize → minutes | local LLM via **Ollama** | ✅ |

---

## Setup (Windows work machine)

1. **Install Python 3.10+** (from python.org; tick "Add to PATH"). Tested on
   3.10 and 3.11.

2. **Install Ollama** and pull a summary model:
   ```powershell
   # download Ollama from https://ollama.com/download then:
   ollama pull qwen2.5:7b      # good general model for summaries
   ```

3. **Install the Python dependencies:**
   ```powershell
   cd meeting-minutes
   python -m venv venv
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   **NVIDIA GPU? Re-install the CUDA build of PyTorch _after_ the line above.**
   `requirements.txt` pulls WhisperX, which depends on `torch~=2.8.0` — and the
   default PyPI wheel on Windows is **CPU-only**, silently overriding any CUDA
   build. So install the CUDA wheels last (cu128 works on RTX 40-series):
   ```powershell
   pip install --force-reinstall --no-deps `
     torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0 `
     --index-url https://download.pytorch.org/whl/cu128
   # verify:
   python -c "import torch; print(torch.cuda.is_available())"   # must print True
   ```
   On a CPU-only machine, skip this — the CPU torch from `requirements.txt` is fine.

   **Two Windows must-dos:**
   - **UTF-8 mode.** The console is cp1252 and the tool prints `✓`/`→`, which
     crash without UTF-8 mode:  `setx PYTHONUTF8 1`
   - **FFmpeg (shared build).** pyannote's audio backend wants FFmpeg's shared
     DLLs. Install a *shared* build (not the "essentials"/static one), e.g. from
     https://github.com/BtbN/FFmpeg-Builds/releases, and add its `bin\` to PATH.

   **Shortcut:** instead of setting the env vars by hand, run the matching
   preset (see [Machine presets](#machine-presets) below).

4. **Enable speaker labels (one-time):**
   - Make a free account at https://huggingface.co
   - Accept the terms on the diarization model the current stack uses:
     - https://huggingface.co/pyannote/speaker-diarization-community-1
   - Create a token at https://huggingface.co/settings/tokens (a **Read** token
     is enough)
   - Set it (PowerShell):
     ```powershell
     setx MM_HF_TOKEN "hf_xxxxxxxxxxxxxxxxx"
     ```
   (Skip this and the tool still works — it just won't separate speakers.)

   > **Why community-1?** whisperx 3.8 + pyannote.audio 4.x default to (and
   > internally depend on) `speaker-diarization-community-1`. Accepting only the
   > older `speaker-diarization-3.1` / `segmentation-3.0` is **not** sufficient
   > anymore — you'll get a 403. Override the model with `MM_DIARIZE_MODEL` if
   > you've accepted a different one.

5. **Point it at your summary model:**
   ```powershell
   setx MM_SUMMARY_MODEL "qwen2.5:7b"
   ```

6. **Fill in `glossary.txt`** with the institute's real terms, drug names,
   abbreviations, and staff names. This improves both transcription accuracy
   and summary quality.

---

## Usage

```powershell
# Full flow: record now, stop with Enter, get minutes automatically
python main.py run

# Record for a fixed length, then process automatically (no Enter needed).
# Handy for a known-length meeting or unattended capture. -d is in SECONDS:
python main.py run -d 600              # record 10 minutes, then summarise

# Or in two steps:
python main.py record                 # → recordings/meeting-<timestamp>.wav
python main.py record -d 1800         # record exactly 30 minutes
python main.py process recordings/meeting-<timestamp>.wav

# Re-summarize an existing recording or transcribe a file from elsewhere:
python main.py process some-meeting.mp3 -o minutes/today.md
```

Output lands in `minutes/`:
- `*.transcript.txt` — full speaker-labelled transcript
- `*.minutes.md` — the structured minutes

---

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `MM_WHISPER_MODEL` | `large-v3` | `medium`/`small` are faster & lighter |
| `MM_LANGUAGE` | auto | pin to `en` or `de` if known |
| `MM_DEVICE` | `cpu` | set `cuda` with an NVIDIA GPU |
| `MM_COMPUTE_TYPE` | `int8` | `float16` on GPU |
| `MM_SUMMARY_MODEL` | `qwen2.5-coder:3b` | any Ollama model |
| `MM_HF_TOKEN` | — | enables speaker labels |
| `MM_DIARIZE_MODEL` | `pyannote/speaker-diarization-community-1` | which pyannote pipeline to use |
| `MM_MIN_SPEAKERS` / `MM_MAX_SPEAKERS` | — | hint the diarizer |
| `MM_CAPTURE_MIC` / `MM_CAPTURE_SYSTEM` | `true` | toggle each source |
| `PYANNOTE_METRICS_ENABLED` | `false` | set by the tool to disable pyannote telemetry (see below) |

---

## Machine presets

Instead of setting the env vars by hand, run the preset that matches the
machine (sets everything via `setx` and for the current shell):

```powershell
# NVIDIA GPU workstation — cuda + float16 + large-v3 + qwen2.5:7b
.\presets\workstation-gpu.ps1

# CPU-only laptop (e.g. AMD iGPU) — cpu + int8 + medium model
.\presets\laptop-cpu.ps1
```

Then set your token once: `setx MM_HF_TOKEN "hf_..."`.

> **CPU-only machines (e.g. a laptop with integrated/AMD graphics):** the
> integrated GPU can't accelerate this — CTranslate2 (Whisper) and Ollama only
> use CUDA or CPU on Windows. Use `laptop-cpu.ps1`. `large-v3` on CPU is very
> slow; `medium` (or `small`) is the realistic choice, and a 10-minute meeting
> will still take a good while to process.

---

## Privacy: fully local, telemetry disabled

The pipeline makes **no cloud API calls** and costs nothing per use — the only
network traffic is one-time model downloads. The tool's own code only ever
talks to your local Ollama (`localhost:11434`).

One caveat the tool handles for you: **pyannote.audio 4.x ships with usage
telemetry enabled by default**, which POSTs metadata (audio *duration*, speaker
count, a session UUID, library version — never your audio/transcript) to
`otel.pyannote.ai` on each diarization. `config.py` disables this on import
(`PYANNOTE_METRICS_ENABLED=false`, `OTEL_SDK_DISABLED=true`) so nothing leaves
the machine. For a belt-and-suspenders guarantee in a clinical/air-gapped
setting, also block outbound network access at the firewall.

---

## Notes & limitations

- **Capture model:** you attend the call normally; the tool records what your
  speakers play (other participants) plus your mic (you). It does **not** join
  the meeting as a bot — that's intentional (simpler, more private, no Azure).
- **First run is slow:** Whisper and pyannote models download once (a few GB),
  then are cached.
- **RAM:** `large-v3` + a 7B summary model is heavy. If the machine struggles,
  drop to `MM_WHISPER_MODEL=medium` and a smaller summary model.
- **Accuracy:** clinical terms transcribe far better once `glossary.txt`
  reflects the real vocabulary. Always have a human check the minutes before
  they're treated as a record.
