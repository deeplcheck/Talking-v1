param()

$ErrorActionPreference = "Stop"
$baseDir = Split-Path -Parent $PSScriptRoot
$targetDir = Join-Path $baseDir "reference_voices"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

Add-Type -AssemblyName System.Speech

$voices = New-Object System.Speech.Synthesis.SpeechSynthesizer
$installed = $voices.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }

function Export-VoiceFile {
  param(
    [string]$VoiceName,
    [string]$Text,
    [string]$OutputPath,
    [int]$Rate
  )

  $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $speaker.Rate = $Rate
  if ($VoiceName) {
    $speaker.SelectVoice($VoiceName)
  }
  $speaker.SetOutputToWaveFile($OutputPath)
  $speaker.Speak($Text)
  $speaker.Dispose()
}

$maleText = "Hello, this is a calm male preset sample for voice cloning. The delivery should sound steady and clear."
$femaleText = "Hello, this is a bright female preset sample for voice cloning. The delivery should sound light and natural."

$maleVoice = $installed | Where-Object { $_ -match "Huihui|Yun|Male|David|Mark" } | Select-Object -First 1
$femaleVoice = $installed | Where-Object { $_ -match "Female|Zira|Xiaoxiao|Huihui" } | Select-Object -First 1

if (-not $maleVoice -and $installed.Count -gt 0) {
  $maleVoice = $installed[0]
}

if (-not $femaleVoice -and $installed.Count -gt 1) {
  $femaleVoice = $installed[1]
}

if (-not $femaleVoice) {
  $femaleVoice = $maleVoice
}

Export-VoiceFile -VoiceName $maleVoice -Text $maleText -OutputPath (Join-Path $targetDir "dashu.wav") -Rate -1
Export-VoiceFile -VoiceName $femaleVoice -Text $femaleText -OutputPath (Join-Path $targetDir "shounv.wav") -Rate 1

Write-Host "Prepared preset voices:"
Write-Host " - dashu.wav"
Write-Host " - shounv.wav"
