@echo off
REM Show live container logs.
cd /d "%~dp0"
docker compose logs -f --tail=200
