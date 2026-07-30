# trigger-dispatch.ps1
# Daily trigger for the GitHub Actions "Daily Data Update" workflow.
# Purpose: fallback trigger via local Task Scheduler when GitHub schedule is unreliable.
# The token is never stored on disk: it is fetched from Git Credential Manager at runtime.

$repo = "DScongcong/industry-sentiment-dashboard"
$workflow = "daily-update.yml"

$credOut = "protocol=https`nhost=github.com`n`n" | git credential fill 2>$null
$token = ($credOut | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) {
    Write-Error "Failed to get GitHub token from Git Credential Manager. Run any git command once to sign in."
    exit 1
}

$headers = @{
    Authorization  = "Bearer $token"
    Accept         = "application/vnd.github+json"
    "User-Agent"   = "local-daily-dispatch"
}

try {
    Invoke-RestMethod -Method Post `
        -Uri "https://api.github.com/repos/$repo/actions/workflows/$workflow/dispatches" `
        -Headers $headers -Body '{"ref":"main"}' -ContentType "application/json" | Out-Null
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') dispatched $workflow"
}
catch {
    Write-Error "Dispatch failed: $_"
    exit 1
}
