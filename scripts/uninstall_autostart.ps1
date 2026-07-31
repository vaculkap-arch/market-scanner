$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "MarketScanner.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Autostart odstraneny."
} else {
    Write-Host "Autostart nebol nastaveny."
}