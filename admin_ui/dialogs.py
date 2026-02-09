import math
import os
import random
import re
import sys
from datetime import datetime
from urllib.parse import quote

import qrcode
from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia

from admin_ui.utils import get_local_ip
from admin_ui.widgets import WaveformWidget
from extensions import db
from musicquiz.models import Question
from musicquiz.services.file_import_service import import_song_file, scan_mp3_folder


class CreateQuizDialog(QtWidgets.QDialog):
    def __init__(self, parent, with_app, on_created=None, prepare_animation=None):
        super().__init__(parent)
        self._with_app = with_app
        self._on_created = on_created
        self.setWindowTitle("Novi kviz")
        layout = QtWidgets.QFormLayout(self)
        self._title_input = QtWidgets.QLineEdit()
        self._date_input = QtWidgets.QLineEdit()
        layout.addRow("Naziv kviza", self._title_input)
        layout.addRow("Datum (YYYY-MM-DD)", self._date_input)
        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self._buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Spremi")
        self._buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Odustani")
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self._cancel)
        layout.addRow(self._buttons)
        if prepare_animation:
            prepare_animation(self)

    def _save(self):
        title = self._title_input.text().strip()
        if not title:
            QtWidgets.QMessageBox.warning(self, "Kviz", "Unesi naziv kviza.")
            return
        date_raw = self._date_input.text().strip()
        event_date = None
        if date_raw:
            try:
                event_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Kviz", "Datum mora biti YYYY-MM-DD.")
                return

        def _create():
            from musicquiz.models import Quiz

            Quiz.query.update({Quiz.is_active: False})
            quiz = Quiz(title=title, event_date=event_date, is_active=True)
            db.session.add(quiz)
            db.session.commit()

        self._with_app(_create)
        if self._on_created:
            self._on_created()
        self.accept()


class ImportFolderDialog(QtWidgets.QDialog):
    def __init__(self, parent, quiz_id, with_app, get_next_position, on_imported=None, prepare_animation=None):
        super().__init__(parent)
        self._quiz_id = quiz_id
        self._with_app = with_app
        self._get_next_position = get_next_position
        self._on_imported = on_imported
        self._files_state = {"base": None, "rels": []}
        self.setWindowTitle("Uvoz mape")
        self.resize(700, 600)
        layout = QtWidgets.QVBoxLayout(self)

        folder_row = QtWidgets.QHBoxLayout()
        self._folder_input = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton("Odaberi")
        browse_btn.clicked.connect(self._browse)
        folder_row.addWidget(self._folder_input, 1)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Runda"))
        self._round_combo = QtWidgets.QComboBox()
        self._round_combo.addItems(["1", "2", "3", "4", "5"])
        controls.addWidget(self._round_combo)
        controls.addSpacing(12)
        controls.addWidget(QtWidgets.QLabel("Trajanje"))
        self._duration = QtWidgets.QDoubleSpinBox()
        self._duration.setRange(5, 120)
        self._duration.setValue(30)
        controls.addWidget(self._duration)
        scan_btn = QtWidgets.QPushButton("Skeniraj")
        scan_btn.clicked.connect(self._scan)
        controls.addStretch(1)
        controls.addWidget(scan_btn)
        layout.addLayout(controls)

        self._files_list = QtWidgets.QListWidget()
        self._files_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        layout.addWidget(self._files_list, 1)

        action_row = QtWidgets.QHBoxLayout()
        action_row.addStretch(1)
        import_btn = QtWidgets.QPushButton("Uvezi odabrano")
        import_btn.clicked.connect(self._import)
        action_row.addWidget(import_btn)
        layout.addLayout(action_row)

        if prepare_animation:
            prepare_animation(self)

    def _browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            self._folder_input.setText(path)

    def _scan(self):
        base = self._folder_input.text().strip()
        if not base or not os.path.isdir(base):
            QtWidgets.QMessageBox.warning(self, "Uvoz", "Mapa nije pronadena.")
            return
        rels = scan_mp3_folder(base)
        self._files_state["base"] = base
        self._files_state["rels"] = rels
        self._files_list.clear()
        for rel in rels:
            self._files_list.addItem(rel)

    def _import(self):
        if not self._files_state["rels"]:
            QtWidgets.QMessageBox.warning(self, "Uvoz", "Nema datoteka za uvoz.")
            return
        selected = self._files_list.selectedItems()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "Uvoz", "Nista nije odabrano.")
            return
        round_num = int(self._round_combo.currentText())
        duration = float(self._duration.value())
        base = self._files_state["base"]
        rels = [item.text() for item in selected]

        def _do_import():
            from musicquiz.models import Song
            from admin_ui.utils import guess_artist_title

            position = self._get_next_position(self._quiz_id, round_num)
            for rel in rels:
                full_path = os.path.join(base, rel)
                filename = import_song_file(full_path, os.path.basename(rel))
                artist, title = guess_artist_title(rel)
                question = Question(
                    quiz_id=self._quiz_id,
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

        self._with_app(_do_import)
        if self._on_imported:
            self._on_imported()
        self.accept()


class LoadingSpinner(QtWidgets.QWidget):
    def __init__(self, parent=None, size=18, line_count=12):
        super().__init__(parent)
        self._angle = 0
        self._line_count = max(6, int(line_count))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._step)
        self.setFixedSize(size, size)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()

    def _step(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        radius = min(rect.width(), rect.height()) / 2 - 1
        center = rect.center()
        base_color = QtGui.QColor("#ffffff")
        for i in range(self._line_count):
            alpha = int(255 * (i + 1) / self._line_count)
            color = QtGui.QColor(base_color)
            color.setAlpha(alpha)
            painter.setPen(QtGui.QPen(color, 2))
            angle = (self._angle + (360 / self._line_count) * i) * 3.14159265 / 180.0
            x = center.x() + radius * 0.75 * math.cos(angle)
            y = center.y() + radius * 0.75 * math.sin(angle)
            painter.drawPoint(QtCore.QPointF(x, y))


class AudioQuestionEditorDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent,
        data,
        with_app,
        get_round_count,
        reposition_question,
        on_saved=None,
        prepare_animation=None,
    ):
        super().__init__(parent)
        self._data = data
        self._with_app = with_app
        self._get_round_count = get_round_count
        self._reposition_question = reposition_question
        self._on_saved = on_saved
        self.setWindowTitle(f"Uredi {data['type']}")
        self.resize(520, 520)
        layout = QtWidgets.QFormLayout(self)
        if prepare_animation:
            prepare_animation(self)

        self._round_combo = QtWidgets.QComboBox()
        self._round_combo.addItems(["1", "2", "3", "4", "5"])
        self._round_combo.setCurrentText(str(data.get("round", 1)))
        self._position_spin = QtWidgets.QSpinBox()
        self._position_spin.setRange(1, 1)
        self._position_spin.setValue(int(data.get("position", 1)))
        self._position_initialized = False

        def _update_position_range():
            quiz_id = data.get("quiz_id")
            new_round = int(self._round_combo.currentText())
            count = self._get_round_count(quiz_id, new_round) if quiz_id else 1
            max_pos = count if new_round == int(data.get("round", 1)) else count + 1
            self._position_spin.setRange(1, max(1, max_pos))
            if not self._position_initialized:
                desired = int(data.get("position", 1))
                self._position_spin.setValue(min(max(1, desired), max(1, max_pos)))
                self._position_initialized = True

        self._round_combo.currentIndexChanged.connect(_update_position_range)
        _update_position_range()

        layout.addRow("Runda", self._round_combo)
        layout.addRow("Pozicija", self._position_spin)

        self._artist = QtWidgets.QLineEdit(data.get("artist", ""))
        self._title = QtWidgets.QLineEdit(data.get("title", ""))
        self._start = QtWidgets.QDoubleSpinBox()
        self._start.setRange(0, 120)
        self._start.setValue(float(data.get("start", 0)))
        self._duration = QtWidgets.QDoubleSpinBox()
        self._duration.setRange(5, 120)
        self._duration.setValue(float(data.get("duration", 30)))

        layout.addRow("Izvodac", self._artist)
        layout.addRow("Naslov", self._title)
        layout.addRow("Start", self._start)
        layout.addRow("Trajanje", self._duration)

        self._media_path = data.get("media_path")
        self._player = QtMultimedia.QMediaPlayer(self)
        self._audio_output = QtMultimedia.QAudioOutput(self)
        self._audio_output.setVolume(0.4)
        self._player.setAudioOutput(self._audio_output)

        self._waveform = WaveformWidget()
        self._waveform.setFixedHeight(90)
        self._waveform.set_clip_range(
            int(float(self._start.value()) * 1000),
            int(float(self._duration.value()) * 1000),
        )

        preview_overlay = QtWidgets.QWidget()
        preview_overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        preview_overlay.setStyleSheet("background: rgba(0, 0, 0, 110);")
        preview_overlay.setVisible(False)
        preview_overlay.setMinimumHeight(90)

        preview_status = QtWidgets.QLabel("Loading preview...")
        preview_status.setAlignment(QtCore.Qt.AlignCenter)
        preview_status.setStyleSheet("color: #ffffff;")
        preview_spinner = LoadingSpinner()

        preview_overlay_layout = QtWidgets.QVBoxLayout(preview_overlay)
        preview_overlay_layout.setContentsMargins(16, 10, 16, 10)
        preview_overlay_layout.addStretch(1)
        preview_overlay_layout.addWidget(preview_status)
        preview_overlay_layout.addWidget(preview_spinner, 0, QtCore.Qt.AlignCenter)
        preview_overlay_layout.addStretch(1)

        preview_frame = QtWidgets.QWidget()
        preview_layout = QtWidgets.QGridLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self._waveform, 0, 0)
        preview_layout.addWidget(preview_overlay, 0, 0)

        def _set_preview_loading(is_loading):
            preview_overlay.setVisible(is_loading)
            if is_loading:
                preview_spinner.start()
            else:
                preview_spinner.stop()

        def _on_preview_finished(_success):
            _set_preview_loading(False)

        self._waveform.loadStarted.connect(lambda: _set_preview_loading(True))
        self._waveform.loadFinished.connect(_on_preview_finished)

        if self._media_path and os.path.exists(self._media_path):
            self._player.setSource(QtCore.QUrl.fromLocalFile(self._media_path))
            self._waveform.load(self._media_path)

        style = self.style()

        zoom_label = QtWidgets.QLabel("Zoom")
        zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        zoom_slider.setRange(50, 400)
        zoom_slider.setValue(100)
        zoom_slider.valueChanged.connect(lambda v: self._waveform.set_zoom(v / 100.0))

        zoom_row = QtWidgets.QHBoxLayout()
        zoom_row.addWidget(zoom_label)
        zoom_row.addWidget(zoom_slider, 1)

        volume_label = QtWidgets.QLabel("Volume")
        volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        volume_slider.setRange(0, 100)
        volume_slider.setValue(40)

        volume_value = QtWidgets.QLabel("40%")
        volume_value.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        mute_btn = QtWidgets.QToolButton()
        mute_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaVolumeMuted))
        mute_btn.setToolTip("Mute")
        mute_btn.setCheckable(True)

        last_volume = {"value": volume_slider.value()}

        def _apply_volume(value):
            volume_value.setText(f"{value}%")
            self._audio_output.setVolume(max(0.0, min(1.0, value / 100.0)))

        def _on_volume_changed(value):
            if value > 0 and mute_btn.isChecked():
                mute_btn.setChecked(False)
            if value > 0:
                last_volume["value"] = value
            _apply_volume(value)

        def _on_mute_toggled(checked):
            if checked:
                last_volume["value"] = volume_slider.value() or last_volume["value"]
                volume_slider.setValue(0)
            else:
                restore = last_volume["value"] or 40
                volume_slider.setValue(restore)

        volume_slider.valueChanged.connect(_on_volume_changed)
        mute_btn.toggled.connect(_on_mute_toggled)

        volume_row = QtWidgets.QHBoxLayout()
        volume_row.addWidget(volume_label)
        volume_row.addWidget(volume_slider, 1)
        volume_row.addWidget(volume_value)
        volume_row.addWidget(mute_btn)

        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 0)

        time_label = QtWidgets.QLabel("0:00 / 0:00")

        def _format_ms(value):
            seconds = int(value / 1000)
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}:{seconds:02d}"

        def _on_duration_changed(ms):
            slider.setRange(0, int(ms or 0))
            self._waveform.set_duration(ms or 1)
            time_label.setText(f"0:00 / {_format_ms(ms or 0)}")

        def _on_position_changed(ms):
            if not slider.isSliderDown():
                slider.setValue(int(ms or 0))
            self._waveform.set_progress(ms or 0)
            time_label.setText(
                f"{_format_ms(ms or 0)} / {_format_ms(self._player.duration() or 0)}"
            )

        self._player.durationChanged.connect(_on_duration_changed)
        self._player.positionChanged.connect(_on_position_changed)
        slider.sliderMoved.connect(lambda v: self._player.setPosition(int(v)))
        self._waveform.seekRequested.connect(lambda ms: self._player.setPosition(int(ms)))

        def _on_clip_change():
            self._waveform.set_clip_range(
                int(float(self._start.value()) * 1000),
                int(float(self._duration.value()) * 1000),
            )

        self._start.valueChanged.connect(_on_clip_change)
        self._duration.valueChanged.connect(_on_clip_change)

        clip_btn = QtWidgets.QPushButton("Play Clip")
        play_btn = QtWidgets.QToolButton()
        play_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        play_btn.setToolTip("Play")
        pause_btn = QtWidgets.QToolButton()
        pause_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaPause))
        pause_btn.setToolTip("Pause")
        stop_btn = QtWidgets.QToolButton()
        stop_btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_MediaStop))
        stop_btn.setToolTip("Stop")

        clip_timer = QtCore.QTimer(self)
        clip_timer.setSingleShot(True)

        def _play():
            if not self._media_path:
                return
            clip_timer.stop()
            _apply_volume(volume_slider.value())
            self._player.play()

        def _pause():
            if not self._media_path:
                return
            self._player.pause()

        def _stop():
            if not self._media_path:
                return
            clip_timer.stop()
            self._player.stop()

        def _play_clip():
            if not self._media_path:
                return
            clip_timer.stop()
            _apply_volume(volume_slider.value())
            start_ms = int(float(self._start.value()) * 1000)
            duration_ms = int(float(self._duration.value()) * 1000)
            self._player.setPosition(start_ms)
            self._player.play()
            if duration_ms > 0:
                clip_timer.start(duration_ms)

        def _stop_clip():
            self._player.pause()

        clip_timer.timeout.connect(_stop_clip)
        play_btn.clicked.connect(_play)
        pause_btn.clicked.connect(_pause)
        stop_btn.clicked.connect(_stop)
        clip_btn.clicked.connect(_play_clip)

        player_box = QtWidgets.QVBoxLayout()
        player_box.addWidget(preview_frame)
        player_box.addLayout(zoom_row)
        player_box.addLayout(volume_row)
        player_box.addWidget(slider)
        controls_row = QtWidgets.QHBoxLayout()
        controls_row.addWidget(clip_btn)
        controls_row.addSpacing(6)
        controls_row.addWidget(play_btn)
        controls_row.addWidget(pause_btn)
        controls_row.addWidget(stop_btn)
        controls_row.addStretch(1)
        controls_row.addWidget(time_label)
        player_box.addLayout(controls_row)

        player_container = QtWidgets.QWidget()
        player_container.setLayout(player_box)
        layout.addRow("Pretpregled", player_container)

        self._extra_q = None
        self._extra_a = None
        if data["type"] == "simultaneous":
            self._extra_q = QtWidgets.QLineEdit(data.get("extra_q", ""))
            self._extra_a = QtWidgets.QLineEdit(data.get("extra_a", ""))
            layout.addRow("Extra pitanje", self._extra_q)
            layout.addRow("Extra odgovor", self._extra_a)

        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self._buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Spremi")
        self._buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Odustani")
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def _save(self):
        self._stop_playback()
        new_artist = self._artist.text().strip()
        new_title = self._title.text().strip()
        new_start = float(self._start.value())
        new_duration = float(self._duration.value())
        new_extra_q = self._extra_q.text().strip() if self._extra_q else ""
        new_extra_a = self._extra_a.text().strip() if self._extra_a else ""
        new_round = int(self._round_combo.currentText())
        new_position = int(self._position_spin.value())

        def _update():
            question = db.session.get(Question, self._data["id"])
            if not question:
                return
            if question.round_number != new_round or question.position != new_position:
                self._reposition_question(question, new_round, new_position)
            question.duration = new_duration
            if question.type == "audio" and question.song:
                question.song.artist = new_artist
                question.song.title = new_title
                question.song.start_time = new_start
            elif question.type == "video" and question.video:
                question.video.artist = new_artist
                question.video.title = new_title
                question.video.start_time = new_start
            elif question.type == "simultaneous" and question.simultaneous:
                question.simultaneous.artist = new_artist
                question.simultaneous.title = new_title
                question.simultaneous.start_time = new_start
                question.simultaneous.extra_question = new_extra_q
                question.simultaneous.extra_answer = new_extra_a
            db.session.commit()

        self._with_app(_update)
        if self._on_saved:
            self._on_saved()
        self.accept()

    def _stop_playback(self):
        if self._player:
            self._player.stop()
        if self._waveform:
            self._waveform.stop()

    def _cancel(self):
        self._stop_playback()
        self.reject()

    def closeEvent(self, event):
        self._stop_playback()
        super().closeEvent(event)


class TextQuestionEditorDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent,
        data,
        with_app,
        get_round_count,
        reposition_question,
        on_saved=None,
        prepare_animation=None,
    ):
        super().__init__(parent)
        self._data = data
        self._with_app = with_app
        self._get_round_count = get_round_count
        self._reposition_question = reposition_question
        self._on_saved = on_saved
        self.setWindowTitle(f"Uredi {data['type']}")
        self.resize(520, 520)
        layout = QtWidgets.QFormLayout(self)
        if prepare_animation:
            prepare_animation(self)

        self._round_combo = QtWidgets.QComboBox()
        self._round_combo.addItems(["1", "2", "3", "4", "5"])
        self._round_combo.setCurrentText(str(data.get("round", 1)))
        self._position_spin = QtWidgets.QSpinBox()
        self._position_spin.setRange(1, 1)
        self._position_spin.setValue(int(data.get("position", 1)))
        self._position_initialized = False

        def _update_position_range():
            quiz_id = data.get("quiz_id")
            new_round = int(self._round_combo.currentText())
            count = self._get_round_count(quiz_id, new_round) if quiz_id else 1
            max_pos = count if new_round == int(data.get("round", 1)) else count + 1
            self._position_spin.setRange(1, max(1, max_pos))
            if not self._position_initialized:
                desired = int(data.get("position", 1))
                self._position_spin.setValue(min(max(1, desired), max(1, max_pos)))
                self._position_initialized = True

        self._round_combo.currentIndexChanged.connect(_update_position_range)
        _update_position_range()

        layout.addRow("Runda", self._round_combo)
        layout.addRow("Pozicija", self._position_spin)

        self._question_text = QtWidgets.QLineEdit(data.get("question_text", ""))
        self._duration = QtWidgets.QDoubleSpinBox()
        self._duration.setRange(5, 120)
        self._duration.setValue(float(data.get("duration", 30)))
        layout.addRow("Pitanje", self._question_text)

        self._answer_text = None
        self._choices_box = None
        self._correct_spin = None

        if data["type"] == "text":
            self._answer_text = QtWidgets.QLineEdit(data.get("answer_text", ""))
            layout.addRow("Tocan odgovor", self._answer_text)
        else:
            self._choices_box = QtWidgets.QPlainTextEdit()
            choices = data.get("choices", [])
            self._choices_box.setPlainText("\n".join(choices))
            self._correct_spin = QtWidgets.QSpinBox()
            self._correct_spin.setRange(1, 20)
            self._correct_spin.setValue(int(data.get("correct_index", 1)))
            layout.addRow("Mogucnosti", self._choices_box)
            layout.addRow("Tocan", self._correct_spin)

        layout.addRow("Trajanje", self._duration)

        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self._buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Spremi")
        self._buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Odustani")
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def _save(self):
        text = self._question_text.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "Pitanje", "Pitanje ne smije biti prazno.")
            return
        new_duration = float(self._duration.value())
        new_round = int(self._round_combo.currentText())
        new_position = int(self._position_spin.value())

        new_answer = self._answer_text.text().strip() if self._answer_text else ""
        new_choices = []
        new_correct = 0
        if self._choices_box:
            new_choices = [
                line.strip()
                for line in self._choices_box.toPlainText().splitlines()
                if line.strip()
            ]
            new_correct = max(0, int(self._correct_spin.value()) - 1) if self._correct_spin else 0

        def _update():
            question = db.session.get(Question, self._data["id"])
            if not question:
                return
            if question.round_number != new_round or question.position != new_position:
                self._reposition_question(question, new_round, new_position)
            question.duration = new_duration
            if question.type == "text" and question.text:
                question.text.question_text = text
                question.text.answer_text = new_answer
            elif question.type == "text_multiple" and question.text_multiple:
                question.text_multiple.question_text = text
                question.text_multiple.set_choices(new_choices)
                question.text_multiple.correct_index = new_correct
            db.session.commit()

        self._with_app(_update)
        if self._on_saved:
            self._on_saved()
        self.accept()


class QrPinDialog(QtWidgets.QDialog):
    def __init__(self, parent, port_getter, prepare_animation=None):
        super().__init__(parent)
        self._port_getter = port_getter
        self.setWindowTitle("QR/PIN generator")
        self.resize(520, 520)
        layout = QtWidgets.QVBoxLayout(self)
        if prepare_animation:
            prepare_animation(self)

        label = QtWidgets.QLabel("Timovi (jedan po retku)")
        layout.addWidget(label)

        self._teams_box = QtWidgets.QPlainTextEdit()
        layout.addWidget(self._teams_box, 1)

        btn = QtWidgets.QPushButton("Generiraj")
        btn.clicked.connect(self._generate)
        layout.addWidget(btn)

    def _generate(self):
        raw = self._teams_box.toPlainText().strip()
        if not raw:
            QtWidgets.QMessageBox.warning(self, "QR", "Unesi barem jedan tim.")
            return

        teams = [line.strip() for line in raw.splitlines() if line.strip()]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(base_dir, "qr_output")
        os.makedirs(out_dir, exist_ok=True)

        ip = get_local_ip()
        port = int(self._port_getter())
        pins = set()
        lines = []

        for team in teams:
            pin = random.randint(1000, 9999)
            while pin in pins:
                pin = random.randint(1000, 9999)
            pins.add(pin)

            url = f"http://{ip}:{port}/player?name={quote(team)}&pin={pin}"
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", team).strip("_") or "team"
            img = qrcode.make(url)
            img_path = os.path.join(out_dir, f"{safe_name}_{pin}.png")
            img.save(img_path)
            lines.append(f"{team}\t{pin}\t{url}")

        summary_path = os.path.join(out_dir, "teams.txt")
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

        QtWidgets.QMessageBox.information(
            self,
            "QR",
            f"Generirano {len(teams)} QR kodova u {out_dir}",
        )
        if sys.platform.startswith("win"):
            os.startfile(out_dir)
