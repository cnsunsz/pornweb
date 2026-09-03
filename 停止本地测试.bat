@echo off
taskkill /FI "WindowTitle eq MV-Backend*" /F >nul 2>&1
taskkill /FI "WindowTitle eq MV-Frontend*" /F >nul 2>&1
echo All services stopped.
