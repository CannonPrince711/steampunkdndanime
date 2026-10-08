@echo off
REM ============================================================
REM  BRASS INITIATIVE — build the Windows .exe (run on Windows)
REM  Double-click this, or:  build_exe.bat
REM ============================================================
cd /d %~dp0

echo.
echo [1/3] Python check
python -c "import struct,sys; bits=struct.calcsize('P')*8; print('Python', sys.version.split()[0], bits, '-bit')" || (echo Python 3.10+ is required. Install 64-bit Python from python.org and re-run. & pause & exit /b 1)

echo.
echo [2/3] Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || (echo pip install failed & pause & exit /b 1)

echo.
echo [3/3] Building the exe
python make_icon.py
pyinstaller --noconfirm --onefile --windowed --name "Brass Initiative" ^
  --icon make_icon.ico ^
  --collect-all PySide6 ^
  brass_launcher.py || (echo pyinstaller failed & pause & exit /b 1)

if not exist "dist\Brass Initiative.exe" (
  echo.
  echo BUILD FAILED — dist\Brass Initiative.exe was not produced.
  echo Check the messages above and re-run.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  BUILD OK.  Your exe is:
echo      dist\Brass Initiative.exe
echo
echo  Put it anywhere inside the repo (e.g. the repo root) and
echo  double-click it — it finds the repo by walking up.
echo  (The "build" and "spec" folders are scratch space — the
echo   only thing to run is dist\Brass Initiative.exe)
echo ============================================================
echo.
echo  If it says "Failed to load Python DLL ... python312.dll":
echo    1. Install the Visual C++ Redistributable (x64):
echo       https://aka.ms/vs/17/release/vc_redist.x64.exe
echo       then reboot and try again.
echo    2. Make sure your Python is 64-bit (see the check above).
echo ============================================================
pause
