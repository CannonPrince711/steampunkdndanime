"""The control room: series state, pipeline, ledger, log, and the autopilot deck."""
import json
import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QLineEdit,
    QSpinBox,
)

from . import theme
from .engine import Engine
from .runner_cli import RunnerCLI, RunnerError


def _app_dir():
    """Where the app lives: the exe's folder when frozen (PyInstaller),
    the launcher/ folder when run from source."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


SETTINGS_PATH = os.path.join(_app_dir(), "settings.json")

DEFAULTS = {
    "mode": "sim",
    "root": "",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "context_chars": 120000,
    "timeout": 900,
    "blender_path": "",
    "ffmpeg_path": "",
    "gpu_cap": 900,
}


def find_root():
    """Locate the repo (the folder containing canon/series_state.json).
    Checks BRASS_ROOT, then walks up from cwd and from the app's own folder —
    so the exe works from the repo root, launcher/, or launcher/dist/."""
    def walk_up(start, depth=8):
        c = os.path.abspath(start)
        for _ in range(depth):
            if os.path.exists(os.path.join(c, "canon", "series_state.json")):
                return c
            parent = os.path.dirname(c)
            if parent == c:
                break
            c = parent
        return None

    cands = []
    if os.environ.get("BRASS_ROOT"):
        cands.append(os.environ["BRASS_ROOT"])
    cands.append(os.getcwd())
    cands.append(_app_dir())
    for c in cands:
        found = walk_up(c)
        if found:
            return found
    return cands[0]


def load_settings():
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as fh:
                s.update(json.load(fh))
        except (OSError, json.JSONDecodeError):
            pass
    if not s.get("root"):
        s["root"] = find_root()
    return s


def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=2)
            fh.write("\n")
    except OSError:
        pass


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — Brass Initiative")
        self.resize(460, 420)
        self.settings = dict(settings)
        form = QFormLayout(self)
        form.setSpacing(10)
        self.mode = QComboBox()
        self.mode.addItems(["sim — offline autopilot (no API needed)",
                            "llm — OpenAI-compatible API autopilot"])
        self.base_url = QLineEdit(self.settings.get("base_url", ""))
        self.api_key = QLineEdit(self.settings.get("api_key", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.model = QLineEdit(self.settings.get("model", ""))
        self.context = QSpinBox()
        self.context.setRange(8000, 2000000)
        self.context.setSingleStep(8000)
        self.context.setValue(int(self.settings.get("context_chars", 120000)))
        self.timeout = QSpinBox()
        self.timeout.setRange(60, 7200)
        self.timeout.setValue(int(self.settings.get("timeout", 900)))
        self.blender = QLineEdit(self.settings.get("blender_path", ""))
        self.ffmpeg = QLineEdit(self.settings.get("ffmpeg_path", ""))
        self.gpu = QSpinBox()
        self.gpu.setRange(60, 100000)
        self.gpu.setValue(int(self.settings.get("gpu_cap", 900)))
        root_row = QHBoxLayout()
        self.root = QLineEdit(self.settings.get("root", ""))
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._pick_root)
        root_row.addWidget(self.root)
        root_row.addWidget(browse)
        root_widget = QWidget()
        root_widget.setLayout(root_row)
        form.addRow("Mode", self.mode)
        form.addRow("Repo root", root_widget)
        form.addRow("API base URL", self.base_url)
        form.addRow("API key", self.api_key)
        form.addRow("Model", self.model)
        form.addRow("Context chars / step", self.context)
        form.addRow("LLM timeout (s)", self.timeout)
        form.addRow("Blender path", self.blender)
        form.addRow("ffmpeg path", self.ffmpeg)
        form.addRow("GPU min cap / ep", self.gpu)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _pick_root(self):
        d = QFileDialog.getExistingDirectory(self, "Repo root", self.root.text())
        if d:
            self.root.setText(d)

    def accept(self):
        self.settings.update({
            "mode": "sim" if self.mode.currentIndex() == 0 else "llm",
            "root": self.root.text().strip(),
            "base_url": self.base_url.text().strip(),
            "api_key": self.api_key.text().strip(),
            "model": self.model.text().strip(),
            "context_chars": self.context.value(),
            "timeout": self.timeout.value(),
            "blender_path": self.blender.text().strip(),
            "ffmpeg_path": self.ffmpeg.text().strip(),
            "gpu_cap": self.gpu.value(),
        })
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.setWindowTitle("BRASS INITIATIVE — Series Autopilot")
        self.resize(1440, 860)
        self.cli = RunnerCLI(self.settings["root"])
        self.engine = None
        self._build_ui()
        QTimer.singleShot(60, self.refresh)

    def closeEvent(self, event):
        # Stopping the window must stop the autopilot too — otherwise the
        # loop keeps running headless and the next launch looks like it
        # "opened up more".
        if self.engine is not None and self.engine.isRunning():
            self.engine.request_stop()
            if not self.engine.wait(4000):
                self.engine.terminate()
                self.engine.wait(1000)
        super().closeEvent(event)

    # ------------------------------------------------------------------- ui
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # header
        header = QHBoxLayout()
        title = QLabel("⚙ BRASS INITIATIVE")
        title.setObjectName("appTitle")
        sub = QLabel("autonomous steampunk D&D anime series engine")
        sub.setObjectName("appSub")
        tbox = QVBoxLayout()
        tbox.setSpacing(0)
        tbox.addWidget(title)
        tbox.addWidget(sub)
        header.addLayout(tbox)
        self.tag_chip = QLabel("S01E01")
        self.tag_chip.setObjectName("tagChip")
        self.mode_chip = QLabel("SIM")
        self.mode_chip.setObjectName("modeChip")
        header.addWidget(self.tag_chip)
        header.addWidget(self.mode_chip)
        header.addStretch(1)
        self.status_line = QLabel("—")
        self.status_line.setObjectName("statusLine")
        self.status_line.setStyleSheet("max-width: 560px;")
        header.addWidget(self.status_line, 1)
        self.led = QLabel()
        self.led.setObjectName("led")
        self.led.setFixedSize(14, 14)
        header.addWidget(self.led)
        root.addLayout(header)

        # body
        body = QSplitter(Qt.Horizontal)

        # left: state
        left = QGroupBox("SERIES STATE")
        lv = QVBoxLayout(left)
        lv.setSpacing(8)
        self.ep_big = QLabel("S1E1")
        self.ep_big.setObjectName("bigEp")
        lv.addWidget(self.ep_big)
        lv.addWidget(self._metric("ASSAY AWARENESS"))
        self.assay_bar = QProgressBar()
        self.assay_bar.setRange(0, 100)
        lv.addWidget(self.assay_bar)
        self.assay_tier = QLabel("tier —")
        self.assay_tier.setObjectName("metricVal")
        lv.addWidget(self.assay_tier)
        lv.addWidget(self._metric("PISTOL — SECOND OPINION"))
        self.pistol_bar = QProgressBar()
        self.pistol_bar.setRange(0, 100)
        self.pistol_bar.setObjectName("amberBar")
        lv.addWidget(self.pistol_bar)
        self.pistol_meta = QLabel("")
        self.pistol_meta.setObjectName("metricVal")
        lv.addWidget(self.pistol_meta)
        self.cyl_row = QHBoxLayout()
        lv.addLayout(self.cyl_row)
        lv.addWidget(self._metric("COG — ELSIE BRASSWRIGHT"))
        self.cog_lines = QLabel("")
        self.cog_lines.setObjectName("metricVal")
        self.cog_lines.setWordWrap(True)
        lv.addWidget(self.cog_lines)
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setObjectName("tealBar")
        lv.addWidget(self.conf_bar)
        self.ct_group = QGroupBox("CONTRAPTIONS")
        ctv = QVBoxLayout(self.ct_group)
        ctv.setSpacing(4)
        self.ct_container = ctv
        lv.addWidget(self.ct_group)
        self.thread_label = QLabel("")
        self.thread_label.setObjectName("metricVal")
        self.thread_label.setWordWrap(True)
        lv.addWidget(self.thread_label)
        lv.addWidget(self._metric("GPU MINUTES"))
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setObjectName("shockBar")
        lv.addWidget(self.gpu_bar)
        lv.addStretch(1)

        # center: pipeline + detail
        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(8)
        pipe_box = QGroupBox("PIPELINE")
        pv = QVBoxLayout(pipe_box)
        pv.setContentsMargins(6, 10, 6, 6)
        self.pipeline_scroll = QScrollArea()
        self.pipeline_scroll.setWidgetResizable(True)
        self.pipeline_inner = QWidget()
        self.pipeline_v = QVBoxLayout(self.pipeline_inner)
        self.pipeline_v.setContentsMargins(0, 0, 6, 0)
        self.pipeline_v.setSpacing(0)
        self.pipeline_v.addStretch(1)
        self.pipeline_scroll.setWidget(self.pipeline_inner)
        pv.addWidget(self.pipeline_scroll)
        cv.addWidget(pipe_box, 3)
        detail_box = QGroupBox("STEP DETAIL")
        dv = QVBoxLayout(detail_box)
        dv.setContentsMargins(6, 10, 6, 6)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(190)
        dv.addWidget(self.detail)
        self.sheet_row = QHBoxLayout()
        self.sheet_label = QLabel("")
        self.sheet_label.setScaledContents(True)
        self.sheet_label.setStyleSheet(f"border: 1px solid {theme.BORDER}; border-radius: 4px;")
        self.sheet_label.setMinimumHeight(64)
        self.sheet_row.addWidget(self.sheet_label, 1)
        dv.addLayout(self.sheet_row)
        cv.addWidget(detail_box, 2)
        body.addWidget(left)
        body.addWidget(center)

        # right: ledger + log
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        led_box = QGroupBox("LEDGER")
        lrv = QVBoxLayout(led_box)
        lrv.setContentsMargins(6, 10, 6, 6)
        self.ledger = QTableWidget(0, 5)
        self.ledger.setHorizontalHeaderLabels(["EP", "TITLE", "ASKS", "ASSAY", "STATUS"])
        h = self.ledger.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.ledger.setColumnWidth(0, 52)
        self.ledger.setColumnWidth(1, 110)
        self.ledger.setColumnWidth(2, 44)
        self.ledger.setColumnWidth(3, 50)
        self.ledger.verticalHeader().setVisible(False)
        self.ledger.setEditTriggers(QTableWidget.NoEditTriggers)
        lrv.addWidget(self.ledger)
        rv.addWidget(led_box, 2)
        log_box = QGroupBox("LOG")
        lg = QVBoxLayout(log_box)
        lg.setContentsMargins(6, 10, 6, 6)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lg.addWidget(self.log)
        rv.addWidget(log_box, 3)
        body.addWidget(right)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        body.setSizes([270, 560, 380])
        root.addWidget(body, 1)

        # footer
        footer = QHBoxLayout()
        self.btn_auto = QPushButton("▶ AUTO RUN")
        self.btn_auto.setObjectName("primary")
        self.btn_auto.clicked.connect(self.on_auto)
        self.btn_pause = QPushButton("⏸ PAUSE")
        self.btn_pause.clicked.connect(self.on_pause)
        self.btn_pause.setEnabled(False)
        self.btn_step = QPushButton("⏭ STEP")
        self.btn_step.clicked.connect(self.on_step)
        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_mach = QPushButton("✔ MACHINE DONE")
        self.btn_mach.clicked.connect(self.on_machine_done)
        self.btn_mach.hide()
        self.btn_skip = QPushButton("SKIP → SIM")
        self.btn_skip.clicked.connect(self.on_skip_machine)
        self.btn_skip.hide()
        self.btn_settings = QPushButton("⚙ SETTINGS")
        self.btn_settings.clicked.connect(self.on_settings)
        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedWidth(38)
        self.btn_refresh.clicked.connect(self.refresh)
        footer.addWidget(self.btn_auto)
        footer.addWidget(self.btn_pause)
        footer.addWidget(self.btn_step)
        footer.addWidget(self.btn_stop)
        footer.addWidget(self.btn_mach)
        footer.addWidget(self.btn_skip)
        footer.addStretch(1)
        footer.addWidget(self.btn_settings)
        footer.addWidget(self.btn_refresh)
        root.addLayout(footer)

        self.setCentralWidget(central)

    def _metric(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("metricName")
        return lbl

    # ------------------------------------------------------------- rendering
    def refresh(self):
        try:
            status = self.cli.status()
        except RunnerError as exc:
            self.append_log(f"runner: {exc}", "err")
            return
        self._render_status(status)

    def _render_status(self, status):
        tag = status.get("tag", "S?E?")
        self.tag_chip.setText(tag)
        s = status.get("state_summary", {})
        self.ep_big.setText(f"S{status.get('season', 1):02d}E{status.get('episode', 1):02d}")
        aw = s.get("assay_awareness", 0.0)
        self.assay_bar.setValue(int(aw * 100))
        tiers = [(0.9, "branding"), (0.75, "Tallyman squad"), (0.5, "inspector"),
                 (0.3, "clerk"), (0.0, "unnoticed")]
        self.assay_tier.setText("tier " + next(n for t, n in tiers if aw >= t))
        cond = s.get("pistol_condition", 1.0)
        self.pistol_bar.setValue(int(cond * 100))
        self.pistol_meta.setText(
            f"condition {cond:.2f}   shots {s.get('pistol_shots', 0)}")
        # cylinder chips
        while self.cyl_row.count():
            it = self.cyl_row.takeAt(0)
            wgt = it.widget()
            if wgt:
                wgt.deleteLater()
        self.cyl_row.addStretch(1)
        for i, cyl in enumerate(s.get("pistol_cylinders", [])):
            chip = QLabel(cyl)
            chip.setStyleSheet(
                f"background: {theme.BRASS_DIM}; border-radius: 3px; padding: 2px 6px;"
                f"font-size: 10px; font-weight: 700;")
            self.cyl_row.insertWidget(i, chip)
        target = s.get("cog_asks_target", "?")
        actual = s.get("cog_asks_last")
        actual = "—" if actual is None else str(actual)
        self.cog_lines.setText(
            f"permission asks: {actual}   next target {target}\n"
            f"soot baseline {s.get('cog_soot', 0.0):.2f}   "
            f"confidence bar below")
        self.conf_bar.setValue(int((s.get("cog_confidence", 0.0) or 0.0) * 100))
        # contraptions
        cts = s.get("contraptions", [])
        # rebuild simply: clear container children
        while self.ct_container.count():
            it = self.ct_container.takeAt(0)
            wgt = it.widget()
            if wgt:
                wgt.deleteLater()
        for c in cts:
            row = QWidget()
            row.setProperty("ctrow", True)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            name = QLabel(c["id"])
            name.setStyleSheet(f"color: {theme.TEXT}; font-size: 11px; min-width: 86px;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(c["condition"] * 100))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            if c["condition"] < 0.7:
                bar.setObjectName("amberBar")
            h.addWidget(name)
            h.addWidget(bar, 1)
            self.ct_container.addWidget(row)
        threads = s.get("open_threads", [])
        self.thread_label.setText(
            f"OPEN THREADS: {len(threads)}\n" +
            "\n".join("• " + t[:90] for t in threads[-3:]))
        cap = max(1, s.get("gpu_cap", 900))
        self.gpu_bar.setValue(int(min(1.0, s.get("gpu_used", 0) / cap) * 100))
        # pipeline rows
        while self.pipeline_v.count() > 1:
            it = self.pipeline_v.takeAt(0)
            wgt = it.widget()
            if wgt:
                wgt.deleteLater()
        steps = status.get("steps", [])
        nxt = (status.get("next") or {}).get("step") or {}
        for st in steps:
            self.pipeline_v.addWidget(self._step_row(st, nxt.get("id")))
        self.pipeline_v.addStretch(1)
        # detail: next step's card
        if nxt:
            self._show_detail(nxt)
        else:
            self.detail.setPlainText("— no pending step —")
        # sheet
        ep = status.get("episode", 1)
        sheet = os.path.join(self.cli.root, "output", f"EP{ep:02d}",
                             f"EP{ep:02d}_contact_sheet.png")
        if os.path.exists(sheet):
            pm = QPixmap(sheet)
            if not pm.isNull():
                self.sheet_label.setPixmap(pm)
        else:
            self.sheet_label.clear()
        # ledger
        self._render_ledger()

    def _step_row(self, st, active_id):
        done = st.get("done", False)
        active = st.get("id") == active_id
        row = QFrame()
        row.setObjectName("stepRowActive" if active else ("stepRowDone" if done else "stepRow"))
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 5, 8, 5)
        h.setSpacing(10)
        dot = QLabel()
        dot.setObjectName("dot")
        dot.setFixedSize(10, 10)
        color = theme.OK if done else (theme.AMBER if active else theme.BORDER)
        dot.setStyleSheet(f"background: {color};")
        sid = QLabel(st["id"])
        sid.setObjectName("stepId")
        name = QLabel(st["lane"].upper() if st["id"].startswith("M") else st["label"])
        name.setObjectName("stepName")
        badge = QLabel("MACHINE" if st["lane"] == "machine" else "TEXT")
        badge.setObjectName("laneMachine" if st["lane"] == "machine" else "laneText")
        state = QLabel("✓ done" if done else ("▸ active" if active else "pending"))
        state.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        h.addWidget(dot)
        h.addWidget(sid)
        h.addWidget(name, 1)
        h.addWidget(badge)
        h.addWidget(state)
        return row

    def _show_detail(self, step):
        lines = [
            f"STEP   {step['id']}",
            f"AGENT  {step.get('agent_label', '')}",
            f"LANE   {step.get('lane', '')}",
            "",
            "READ",
        ]
        lines += [f"  {r}" for r in step.get("read", [])]
        lines += ["", "WRITE (completion gate)"]
        lines += [f"  {w}" for w in step.get("write", [])]
        if step.get("notes"):
            lines += ["", f"NOTES  {step['notes']}"]
        self.detail.setPlainText("\n".join(lines))

    def _render_ledger(self):
        try:
            rows = self.cli.ledger_rows()
        except OSError:
            rows = []
        self.ledger.setRowCount(0)
        for cells in rows:
            r = self.ledger.rowCount()
            self.ledger.insertRow(r)
            vals = [cells[0], cells[1] if len(cells) > 1 else "",
                    cells[6] if len(cells) > 6 else "",
                    cells[7] if len(cells) > 7 else "",
                    cells[-1] if cells else ""]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if c == 1 else Qt.AlignCenter))
                self.ledger.setItem(r, c, it)
        self.ledger.scrollToBottom()

    # ----------------------------------------------------------------- log
    def append_log(self, msg, level="info"):
        colors = {"info": "#cfc8bd", "ok": theme.OK, "warn": theme.AMBER, "err": theme.ERR}
        self.log.appendHtml(
            f'<span style="color:{colors.get(level, theme.TEXT)}">{msg}</span>')

    # -------------------------------------------------------------- controls
    def _engine_running(self):
        return self.engine is not None and self.engine.isRunning()

    def _start_engine(self, step_once=False):
        if self._engine_running():
            return
        self.settings["mode"] = "sim" if self.settings.get("mode") == "sim" else "llm"
        self.mode_chip.setText("LLM" if self.settings["mode"] == "llm" else "SIM")
        self.cli = RunnerCLI(self.settings["root"])
        eng = Engine(self.settings["root"], self.settings)
        eng.log.connect(self.append_log)
        eng.line.connect(self.status_line.setText)
        eng.state_changed.connect(self._render_status)
        eng.episode_certified.connect(lambda tag, line: self.append_log(line, "ok"))
        eng.season_complete.connect(lambda line: self.append_log(line, "ok"))
        eng.blocked.connect(lambda msg: (self.append_log("BLOCKED: " + msg, "err"),
                                         self._set_running(False)))
        eng.awaiting_machine.connect(self._on_awaiting_machine)
        eng.stopped.connect(self._on_stopped)
        if step_once:
            eng.request_step_once()
        eng.start()
        self.engine = eng
        self._set_running(True)

    def _on_awaiting_machine(self, info):
        self.btn_mach.show()
        self.btn_skip.show()
        self.append_log(f"AWAITING MACHINE {info['stage']} — {info.get('reason', '')}", "warn")

    def _set_running(self, running):
        self.led.setStyleSheet(
            f"background: {theme.AMBER if running else theme.BRASS_DIM}; border-radius: 7px;")
        self.btn_auto.setEnabled(not running)
        self.btn_step.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running)
        if not running:
            self.btn_mach.hide()
            self.btn_skip.hide()

    def _on_stopped(self, msg):
        self._set_running(False)
        self.append_log(msg, "info")
        self.refresh()

    def on_auto(self):
        self._start_engine()

    def on_step(self):
        self._start_engine(step_once=True)

    def on_pause(self):
        if self.engine:
            paused = not self.engine._pause
            self.engine.set_pause(paused)
            self.btn_pause.setText("▶ RESUME" if paused else "⏸ PAUSE")
            self.append_log("paused" if paused else "resumed", "warn")

    def on_stop(self):
        if self.engine:
            self.engine.request_stop()
            self.append_log("stop requested", "warn")

    def on_machine_done(self):
        if self.engine:
            self.engine.machine_done_clicked()
            self.btn_mach.hide()
            self.btn_skip.hide()

    def on_skip_machine(self):
        if self.engine:
            self.engine._machine_resume = True
            self.btn_mach.hide()
            self.btn_skip.hide()
            self.append_log("machine step skipped — sim artifacts will be laid down", "warn")

    def on_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.settings = dlg.settings
            save_settings(self.settings)
            self.cli = RunnerCLI(self.settings["root"])
            self.append_log("settings saved", "ok")
            self.refresh()
