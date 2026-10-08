"""Application entry: QApplication + theme + main window."""
import os
import sys

from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow
from . import theme


def main() -> int:
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("Brass Initiative")
    app.setOrganizationName("BrassInitiative")
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.show()
    return app.exec()
