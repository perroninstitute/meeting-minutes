# Preset: CPU-only Windows laptop (e.g. AMD Ryzen 7730U + integrated Radeon,
# 16 GB RAM). The integrated GPU CANNOT accelerate this stack (CTranslate2 and
# Ollama only use CUDA or CPU on Windows), so everything runs on the CPU.
#
# Tuned for "it finishes in reasonable time on a laptop" over maximum accuracy:
#   - Whisper "medium" instead of "large-v3" (large-v3 on CPU is painfully slow).
#   - int8 compute (CPU-friendly).
# Transcription + diarization will still be well above real-time on a laptop —
# expect a 10-minute meeting to take a good while. Drop to "small" if needed,
# and consider a smaller summary model if qwen2.5:7b is too slow on CPU.
#
# Run once:   .\presets\laptop-cpu.ps1
# NOTE: set your Hugging Face token separately (it is a secret):
#   setx MM_HF_TOKEN "hf_xxxxxxxxxxxx"

$vars = @{
    # Transcription: CPU + int8 + lighter model.
    "MM_DEVICE"        = "cpu"
    "MM_COMPUTE_TYPE"  = "int8"
    "MM_WHISPER_MODEL" = "medium"
    # Summary model (pull it first:  ollama pull qwen2.5:7b). If summaries are
    # too slow on CPU, try a 3B model and set MM_SUMMARY_MODEL to it instead.
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
Write-Host "`nLaptop (CPU) preset applied (persisted + current shell)."
Write-Host "Remember: MM_HF_TOKEN must be set separately for speaker labels."
