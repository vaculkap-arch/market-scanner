$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
Set-Location $project

function Get-EnvValue([string]$key) {
    $path = Join-Path $project ".env"
    if (-not (Test-Path $path)) { return $null }
    foreach ($line in Get-Content $path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        $i = $t.IndexOf("=")
        if ($i -lt 1) { continue }
        $k = $t.Substring(0, $i).Trim()
        if ($k -eq $key) {
            return $t.Substring($i + 1).Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

Write-Host "=== Market Scanner -> GitHub ===" -ForegroundColor Cyan

$ghCmd = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghCmd) {
    $candidates = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "$env:LocalAppData\Programs\GitHub CLI\gh.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $env:Path = "$(Split-Path $c);$env:Path"
            break
        }
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI (gh) nie je nainstalovane." -ForegroundColor Red
    exit 1
}

& gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nie si prihlaseny. Spusti: gh auth login" -ForegroundColor Red
    exit 1
}

$user = (& gh api user --jq .login).Trim()
Write-Host "GitHub ucet: $user" -ForegroundColor Green

$repoName = "market-scanner"
$repoFull = "$user/$repoName"

& gh repo view $repoFull 2>$null | Out-Null
$exists = ($LASTEXITCODE -eq 0)

if (-not $exists) {
    Write-Host "Vytvaram private repo $repoFull ..."
    & gh repo create $repoName --private --source=. --remote=origin --push
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "Repo uz existuje: $repoFull"
    $remote = & git remote get-url origin 2>$null
    if (-not $remote) {
        & git remote add origin "https://github.com/$repoFull.git"
    }
    Write-Host "Pushujem main..."
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

$gmailAddress = Get-EnvValue "GMAIL_ADDRESS"
$gmailPassword = Get-EnvValue "GMAIL_APP_PASSWORD"
$gmailTo = Get-EnvValue "GMAIL_TO"
if (-not $gmailTo) { $gmailTo = $gmailAddress }

if ($gmailAddress -and $gmailPassword) {
    Write-Host "Nastavujem Actions Secrets (Gmail)..."
    $gmailAddress | & gh secret set GMAIL_ADDRESS --repo $repoFull
    $gmailPassword | & gh secret set GMAIL_APP_PASSWORD --repo $repoFull
    $gmailTo | & gh secret set GMAIL_TO --repo $repoFull

    $tg = Get-EnvValue "TELEGRAM_BOT_TOKEN"
    $tgChat = Get-EnvValue "TELEGRAM_CHAT_ID"
    if ($tg) { $tg | & gh secret set TELEGRAM_BOT_TOKEN --repo $repoFull }
    if ($tgChat) { $tgChat | & gh secret set TELEGRAM_CHAT_ID --repo $repoFull }

    Write-Host "Secrets nastavene." -ForegroundColor Green
} else {
    Write-Host "V .env chyba GMAIL - Secrets som nenastavil." -ForegroundColor Yellow
}

Write-Host "Spustam testovaci scan workflow..."
& gh workflow run "Market Scan" --repo $repoFull
Write-Host "Repo: https://github.com/$repoFull"
Write-Host "Actions: https://github.com/$repoFull/actions"
Write-Host "Dalej Streamlit: https://share.streamlit.io"