# Run in your authenticated PowerShell; secrets are entered directly into gh.
$ErrorActionPreference = 'Stop'
$repo = 'Robert-F-Mulligan/fantasy-football'
$ghPath = Join-Path $PSScriptRoot '../work/github-cli/bin/gh.exe'
if (-not (Test-Path -LiteralPath $ghPath)) { $ghPath = 'gh' }
& $ghPath auth status
if ($LASTEXITCODE -ne 0) { throw 'Sign into gh before running this script.' }
& $ghPath variable set FF_LEAGUE_ID --repo $repo --body '1313253652600721408'
if ($LASTEXITCODE -ne 0) { throw 'Failed to save league ID.' }
& $ghPath variable set FF_TEAM_NAME --repo $repo --body 'Bower Rangers'
if ($LASTEXITCODE -ne 0) { throw 'Failed to save team name.' }
& $ghPath variable set FF_SEASON --repo $repo --body '2026'
if ($LASTEXITCODE -ne 0) { throw 'Failed to save season.' }
& $ghPath variable set REPORT_EMAIL_ENABLED --repo $repo --body 'false'
if ($LASTEXITCODE -ne 0) { throw 'Failed to set cutover gate.' }
foreach ($secretName in @('REPORT_EMAIL_TO', 'GMAIL_USERNAME', 'GMAIL_APP_PASSWORD')) {
    Write-Host "Enter $secretName when gh prompts. For the first two, use your Gmail address."
    & $ghPath secret set $secretName --repo $repo
    if ($LASTEXITCODE -ne 0) { throw "Failed to save $secretName." }
}
Write-Host 'Configuration saved. Email remains gated off until the hosted dry run passes and the local schedule is paused.'
