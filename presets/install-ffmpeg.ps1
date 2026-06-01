# Downloads FFmpeg (a free audio/video tool the transcriber needs) and adds it
# to your PATH automatically, so you don't have to edit system settings by hand.
#
# Run once:   .\presets\install-ffmpeg.ps1
#
# What it does, in plain terms:
#   1. Downloads a "shared" FFmpeg build (~100 MB) into your user folder.
#   2. Unzips it.
#   3. Tells Windows where to find it (adds it to your PATH) so the tool can
#      use it from any terminal.
# Nothing is installed system-wide and no admin rights are needed.

$ErrorActionPreference = "Stop"

$dest = Join-Path $env:USERPROFILE "ffmpeg"
$zip  = Join-Path $env:TEMP "ffmpeg-shared.zip"
$url  = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"

Write-Host "Downloading FFmpeg (~100 MB, this can take a minute)..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

Write-Host "Unzipping..."
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Expand-Archive -Path $zip -DestinationPath $dest -Force
Remove-Item $zip -Force

$bin = (Get-ChildItem -Path $dest -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1).DirectoryName
if (-not $bin) { throw "Could not find ffmpeg.exe after unzipping." }

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$bin*") {
    [Environment]::SetEnvironmentVariable("PATH", ($userPath.TrimEnd(';') + ";" + $bin), "User")
    Write-Host "Added FFmpeg to your PATH."
} else {
    Write-Host "FFmpeg was already on your PATH."
}
$env:PATH = $env:PATH + ";" + $bin

Write-Host ""
Write-Host "Done! FFmpeg installed at: $bin"
Write-Host "IMPORTANT: close this terminal and open a NEW one so the PATH change takes effect."
