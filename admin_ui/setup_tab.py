import os
import re

from PySide6 import QtCore, QtWidgets

from admin_ui.dialogs import (
    AudioQuestionEditorDialog,
    CreateQuizDialog,
    ImportFolderDialog,
    TextQuestionEditorDialog,
)
from admin_ui.utils import ensure_videos_dir, guess_artist_title, import_video_file
from config import Config
from extensions import db
from musicquiz.models import (
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


class _RepoScanWorker(QtCore.QObject):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(self, base_path):
        super().__init__()
        self._base_path = base_path

    @QtCore.Slot()
    def run(self):
        try:
            files = scan_mp3_folder(self._base_path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(files)


class SetupTabMixin:
    def _build_setup_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_setup)
        top_bar = QtWidgets.QHBoxLayout()
        layout.addLayout(top_bar)

        top_bar.addWidget(QtWidgets.QLabel("ACTIVE:"))

        self.quiz_combo = QtWidgets.QComboBox()
        self.quiz_combo.currentIndexChanged.connect(self.refresh_questions)
        top_bar.addWidget(self.quiz_combo)

        new_quiz_btn = QtWidgets.QPushButton("New Quiz")
        new_quiz_btn.clicked.connect(self.create_quiz_modal)
        top_bar.addWidget(new_quiz_btn)

        top_bar.addStretch(1)

        body = QtWidgets.QHBoxLayout()
        layout.addLayout(body, 1)

        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        body.addLayout(left, 5)
        body.addLayout(right, 7)

        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.addWidget(QtWidgets.QLabel("Pitanje:"))
        self.question_mode_audio = QtWidgets.QPushButton("Audio")
        self.question_mode_audio.setCheckable(True)
        self.question_mode_audio.setProperty("modeToggle", True)
        self.question_mode_other = QtWidgets.QPushButton("Ostalo")
        self.question_mode_other.setCheckable(True)
        self.question_mode_other.setProperty("modeToggle", True)
        self.question_mode_group = QtWidgets.QButtonGroup(self)
        self.question_mode_group.setExclusive(True)
        self.question_mode_group.addButton(self.question_mode_audio, 0)
        self.question_mode_group.addButton(self.question_mode_other, 1)
        self.question_mode_audio.setChecked(True)
        self._update_question_mode_buttons()
        toggle_row.addWidget(self.question_mode_audio)
        toggle_row.addWidget(self.question_mode_other)
        toggle_row.addStretch(1)
        left.addLayout(toggle_row)

        self.create_mode_stack = QtWidgets.QStackedWidget()
        self.repo_panel = self._build_repo_panel()
        self.create_panel = self._build_create_panel()
        self.create_mode_stack.addWidget(self.repo_panel)
        self.create_mode_stack.addWidget(self.create_panel)
        left.addWidget(self.create_mode_stack, 1)
        self.question_mode_group.idClicked.connect(self._on_question_mode_changed)
        self._build_questions_panel(right)

    def _build_repo_panel(self):
        group = QtWidgets.QGroupBox("LOKALNI REPOZITORIJ")
        group_layout = QtWidgets.QVBoxLayout(group)

        path_row = QtWidgets.QHBoxLayout()
        self.repo_path = QtWidgets.QLineEdit()
        self.repo_browse_btn = QtWidgets.QPushButton("Browse")
        self.repo_browse_btn.clicked.connect(self.browse_repo_folder)
        import_btn = QtWidgets.QPushButton("Import Folder")
        import_btn.clicked.connect(self.open_import_folder_modal)
        path_row.addWidget(self.repo_path, 1)
        path_row.addWidget(self.repo_browse_btn)
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

        return group

    def _build_create_panel(self):
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

        return group

    def _on_question_mode_changed(self, mode_id):
        if hasattr(self, "create_mode_stack"):
            self.create_mode_stack.setCurrentIndex(mode_id)
        self._update_question_mode_buttons()

    def _update_question_mode_buttons(self):
        if not hasattr(self, "question_mode_audio") or not hasattr(self, "question_mode_other"):
            return
        audio_selected = self.question_mode_audio.isChecked()
        self.question_mode_audio.setProperty("inactive", not audio_selected)
        self.question_mode_other.setProperty("inactive", audio_selected)
        for button in (self.question_mode_audio, self.question_mode_other):
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

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
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Round:"))
        self.round_combo = QtWidgets.QComboBox()
        self.round_combo.addItems(["1", "2", "3", "4", "5"])
        self.round_combo.currentIndexChanged.connect(self.refresh_questions)
        header.addWidget(self.round_combo)
        header.addStretch(1)
        layout.addLayout(header)

        self.questions_list = QtWidgets.QListWidget()
        self.questions_list.setObjectName("QuestionList")
        self.questions_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.questions_list.setSpacing(8)
        self.questions_list.itemDoubleClicked.connect(lambda _item: self.open_editor_dialog())
        layout.addWidget(self.questions_list, 1)

        parent_layout.addWidget(group, 2)

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
        self.live_quiz_combo.blockSignals(True)
        self.live_quiz_combo.clear()
        for quiz in quizzes:
            date_text = ""
            if getattr(quiz, "event_date", None):
                date_text = f" ({quiz.event_date.strftime('%d.%m.%Y')})"
            label = f"{quiz.id}: {quiz.title}{date_text}"
            self.quiz_combo.addItem(label, quiz.id)
            self.live_quiz_combo.addItem(label, quiz.id)
        self.quiz_combo.blockSignals(False)
        self.live_quiz_combo.blockSignals(False)

        if active:
            idx = self.quiz_combo.findData(active.id)
            if idx >= 0:
                self.quiz_combo.setCurrentIndex(idx)
            live_idx = self.live_quiz_combo.findData(active.id)
            if live_idx >= 0:
                self.live_quiz_combo.setCurrentIndex(live_idx)

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

    def set_active_quiz_by_id(self, quiz_id):
        if not quiz_id:
            return

        def _set():
            Quiz.query.update({Quiz.is_active: False})
            quiz = db.session.get(Quiz, quiz_id)
            if quiz:
                quiz.is_active = True
            db.session.commit()

        self.with_app(_set)
        self.refresh_questions()
        self.refresh_live_questions()

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
            self._start_repo_scan(path)

    def _start_repo_scan(self, base):
        if not base or not os.path.isdir(base):
            return
        thread = getattr(self, "_repo_scan_thread", None)
        if thread and thread.isRunning():
            return
        self.repo_base = base
        self._set_repo_scan_busy(True)
        self._repo_scan_thread = QtCore.QThread(self)
        self._repo_scan_worker = _RepoScanWorker(base)
        self._repo_scan_worker.moveToThread(self._repo_scan_thread)
        self._repo_scan_thread.started.connect(self._repo_scan_worker.run)
        self._repo_scan_worker.finished.connect(self._on_repo_scan_finished)
        self._repo_scan_worker.failed.connect(self._on_repo_scan_failed)
        self._repo_scan_worker.finished.connect(self._repo_scan_thread.quit)
        self._repo_scan_worker.failed.connect(self._repo_scan_thread.quit)
        self._repo_scan_thread.finished.connect(self._repo_scan_worker.deleteLater)
        self._repo_scan_thread.finished.connect(self._repo_scan_thread.deleteLater)
        self._repo_scan_thread.start()

    def _set_repo_scan_busy(self, busy):
        if hasattr(self, "repo_browse_btn"):
            self.repo_browse_btn.setEnabled(not busy)

    def _on_repo_scan_finished(self, files):
        self.repo_files = files or []
        self.filter_repo_list()
        self._set_repo_scan_busy(False)

    def _on_repo_scan_failed(self, message):
        self._set_repo_scan_busy(False)
        if message:
            QtWidgets.QMessageBox.warning(self, "Scan", f"Neuspjelo skeniranje: {message}")

    def filter_repo_list(self):
        query = self.repo_search.text().strip().lower()
        files = getattr(self, "repo_files", [])
        if query:
            self.repo_filtered = [f for f in files if query in f.lower()]
        else:
            self.repo_filtered = list(files)
        self.repo_list.clear()
        sorted_files = sorted(self.repo_filtered, key=lambda rel: self._format_repo_display_name(rel).lower())
        for rel in sorted_files:
            display = self._format_repo_display_name(rel)
            item = QtWidgets.QListWidgetItem(display)
            item.setData(QtCore.Qt.UserRole, rel)
            self.repo_list.addItem(item)

    def _format_repo_display_name(self, rel_path):
        filename = os.path.basename(rel_path)
        name, _ext = os.path.splitext(filename)
        name = re.sub(r"^\s*\d+\s*[-._ ]+", "", name)
        return name.strip()

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
        files = [item.data(QtCore.Qt.UserRole) or item.text() for item in items]

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

    def _on_questions_changed(self):
        self._load_quizzes()
        self.refresh_questions()
