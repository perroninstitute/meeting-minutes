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

## Quick reference (also in README.md)

```powershell
git clone <this-repo-url>
cd meeting-minutes
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Ollama: install from https://ollama.com/download, then:
ollama pull qwen2.5:7b
setx MM_SUMMARY_MODEL "qwen2.5:7b"

# Speaker labels: free HF token (see README step 4), then:
setx MM_HF_TOKEN "hf_xxxxxxxxxxxx"

# Run it:
python main.py run
```
