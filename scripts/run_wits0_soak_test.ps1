param(
    [double]$DurationHours = 8,
    [double]$RateHz = 20,
    [string]$OutputDirectory = ".\soak-output",
    [int]$DisconnectIntervalSeconds = 300
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$rawDirectory = Join-Path $OutputDirectory "raw"
$report = Join-Path $OutputDirectory "report.json"
$durationSeconds = [int]($DurationHours * 3600)

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Push-Location $projectRoot
try {
    python .\tools\wits0_soak_test.py `
        --duration-seconds $durationSeconds `
        --rate-hz $RateHz `
        --disconnect-interval-seconds $DisconnectIntervalSeconds `
        --raw-directory $rawDirectory `
        --report $report
    if ($LASTEXITCODE -ne 0) {
        throw "WITS0 soak test failed. See $report"
    }
    Write-Host "WITS0 soak test completed successfully: $report"
}
finally {
    Pop-Location
}
