@echo off
echo ========================================
echo AMDS Simple Build Script
echo ========================================

REM Change to script directory
cd /d "%~dp0"

echo.
echo [1/4] Checking Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

echo [OK] Python is installed

echo.
echo [2/4] Checking dependencies...

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
) else (
    echo [OK] PyInstaller already installed
)

pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo Installing Pillow...
    pip install Pillow
) else (
    echo [OK] Pillow already installed
)

echo.
echo [3/4] Converting PNG to ICO...

python -c "from PIL import Image; img = Image.open('assets/images/ic_launcher.png'); img.save('assets/images/icon.ico', format='ICO', sizes=[(256,256)])"

if errorlevel 1 (
    echo [ERROR] Failed to convert icon
    pause
    exit /b 1
)

echo [OK] Icon converted

echo.
echo [4/4] Building...

python -m PyInstaller --onefile --windowed --name "AMDS" --icon="assets/images/icon.ico" --add-data "assets;assets" "src/main.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Output file: dist\AMDS.exe

pause