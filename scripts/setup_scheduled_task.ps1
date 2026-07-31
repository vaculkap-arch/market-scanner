# Scan kazdu hodinu - Python preskoci ak US burza nie je otvorena
$taskName = "MarketScanner"
$scriptPath = "C:\Users\VACA\Projects\market-scanner\scripts\run_scan.bat"

$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 60) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Uloha '$taskName' vytvorena - kazdu hodinu (scan len 09:30-16:00 ET, Po-Pi)."