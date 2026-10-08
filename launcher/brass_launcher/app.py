"""Application entry: QApplication + theme + main window.

Single instance: a second launch (double-clicking the exe again while one is
running) gets a friendly note instead of a second control room.
"""
import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .mainwindow import MainWindow
from . import theme

_LOCK = None  # keep the handle alive for the process lifetime


def _acquire_single_instance():
    """Return a handle to hold for the process lifetime, or None when a
    control room is already running."""
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.GetLastError.restype = ctypes.c_uint32
        handle = k32.CreateMutexW(None, 0, "Local\\BrassInitiative.ControlRoom")
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    import fcntl
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "brass_initiative_controlroom.lock")
    fh = open(path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main() -> int:
    global _LOCK
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    _LOCK = _acquire_single_instance()
    app = QApplication(sys.argv)
    app.setApplicationName("Brass Initiative")
    app.setOrganizationName("BrassInitiative")
    app.setStyleSheet(theme.QSS)
    if _LOCK is None:
        QMessageBox.information(
            None, "Brass Initiative",
            "Brass Initiative is already running.\n\n"
            "Close the existing window first — all progress is safe on disk.")
        return 0
    win = MainWindow()
    win.show()
    return app.exec()
