"""Dark brass & soot theme. The UI wears the show's palette."""
BG = "#14110e"
PANEL = "#1e1a15"
PANEL2 = "#262019"
BORDER = "#3a3226"
BRASS = "#C9A227"
BRASS_DIM = "#8A6B1F"
TEAL = "#1F7A74"
AMBER = "#FFB33A"
TEXT = "#F2EDE3"
DIM = "#9a938a"
ERR = "#d9534f"
OK = "#6fbf73"
SHOCK = "#4FC8E8"

QSS = f"""
* {{
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  color: {TEXT};
  font-size: 13px;
}}
QMainWindow, QWidget {{ background: {BG}; }}
QGroupBox {{
  background: {PANEL};
  border: 1px solid {BORDER};
  border-radius: 8px;
  margin-top: 14px;
  padding: 10px 8px 8px 8px;
  font-weight: 600;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  subcontrol-position: top left;
  left: 12px;
  padding: 0 6px;
  color: {BRASS};
  font-size: 11px;
  letter-spacing: 2px;
}}
QLabel {{ background: transparent; }}
QLabel#appTitle {{
  color: {BRASS};
  font-size: 19px;
  font-weight: 700;
  font-family: Georgia, 'Times New Roman', serif;
  letter-spacing: 3px;
}}
QLabel#appSub {{ color: {DIM}; font-size: 11px; }}
QLabel#tagChip {{
  color: {BG};
  background: {BRASS};
  border-radius: 4px;
  padding: 3px 10px;
  font-weight: 700;
  font-family: Consolas, 'Cascadia Mono', Menlo, monospace;
  font-size: 13px;
}}
QLabel#modeChip {{
  color: {TEXT};
  background: {PANEL2};
  border: 1px solid {BORDER};
  border-radius: 4px;
  padding: 3px 10px;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 1px;
}}
QLabel#statusLine {{
  color: {AMBER};
  font-family: Consolas, 'Cascadia Mono', Menlo, monospace;
  font-size: 12px;
}}
QLabel#bigEp {{
  color: {TEXT};
  font-size: 24px;
  font-weight: 700;
  font-family: Georgia, serif;
}}
QLabel#metricName {{ color: {DIM}; font-size: 11px; letter-spacing: 1px; }}
QLabel#metricVal {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
QLabel#led {{
  background: {BRASS_DIM};
  border-radius: 7px;
  min-width: 14px; min-height: 14px;
  max-width: 14px; max-height: 14px;
}}
QProgressBar {{
  background: {PANEL2};
  border: 1px solid {BORDER};
  border-radius: 4px;
  height: 14px;
  text-align: center;
  font-size: 9px;
  color: {DIM};
}}
QProgressBar::chunk {{ background: {BRASS}; border-radius: 3px; }}
QProgressBar#tealBar::chunk {{ background: {TEAL}; }}
QProgressBar#amberBar::chunk {{ background: {AMBER}; }}
QProgressBar#shockBar::chunk {{ background: {SHOCK}; }}
QFrame#stepRow {{
  background: {PANEL};
  border: 1px solid {BORDER};
  border-radius: 6px;
  margin: 3px 2px;
  padding: 6px 8px;
}}
QFrame#stepRowActive {{
  background: {PANEL2};
  border: 1px solid {BRASS};
  border-radius: 6px;
  margin: 3px 2px;
  padding: 6px 8px;
}}
QFrame#stepRowDone {{
  background: {PANEL};
  border: 1px solid {BORDER};
  border-radius: 6px;
  margin: 3px 2px;
  padding: 6px 8px;
  opacity: 0.75;
}}
QLabel#stepId {{
  font-family: Consolas, 'Cascadia Mono', Menlo, monospace;
  color: {DIM};
  font-size: 11px;
  min-width: 118px;
}}
QLabel#stepName {{ font-weight: 600; }}
QLabel#laneBadge {{
  font-size: 9px;
  letter-spacing: 1px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: 700;
}}
QLabel#laneText {{ background: {TEAL}; color: {TEXT}; }}
QLabel#laneMachine {{ background: {BRASS_DIM}; color: {TEXT}; }}
QLabel#dot {{
  border-radius: 5px; min-width: 10px; min-height: 10px;
  max-width: 10px; max-height: 10px;
  background: {BORDER};
}}
QPushButton {{
  background: {PANEL2};
  color: {TEXT};
  border: 1px solid {BORDER};
  border-radius: 6px;
  padding: 8px 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}}
QPushButton:hover {{ border-color: {BRASS_DIM}; background: #2d261d; }}
QPushButton:pressed {{ background: #191510; }}
QPushButton:disabled {{ color: #5c564d; background: {PANEL}; border-color: #2a251d; }}
QPushButton#primary {{
  background: {BRASS};
  color: {BG};
  border: 1px solid {BRASS};
  font-weight: 700;
}}
QPushButton#primary:hover {{ background: #d8b23a; }}
QPushButton#primary:disabled {{ background: {BRASS_DIM}; color: #14110e; }}
QPushButton#danger {{ color: #e8b0ae; border-color: #5a3532; }}
QPushButton#danger:hover {{ border-color: {ERR}; background: #2c1b19; }}
QPlainTextEdit, QTextEdit {{
  background: #100e0b;
  border: 1px solid {BORDER};
  border-radius: 6px;
  font-family: Consolas, 'Cascadia Mono', Menlo, monospace;
  font-size: 11px;
  color: #cfc8bd;
}}
QTableWidget {{
  background: #100e0b;
  border: 1px solid {BORDER};
  border-radius: 6px;
  gridline-color: {BORDER};
  font-family: Consolas, 'Cascadia Mono', Menlo, monospace;
  font-size: 11px;
}}
QTableWidget::item {{ padding: 3px 6px; }}
QHeaderView::section {{
  background: {PANEL};
  color: {BRASS};
  border: none;
  border-bottom: 1px solid {BORDER};
  padding: 4px;
  font-size: 10px;
  letter-spacing: 1px;
}}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {BRASS_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QComboBox, QSpinBox, QLineEdit {{
  background: #100e0b;
  border: 1px solid {BORDER};
  border-radius: 5px;
  padding: 6px 8px;
  color: {TEXT};
  font-size: 12px;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {BRASS_DIM}; }}
QComboBox QAbstractItemView {{
  background: {PANEL};
  border: 1px solid {BORDER};
  selection-background-color: {BRASS_DIM};
}}
QSplitter::handle {{ background: {BORDER}; width: 2px; }}
QCheckBox {{ color: {TEXT}; }}
"""
