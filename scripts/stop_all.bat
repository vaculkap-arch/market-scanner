@echo off
echo Ukoncujem Market Scanner procesy...
taskkill /FI "WINDOWTITLE eq MarketScanner-Agent*" /F 2>nul
taskkill /FI "WINDOWTITLE eq MarketScanner-App*" /F 2>nul
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /I "PID"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr /I "market_scanner streamlit" >nul && taskkill /PID %%a /F 2>nul
)
echo Hotovo.
timeout /t 3