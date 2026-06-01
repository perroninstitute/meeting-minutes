# Windows handoff — prompt for Claude Code

Clone this repo on the Windows machine, open Claude Code in the folder, and
paste the prompt below to continue.

---

## Prompt to give Claude Code

> I'm continuing work on this local meeting-minutes tool (already in this repo).
> It records a meeting I'm attending, transcribes it with **WhisperX**
> (including **speaker diarization**), and summarizes it into clinical meeting
> minutes using a **local LLM via Ollama** — everything runs locally, nothing
> goes to the cloud. The summarization step is already built and tested; the
> code is in `recorder.py`, `transcriber.py`, `summarizer.py`, `main.py`,
> `config.py`. Read `README.md` and `config.py` first.
>
> This is a **Windows** machine and is the real runtime target. Help me:
> 1. Set up a virtual environment and `pip install -r requirements.txt`
>    (install the correct PyTorch build for this machine — check if there's an
>    NVIDIA GPU with `nvidia-smi`; if so use the CUDA wheel, else CPU).
> 2. Install Ollama and pull a good general summary model (e.g. `qwen2.5:7b`),
>    then set `MM_SUMMARY_MODEL` to it.
> 3. Set up the Hugging Face token for pyannote diarization (`MM_HF_TOKEN`) —
>    walk me through accepting the model terms and creating the token.
> 4. **Verify the audio capture works on Windows**: `python main.py record`
>    should capture both my microphone and the system audio (other Teams
>    participants via WASAPI loopback) and mix them. Test it against a short
>    YouTube clip playing through my speakers + me talking, and confirm the WAV
>    contains both. The capture uses the `soundcard` library — if loopback
>    doesn't work, help me fix the device selection or switch to a fallback.
> 5. Run the full flow `python main.py run` end-to-end on a short **dummy**
>    meeting and check the transcript has correct speaker labels and the
>    minutes look right.
>
> Don't feed any real patient data through it until it's confirmed working with
> dummy audio. Tell me what hardware this machine has (RAM/GPU) and whether
> `large-v3` is realistic or we should use a smaller Whisper model.

---

## Status: set up & verified (2026-06-01)

Initial Windows setup is done and the full pipeline was verified end-to-end on a
GPU test bench (record → mix → WhisperX transcribe+diarize → Ollama minutes).
A few fixes were needed along the way (CPU-torch trap, a recorder threading bug,
the whisperx diarization API change, the community-1 license, UTF-8 mode, FFmpeg,
and disabling pyannote telemetry) — all folded into the code and **README.md**.
Use the README as the source of truth; the quick reference below is updated.

## Quick reference (full details in README.md)

```powershell
git clone <this-repo-url>
cd meeting-minutes
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# NVIDIA GPU only: re-install the CUDA build of torch AFTER the line above
# (WhisperX pulls a CPU-only torch that overrides it):
pip install --force-reinstall --no-deps torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0 `
  --index-url https://download.pytorch.org/whl/cu128

# Ollama: install from https://ollama.com/download, then:
ollama pull qwen2.5:7b

# Apply the machine preset (sets MM_*, PYTHONUTF8, telemetry off):
.\presets\workstation-gpu.ps1     # GPU box
# .\presets\laptop-cpu.ps1        # CPU-only laptop

# Speaker labels: accept https://huggingface.co/pyannote/speaker-diarization-community-1
# then set a free HF read token:
setx MM_HF_TOKEN "hf_xxxxxxxxxxxx"

# Also install a SHARED FFmpeg build and add its bin\ to PATH (see README).

# Run it (record 10 min then summarise, or omit -d to stop with Enter):
python main.py run -d 600
```
