@echo off
REM MVP verification script using uv

setlocal

echo ====================================
echo Game Save Transfer MVP verification
echo ====================================
echo.

echo [1/3] Linting...
uv run ruff check src/ tests/ --select I,E,F,W
if %errorlevel% neq 0 (
    echo Lint failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Running tests...
uv run pytest tests/ -v
if %errorlevel% neq 0 (
    echo Tests failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Running app entry point...
uv run python src\main.py
if %errorlevel% neq 0 (
    echo App entry point failed.
    pause
    exit /b 1
)

echo.
echo ====================================
echo MVP verification completed.
echo ====================================
pause
