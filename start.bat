@echo off
cls
echo ===========================================
echo   Price Analysis Agent
echo ===========================================

echo [1/2] Starting backend (port 8000)...
start "PriceAgent-Backend" cmd /k "cd /d %~dp0backend && E:\anaconda\envs\price_agent\python.exe -m src.main"

echo [2/2] Starting frontend (port 5175)...
start "PriceAgent-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ===========================================
echo   Backend API : http://localhost:8000/docs
echo   Frontend    : http://localhost:5175
echo ===========================================
pause
