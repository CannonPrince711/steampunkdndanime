@echo off
REM ============================================================
REM  BRASS INITIATIVE — build the Windows .exe (run on Windows)
REM  Double-click this, or:  build_exe.bat
REM ============================================================
cd /d %~dp0

echo.
echo [1/3] Python check
python --version || (echo Python 3.10+ is required. Install from python.org and re-run. & pause & exit /b 1)

echo.
echo [2/3] Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || (echo pip install failed & pause & exit /b 1)

echo.
echo [3/3] Building the exe
python make_icon.py
pyinstaller --noconfirm --windowed --name "Brass Initiative" ^
  --icon make_icon.ico ^
  --collect-all PySide6 ^
  brass_launcher.py || (echo pyinstaller failed & pause & exit /b 1)

echo.
echo ============================================================
echo  Done. Your exe is in:  dist\Brass Initiative.exe
echo  Copy it anywhere — it finds the repo next to itself,
echo  or set BRASS_ROOT to the repo folder.
echo ============================================================
pause
