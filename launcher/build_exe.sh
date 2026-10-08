#!/usr/bin/env bash
# BRASS INITIATIVE — build the desktop binary on Linux/macOS (run where Blender is)
set -e
cd "$(dirname "$0")"

echo "[1/3] venv check"
python3 --version || { echo "Python 3.10+ required"; exit 1; }

echo "[2/3] install"
python3 -m venv .buildenv 2>/dev/null || true
./.buildenv/bin/pip install --quiet --upgrade pip
./.buildenv/bin/pip install --quiet -r requirements.txt pyinstaller

echo "[3/3] build"
python3 make_icon.py
./.buildenv/bin/pyinstaller --noconfirm --onefile --windowed --name "brass_initiative" \
  --icon make_icon.ico --collect-all PySide6 brass_launcher.py

[ -x dist/brass_initiative ] || { echo "BUILD FAILED — dist/brass_initiative missing"; exit 1; }
echo
echo "Done: dist/brass_initiative  (single file; place it inside the repo)"
