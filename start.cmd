@echo off
REM Start the Epic weekly free-games claimer in the background.
cd /d "%~dp0"
docker compose up -d
echo.
echo Started. Tail the logs with:  logs.cmd
pause
