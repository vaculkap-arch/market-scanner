# Deploy Market Scanner to GitHub (repo + push + Actions secrets).
# Usage (PowerShell):
#   cd C:\Users\VACA\Projects\market-scanner
#   .\scripts\deploy_github.ps1
#
# Prerequisites:
#   1) One-time: gh auth login
#   2) Local .env with GMAIL_* values (not committed)

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

Write-Host "=== Market Scanner → GitHub ===" -ForegroundColor Cyan

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
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
    Write-Host "GitHub CLI (gh) nie je nainštalované. Spusti:" -ForegroundColor Red
    Write-Host "  winget install --id GitHub.cli -e"
    exit 1
}

Write-Host "Kontrolujem prihlásenie do GitHubu..."
$auth = & gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Nie si prihlásený. Otvorím login (prehliadač)..." -ForegroundColor Yellow
    & gh auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Prihlásenie zlyhalo. Spusti ručne: gh auth login" -ForegroundColor Red
        exit 1
    }
}

$user = (& gh api user --jq .login).Trim()
if (-not $user) {
    Write-Host "Nepodarilo sa zistiť GitHub username." -ForegroundColor Red
    exit 1
}
Write-Host "GitHub účet: $user" -ForegroundColor Green

$repoName = "market-scanner"
$repoFull = "$user/$repoName"
$exists = $true
& gh repo view $repoFull 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { $exists = $false }

if (-not $exists) {
    Write-Host "Vytváram private repo $repoFull ..."
    & gh repo create $repoName --private --source=. --remote=origin --push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Vytvorenie / push zlyhal." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Repo už existuje: $repoFull"
    $remote = & git remote get-url origin 2>$null
    if (-not $remote) {
        & git remote add origin "https://github.com/$repoFull.git"
    }
    Write-Host "Pushujem main..."
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Push zlyhal." -ForegroundColor Red
        exit 1
    }
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

    Write-Host "Secrets nastavené." -ForegroundColor Green
} else {
    Write-Host "V .env chýba GMAIL_ADDRESS / GMAIL_APP_PASSWORD — Secrets som nenastavil." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Spúšťam testovací scan workflow..."
& gh workflow run "Market Scan" --repo $repoFull
if ($LASTEXITCODE -eq 0) {
    Write-Host "Workflow spustený. Stav: https://github.com/$repoFull/actions" -ForegroundColor Green
} else {
    Write-Host "Workflow sa nepodarilo spustiť (možno ešte nie je na remote). Skús Actions v UI." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== GitHub hotovo ===" -ForegroundColor Cyan
Write-Host "Repo: https://github.com/$repoFull"
Write-Host ""
Write-Host "Zostáva Streamlit Cloud (musíš kliknúť v prehliadači):"
Write-Host "  1) https://share.streamlit.io  (login cez GitHub)"
Write-Host "  2) New app → $repoFull → main → app.py"
Write-Host "  3) Secrets: skopíruj zo súboru streamlit_secrets.toml.example"
Write-Host "  4) Deploy"
Write-Host ""
Write-Host "Detail: DEPLOY.md"
