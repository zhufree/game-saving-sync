@echo off
REM Build Windows desktop package with PyInstaller.

setlocal

echo ====================================
echo Building Game Save Transfer
echo ====================================
echo.

if not exist .venv\Scripts\python.exe (
    echo Error: .venv was not found.
    echo Run setup_dev.bat or uv sync --group dev first.
    pause
    exit /b 1
)

echo Checking PyInstaller...
.venv\Scripts\python.exe -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller is not installed. Installing it into .venv...
    .venv\Scripts\python.exe -m ensurepip --upgrade
    .venv\Scripts\python.exe -m pip install "pyinstaller>=6.3.0"
    if %errorlevel% neq 0 (
        echo Error: failed to install PyInstaller.
        pause
        exit /b 1
    )
)

echo.
echo Running PyInstaller...
.venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name GameSaveTransfer ^
  --paths src ^
  --hidden-import qfluentwidgets ^
  --hidden-import qframelesswindow ^
  src\main.py

if %errorlevel% neq 0 (
    echo Error: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Creating zip package...
if exist dist\GameSaveTransfer-windows-x64.zip del /f /q dist\GameSaveTransfer-windows-x64.zip
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\GameSaveTransfer\*' -DestinationPath 'dist\GameSaveTransfer-windows-x64.zip' -CompressionLevel Optimal"

if %errorlevel% neq 0 (
    echo Error: zip package failed.
    pause
    exit /b 1
)

echo.
echo ====================================
echo Build completed.
echo ====================================
echo Folder: dist\GameSaveTransfer
echo Zip:    dist\GameSaveTransfer-windows-x64.zip
echo.
pause
