import os

from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

from admin_ui.constants import THEME
from admin_ui.utils import ensure_videos_dir
from config import Config
from extensions import db
from musicquiz.models import Answer, Question, Quiz
from musicquiz.services.question_service import get_question_display


class _TimerRingWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._remaining = None
        self._total = None
        self._label = ""
        self._drain = False
        self.setFixedSize(60, 60)

    def set_time(self, remaining, total, label=None, drain=None):
        self._remaining = remaining
        self._total = total
        if label is not None:
            self._label = label
        if drain is not None:
            self._drain = bool(drain)
        self.update()

    def set_idle(self):
        self._remaining = None
        self._total = None
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        size = min(self.width(), self.height())
        margin = 8
        rect = QtCore.QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        base_pen = QtGui.QPen(QtGui.QColor(THEME["border"]))
        base_pen.setWidth(6)
        painter.setPen(base_pen)
        painter.drawEllipse(rect)

        if self._remaining is not None and self._total:
            ratio = float(self._remaining) / float(self._total)
            progress = max(0.0, min(1.0, ratio if self._drain else (1.0 - ratio)))
            arc_pen = QtGui.QPen(QtGui.QColor(THEME["primary"]))
            arc_pen.setWidth(6)
            arc_pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(arc_pen)
            painter.drawArc(rect, 90 * 16, int(-progress * 360 * 16))

        painter.setPen(QtGui.QColor(THEME["text"]))
        value_text = "--" if self._remaining is None else str(int(self._remaining))
        value_font = QtGui.QFont("Oswald", 12)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(rect, QtCore.Qt.AlignCenter, value_text)

        # No label under the timer ring.


class LiveTabMixin:
    def _graphics_path(self, name):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, "assets", "graphics", name)

    def _add_panel_header(self, layout, title, icon_name):
        row = QtWidgets.QHBoxLayout()
        icon = QtWidgets.QLabel()
        icon.setObjectName("PanelIcon")
        icon_path = self._graphics_path(icon_name)
        if os.path.exists(icon_path):
            pixmap = QtGui.QPixmap(icon_path)
            icon.setPixmap(pixmap.scaledToHeight(18, QtCore.Qt.SmoothTransformation))
        label = QtWidgets.QLabel(title)
        label.setObjectName("PanelTitle")
        row.addWidget(icon)
        row.addSpacing(6)
        row.addWidget(label)
        row.addStretch(1)
        layout.addLayout(row)

    def _build_live_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_live)
        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        top_icon = QtWidgets.QLabel()
        top_icon.setObjectName("PanelIcon")
        top_icon_path = self._graphics_path("rock_live.svg")
        if os.path.exists(top_icon_path):
            pixmap = QtGui.QPixmap(top_icon_path)
            top_icon.setPixmap(pixmap.scaledToHeight(18, QtCore.Qt.SmoothTransformation))
        top_title = QtWidgets.QLabel("LIVE")
        top_title.setObjectName("PanelTitle")
        top.addWidget(top_icon)
        top.addWidget(top_title)
        top.addSpacing(8)

        top.addWidget(QtWidgets.QLabel("Status:"))
        self.live_status_label = QtWidgets.QLabel("Disconnected")
        self.live_status_label.setObjectName("StatusLabel")
        self.live_status_label.setProperty("badge", "cyan")
        top.addWidget(self.live_status_label)

        top.addSpacing(12)
        top.addWidget(QtWidgets.QLabel("Round:"))
        self.live_round = QtWidgets.QComboBox()
        self.live_round.addItems(["1", "2", "3", "4", "5"])
        self.live_round.currentIndexChanged.connect(self._on_live_round_changed)
        top.addWidget(self.live_round)

        top.addSpacing(12)
        top.addWidget(QtWidgets.QLabel("Quiz:"))
        self.live_quiz_combo = QtWidgets.QComboBox()
        self.live_quiz_combo.currentIndexChanged.connect(self._on_live_quiz_changed)
        top.addWidget(self.live_quiz_combo)

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

        now_group = QtWidgets.QGroupBox()
        now_group.setProperty("panel", True)
        now_group.setProperty("watermark", "live")
        now_layout = QtWidgets.QHBoxLayout(now_group)
        left_col = QtWidgets.QVBoxLayout()
        self._add_panel_header(left_col, "NOW PLAYING", "rock_live.svg")
        self.now_question_label = QtWidgets.QLabel("Playing: --")
        self.now_question_label.setObjectName("SectionTitle")
        self.now_question_label.setWordWrap(True)
        left_col.addWidget(self.now_question_label)
        self.now_meta_label = QtWidgets.QLabel("Round: -- | Type: --")
        self.now_meta_label.setVisible(False)
        self.live_event_label = QtWidgets.QLabel("Last event: --")
        self.live_event_label.setVisible(False)
        now_layout.addLayout(left_col, 1)
        now_layout.addStretch(1)
        self.timer_ring = _TimerRingWidget()
        now_layout.addWidget(self.timer_ring)
        layout.addWidget(now_group)

        self.live_display_timer = QtCore.QTimer(self)
        self.live_display_timer.setInterval(1000)
        self.live_display_timer.timeout.connect(self._tick_live_display_timer)
        self.is_round_countdown = False
        self.countdown_total = None

        self.server_status_label = QtWidgets.QLabel("Stopped")
        self.server_status_label.setObjectName("StatusLabel")
        self.server_status_label.setProperty("badge", "red")
        self.server_status_label.setVisible(False)
        self.port_input.valueChanged.connect(self.update_address)
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setVisible(False)

        grading_group = QtWidgets.QGroupBox()
        grading_group.setProperty("panel", True)
        grading_group.setProperty("watermark", "list")
        grading_layout = QtWidgets.QVBoxLayout(grading_group)
        self._add_panel_header(grading_layout, "ODGOVORI UZIVO", "rock_list.svg")

        filter_row = QtWidgets.QHBoxLayout()
        self.filter_player = QtWidgets.QLineEdit()
        self.filter_player.setPlaceholderText("Player")
        self.filter_player.textChanged.connect(self.apply_grading_filter)
        self.filter_round = QtWidgets.QLineEdit()
        self.filter_round.setPlaceholderText("Round")
        self.filter_round.setFixedWidth(35)
        self.filter_round.textChanged.connect(self.apply_grading_filter)
        self.filter_position = QtWidgets.QLineEdit()
        self.filter_position.setPlaceholderText("Pos")
        self.filter_position.setFixedWidth(35)
        self.filter_position.textChanged.connect(self.apply_grading_filter)
        self.filter_artist = QtWidgets.QLineEdit()
        self.filter_artist.setPlaceholderText("Artist")
        self.filter_artist.textChanged.connect(self.apply_grading_filter)
        self.filter_title = QtWidgets.QLineEdit()
        self.filter_title.setPlaceholderText("Title")
        self.filter_title.textChanged.connect(self.apply_grading_filter)

        filter_row.addWidget(QtWidgets.QLabel("Filter:"))
        filter_row.addWidget(self.filter_player)
        filter_row.addWidget(self.filter_round)
        filter_row.addWidget(self.filter_position)
        filter_row.addWidget(self.filter_artist)
        filter_row.addWidget(self.filter_title)
        grading_layout.addLayout(filter_row)

        finalize_row = QtWidgets.QHBoxLayout()
        finalize_row.addStretch(1)
        self.finalize_round_btn = QtWidgets.QPushButton("Finalize Round")
        self.finalize_round_btn.clicked.connect(self.finalize_round)
        finalize_row.addWidget(self.finalize_round_btn)
        grading_layout.addLayout(finalize_row)

        self.grading_table = QtWidgets.QTableWidget(0, 6)
        self.grading_table.setHorizontalHeaderLabels(["ID", "R", "P", "Player", "Artist", "Title"])
        self.grading_table.setColumnWidth(1, 35)
        self.grading_table.setColumnWidth(2, 35)
        self.grading_table.horizontalHeader().setStretchLastSection(True)
        self.grading_table.verticalHeader().setVisible(False)
        self.grading_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.grading_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.grading_table.setShowGrid(False)
        self.grading_table.setAlternatingRowColors(True)
        self.grading_table.setColumnHidden(0, True)
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
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(lambda _=False, v=value, t=score_type: self.set_score(v, t))
            score_row.addWidget(btn)
        score_row.addStretch(1)
        grading_layout.addLayout(score_row)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QHBoxLayout(right)

        players_group = QtWidgets.QGroupBox()
        players_group.setProperty("panel", True)
        players_group.setProperty("watermark", "users")
        players_layout = QtWidgets.QVBoxLayout(players_group)
        self._add_panel_header(players_layout, "TIMOVI", "rock_users.svg")
        self.players_table = QtWidgets.QTableWidget(0, 4)
        self.players_table.setHorizontalHeaderLabels(["Status", "Player", "Score", "Lock"])
        self.players_table.setColumnWidth(0, 70)
        self.players_table.setColumnWidth(2, 70)
        self.players_table.horizontalHeader().setStretchLastSection(True)
        self.players_table.verticalHeader().setVisible(False)
        self.players_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.players_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.players_table.setAlternatingRowColors(True)
        players_layout.addWidget(self.players_table, 1)

        playlist_group = QtWidgets.QGroupBox()
        playlist_group.setProperty("panel", True)
        playlist_group.setProperty("watermark", "list")
        playlist_layout = QtWidgets.QVBoxLayout(playlist_group)
        self._add_panel_header(playlist_layout, "PITANJA U RUNDI", "rock_list.svg")
        self.live_questions_list = QtWidgets.QListWidget()
        self.live_questions_list.setObjectName("LiveQuestionList")
        self.live_questions_list.setSpacing(6)
        playlist_layout.addWidget(self.live_questions_list, 1)

        right_layout.addWidget(players_group, 1)
        right_layout.addWidget(playlist_group, 1)

        split = QtWidgets.QSplitter()
        split.addWidget(grading_group)
        split.addWidget(right)
        split.setSizes([520, 480])
        layout.addWidget(split, 1)

    def toggle_live_connection(self):
        if self.sio_connected:
            self.sio.disconnect()
            self.next_round_ready = False
            self.update_autoplay_buttons()
            self.stop_live_media()
            self.now_question_label.setText("Now: --")
            self.now_meta_label.setText("Round: -- | Type: --")
            self._clear_timer_display()
            return
        url = f"http://localhost:{self.port_input.value()}"
        self.last_connect_url = url
        try:
            self.sio.connect(url, wait_timeout=5)
        except Exception as exc:
            self.signals.live_status.emit("Disconnected")
            self._store_log("socket", f"connect_failed:{url}:{exc}")

    def ensure_live_connection(self):
        if self.sio_connected:
            return
        self.toggle_live_connection()

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

    def _on_live_quiz_changed(self):
        quiz_id = self.live_quiz_combo.currentData()
        if quiz_id:
            self.set_active_quiz_by_id(quiz_id)

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
            QtWidgets.QMessageBox.warning(self, "Live", "Niste spojeni na server.")
            self.start_connect_retry()
            return
        round_num = int(self.live_round.currentText())

        self.now_question_label.setText("Now: Autoplay requested...")
        self.now_meta_label.setText(f"Round: {round_num} | Type: autoplay")
        self._set_last_event("autoplay requested")
        self._store_log("ui", f"autoplay_request:round={round_num}")
        self._start_autoplay_wait()

        def _get_first():
            quiz = Quiz.query.filter_by(is_active=True).first()
            if not quiz:
                return None, "Nema aktivnog kviza."
            question = Question.query.filter_by(quiz_id=quiz.id, round_number=round_num) \
                .order_by(Question.position).first()
            if not question:
                return None, "Nema pitanja u odabranoj rundi."
            return question.id, None

        qid, error_msg = self.with_app(_get_first)
        if not qid:
            if error_msg:
                self.now_question_label.setText(f"Now: {error_msg}")
                self.now_meta_label.setText(f"Round: {round_num} | Type: idle")
                QtWidgets.QMessageBox.warning(self, "Live", error_msg)
            return
        self.pending_autoplay = None
        if not self.safe_emit("admin_start_auto_run", {"id": qid, "round": round_num}):
            self._set_now_status("Nije moguce poslati start. Provjeri vezu.")
            return
        self.next_round_ready = False
        self.update_autoplay_buttons()

    def toggle_pause(self):
        if not self.sio_connected:
            return
        self.sio.emit("admin_toggle_pause", {"paused": not self.is_paused})
        self._store_log("ui", f"toggle_pause:{not self.is_paused}")

    def unlock_registrations(self):
        if not self.sio_connected:
            QtWidgets.QMessageBox.warning(self, "Live", "Niste spojeni na server.")
            return
        if self.registrations_open:
            return
        self.sio.emit("admin_toggle_registrations", {"open": True})
        self.registrations_open = True

    def update_pause_button(self, paused):
        self.is_paused = paused
        self.pause_btn.setEnabled(self.sio_connected)
        self.pause_btn.setText("Resume" if paused else "Pause")

    def update_live_status(self, text):
        self.live_status_label.setText(text)
        self._set_last_event(f"status: {text}")

    def start_countdown(self, seconds, round_num):
        self.countdown_total = max(1, int(seconds))
        self.countdown_remaining = self.countdown_total
        self.is_round_countdown = True
        self.now_question_label.setText(f"Runda {round_num} počinje")
        self.update_live_timer(self.countdown_remaining, self.countdown_total, source="server", label="COUNTDOWN")
        if self.countdown_remaining > 0:
            if not self.countdown_timer.isActive():
                self.countdown_timer.start()

    def _tick_countdown(self):
        if self.countdown_remaining <= 0:
            self.countdown_timer.stop()
            self.is_round_countdown = False
            self._clear_timer_display()
            return
        self.countdown_remaining -= 1
        if self.countdown_remaining <= 0:
            self.countdown_timer.stop()
            self.is_round_countdown = False
            self._clear_timer_display()
        else:
            self.update_live_timer(self.countdown_remaining, self.countdown_total, source="server", label="COUNTDOWN")

    def mark_round_finished(self, round_num):
        current_round = int(self.live_round.currentText())
        if round_num == current_round:
            self.next_round_ready = True
            self.update_autoplay_buttons()
            self.now_question_label.setText(f"Runda {round_num} završila")
            self._clear_timer_display()

    def update_autoplay_buttons(self):
        self.autoplay_btn.setEnabled(self.sio_connected)
        self.autoplay_btn.setText("Start Autoplay")

    def _start_autoplay_wait(self):
        self.awaiting_autoplay = True
        self.autoplay_wait_timer.start(5000)

    def _clear_autoplay_wait(self):
        self.awaiting_autoplay = False
        if self.autoplay_wait_timer.isActive():
            self.autoplay_wait_timer.stop()

    def _on_autoplay_timeout(self):
        if not self.awaiting_autoplay:
            return
        self.awaiting_autoplay = False
        self._set_now_status("Nema odgovora s servera. Provjeri live arm i rundu.")

    def _on_live_arm_ack(self, data):
        if not data or not data.get("armed"):
            return
        if not self.pending_autoplay:
            return
        payload = self.pending_autoplay
        self.pending_autoplay = None
        self.safe_emit("admin_start_auto_run", payload)

    def _set_now_status(self, message):
        self.now_question_label.setText(f"Now:\n{message}")

    def _set_last_event(self, name):
        if hasattr(self, "live_event_label"):
            self.live_event_label.setText(f"Last event: {name}")

    def _on_round_countdown_signal(self, data):
        round_num = data.get("round", 1)
        seconds = int(data.get("seconds", 30))
        self._clear_autoplay_wait()
        self._set_last_event("round_countdown_start")
        self.start_countdown(seconds, round_num)
        self._store_log("socket", f"round_countdown_start:r{round_num}")

    def _on_play_audio_signal(self, data):
        self._clear_autoplay_wait()
        self._set_last_event("play_audio")
        self.handle_live_media(data)
        self._store_log("socket", f"play_audio:{data.get('id')}")

    def _on_timer_update_signal(self, data):
        remaining = data.get("remaining")
        total = data.get("total")
        self._log_timer_update(remaining, total, data)
        self._set_last_event("timer_update")
        if getattr(self, "is_round_countdown", False):
            return
        self.update_live_timer(remaining, total, source="server", label="TIME")

    def _on_tv_start_timer_signal(self, data):
        self._log_socket_event("tv_start_timer", data)
        seconds = data.get("seconds")
        self._set_last_event("tv_start_timer")
        self.update_live_timer(seconds, seconds)

    def _on_show_correct_signal(self, data):
        self._log_socket_event("screen_show_correct", data)
        self._set_last_event("screen_show_correct")
        self.handle_show_correct(data)
        self._store_log("socket", f"screen_show_correct:{data.get('id')}")

    def _on_round_finished_signal(self, data):
        self._log_socket_event("admin_round_finished", data)
        round_num = int(data.get("round", self.live_round.currentText()))
        self.mark_round_finished(round_num)
        self._store_log("socket", f"round_finished:r{round_num}")

    def _on_single_player_update_signal(self, data):
        self._log_socket_event("admin_single_player_update", data)
        name = data.get("name")
        status = data.get("status")
        self.update_single_player_status(name, status)
        if name and status:
            prev_status = self.player_status_cache.get(name)
            if prev_status != status:
                self.player_status_cache[name] = status
                self._store_log("socket", f"player_status:{name}:{status}")

    def _on_live_guard_blocked_signal(self, data):
        msg = data.get("message", "Live control blocked.")
        QtWidgets.QMessageBox.warning(self, "Live", msg)
        self._set_now_status(msg)
        self._set_last_event("guard blocked")
        self._store_log("socket", f"guard_blocked:{msg}")

    def _log_socket_event(self, name, payload=None):
        if name in self.noisy_socket_events:
            return
        summary = self._summarize_payload(payload)
        self._store_log("socket", f"recv:{name}:{summary}")

    def _log_timer_update(self, remaining, total, payload):
        try:
            remaining_val = int(float(remaining))
        except (TypeError, ValueError):
            return
        if remaining_val <= 5:
            summary = self._summarize_payload(payload)
            self._store_log("socket", f"recv:timer_update:{summary}")

    def _summarize_payload(self, payload, max_len=200):
        if payload is None:
            return "None"
        if isinstance(payload, dict):
            return f"dict keys={list(payload.keys())}"
        if isinstance(payload, (list, tuple)):
            return f"{type(payload).__name__} len={len(payload)}"
        text = str(payload)
        if len(text) > max_len:
            text = text[:max_len] + "..."
        return text

    def update_players(self, players):
        self.players_table.setRowCount(0)
        self.player_row_map.clear()
        sorted_players = sorted(players, key=lambda p: p.get("score", 0), reverse=True)
        for idx, p in enumerate(sorted_players, 1):
            name = p.get("name")
            score = p.get("score", 0)
            status = p.get("status", "offline")
            row = self.players_table.rowCount()
            self.players_table.insertRow(row)
            status_item = QtWidgets.QTableWidgetItem(str(status))
            player_item = QtWidgets.QTableWidgetItem(str(name))
            score_item = QtWidgets.QTableWidgetItem(str(score))
            self.players_table.setItem(row, 0, status_item)
            self.players_table.setItem(row, 1, player_item)
            self.players_table.setItem(row, 2, score_item)
            lock_btn = QtWidgets.QToolButton()
            lock_btn.setText("Lock")
            lock_btn.clicked.connect(lambda _=False, n=name: self.lock_player(n))
            self.players_table.setCellWidget(row, 3, lock_btn)
            self.player_row_map[name] = row

    def update_leaderboard(self, data):
        if not data:
            return
        for name, score in data.items():
            row = self.player_row_map.get(name)
            if row is None:
                continue
            score_item = self.players_table.item(row, 2)
            if score_item:
                score_item.setText(str(score))

    def update_grading(self, rows):
        self.grading_rows = rows or []
        self.apply_grading_filter()

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

    def apply_grading_filter(self):
        def _format_points(value):
            try:
                num = float(value)
            except (TypeError, ValueError):
                num = 0.0
            return f"{num:g}"

        def _guess_with_points(guess, points):
            text = str(guess or "")
            return f"{text} ({_format_points(points)})".strip()

        filters = {
            "player": self.filter_player.text().strip().lower(),
            "round": self.filter_round.text().strip().lower(),
            "position": self.filter_position.text().strip().lower(),
            "artist": self.filter_artist.text().strip().lower(),
            "title": self.filter_title.text().strip().lower(),
            "extra": "",
        }
        self.grading_table.setRowCount(0)
        sorted_rows = sorted(
            self.grading_rows,
            key=lambda r: (
                r.get("round_number") or 0,
                r.get("position") or 0,
                str(r.get("player_name") or "").lower(),
            ),
        )
        for row in sorted_rows:
            if filters["player"] and filters["player"] not in str(row.get("player_name", "")).lower():
                continue
            if filters["round"] and filters["round"] not in str(row.get("round_number", "")).lower():
                continue
            if filters["position"] and filters["position"] not in str(row.get("position", "")).lower():
                continue
            if filters["artist"] and filters["artist"] not in str(row.get("artist_guess", "")).lower():
                continue
            if filters["title"] and filters["title"] not in str(row.get("title_guess", "")).lower():
                continue
            values = [
                row.get("id"),
                row.get("round_number"),
                row.get("position"),
                row.get("player_name"),
                _guess_with_points(row.get("artist_guess"), row.get("artist_points")),
                _guess_with_points(row.get("title_guess"), row.get("title_points")),
            ]
            table_row = self.grading_table.rowCount()
            self.grading_table.insertRow(table_row)
            for col, value in enumerate(values):
                self.grading_table.setItem(table_row, col, QtWidgets.QTableWidgetItem(str(value)))

    def lock_player(self, name):
        if not self.sio_connected:
            return
        if not name:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Lock Player",
            f"Zakljucati igraca '{name}'?"
        )
        if confirm == QtWidgets.QMessageBox.Yes:
            self.sio.emit("admin_lock_player", {"player_name": name})

    def update_single_player_status(self, name, status):
        if not name:
            return
        row = self.player_row_map.get(name)
        if row is None:
            return
        status_item = self.players_table.item(row, 0)
        if status_item:
            status_item.setText(str(status))

    def finalize_round(self):
        if not self.sio_connected:
            return
        round_num = int(self.live_round.currentText())
        self.sio.emit("admin_finalize_round", {"round": round_num})

    def handle_live_media(self, data):
        if isinstance(data, dict):
            self._store_log("socket", f"handle_live_media:id={data.get('id')} url={data.get('url')}")
        self.update_now_playing(data)
        self.play_live_media(data)

    def handle_show_correct(self, data):
        self.stop_live_media()
        self.update_correct_answer(data)

    def play_live_media(self, data):
        url = data.get("url")
        if not url:
            self._store_log("socket", "play_live_media:no_url")
            self.stop_live_media()
            return
        resolved = self.resolve_media_url(url)
        if not resolved:
            self._store_log("socket", f"play_live_media:unresolved:{url}")
            self.stop_live_media()
            return
        start_ms = int(float(data.get("start", 0)) * 1000)
        duration_s = data.get("duration")
        self.live_media_seek_ms = max(0, start_ms)
        self.live_player.stop()
        self.live_player.setSource(resolved)
        self.live_player.play()
        if duration_s:
            try:
                duration_ms = int(float(duration_s) * 1000)
            except (TypeError, ValueError):
                duration_ms = None
            if duration_ms and duration_ms > 0:
                self.live_audio_stop_timer.start(duration_ms)

    def stop_live_media(self):
        if self.live_audio_stop_timer.isActive():
            self.live_audio_stop_timer.stop()
        self.live_media_seek_ms = None
        if self.live_player.playbackState() != QtMultimedia.QMediaPlayer.StoppedState:
            self.live_player.stop()

    def set_live_audio_paused(self, paused):
        if self.live_player.source().isEmpty():
            return
        if paused:
            self.live_player.pause()
        else:
            self.live_player.play()

    def _on_live_media_status(self, status):
        if self.live_media_seek_ms is None:
            return
        if status in (
            QtMultimedia.QMediaPlayer.MediaStatus.LoadedMedia,
            QtMultimedia.QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self.live_player.setPosition(self.live_media_seek_ms)
            self.live_media_seek_ms = None

    def _on_live_media_error(self, error, error_string):
        self._store_log("socket", f"media_error:{error}:{error_string}")

    def resolve_media_url(self, url):
        if url.startswith("http://") or url.startswith("https://"):
            return QtCore.QUrl(url)
        if url.startswith("/stream_song/"):
            filename = url.split("/stream_song/", 1)[1]
            path = os.path.join(Config.SONGS_DIR, filename)
            if os.path.exists(path):
                return QtCore.QUrl.fromLocalFile(path)
            self._store_log("socket", f"resolve_media_url:missing_song:{path}")
        if url.startswith("/stream_video/"):
            filename = url.split("/stream_video/", 1)[1]
            path = os.path.join(ensure_videos_dir(), filename)
            if os.path.exists(path):
                return QtCore.QUrl.fromLocalFile(path)
            self._store_log("socket", f"resolve_media_url:missing_video:{path}")
        if url.startswith("/"):
            self._store_log("socket", f"resolve_media_url:http:{url}")
            return QtCore.QUrl(f"http://localhost:{self.port_input.value()}{url}")
        return None

    def update_now_playing(self, data):
        if isinstance(data, dict):
            self._store_log("socket", f"update_now_playing:id={data.get('id')} type={data.get('question_type')}")
        idx = data.get("question_index") or data.get("id") or ""
        qtype = data.get("question_type") or "audio"

        if qtype in ["text", "text_multiple"]:
            text = data.get("question_text") or "Pitanje"
            title = text
        elif qtype == "simultaneous":
            text = data.get("extra_question") or data.get("question_text") or "Pitanje"
            title = text
        else:
            artist = data.get("artist") or "?"
            title_val = data.get("title") or ""
            title = f"{artist} / {title_val}" if title_val else artist

        prefix = f"{idx}. " if idx else ""
        self.now_question_label.setText(f"Now:\n{prefix}{title}")
        duration = data.get("duration")
        if duration:
            self.update_live_timer(duration, duration)

    def update_correct_answer(self, data):
        artist = data.get("artist") or ""
        title = data.get("title") or ""
        if artist and title:
            label = f"Answer:\n{artist} - {title}"
        else:
            label = "Answer\nshown"
        self.now_question_label.setText(label)
        self.update_live_timer(15, 15)

    def _clear_timer_display(self):
        if hasattr(self, "timer_ring"):
            self.timer_ring.set_idle()
        if hasattr(self, "live_display_timer") and self.live_display_timer.isActive():
            self.live_display_timer.stop()

    def _tick_live_display_timer(self):
        remaining = getattr(self, "live_timer_remaining", None)
        total = getattr(self, "live_timer_total", None)
        if remaining is None:
            self._clear_timer_display()
            return
        remaining = max(0, int(remaining) - 1)
        self.live_timer_remaining = remaining
        if remaining <= 0:
            self.timer_ring.set_time(0, total, getattr(self, "_live_timer_label", "TIME"), self._live_timer_drain)
            self._clear_timer_display()
            return
        self.timer_ring.set_time(remaining, total, getattr(self, "_live_timer_label", "TIME"), self._live_timer_drain)

    def update_live_timer(self, remaining, total, source="local", label="TIME"):
        if remaining is None:
            return
        try:
            remaining_val = int(float(remaining))
        except (TypeError, ValueError):
            return
        total_val = None
        if total is not None:
            try:
                total_val = int(float(total))
            except (TypeError, ValueError):
                total_val = None
        if not total_val:
            total_val = max(1, remaining_val)
        self._live_timer_label = ""
        self._live_timer_drain = (label == "COUNTDOWN")
        self.live_timer_remaining = remaining_val
        self.live_timer_total = total_val
        if hasattr(self, "timer_ring"):
            self.timer_ring.set_time(remaining_val, total_val, label, self._live_timer_drain)
        if source == "server":
            if hasattr(self, "live_display_timer") and self.live_display_timer.isActive():
                self.live_display_timer.stop()
        else:
            if hasattr(self, "live_display_timer") and not self.live_display_timer.isActive():
                self.live_display_timer.start()
