@echo off
REM Test runner using uv

setlocal

echo ====================================
echo Running Game Save Transfer tests
echo ====================================
echo.

uv run pytest tests/ -v --tb=short

pause
