@echo off
cd /d C:\Users\VACA\Projects\market-scanner
if not exist logs mkdir logs

echo [%date% %time%] Spustam Market Scanner... >> logs\startup.log

start "MarketScanner-Agent" /min cmd /c "cd /d C:\Users\VACA\Projects\market-scanner && .venv\Scripts\python.exe -m market_scanner.main >> logs\agent.log 2>&1"

timeout /t 3 /nobreak >nul

start "MarketScanner-App" /min cmd /c "cd /d C:\Users\VACA\Projects\market-scanner && .venv\Scripts\python.exe -m streamlit run app.py --server.port 8501 --server.headless true >> logs\app.log 2>&1"

echo Market Scanner bezi na pozadi.
echo Agent: skenuje trh pocas US hodin
echo Appka: http://localhost:8501
timeout /t 5