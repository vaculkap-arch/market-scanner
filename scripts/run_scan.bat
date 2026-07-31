@echo off
cd /d C:\Users\VACA\Projects\market-scanner
call .venv\Scripts\activate.bat
py -m market_scanner.main --once