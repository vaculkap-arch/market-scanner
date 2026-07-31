# Autostart: agent + appka po prihlaseni do Windows (bez okien)
$project = "C:\Users\VACA\Projects\market-scanner"
$vbsPath = "$project\scripts\start_hidden.vbs"
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "MarketScanner.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbsPath`""
$shortcut.WorkingDirectory = $project
$shortcut.WindowStyle = 7
$shortcut.Description = "Market Scanner - agent + appka non-stop"
$shortcut.Save()

Write-Host ""
Write-Host "HOTOVO - Autostart nastaveny!" -ForegroundColor Green
Write-Host ""
Write-Host "Co sa stane:"
Write-Host "  - Pri kazdom prihlaseni do Windows sa automaticky spusti:"
Write-Host "    1. Agent (scan + Gmail alerty pocas US hodin)"
Write-Host "    2. Web appka na http://localhost:8501"
Write-Host ""
Write-Host "  - Bezi na pozadi, nemusis nic spustat"
Write-Host "  - Logy: $project\logs\"
Write-Host ""
Write-Host "Spustit teraz (bez restartu PC):"
Write-Host "  dvojklik na scripts\start_all.bat"