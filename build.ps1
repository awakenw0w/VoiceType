$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m PyInstaller --noconfirm --clean VoiceType.spec

$zip = Join-Path $root "VoiceType-portable.zip"
if (Test-Path $zip) {
    Remove-Item $zip
}
Compress-Archive -Path (Join-Path $root "dist\VoiceType\*") -DestinationPath $zip
Write-Host "Built $zip"
