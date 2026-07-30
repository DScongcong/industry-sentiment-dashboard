# trigger-dispatch.ps1
# 每日触发 GitHub Actions「Daily Data Update」工作流。
# 用途：GitHub 定时任务（schedule）在部分仓库上不稳定时，用本机计划任务兜底触发。
# 令牌不落地存储：每次运行时从 Git 凭据管理器（Git Credential Manager）实时获取。

$repo = "DScongcong/industry-sentiment-dashboard"
$workflow = "daily-update.yml"

$credOut = "protocol=https`nhost=github.com`n`n" | git credential fill 2>$null
$token = ($credOut | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) {
    Write-Error "未能从 Git 凭据管理器获取 GitHub 令牌，请先在浏览器登录一次 GitHub（git 操作触发）。"
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
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') 已触发 $workflow"
}
catch {
    Write-Error "触发失败: $_"
    exit 1
}
