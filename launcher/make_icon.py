#!/usr/bin/env python3
"""Draw the launcher icon (brass gear + d20) offscreen with Qt. Needs PySide6."""
import math
import os
import sys

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication


def draw(size):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = size / 2
    # soot disc
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(20, 17, 14, 235))
    p.drawEllipse(QPointF(c, c), c * 0.92, c * 0.92)
    # gear
    p.setBrush(QColor("#C9A227"))
    p.setPen(QPen(QColor("#8A6B1F"), size * 0.02))
    outer, inner, teeth = c * 0.62, c * 0.5, 12
    pts = []
    for i in range(teeth * 2):
        ang = math.pi * i / teeth
        r = outer if i % 2 == 0 else inner
        pts.append(QPointF(c + r * math.cos(ang), c + r * math.sin(ang)))
    p.drawPolygon(QPolygonF(pts))
    # gear hole
    p.setBrush(QColor(26, 23, 20))
    p.drawEllipse(QPointF(c, c), c * 0.28, c * 0.28)
    # d20 (hex with center tri)
    p.setBrush(QColor("#1F7A74"))
    p.setPen(QPen(QColor("#FFB33A"), size * 0.015))
    hc = QPointF(c, c)
    hexpts = [QPointF(c + c * 0.2 * math.cos(math.pi / 3 * i + math.pi / 6),
                      c + c * 0.2 * math.sin(math.pi / 3 * i + math.pi / 6))
              for i in range(6)]
    p.drawPolygon(QPolygonF(hexpts))
    tri = [QPointF(c - c * 0.12, c + c * 0.09), QPointF(c + c * 0.12, c + c * 0.09),
           QPointF(c, c - c * 0.11)]
    p.setBrush(QColor("#FFB33A"))
    p.drawPolygon(QPolygonF(tri))
    p.end()
    return pm


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    here = os.path.dirname(os.path.abspath(__file__))
    for name, size in (("make_icon.ico", 256), ("make_icon.png", 512)):
        pm = draw(size)
        out = os.path.join(here, name)
        ok = pm.save(out, "ICO" if name.endswith(".ico") else "PNG")
        print(f"{'wrote' if ok else 'FAILED'} {out}")
        if not ok:
            print("note: .ico save unsupported on this platform — exe will use the default icon")


if __name__ == "__main__":
    main()
