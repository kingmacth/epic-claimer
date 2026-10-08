@echo off
REM Stop the Epic weekly free-games claimer.
cd /d "%~dp0"
docker compose down
echo.
echo Stopped.
pause
