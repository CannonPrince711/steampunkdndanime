#!/usr/bin/env python3
"""Brass Initiative launcher — top-level entry point (PyInstaller target).

Run from anywhere:  python launcher/brass_launcher.py
The repo root is auto-detected (BRASS_ROOT env var or the launcher's parent).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brass_launcher.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
