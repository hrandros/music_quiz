import os
import subprocess
import sys
import threading

import socketio
from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

from admin_ui.constants import APP_HOST, APP_PORT, THEME
from admin_ui.database_tab import DatabaseTabMixin
from admin_ui.live_tab import LiveTabMixin
from admin_ui.setup_tab import SetupTabMixin
from admin_ui.styles import build_styles
from admin_ui.utils import get_local_ip
from admin_ui.widgets import UiSignals
from app import create_app
from extensions import db
from musicquiz.models import LogEntry


class AdminLauncher(QtWidgets.QMainWindow, SetupTabMixin, LiveTabMixin, DatabaseTabMixin):
    def __init__(self):
        super().__init__()

        self.app = create_app()
        self.sio = socketio.Client(reconnection=True)
        self.sio_connected = False
        self.is_paused = False
        self.registrations_open = False
        self.next_round_ready = False
        self.countdown_remaining = 0
        self.countdown_timer = QtCore.QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._tick_countdown)
        self.grading_rows = []
        self.player_row_map = {}
        self.player_status_cache = {}
        self.live_timer_remaining = None
        self.live_timer_total = None
        self.live_player = QtMultimedia.QMediaPlayer(self)
        self.live_audio_output = QtMultimedia.QAudioOutput(self)
        self.live_audio_output.setVolume(0.7)
        self.live_player.setAudioOutput(self.live_audio_output)
        self.live_media_seek_ms = None
        self.live_player.mediaStatusChanged.connect(self._on_live_media_status)
        self.live_player.errorOccurred.connect(self._on_live_media_error)
        self.live_audio_stop_timer = QtCore.QTimer(self)
        self.live_audio_stop_timer.setSingleShot(True)
        self.live_audio_stop_timer.timeout.connect(self.stop_live_media)
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(APP_PORT)
        self.autoplay_wait_timer = QtCore.QTimer(self)
        self.autoplay_wait_timer.setSingleShot(True)
        self.autoplay_wait_timer.timeout.connect(self._on_autoplay_timeout)
        self.awaiting_autoplay = False
        self.pending_autoplay = None
        self.connect_retry_timer = QtCore.QTimer(self)
        self.connect_retry_timer.setInterval(1000)
        self.connect_retry_timer.timeout.connect(self._connect_retry_tick)
        self.connect_retry_deadline = None
        self.last_connect_url = None
        self.process = None
        self.stop_monitor = False
        self.monitor_thread = None
        self.server_starting = False
        self.noisy_socket_events = {
            "admin_player_list_full",
            "admin_update_player_list",
            "admin_single_player_update",
            "update_leaderboard",
            "admin_receive_grading_data",
        }

        self.signals = UiSignals()

        self._load_fonts()
        self._build_ui()
        self._apply_styles()

        self._bind_signals()
        self._bind_socket_events()

        self._load_quizzes()
        self.refresh_questions()

    def _load_fonts(self):
        fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
        for name in [
            "Oswald-Regular.ttf",
            "Oswald-Bold.ttf",
            "RobotoCondensed-Regular.ttf",
            "RobotoCondensed-Bold.ttf",
        ]:
            path = os.path.join(fonts_dir, name)
            if os.path.exists(path):
                QtGui.QFontDatabase.addApplicationFont(path)

    def _build_ui(self):
        self.setWindowTitle("Rock Quiz Admin")
        self.resize(1200, 700)
        self.setMinimumHeight(700)

        root = QtWidgets.QWidget()
        root_layout = QtWidgets.QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(10)

        logo = QtWidgets.QLabel("ROCK QUIZ")
        logo.setObjectName("SidebarLogo")
        sidebar_layout.addWidget(logo)

        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.addItems(["Setup", "Live", "Database"])
        self.nav_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.nav_list, 1)

        sidebar_layout.addStretch(1)

        self.start_stop_btn = QtWidgets.QPushButton("Start Server")
        self.start_stop_btn.clicked.connect(self.toggle_server)
        sidebar_layout.addWidget(self.start_stop_btn)

        self.server_address = QtWidgets.QLabel(self._format_address_link())
        self.server_address.setObjectName("StatusLabel")
        self.server_address.setTextFormat(QtCore.Qt.RichText)
        self.server_address.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.server_address.setOpenExternalLinks(True)
        sidebar_layout.addWidget(self.server_address)

        root_layout.addWidget(sidebar)

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.page_stack = QtWidgets.QStackedWidget()
        content_layout.addWidget(self.page_stack, 1)
        root_layout.addWidget(content, 1)

        self.tab_setup = QtWidgets.QWidget()
        self.tab_live = QtWidgets.QWidget()
        self.tab_database = QtWidgets.QWidget()
        self.page_stack.addWidget(self.tab_setup)
        self.page_stack.addWidget(self.tab_live)
        self.page_stack.addWidget(self.tab_database)

        self._build_setup_tab()
        self._build_live_tab()
        self._build_database_tab()

        self.nav_list.currentRowChanged.connect(self.page_stack.setCurrentIndex)

        self.setCentralWidget(root)

    def _apply_styles(self):
        self.setStyleSheet(build_styles(THEME))

    def _prepare_dialog_animation(self, dialog):
        dialog.setWindowOpacity(0.0)
        QtCore.QTimer.singleShot(0, lambda: self._fade_in(dialog))

    def _fade_in(self, dialog):
        anim = QtCore.QPropertyAnimation(dialog, b"windowOpacity", dialog)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        dialog._fade_anim = anim
        anim.start()

    def _bind_signals(self):
        self.signals.log_line.connect(self.append_log)
        self.signals.status_text.connect(self.server_status_label.setText)
        self.signals.address_text.connect(self.server_address.setText)
        self.signals.live_status.connect(self.update_live_status)
        self.signals.players.connect(self.update_players)
        self.signals.leaderboard.connect(self.update_leaderboard)
        self.signals.grading.connect(self.update_grading)
        self.signals.pause_state.connect(self.update_pause_button)
        self.signals.round_countdown.connect(self._on_round_countdown_signal)
        self.signals.play_audio.connect(self._on_play_audio_signal)
        self.signals.timer_update.connect(self._on_timer_update_signal)
        self.signals.tv_start_timer.connect(self._on_tv_start_timer_signal)
        self.signals.show_correct.connect(self._on_show_correct_signal)
        self.signals.round_finished.connect(self._on_round_finished_signal)
        self.signals.single_player_update.connect(self._on_single_player_update_signal)
        self.signals.live_guard_blocked.connect(self._on_live_guard_blocked_signal)

    def _bind_socket_events(self):
        @self.sio.event
        def connect():
            self.sio_connected = True
            self.signals.live_status.emit("Connected")
            self.sio.emit("admin_live_arm", {"armed": True})
            self.server_starting = False
            QtCore.QTimer.singleShot(0, lambda: self._sync_server_buttons(True))
            QtCore.QTimer.singleShot(0, self.stop_connect_retry)
            QtCore.QTimer.singleShot(0, lambda: self._set_last_event("socket connected"))
            QtCore.QTimer.singleShot(0, lambda: self._store_log(
                "socket",
                f"connected:{self.last_connect_url or 'unknown'}"
            ))
            self.refresh_live()

        @self.sio.event
        def disconnect():
            self.sio_connected = False
            self.signals.live_status.emit("Disconnected")
            QtCore.QTimer.singleShot(0, lambda: self._set_last_event("socket disconnected"))
            QtCore.QTimer.singleShot(0, lambda: self._store_log(
                "socket",
                f"disconnected:{self.last_connect_url or 'unknown'}"
            ))

        @self.sio.event
        def connect_error(data):
            QtCore.QTimer.singleShot(0, lambda: self._set_last_event("socket connect_error"))
            QtCore.QTimer.singleShot(0, lambda: self._store_log(
                "socket",
                f"connect_error:{data}"
            ))

        @self.sio.on("admin_player_list_full")
        def on_player_list(players):
            self._log_socket_event("admin_player_list_full", players)
            self.signals.players.emit(players)

        @self.sio.on("admin_update_player_list")
        def on_player_list_update(players):
            self._log_socket_event("admin_update_player_list", players)
            self.signals.players.emit(players)

        @self.sio.on("update_leaderboard")
        def on_leaderboard(data):
            self._log_socket_event("update_leaderboard", data)
            self.signals.leaderboard.emit(data)

        @self.sio.on("admin_receive_grading_data")
        def on_grading(data):
            self._log_socket_event("admin_receive_grading_data", data)
            self.signals.grading.emit(data)

        @self.sio.on("admin_auto_run_ack")
        def on_auto_run_ack(data):
            QtCore.QTimer.singleShot(0, lambda: self._set_last_event("auto_run_ack"))
            QtCore.QTimer.singleShot(0, lambda: self._store_log("socket", f"auto_run_ack:{data}"))

        @self.sio.on("admin_live_arm_ack")
        def on_live_arm_ack(data):
            QtCore.QTimer.singleShot(0, lambda: self._set_last_event("live_arm_ack"))
            QtCore.QTimer.singleShot(0, lambda: self._on_live_arm_ack(data))
            QtCore.QTimer.singleShot(0, lambda: self._store_log("socket", f"live_arm_ack:{data}"))

        @self.sio.on("quiz_pause_state")
        def on_pause(data):
            self._log_socket_event("quiz_pause_state", data)
            self.is_paused = bool(data.get("paused"))
            self.signals.pause_state.emit(self.is_paused)
            QtCore.QTimer.singleShot(0, lambda: self.set_live_audio_paused(self.is_paused))

        @self.sio.on("admin_live_guard_blocked")
        def on_guard(data):
            self.signals.live_guard_blocked.emit(data or {})

        @self.sio.on("round_countdown_start")
        def on_round_countdown(data):
            self.signals.round_countdown.emit(data or {})

        @self.sio.on("play_audio")
        def on_play_audio(data):
            self._log_socket_event("play_audio", data)
            self.signals.play_audio.emit(data or {})

        @self.sio.on("timer_update")
        def on_timer_update(data):
            if data.get("phase") == "answer_display":
                return
            self.signals.timer_update.emit(data or {})

        @self.sio.on("tv_start_timer")
        def on_tv_timer(data):
            self.signals.tv_start_timer.emit(data or {})

        @self.sio.on("screen_show_correct")
        def on_show_correct(data):
            self.signals.show_correct.emit(data or {})

        @self.sio.on("admin_round_finished")
        def on_round_finished(data):
            self.signals.round_finished.emit(data or {})

        @self.sio.on("admin_single_player_update")
        def on_player_status_update(data):
            self.signals.single_player_update.emit(data or {})

    def address_text(self):
        port = getattr(self, "port_input", None)
        if port is None:
            port_value = APP_PORT
        else:
            port_value = port.value()
        return f"http://{get_local_ip()}:{port_value}"

    def _format_address_link(self):
        url = self.address_text()
        return f"<a href=\"{url}\">{url}</a>"

    def update_address(self):
        self.signals.address_text.emit(self._format_address_link())
        if hasattr(self, "server_url_label"):
            self.server_url_label.setText(f"Server: {self.address_text()}")

    def append_log(self, line):
        if hasattr(self, "log_box") and self.log_box is not None:
            self.log_box.appendPlainText(line.rstrip())
        self._store_log("server", line.rstrip())

    def with_app(self, fn):
        with self.app.app_context():
            return fn()

    def _store_log(self, source, message):
        if not message:
            return
        if not self._should_store_log(source, message):
            return

        def _write():
            entry = LogEntry(source=source, message=str(message))
            db.session.add(entry)
            db.session.flush()
            count = db.session.query(db.func.count(LogEntry.id)).scalar() or 0
            excess = max(0, count - 1000)
            if excess > 0:
                old_ids = [row[0] for row in db.session.query(LogEntry.id)
                           .order_by(LogEntry.created_at.asc())
                           .limit(excess)
                           .all()]
                if old_ids:
                    LogEntry.query.filter(LogEntry.id.in_(old_ids))\
                        .delete(synchronize_session=False)
            db.session.commit()

        self.with_app(_write)

    def _should_store_log(self, source, message):
        text = str(message)
        if source == "ui":
            return (
                text in {"server_start", "server_stop"}
                or text.startswith("autoplay_request:")
                or text.startswith("toggle_pause:")
            )
        if source == "socket":
            allowed_prefixes = (
                "play_audio:",
                "screen_show_correct:",
                "round_countdown_start:",
                "round_finished:",
                "player_status:",
            )
            return text.startswith(allowed_prefixes)
        if source == "server":
            return text in {"server_start", "server_stop"}
        return True

    def start_server(self):
        if self.process and self.process.poll() is None:
            self.start_connect_retry()
            return
        base_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(base_dir, "app.py")
        if not os.path.exists(app_path):
            return

        port = int(self.port_input.value())
        env = os.environ.copy()
        env["MQ_HOST"] = APP_HOST
        env["MQ_PORT"] = str(port)
        env["MQ_DEBUG"] = "0"

        self.process = subprocess.Popen(
            [sys.executable, app_path],
            cwd=base_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        self.server_starting = True
        self.signals.status_text.emit("Running")
        self.signals.address_text.emit(self._format_address_link())
        self._sync_server_buttons(False)
        self.signals.log_line.emit("Server starting...")
        self._store_log("ui", "server_start")
        QtCore.QTimer.singleShot(5000, self._finish_startup_delay)

        self.stop_monitor = False
        self.monitor_thread = threading.Thread(target=self.monitor_output, daemon=True)
        self.monitor_thread.start()
        QtCore.QTimer.singleShot(500, self.start_connect_retry)

    def monitor_output(self):
        if not self.process or not self.process.stdout:
            return
        while not self.stop_monitor:
            line = self.process.stdout.readline()
            if not line:
                break
            self.signals.log_line.emit(line)
        if self.process and self.process.poll() is not None:
            self.signals.log_line.emit("Server stopped.")
            self.signals.status_text.emit("Stopped")
            self.server_starting = False
            QtCore.QTimer.singleShot(0, lambda: self._sync_server_buttons(False))
            QtCore.QTimer.singleShot(0, self.disconnect_live)

    def stop_server(self):
        if not self.process or self.process.poll() is not None:
            return
        self.signals.log_line.emit("Stopping server...")
        self._store_log("ui", "server_stop")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.stop_monitor = True
        self.signals.status_text.emit("Stopped")
        self.server_starting = False
        self._sync_server_buttons(False)
        self.disconnect_live()

    def _sync_server_buttons(self, running):
        if hasattr(self, "start_stop_btn"):
            if self.server_starting:
                self.start_stop_btn.setText("Starting...")
                self.start_stop_btn.setEnabled(False)
                return
            self.start_stop_btn.setText("Stop Server" if running else "Start Server")
            self.start_stop_btn.setEnabled(True)

    def _finish_startup_delay(self):
        self.server_starting = False
        self._sync_server_buttons(True)

    def toggle_server(self):
        if self.process and self.process.poll() is None:
            self.stop_server()
        else:
            self.start_server()

    def safe_emit(self, event, payload):
        if not self.sio_connected:
            return False
        try:
            self.sio.emit(event, payload)
            return True
        except Exception:
            self.signals.live_status.emit("Disconnected")
            return False

    def start_connect_retry(self):
        if self.sio_connected:
            return
        self.connect_retry_deadline = QtCore.QTime.currentTime().addSecs(15)
        if not self.connect_retry_timer.isActive():
            self.connect_retry_timer.start()
        self._connect_retry_tick()

    def stop_connect_retry(self):
        if self.connect_retry_timer.isActive():
            self.connect_retry_timer.stop()
        self.connect_retry_deadline = None

    def _connect_retry_tick(self):
        if self.sio_connected:
            self.stop_connect_retry()
            return
        if self.connect_retry_deadline and QtCore.QTime.currentTime() > self.connect_retry_deadline:
            self.stop_connect_retry()
            self.signals.live_status.emit("Disconnected")
            return
        self.ensure_live_connection()

    def disconnect_live(self):
        if self.sio_connected:
            self.sio.disconnect()

    def closeEvent(self, event):
        if self.sio_connected:
            self.sio.disconnect()
        if self.process and self.process.poll() is None:
            self.stop_server()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    hr_locale = QtCore.QLocale(QtCore.QLocale.Croatian, QtCore.QLocale.Croatia)
    QtCore.QLocale.setDefault(hr_locale)
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(THEME["bg_body"]))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(THEME["surface"]))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(THEME["surface_alt"]))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(THEME["bg_card"]))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(THEME["primary"]))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(palette)
    window = AdminLauncher()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
