# Preset: NVIDIA GPU workstation (e.g. the RTX 4070 test bench).
# Sets the env vars for fast, high-accuracy local processing and persists them
# for future shells (setx), then applies them to the current shell too.
#
# Run once:   .\presets\workstation-gpu.ps1
# NOTE: set your Hugging Face token separately (it is a secret):
#   setx MM_HF_TOKEN "hf_xxxxxxxxxxxx"

$vars = @{
    # Transcription: GPU + half precision + best model.
    "MM_DEVICE"        = "cuda"
    "MM_COMPUTE_TYPE"  = "float16"
    "MM_WHISPER_MODEL" = "large-v3"
    # Summary model (pull it first:  ollama pull qwen2.5:7b).
    "MM_SUMMARY_MODEL" = "qwen2.5:7b"
    # Windows console is cp1252; Python needs UTF-8 mode for the ✓/→ glyphs.
    "PYTHONUTF8"       = "1"
    # Privacy: hard-disable pyannote.audio's phone-home telemetry.
    "PYANNOTE_METRICS_ENABLED" = "false"
    "OTEL_SDK_DISABLED"        = "true"
}

foreach ($k in $vars.Keys) {
    setx $k $vars[$k] | Out-Null
    Set-Item -Path "Env:$k" -Value $vars[$k]
    "  $k = $($vars[$k])"
}
Write-Host "`nWorkstation (GPU) preset applied (persisted + current shell)."
Write-Host "Remember: MM_HF_TOKEN must be set separately for speaker labels."
