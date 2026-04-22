@echo off
REM Development environment setup script using uv

setlocal

echo ====================================
echo Game Save Transfer development setup
echo ====================================
echo.

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo uv is not installed. Installing uv...
    echo.
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo Error: uv installation failed.
        echo Please install manually: https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
)

echo.
echo Syncing project dependencies...
uv sync --group dev
if %errorlevel% neq 0 (
    echo Error: dependency sync failed.
    pause
    exit /b 1
)

echo.
echo ====================================
echo Development environment is ready.
echo ====================================
echo.
echo Run the app:
echo   uv run python src\main.py
echo.
echo Run tests:
echo   uv run pytest
pause
