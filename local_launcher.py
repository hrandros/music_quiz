import os
import subprocess
import sys
import threading

import socketio
from PySide6 import QtCore, QtGui, QtWidgets

from admin_ui.constants import APP_HOST, APP_PORT, THEME
from admin_ui.dialogs import (
    AudioQuestionEditorDialog,
    CreateQuizDialog,
    ImportFolderDialog,
    QrPinDialog,
    TextQuestionEditorDialog,
)
from admin_ui.styles import build_styles
from admin_ui.utils import ensure_videos_dir, get_local_ip, guess_artist_title, import_video_file
from admin_ui.widgets import UiSignals
from app import create_app
from config import Config
from extensions import db
from musicquiz.models import (
    Answer,
    Question,
    Quiz,
    SimultaneousQuestion,
    Song,
    TextMultiple,
    TextQuestion,
    Video,
)
from musicquiz.services.file_import_service import import_song_file, scan_mp3_folder
from musicquiz.services.question_service import get_question_display


class AdminLauncher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.app = create_app()
        self.sio = socketio.Client(reconnection=True)
        self.sio_connected = False
        self.is_paused = False
        self.process = None
        self.stop_monitor = False
        self.monitor_thread = None

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
        self.nav_list.addItems(["Setup", "Live", "Server"])
        self.nav_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.nav_list, 1)

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
        self.tab_server = QtWidgets.QWidget()
        self.page_stack.addWidget(self.tab_setup)
        self.page_stack.addWidget(self.tab_live)
        self.page_stack.addWidget(self.tab_server)

        self._build_setup_tab()
        self._build_live_tab()
        self._build_server_tab()

        self.nav_list.currentRowChanged.connect(self.page_stack.setCurrentIndex)

        self.setCentralWidget(root)

    def _build_setup_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_setup)
        top_bar = QtWidgets.QHBoxLayout()
        layout.addLayout(top_bar)

        title = QtWidgets.QLabel("SETUP")
        title.setObjectName("SectionTitle")
        top_bar.addWidget(title)

        top_bar.addSpacing(12)
        top_bar.addWidget(QtWidgets.QLabel("ACTIVE:"))

        self.quiz_combo = QtWidgets.QComboBox()
        self.quiz_combo.currentIndexChanged.connect(self.refresh_questions)
        top_bar.addWidget(self.quiz_combo)

        actions_btn = QtWidgets.QToolButton()
        actions_btn.setText("Actions")
        actions_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        actions_menu = QtWidgets.QMenu(actions_btn)
        actions_menu.addAction("Set Active", self.set_active_quiz)
        actions_menu.addAction("New Quiz", self.create_quiz_modal)
        actions_menu.addAction("Refresh", self.refresh_questions)
        actions_btn.setMenu(actions_menu)
        top_bar.addWidget(actions_btn)

        top_bar.addSpacing(12)
        top_bar.addWidget(QtWidgets.QLabel("Round:"))
        self.round_combo = QtWidgets.QComboBox()
        self.round_combo.addItems(["1", "2", "3", "4", "5"])
        self.round_combo.currentIndexChanged.connect(self.refresh_questions)
        top_bar.addWidget(self.round_combo)

        top_bar.addStretch(1)

        body = QtWidgets.QHBoxLayout()
        layout.addLayout(body, 1)

        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        body.addLayout(left, 5)
        body.addLayout(right, 7)

        self._build_repo_panel(left)
        self._build_create_panel(left)
        self._build_questions_panel(right)

    def _build_repo_panel(self, parent_layout):
        group = QtWidgets.QGroupBox("LOKALNI REPOZITORIJ")
        group_layout = QtWidgets.QVBoxLayout(group)

        path_row = QtWidgets.QHBoxLayout()
        self.repo_path = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_repo_folder)
        scan_btn = QtWidgets.QPushButton("Scan")
        scan_btn.clicked.connect(self.scan_repo_folder)
        import_btn = QtWidgets.QPushButton("Import Folder")
        import_btn.clicked.connect(self.open_import_folder_modal)
        path_row.addWidget(self.repo_path, 1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(scan_btn)
        path_row.addWidget(import_btn)
        group_layout.addLayout(path_row)

        search_row = QtWidgets.QHBoxLayout()
        self.repo_search = QtWidgets.QLineEdit()
        self.repo_search.setPlaceholderText("Search (artist/title/file)...")
        self.repo_search.textChanged.connect(self.filter_repo_list)
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_repo_search)
        search_row.addWidget(self.repo_search, 1)
        search_row.addWidget(clear_btn)
        group_layout.addLayout(search_row)

        self.repo_list = QtWidgets.QListWidget()
        self.repo_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        group_layout.addWidget(self.repo_list, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(QtWidgets.QLabel("Round"))
        self.repo_round = QtWidgets.QComboBox()
        self.repo_round.addItems(["1", "2", "3", "4", "5"])
        footer.addWidget(self.repo_round)
        footer.addSpacing(12)
        footer.addWidget(QtWidgets.QLabel("Duration"))
        self.repo_duration = QtWidgets.QDoubleSpinBox()
        self.repo_duration.setRange(5, 120)
        self.repo_duration.setValue(30)
        footer.addWidget(self.repo_duration)
        footer.addStretch(1)
        add_btn = QtWidgets.QPushButton("Add Selected")
        add_btn.clicked.connect(self.add_repo_selected)
        footer.addWidget(add_btn)
        group_layout.addLayout(footer)

        parent_layout.addWidget(group, 2)

    def _build_create_panel(self, parent_layout):
        group = QtWidgets.QGroupBox("KREIRAJ PITANJA")
        layout = QtWidgets.QVBoxLayout(group)

        type_row = QtWidgets.QHBoxLayout()
        type_row.addWidget(QtWidgets.QLabel("Tip pitanja"))
        self.question_type = QtWidgets.QComboBox()
        self.question_type.addItems(["text", "text_multiple", "video", "simultaneous"])
        self.question_type.currentIndexChanged.connect(self.switch_create_panel)
        type_row.addWidget(self.question_type)
        layout.addLayout(type_row)

        self.create_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.create_stack, 1)

        self.panel_text = self._create_text_panel()
        self.panel_multiple = self._create_multiple_panel()
        self.panel_video = self._create_video_panel()
        self.panel_sim = self._create_sim_panel()

        self.create_stack.addWidget(self.panel_text)
        self.create_stack.addWidget(self.panel_multiple)
        self.create_stack.addWidget(self.panel_video)
        self.create_stack.addWidget(self.panel_sim)

        parent_layout.addWidget(group, 3)

    def _create_text_panel(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        self.text_question = QtWidgets.QLineEdit()
        self.text_answer = QtWidgets.QLineEdit()
        self.text_round = QtWidgets.QComboBox()
        self.text_round.addItems(["1", "2", "3", "4", "5"])
        self.text_duration = QtWidgets.QDoubleSpinBox()
        self.text_duration.setRange(5, 120)
        self.text_duration.setValue(30)
        layout.addRow("Pitanje", self.text_question)
        layout.addRow("Tocan odgovor", self.text_answer)
        layout.addRow("Runda", self.text_round)
        layout.addRow("Trajanje", self.text_duration)
        add_btn = QtWidgets.QPushButton("Dodaj")
        add_btn.clicked.connect(self.create_text_question)
        layout.addRow(add_btn)
        return widget

    def _create_multiple_panel(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        self.mult_question = QtWidgets.QLineEdit()
        self.mult_choices = QtWidgets.QPlainTextEdit()
        self.mult_correct = QtWidgets.QSpinBox()
        self.mult_correct.setRange(1, 20)
        self.mult_round = QtWidgets.QComboBox()
        self.mult_round.addItems(["1", "2", "3", "4", "5"])
        self.mult_duration = QtWidgets.QDoubleSpinBox()
        self.mult_duration.setRange(5, 120)
        self.mult_duration.setValue(30)
        layout.addRow("Pitanje", self.mult_question)
        layout.addRow("Mogucnosti", self.mult_choices)
        layout.addRow("Tocan", self.mult_correct)
        layout.addRow("Runda", self.mult_round)
        layout.addRow("Trajanje", self.mult_duration)
        add_btn = QtWidgets.QPushButton("Dodaj")
        add_btn.clicked.connect(self.create_multiple_question)
        layout.addRow(add_btn)
        return widget

    def _create_video_panel(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        self.video_path = QtWidgets.QLineEdit()
        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(lambda: self.browse_file(self.video_path, "video"))
        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.video_path)
        path_row.addWidget(browse)
        layout.addRow("Video", path_row)
        self.video_artist = QtWidgets.QLineEdit()
        self.video_title = QtWidgets.QLineEdit()
        self.video_start = QtWidgets.QDoubleSpinBox()
        self.video_start.setRange(0, 120)
        self.video_duration = QtWidgets.QDoubleSpinBox()
        self.video_duration.setRange(5, 120)
        self.video_duration.setValue(30)
        self.video_round = QtWidgets.QComboBox()
        self.video_round.addItems(["1", "2", "3", "4", "5"])
        layout.addRow("Izvodac", self.video_artist)
        layout.addRow("Naslov", self.video_title)
        layout.addRow("Start", self.video_start)
        layout.addRow("Trajanje", self.video_duration)
        layout.addRow("Runda", self.video_round)
        add_btn = QtWidgets.QPushButton("Dodaj")
        add_btn.clicked.connect(self.create_video_question)
        layout.addRow(add_btn)
        return widget

    def _create_sim_panel(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        self.sim_path = QtWidgets.QLineEdit()
        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(lambda: self.browse_file(self.sim_path, "audio"))
        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.sim_path)
        path_row.addWidget(browse)
        layout.addRow("Audio", path_row)
        self.sim_artist = QtWidgets.QLineEdit()
        self.sim_title = QtWidgets.QLineEdit()
        self.sim_extra_q = QtWidgets.QLineEdit()
        self.sim_extra_a = QtWidgets.QLineEdit()
        self.sim_start = QtWidgets.QDoubleSpinBox()
        self.sim_start.setRange(0, 120)
        self.sim_duration = QtWidgets.QDoubleSpinBox()
        self.sim_duration.setRange(5, 120)
        self.sim_duration.setValue(30)
        self.sim_round = QtWidgets.QComboBox()
        self.sim_round.addItems(["1", "2", "3", "4", "5"])
        layout.addRow("Izvodac", self.sim_artist)
        layout.addRow("Naslov", self.sim_title)
        layout.addRow("Extra pitanje", self.sim_extra_q)
        layout.addRow("Extra odgovor", self.sim_extra_a)
        layout.addRow("Start", self.sim_start)
        layout.addRow("Trajanje", self.sim_duration)
        layout.addRow("Runda", self.sim_round)
        add_btn = QtWidgets.QPushButton("Dodaj")
        add_btn.clicked.connect(self.create_sim_question)
        layout.addRow(add_btn)
        return widget

    def _build_questions_panel(self, parent_layout):
        group = QtWidgets.QGroupBox("PITANJA U KVIZU")
        layout = QtWidgets.QVBoxLayout(group)
        self.questions_list = QtWidgets.QListWidget()
        self.questions_list.setObjectName("QuestionList")
        self.questions_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.questions_list.setSpacing(8)
        self.questions_list.itemDoubleClicked.connect(lambda _item: self.open_editor_dialog())
        layout.addWidget(self.questions_list, 1)

        parent_layout.addWidget(group, 2)

    def _build_live_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_live)
        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        top.addWidget(QtWidgets.QLabel("Status:"))
        self.live_status_label = QtWidgets.QLabel("Disconnected")
        self.live_status_label.setObjectName("StatusLabel")
        top.addWidget(self.live_status_label)

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_live_connection)
        top.addWidget(self.connect_btn)

        top.addSpacing(12)
        top.addWidget(QtWidgets.QLabel("Round:"))
        self.live_round = QtWidgets.QComboBox()
        self.live_round.addItems(["1", "2", "3", "4", "5"])
        self.live_round.currentIndexChanged.connect(self._on_live_round_changed)
        top.addWidget(self.live_round)

        self.autoplay_btn = QtWidgets.QPushButton("Start Autoplay")
        self.autoplay_btn.clicked.connect(self.start_autoplay)
        top.addWidget(self.autoplay_btn)

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        top.addWidget(self.pause_btn)

        self.refresh_live_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_live_btn.clicked.connect(self.refresh_live)
        top.addStretch(1)
        top.addWidget(self.refresh_live_btn)

        grading_group = QtWidgets.QGroupBox("Grading")
        grading_layout = QtWidgets.QVBoxLayout(grading_group)
        self.grading_table = QtWidgets.QTableWidget(0, 7)
        self.grading_table.setHorizontalHeaderLabels(["ID", "Player", "R", "P", "Artist", "Title", "Extra"])
        self.grading_table.horizontalHeader().setStretchLastSection(True)
        self.grading_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.grading_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        grading_layout.addWidget(self.grading_table)

        score_row = QtWidgets.QHBoxLayout()
        score_row.addWidget(QtWidgets.QLabel("Set score:"))
        for label, value, score_type in [
            ("Artist 0", 0.0, "artist"),
            ("Artist 0.5", 0.5, "artist"),
            ("Artist 1", 1.0, "artist"),
            ("Title 0", 0.0, "title"),
            ("Title 0.5", 0.5, "title"),
            ("Title 1", 1.0, "title"),
            ("Extra 0", 0.0, "extra"),
            ("Extra 0.5", 0.5, "extra"),
            ("Extra 1", 1.0, "extra"),
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(lambda _=False, v=value, t=score_type: self.set_score(v, t))
            score_row.addWidget(btn)
        score_row.addStretch(1)
        grading_layout.addLayout(score_row)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.addWidget(QtWidgets.QLabel("Players"))
        self.players_box = QtWidgets.QPlainTextEdit()
        self.players_box.setReadOnly(True)
        right_layout.addWidget(self.players_box)
        right_layout.addWidget(QtWidgets.QLabel("Playlist"))
        self.live_questions_list = QtWidgets.QListWidget()
        self.live_questions_list.setObjectName("LiveQuestionList")
        self.live_questions_list.setSpacing(6)
        right_layout.addWidget(self.live_questions_list, 1)

        split = QtWidgets.QSplitter()
        split.addWidget(grading_group)
        split.addWidget(right)
        split.setSizes([600, 400])
        layout.addWidget(split, 1)

    def _build_server_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_server)
        status_row = QtWidgets.QHBoxLayout()
        layout.addLayout(status_row)

        status_row.addWidget(QtWidgets.QLabel("Status:"))
        self.server_status_label = QtWidgets.QLabel("Stopped")
        self.server_status_label.setObjectName("StatusLabel")
        status_row.addWidget(self.server_status_label)

        status_row.addSpacing(12)
        status_row.addWidget(QtWidgets.QLabel("LAN Address:"))
        self.server_address = QtWidgets.QLabel(self.address_text())
        status_row.addWidget(self.server_address)
        status_row.addStretch(1)

        port_row = QtWidgets.QHBoxLayout()
        layout.addLayout(port_row)
        port_row.addWidget(QtWidgets.QLabel("Port:"))
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(APP_PORT)
        self.port_input.valueChanged.connect(self.update_address)
        port_row.addWidget(self.port_input)
        port_row.addStretch(1)

        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self.start_btn = QtWidgets.QPushButton("Start Game Server")
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn = QtWidgets.QPushButton("Stop Game Server")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)

        tools_row = QtWidgets.QHBoxLayout()
        layout.addLayout(tools_row)
        self.qr_btn = QtWidgets.QPushButton("QR/PIN Generator")
        self.qr_btn.clicked.connect(self.open_qr_modal)
        tools_row.addWidget(self.qr_btn)
        tools_row.addStretch(1)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box, 1)

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
        self.signals.live_status.connect(self.live_status_label.setText)
        self.signals.players.connect(self.update_players)
        self.signals.leaderboard.connect(self.update_leaderboard)
        self.signals.grading.connect(self.update_grading)
        self.signals.pause_state.connect(self.update_pause_button)

    def _bind_socket_events(self):
        @self.sio.event
        def connect():
            self.sio_connected = True
            self.signals.live_status.emit("Connected")
            self.sio.emit("admin_live_arm", {"armed": True})
            self.refresh_live()

        @self.sio.event
        def disconnect():
            self.sio_connected = False
            self.signals.live_status.emit("Disconnected")

        @self.sio.on("admin_player_list_full")
        def on_player_list(players):
            self.signals.players.emit(players)

        @self.sio.on("admin_update_player_list")
        def on_player_list_update(players):
            self.signals.players.emit(players)

        @self.sio.on("update_leaderboard")
        def on_leaderboard(data):
            self.signals.leaderboard.emit(data)

        @self.sio.on("admin_receive_grading_data")
        def on_grading(data):
            self.signals.grading.emit(data)

        @self.sio.on("quiz_pause_state")
        def on_pause(data):
            self.is_paused = bool(data.get("paused"))
            self.signals.pause_state.emit(self.is_paused)

        @self.sio.on("admin_live_guard_blocked")
        def on_guard(data):
            msg = data.get("message", "Live control blocked.")
            QtCore.QTimer.singleShot(0, lambda: QtWidgets.QMessageBox.warning(self, "Live", msg))

    def address_text(self):
        port = getattr(self, "port_input", None)
        if port is None:
            port_value = APP_PORT
        else:
            port_value = port.value()
        return f"http://{get_local_ip()}:{port_value}"

    def update_address(self):
        self.signals.address_text.emit(self.address_text())

    def append_log(self, line):
        self.log_box.appendPlainText(line.rstrip())

    def with_app(self, fn):
        with self.app.app_context():
            return fn()

    def _get_active_quiz_id(self):
        if self.quiz_combo.currentIndex() < 0:
            return None
        data = self.quiz_combo.currentData()
        return data

    def _get_next_position(self, quiz_id, round_number):
        def _next():
            max_pos = db.session.query(db.func.max(Question.position)) \
                .filter(Question.quiz_id == quiz_id) \
                .filter(Question.round_number == round_number) \
                .scalar()
            return (max_pos or 0) + 1

        return self.with_app(_next)

    def _get_round_count(self, quiz_id, round_number):
        def _count():
            return Question.query.filter_by(
                quiz_id=quiz_id,
                round_number=round_number
            ).count()

        return self.with_app(_count)

    def _reposition_question(self, question, new_round, new_position):
        if not question:
            return

        quiz_id = question.quiz_id
        old_round = question.round_number

        def _normalize_positions(questions):
            for idx, q in enumerate(questions, 1):
                q.position = 1000 + idx
            db.session.flush()
            for idx, q in enumerate(questions, 1):
                q.position = idx

        old_list = Question.query.filter_by(
            quiz_id=quiz_id,
            round_number=old_round
        ).order_by(Question.position).all()
        old_list = [q for q in old_list if q.id != question.id]

        if new_round == old_round:
            idx = max(0, min(int(new_position) - 1, len(old_list)))
            old_list.insert(idx, question)
            _normalize_positions(old_list)
            return

        new_list = Question.query.filter_by(
            quiz_id=quiz_id,
            round_number=new_round
        ).order_by(Question.position).all()
        idx = max(0, min(int(new_position) - 1, len(new_list)))
        question.round_number = new_round
        new_list.insert(idx, question)

        _normalize_positions(old_list)
        _normalize_positions(new_list)

    def _load_quizzes(self):
        def _load():
            quizzes = Quiz.query.order_by(Quiz.id.desc()).all()
            active = Quiz.query.filter_by(is_active=True).first()
            return quizzes, active

        quizzes, active = self.with_app(_load)
        self.quiz_combo.blockSignals(True)
        self.quiz_combo.clear()
        for quiz in quizzes:
            date_text = ""
            if getattr(quiz, "event_date", None):
                date_text = f" ({quiz.event_date.strftime('%d.%m.%Y')})"
            self.quiz_combo.addItem(f"{quiz.id}: {quiz.title}{date_text}", quiz.id)
        self.quiz_combo.blockSignals(False)

        if active:
            idx = self.quiz_combo.findData(active.id)
            if idx >= 0:
                self.quiz_combo.setCurrentIndex(idx)

    def refresh_questions(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        round_num = int(self.round_combo.currentText())

        def _fetch():
            questions = Question.query.filter_by(quiz_id=quiz_id, round_number=round_num) \
                .order_by(Question.position).all()
            return [get_question_display(q) for q in questions]

        questions = self.with_app(_fetch)
        self.questions_list.clear()
        for q in questions:
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, q.get("id"))
            widget = self._build_question_item(q)
            item.setSizeHint(widget.sizeHint())
            self.questions_list.addItem(item)
            self.questions_list.setItemWidget(item, widget)

    def set_active_quiz(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return

        def _set():
            Quiz.query.update({Quiz.is_active: False})
            quiz = db.session.get(Quiz, quiz_id)
            if quiz:
                quiz.is_active = True
            db.session.commit()

        self.with_app(_set)

    def create_quiz_modal(self):
        dialog = CreateQuizDialog(
            self,
            with_app=self.with_app,
            on_created=self._on_questions_changed,
            prepare_animation=self._prepare_dialog_animation,
        )
        dialog.exec()

    def switch_create_panel(self, index):
        self.create_stack.setCurrentIndex(index)

    def browse_repo_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            self.repo_path.setText(path)

    def scan_repo_folder(self):
        base = self.repo_path.text().strip()
        if not base or not os.path.isdir(base):
            return
        self.repo_base = base
        self.repo_files = scan_mp3_folder(base)
        self.filter_repo_list()

    def filter_repo_list(self):
        query = self.repo_search.text().strip().lower()
        files = getattr(self, "repo_files", [])
        if query:
            self.repo_filtered = [f for f in files if query in f.lower()]
        else:
            self.repo_filtered = list(files)
        self.repo_list.clear()
        for rel in self.repo_filtered:
            self.repo_list.addItem(rel)

    def clear_repo_search(self):
        self.repo_search.clear()

    def add_repo_selected(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        base = getattr(self, "repo_base", None)
        if not base:
            return
        round_num = int(self.repo_round.currentText())
        duration = float(self.repo_duration.value())
        items = self.repo_list.selectedItems()
        if not items:
            return
        files = [item.text() for item in items]

        def _import():
            position = self._get_next_position(quiz_id, round_num)
            for rel in files:
                full_path = os.path.join(base, rel)
                filename = import_song_file(full_path, os.path.basename(rel))
                artist, title = guess_artist_title(rel)
                question = Question(
                    quiz_id=quiz_id,
                    round_number=round_num,
                    position=position,
                    type="audio",
                    duration=duration,
                )
                db.session.add(question)
                db.session.flush()
                db.session.add(Song(
                    question_id=question.id,
                    filename=filename,
                    artist=artist,
                    title=title,
                    start_time=0.0,
                ))
                position += 1
            db.session.commit()

        self.with_app(_import)
        self.refresh_questions()

    def browse_file(self, target, qtype):
        if qtype == "video":
            filetypes = "Video Files (*.mp4 *.webm *.mkv)"
        else:
            filetypes = "Audio Files (*.mp3)"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select file", "", filetypes)
        if path:
            target.setText(path)

    def create_text_question(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        question_text = self.text_question.text().strip()
        answer_text = self.text_answer.text().strip()
        if not question_text or not answer_text:
            return
        round_num = int(self.text_round.currentText())
        duration = float(self.text_duration.value())

        def _create():
            position = self._get_next_position(quiz_id, round_num)
            question = Question(
                quiz_id=quiz_id,
                round_number=round_num,
                position=position,
                type="text",
                duration=duration,
            )
            db.session.add(question)
            db.session.flush()
            db.session.add(TextQuestion(
                question_id=question.id,
                question_text=question_text,
                answer_text=answer_text,
            ))
            db.session.commit()

        self.with_app(_create)
        self.refresh_questions()

    def create_multiple_question(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        question_text = self.mult_question.text().strip()
        if not question_text:
            return
        choices = self.mult_choices.toPlainText().strip().splitlines()
        choices = [c.strip() for c in choices if c.strip()]
        if len(choices) < 2:
            return
        round_num = int(self.mult_round.currentText())
        duration = float(self.mult_duration.value())
        correct_idx = max(0, int(self.mult_correct.value()) - 1)

        def _create():
            position = self._get_next_position(quiz_id, round_num)
            question = Question(
                quiz_id=quiz_id,
                round_number=round_num,
                position=position,
                type="text_multiple",
                duration=duration,
            )
            db.session.add(question)
            db.session.flush()
            tm = TextMultiple(
                question_id=question.id,
                question_text=question_text,
                correct_index=correct_idx,
            )
            tm.set_choices(choices)
            db.session.add(tm)
            db.session.commit()

        self.with_app(_create)
        self.refresh_questions()

    def create_video_question(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        path = self.video_path.text().strip()
        if not path:
            return
        round_num = int(self.video_round.currentText())
        start_time = float(self.video_start.value())
        duration = float(self.video_duration.value())

        def _create():
            position = self._get_next_position(quiz_id, round_num)
            question = Question(
                quiz_id=quiz_id,
                round_number=round_num,
                position=position,
                type="video",
                duration=duration,
            )
            db.session.add(question)
            db.session.flush()
            filename = import_video_file(path, os.path.basename(path))
            db.session.add(Video(
                question_id=question.id,
                filename=filename,
                artist=self.video_artist.text().strip() or "?",
                title=self.video_title.text().strip() or "?",
                start_time=start_time,
            ))
            db.session.commit()

        self.with_app(_create)
        self.refresh_questions()

    def create_sim_question(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        path = self.sim_path.text().strip()
        if not path:
            return
        round_num = int(self.sim_round.currentText())
        start_time = float(self.sim_start.value())
        duration = float(self.sim_duration.value())

        def _create():
            position = self._get_next_position(quiz_id, round_num)
            question = Question(
                quiz_id=quiz_id,
                round_number=round_num,
                position=position,
                type="simultaneous",
                duration=duration,
            )
            db.session.add(question)
            db.session.flush()
            filename = import_song_file(path, os.path.basename(path))
            db.session.add(SimultaneousQuestion(
                question_id=question.id,
                filename=filename,
                artist=self.sim_artist.text().strip() or "?",
                title=self.sim_title.text().strip() or "?",
                start_time=start_time,
                extra_question=self.sim_extra_q.text().strip(),
                extra_answer=self.sim_extra_a.text().strip(),
            ))
            db.session.commit()

        self.with_app(_create)
        self.refresh_questions()

    def selected_question_id(self):
        item = self.questions_list.currentItem()
        if not item:
            return None
        qid = item.data(QtCore.Qt.UserRole)
        return int(qid) if qid is not None else None

    def _find_question_item(self, qid):
        for index in range(self.questions_list.count()):
            item = self.questions_list.item(index)
            if item.data(QtCore.Qt.UserRole) == qid:
                return item
        return None

    def _select_question_by_id(self, qid):
        item = self._find_question_item(qid)
        if item:
            self.questions_list.setCurrentItem(item)

    def edit_question_by_id(self, qid):
        if not qid:
            return
        self._select_question_by_id(qid)
        self.open_editor_dialog(qid)

    def move_question_by_id(self, qid, direction):
        if not qid:
            return

        def _move():
            q = db.session.get(Question, qid)
            if not q:
                return
            target_pos = q.position + direction
            neighbor = Question.query.filter_by(
                quiz_id=q.quiz_id,
                round_number=q.round_number,
                position=target_pos
            ).first()
            if not neighbor:
                return
            orig_pos = q.position
            neighbor_pos = neighbor.position
            temp_pos = db.session.query(db.func.max(Question.position)) \
                .filter(Question.quiz_id == q.quiz_id) \
                .filter(Question.round_number == q.round_number) \
                .scalar()
            temp_pos = (temp_pos or 0) + 1

            q.position = temp_pos
            db.session.flush()
            neighbor.position = orig_pos
            db.session.flush()
            q.position = neighbor_pos
            db.session.commit()

        self.with_app(_move)
        self.refresh_questions()
        self._select_question_by_id(qid)

    def delete_question_by_id(self, qid):
        if not qid:
            return

        def _delete():
            question = db.session.get(Question, qid)
            if question:
                db.session.delete(question)
                db.session.commit()

        self.with_app(_delete)
        self.refresh_questions()

    def _build_question_item(self, data):
        card = QtWidgets.QFrame()
        card.setObjectName("QuestionCard")
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(12)

        badge = QtWidgets.QLabel(f"R{data.get('round')}  P{data.get('order')}")
        badge.setObjectName("QuestionBadge")
        badge.setAlignment(QtCore.Qt.AlignCenter)
        badge.setFixedWidth(64)
        card_layout.addWidget(badge)

        text_layout = QtWidgets.QVBoxLayout()
        title = data.get("artist") or "?"
        subtitle = data.get("title") or data.get("type", "").upper()
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("QuestionTitle")
        meta_label = QtWidgets.QLabel(subtitle)
        meta_label.setObjectName("QuestionMeta")
        text_layout.addWidget(title_label)
        text_layout.addWidget(meta_label)
        card_layout.addLayout(text_layout, 1)

        type_badge = QtWidgets.QLabel(str(data.get("type", "")).upper())
        type_badge.setObjectName("QuestionType")
        type_badge.setAlignment(QtCore.Qt.AlignCenter)
        type_badge.setFixedWidth(80)
        card_layout.addWidget(type_badge)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(6)

        style = self.style()

        edit_btn = QtWidgets.QToolButton()
        edit_btn.setObjectName("QuestionAction")
        edit_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_FileDialogContentsView))
        edit_btn.setIconSize(QtCore.QSize(16, 16))
        edit_btn.setFixedSize(28, 28)
        edit_btn.setToolTip("Edit")
        edit_btn.setAutoRaise(True)
        edit_btn.clicked.connect(lambda: self.edit_question_by_id(data.get("id")))
        actions_layout.addWidget(edit_btn)

        up_btn = QtWidgets.QToolButton()
        up_btn.setObjectName("QuestionAction")
        up_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowUp))
        up_btn.setIconSize(QtCore.QSize(16, 16))
        up_btn.setFixedSize(28, 28)
        up_btn.setToolTip("Move up")
        up_btn.setAutoRaise(True)
        up_btn.clicked.connect(lambda: self.move_question_by_id(data.get("id"), -1))
        actions_layout.addWidget(up_btn)

        down_btn = QtWidgets.QToolButton()
        down_btn.setObjectName("QuestionAction")
        down_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        down_btn.setIconSize(QtCore.QSize(16, 16))
        down_btn.setFixedSize(28, 28)
        down_btn.setToolTip("Move down")
        down_btn.setAutoRaise(True)
        down_btn.clicked.connect(lambda: self.move_question_by_id(data.get("id"), 1))
        actions_layout.addWidget(down_btn)

        delete_btn = QtWidgets.QToolButton()
        delete_btn.setObjectName("QuestionAction")
        delete_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        delete_btn.setIconSize(QtCore.QSize(16, 16))
        delete_btn.setFixedSize(28, 28)
        delete_btn.setToolTip("Delete")
        delete_btn.setAutoRaise(True)
        delete_btn.clicked.connect(lambda: self.delete_question_by_id(data.get("id")))
        actions_layout.addWidget(delete_btn)

        card_layout.addLayout(actions_layout)

        return card

    def open_editor_dialog(self, qid=None):
        qid = qid or self.selected_question_id()
        if not qid:
            return

        def _fetch():
            q = db.session.get(Question, qid)
            if not q:
                return None

            data = {
                "id": q.id,
                "quiz_id": q.quiz_id,
                "round": q.round_number,
                "position": q.position,
                "type": q.type,
                "duration": float(q.duration or 30),
            }

            if q.type == "audio" and q.song:
                data["media_path"] = os.path.join(Config.SONGS_DIR, q.song.filename)
                data.update({
                    "artist": q.song.artist or "",
                    "title": q.song.title or "",
                    "start": float(q.song.start_time or 0),
                })
            elif q.type == "video" and q.video:
                data["media_path"] = os.path.join(ensure_videos_dir(), q.video.filename)
                data.update({
                    "artist": q.video.artist or "",
                    "title": q.video.title or "",
                    "start": float(q.video.start_time or 0),
                })
            elif q.type == "simultaneous" and q.simultaneous:
                data["media_path"] = os.path.join(Config.SONGS_DIR, q.simultaneous.filename)
                data.update({
                    "artist": q.simultaneous.artist or "",
                    "title": q.simultaneous.title or "",
                    "start": float(q.simultaneous.start_time or 0),
                    "extra_q": q.simultaneous.extra_question or "",
                    "extra_a": q.simultaneous.extra_answer or "",
                })
            elif q.type == "text" and q.text:
                data.update({
                    "question_text": q.text.question_text or "",
                    "answer_text": q.text.answer_text or "",
                })
            elif q.type == "text_multiple" and q.text_multiple:
                data.update({
                    "question_text": q.text_multiple.question_text or "",
                    "choices": q.text_multiple.get_choices(),
                    "correct_index": int((q.text_multiple.correct_index or 0) + 1),
                })

            return data

        data = self.with_app(_fetch)
        if not data:
            return

        if data["type"] in ["audio", "video", "simultaneous"]:
            dialog = AudioQuestionEditorDialog(
                self,
                data,
                with_app=self.with_app,
                get_round_count=self._get_round_count,
                reposition_question=self._reposition_question,
                on_saved=self._on_questions_changed,
                prepare_animation=self._prepare_dialog_animation,
            )
        else:
            dialog = TextQuestionEditorDialog(
                self,
                data,
                with_app=self.with_app,
                get_round_count=self._get_round_count,
                reposition_question=self._reposition_question,
                on_saved=self._on_questions_changed,
                prepare_animation=self._prepare_dialog_animation,
            )
        dialog.exec()

    def open_import_folder_modal(self):
        quiz_id = self._get_active_quiz_id()
        if not quiz_id:
            return
        dialog = ImportFolderDialog(
            self,
            quiz_id=quiz_id,
            with_app=self.with_app,
            get_next_position=self._get_next_position,
            on_imported=self._on_questions_changed,
            prepare_animation=self._prepare_dialog_animation,
        )
        dialog.exec()

    def delete_selected_question(self):
        qid = self.selected_question_id()
        self.delete_question_by_id(qid)

    def move_question(self, direction):
        qid = self.selected_question_id()
        self.move_question_by_id(qid, direction)

    def toggle_live_connection(self):
        if self.sio_connected:
            self.sio.disconnect()
            return
        url = f"http://localhost:{self.port_input.value()}"
        try:
            self.sio.connect(url, wait_timeout=5)
        except Exception:
            self.signals.live_status.emit("Disconnected")

    def refresh_live(self):
        if not self.sio_connected:
            return
        self.sio.emit("admin_get_players")
        self.sio.emit("admin_request_grading", {"round": int(self.live_round.currentText())})
        self.update_pause_button(self.is_paused)
        self.refresh_live_questions()

    def _on_live_round_changed(self):
        self.refresh_live_questions()
        if self.sio_connected:
            self.refresh_live()

    def refresh_live_questions(self):
        round_num = int(self.live_round.currentText())

        def _fetch():
            quiz = Quiz.query.filter_by(is_active=True).first()
            if not quiz:
                return []
            questions = Question.query.filter_by(
                quiz_id=quiz.id,
                round_number=round_num
            ).order_by(Question.position).all()
            return [get_question_display(q) for q in questions]

        questions = self.with_app(_fetch)
        self.live_questions_list.clear()
        for q in questions:
            order = q.get("order")
            artist = q.get("artist") or "?"
            title = q.get("title") or q.get("type", "").upper()
            text = f"P{order} - {artist} / {title}"
            self.live_questions_list.addItem(text)

    def start_autoplay(self):
        if not self.sio_connected:
            return
        round_num = int(self.live_round.currentText())

        def _get_first():
            quiz = Quiz.query.filter_by(is_active=True).first()
            if not quiz:
                return None
            question = Question.query.filter_by(quiz_id=quiz.id, round_number=round_num) \
                .order_by(Question.position).first()
            return question.id if question else None

        qid = self.with_app(_get_first)
        if not qid:
            return
        self.sio.emit("admin_start_auto_run", {"id": qid, "round": round_num})

    def toggle_pause(self):
        if not self.sio_connected:
            return
        self.sio.emit("admin_toggle_pause", {"paused": not self.is_paused})

    def update_pause_button(self, paused):
        self.is_paused = paused
        self.pause_btn.setEnabled(self.sio_connected)
        self.pause_btn.setText("Resume" if paused else "Pause")

    def update_players(self, players):
        self.players_box.clear()
        sorted_players = sorted(players, key=lambda p: p.get("score", 0), reverse=True)
        for idx, p in enumerate(sorted_players, 1):
            name = p.get("name")
            score = p.get("score", 0)
            self.players_box.appendPlainText(f"{idx}. {name}  {score}")

    def update_leaderboard(self, data):
        players = [{"name": name, "score": score} for name, score in data.items()]
        self.update_players(players)

    def update_grading(self, rows):
        self.grading_table.setRowCount(0)
        for row in rows:
            values = [
                row.get("id"),
                row.get("player_name"),
                row.get("round_number"),
                row.get("position"),
                row.get("artist_guess"),
                row.get("title_guess"),
                row.get("extra_guess"),
            ]
            table_row = self.grading_table.rowCount()
            self.grading_table.insertRow(table_row)
            for col, value in enumerate(values):
                self.grading_table.setItem(table_row, col, QtWidgets.QTableWidgetItem(str(value)))

    def set_score(self, value, score_type):
        row = self.grading_table.currentRow()
        if row < 0:
            return
        item = self.grading_table.item(row, 0)
        if not item:
            return
        answer_id = int(item.text())
        if self.sio_connected:
            self.sio.emit("admin_update_score", {
                "answer_id": answer_id,
                "type": score_type,
                "value": value
            })
        else:
            def _update():
                ans = db.session.get(Answer, answer_id)
                if not ans:
                    return
                if score_type == "artist":
                    ans.artist_points = value
                elif score_type == "title":
                    ans.title_points = value
                else:
                    ans.extra_points = value
                db.session.commit()

            self.with_app(_update)

    def open_qr_modal(self):
        dialog = QrPinDialog(
            self,
            port_getter=lambda: self.port_input.value(),
            prepare_animation=self._prepare_dialog_animation,
        )
        dialog.exec()

    def _on_questions_changed(self):
        self._load_quizzes()
        self.refresh_questions()

    def start_server(self):
        if self.process and self.process.poll() is None:
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

        self.signals.status_text.emit("Running")
        self.signals.address_text.emit(self.address_text())
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.signals.log_line.emit("Server starting...")

        self.stop_monitor = False
        self.monitor_thread = threading.Thread(target=self.monitor_output, daemon=True)
        self.monitor_thread.start()

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
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def stop_server(self):
        if not self.process or self.process.poll() is not None:
            return
        self.signals.log_line.emit("Stopping server...")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.stop_monitor = True
        self.signals.status_text.emit("Stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        if self.sio_connected:
            self.sio.disconnect()
        if self.process and self.process.poll() is None:
            self.stop_server()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
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
