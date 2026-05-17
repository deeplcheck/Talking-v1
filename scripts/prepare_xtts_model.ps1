param()

$ErrorActionPreference = "Stop"
$modelDir = Join-Path $env:LOCALAPPDATA "tts\tts_models--multilingual--multi-dataset--xtts_v2"
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

$tosFile = Join-Path $modelDir "tos_agreed.txt"
if (-not (Test-Path $tosFile)) {
  Set-Content -Path $tosFile -Value "I have read, understood and agreed to the Terms and Conditions." -Encoding UTF8
}

$files = @(
  @{ Name = "model.pth"; Url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/model.pth" },
  @{ Name = "config.json"; Url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/config.json" },
  @{ Name = "vocab.json"; Url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/vocab.json" },
  @{ Name = "hash.md5"; Url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/hash.md5" },
  @{ Name = "speakers_xtts.pth"; Url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/speakers_xtts.pth" }
)

foreach ($file in $files) {
  $target = Join-Path $modelDir $file.Name
  Write-Host "Downloading $($file.Name)..."
  & curl.exe --retry 20 --retry-delay 5 -L -C - -o $target $file.Url
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to download $($file.Name)"
  }
}

Write-Host "XTTS model files are ready in $modelDir"
