@echo off
title Market Scanner App
cd /d C:\Users\VACA\Projects\market-scanner
call .venv\Scripts\activate.bat
start http://localhost:8501
py -m streamlit run app.py --server.port 8501