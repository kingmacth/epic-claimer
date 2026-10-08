@echo off
REM Epic weekly free-games claimer - one-time setup
REM Fetches the upstream source, applies the local patches, creates .env
REM Just double-click this file. (Chinese guide: see README.md)
setlocal
cd /d "%~dp0"

set "UPSTREAM=https://github.com/Ronchy2000/epic-freebies-helper.git"
set "BASE_COMMIT=d90190bf3f9f87e9da71c50c81f155c4586bdb33"

echo [1/3] Upstream : %UPSTREAM%
echo       Commit   : %BASE_COMMIT:~0,7%
echo.

REM Use upstream's pyproject.toml to tell whether repo\ is really ready
REM (a failed download would leave an empty shell behind)
if exist "repo\pyproject.toml" (
    echo       repo\ already present, skipping download
    echo       ^(delete repo\ first if you want a clean rebuild^)
) else (
    if exist "repo" rmdir /s /q "repo"
    mkdir "repo"
    echo [2/3] Downloading upstream source ...
    git -C repo init -q
    if errorlevel 1 goto :fail
    git -C repo remote add origin "%UPSTREAM%"
    git -C repo -c core.autocrlf=false fetch -q --depth 1 origin "%BASE_COMMIT%"
    if errorlevel 1 (
        echo       download failed, retrying in 5s ...
        timeout /t 5 /nobreak >nul
        git -C repo -c core.autocrlf=false fetch -q --depth 1 origin "%BASE_COMMIT%"
        if errorlevel 1 (
            rmdir /s /q "repo"
            goto :fail
        )
    )
    git -C repo -c core.autocrlf=false checkout -q FETCH_HEAD
    if errorlevel 1 goto :fail
)

echo [3/3] Applying local patches ...
for %%p in ("patches\*.patch") do (
    echo       - %%~nxp
    git -C repo apply --3way "%%~fp"
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to apply patch: %%~nxp
        echo         The upstream code may have changed.
        echo         See patches\README.md for manual steps.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo       .env created
) else (
    echo       .env already exists, left unchanged
)

echo.
echo Done. Next steps:
echo   1. Edit .env and fill in EPIC_EMAIL, EPIC_PASSWORD, GLM_API_KEY
echo   2. Double-click start.cmd  ^(or run: docker compose up -d --build^)
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Failed to download upstream source.
echo         If GitHub is slow or blocked, configure a proxy for git first:
echo             git config --global http.proxy http://127.0.0.1:7890
echo         ^(use your own port; undo with: git config --global --unset http.proxy^)
pause
exit /b 1
