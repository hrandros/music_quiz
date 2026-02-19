import struct
import threading

try:
    import numpy as np
    import librosa
    _HAS_LIBROSA = True
except Exception:
    np = None
    librosa = None
    _HAS_LIBROSA = False

from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia

from admin_ui.constants import THEME


class UiSignals(QtCore.QObject):
    log_line = QtCore.Signal(str)
    status_text = QtCore.Signal(str)
    address_text = QtCore.Signal(str)
    live_status = QtCore.Signal(str)
    players = QtCore.Signal(list)
    leaderboard = QtCore.Signal(dict)
    grading = QtCore.Signal(list)
    pause_state = QtCore.Signal(bool)
    round_countdown = QtCore.Signal(dict)
    play_audio = QtCore.Signal(dict)
    timer_update = QtCore.Signal(dict)
    tv_start_timer = QtCore.Signal(dict)
    show_correct = QtCore.Signal(dict)
    round_finished = QtCore.Signal(dict)
    single_player_update = QtCore.Signal(dict)
    live_guard_blocked = QtCore.Signal(dict)


class WaveformWidget(QtWidgets.QWidget):
    seekRequested = QtCore.Signal(int)
    loadStarted = QtCore.Signal()
    loadFinished = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks = []
        self._progress_ms = 0
        self._duration_ms = 1
        self._clip_start_ms = 0
        self._clip_end_ms = 0
        self._decode_limit_ms = None
        self._decoded_frames = 0
        self._sample_rate = 44100
        self._zoom = 1.0
        self._bucket_max = 0
        self._bucket_count = 0
        self._bucket_size = 4096
        self._max_peaks = 480
        self._update_counter = 0
        self._decoder = None
        self._view_center_ratio = None
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_ratio = 0.0
        self._hover_x = None
        self._decode_thread = None
        self._stop_decode = False
        self._load_finished_emitted = False

    def stop(self):
        self._stop_decode = True
        if self._decoder:
            self._decoder.stop()
            self._decoder.deleteLater()
            self._decoder = None

    def _post_to_main(self, fn):
        QtCore.QTimer.singleShot(0, self, fn)

    def set_duration(self, duration_ms):
        self._duration_ms = max(1, int(duration_ms or 1))
        self.update()

    def set_progress(self, progress_ms):
        self._progress_ms = max(0, int(progress_ms or 0))
        if self._zoom <= 1.0 or self._view_center_ratio is None:
            self._view_center_ratio = self._progress_ms / max(1, self._duration_ms)
        self.update()

    def set_clip_range(self, start_ms, duration_ms):
        start_ms = max(0, int(start_ms or 0))
        duration_ms = max(0, int(duration_ms or 0))
        self._clip_start_ms = start_ms
        self._clip_end_ms = start_ms + duration_ms
        self.update()

    def set_decode_limit(self, limit_ms):
        self._decode_limit_ms = int(limit_ms) if limit_ms is not None else None

    def set_zoom(self, zoom):
        self._zoom = max(0.5, min(4.0, float(zoom)))
        if self._zoom <= 1.0:
            self._view_center_ratio = None
        self.update()

    def _set_view_center_ratio(self, ratio, window_ratio):
        if window_ratio <= 0:
            return
        half = window_ratio / 2
        clamped = max(half, min(1.0 - half, ratio))
        self._view_center_ratio = clamped

    def load(self, path):
        self._load_finished_emitted = False
        self.loadStarted.emit()
        self._peaks = []
        self._bucket_max = 0
        self._bucket_count = 0
        self._update_counter = 0
        self._decoded_frames = 0
        if self._decoder:
            self._decoder.stop()
            self._decoder.deleteLater()
            self._decoder = None
        self._stop_decode = True
        if self._decode_thread and self._decode_thread.is_alive():
            self._decode_thread = None
        self._stop_decode = False
        if _HAS_LIBROSA:
            self._decode_thread = threading.Thread(
                target=self._decode_with_librosa,
                args=(path,),
                daemon=True,
            )
            self._decode_thread.start()
            return
        self._start_qt_decoder(path)

    def _start_qt_decoder(self, path):
        decoder = QtMultimedia.QAudioDecoder(self)
        decoder.setSource(QtCore.QUrl.fromLocalFile(path))
        decoder.bufferReady.connect(lambda: self._on_buffer(decoder))
        decoder.finished.connect(self._on_finished)
        if hasattr(decoder, "errorOccurred"):
            decoder.errorOccurred.connect(self._on_decode_error)
        elif hasattr(decoder, "errorChanged"):
            decoder.errorChanged.connect(lambda _err: self._on_decode_error(_err))
        self._decoder = decoder
        decoder.start()

    def _decode_with_librosa(self, path):
        try:
            data, sr = librosa.load(path, sr=None, mono=True)
            if self._stop_decode:
                return
            if data is None or len(data) == 0:
                self._post_to_main(lambda: self._emit_load_finished(False))
                return
            abs_data = np.abs(data)
            max_peaks = max(1, int(self._max_peaks))
            chunks = np.array_split(abs_data, max_peaks)
            peaks = [float(chunk.max()) if chunk.size else 0.0 for chunk in chunks]
            max_peak = max(peaks) or 1.0
            peaks_norm = [p / max_peak for p in peaks]
            sr_int = int(sr or self._sample_rate)
            self._post_to_main(lambda: self._apply_librosa_result(peaks_norm, sr_int))
            self._post_to_main(lambda: self._emit_load_finished(True))
        except Exception:
            if self._stop_decode:
                return
            self._post_to_main(lambda: self._start_qt_decoder(path))


    def _apply_librosa_result(self, peaks, sample_rate):
        # Ensure widget state is mutated only on the Qt main thread.
        self._peaks = list(peaks or [])
        try:
            self._sample_rate = int(sample_rate or self._sample_rate)
        except (TypeError, ValueError):
            pass
        self.update()

    def _emit_load_finished(self, success):
        if self._load_finished_emitted:
            return
        self._load_finished_emitted = True
        self.loadFinished.emit(bool(success))

    def _on_decode_error(self, _error):
        self._decoder = None
        self.update()
        self._emit_load_finished(False)

    def _append_sample(self, value):
        self._bucket_max = max(self._bucket_max, value)
        self._bucket_count += 1
        if self._bucket_count >= self._bucket_size:
            self._peaks.append(self._bucket_max)
            self._bucket_max = 0
            self._bucket_count = 0
            if self._max_peaks and len(self._peaks) >= self._max_peaks:
                if self._decoder:
                    self._decoder.stop()
                if not self._load_finished_emitted:
                    QtCore.QTimer.singleShot(0, self._on_finished)
                return

    def _on_buffer(self, decoder):
        buffer = decoder.read()
        fmt = buffer.format()
        self._sample_rate = max(1, fmt.sampleRate())
        sample_format = None
        if hasattr(fmt, "sampleFormat"):
            sample_format = fmt.sampleFormat()
        data = bytes(buffer.data())
        channels = max(1, fmt.channelCount())
        bytes_per_sample = None
        if hasattr(fmt, "bytesPerSample"):
            bytes_per_sample = int(fmt.bytesPerSample())
        if not bytes_per_sample:
            bytes_per_sample = max(1, int(fmt.sampleSize() or 0) // 8)
        bytes_per_frame = bytes_per_sample * channels
        if hasattr(buffer, "bytesPerFrame"):
            bytes_per_frame = int(buffer.bytesPerFrame()) or bytes_per_frame

        fmt_code = None
        scale = 1.0
        if sample_format == QtMultimedia.QAudioFormat.SampleFormat.Int16:
            fmt_code = "<h"
            scale = 32768.0
        elif sample_format == QtMultimedia.QAudioFormat.SampleFormat.Int32:
            fmt_code = "<i"
            scale = 2147483648.0
        elif sample_format == QtMultimedia.QAudioFormat.SampleFormat.Float:
            fmt_code = "<f"
            scale = 1.0
        else:
            if fmt.sampleType() == QtMultimedia.QAudioFormat.SignedInt and fmt.sampleSize() == 16:
                fmt_code = "<h"
                scale = 32768.0
            elif fmt.sampleType() == QtMultimedia.QAudioFormat.SignedInt and fmt.sampleSize() == 32:
                fmt_code = "<i"
                scale = 2147483648.0
            elif fmt.sampleType() == QtMultimedia.QAudioFormat.Float and fmt.sampleSize() == 32:
                fmt_code = "<f"
                scale = 1.0
            else:
                return

        frame_count = 0
        if hasattr(buffer, "frameCount"):
            frame_count = int(buffer.frameCount())
            self._decoded_frames += frame_count
        if frame_count <= 0 and bytes_per_frame > 0:
            frame_count = int(len(data) / bytes_per_frame)

        data_len = len(data)
        for frame in range(frame_count):
            offset = frame * bytes_per_frame
            if offset + bytes_per_sample > data_len:
                break
            sample = struct.unpack_from(fmt_code, data, offset)[0]
            value = abs(sample) / scale
            self._append_sample(value)

        if self._decode_limit_ms is not None:
            decoded_ms = int(self._decoded_frames / self._sample_rate * 1000)
            if decoded_ms >= self._decode_limit_ms:
                if self._decoder:
                    self._decoder.stop()
                self._on_finished()
                return

        self._update_counter += 1
        if self._update_counter % 3 == 0:
            self.update()

    def _on_finished(self):
        if self._load_finished_emitted:
            return
        if self._bucket_count:
            self._peaks.append(self._bucket_max)
            self._bucket_max = 0
            self._bucket_count = 0

        if not self._peaks:
            self.update()
            self._emit_load_finished(False)
            return

        max_peak = max(self._peaks) or 1.0
        self._peaks = [p / max_peak for p in self._peaks]
        self.update()
        self._emit_load_finished(True)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()

        bg_color = QtGui.QColor(THEME["surface_alt"])
        painter.fillRect(rect, bg_color)

        if not self._peaks:
            return

        width = rect.width()
        height = rect.height() / 2.2
        count = len(self._peaks)
        if count == 0:
            return

        window = max(1, int(count / self._zoom))
        window = min(window, count)
        progress_ratio = min(1.0, self._progress_ms / max(1, self._duration_ms))
        if self._zoom > 1.0:
            if self._view_center_ratio is None:
                self._view_center_ratio = progress_ratio
            center_ratio = self._view_center_ratio
        else:
            center_ratio = progress_ratio
        center = int(center_ratio * count)
        start = max(0, min(count - window, center - window // 2))
        end = start + window
        peaks = self._peaks[start:end]

        visible_start_ms = int(self._duration_ms * (start / max(1, count)))
        visible_end_ms = int(self._duration_ms * (end / max(1, count)))
        visible_ms = max(1, visible_end_ms - visible_start_ms)

        def _time_to_x(ms):
            ratio = (ms - visible_start_ms) / visible_ms
            return int(max(0, min(width, ratio * width)))

        clip_start_x = _time_to_x(self._clip_start_ms)
        clip_end_x = _time_to_x(self._clip_end_ms)
        clip_end_x = max(clip_start_x, min(width, clip_end_x))

        if clip_end_x > clip_start_x:
            clip_color = QtGui.QColor(THEME["primary"])
            clip_color.setAlpha(30)
            painter.fillRect(QtCore.QRect(clip_start_x, rect.top(), clip_end_x - clip_start_x, rect.height()), clip_color)

        mid_y = rect.center().y()
        pen = QtGui.QPen(QtGui.QColor(THEME["primary"]), 1.4)
        painter.setPen(pen)

        for i, peak in enumerate(peaks):
            x = int(i * width / max(1, len(peaks) - 1))
            amp = peak * height
            painter.drawLine(x, int(mid_y - amp), x, int(mid_y + amp))

        if self._duration_ms > 0 and width > 0:
            tick_ms = 15000
            min_px = 36
            ms_per_px = visible_ms / max(1, width)
            if ms_per_px * min_px <= tick_ms:
                first_tick = ((visible_start_ms + tick_ms - 1) // tick_ms) * tick_ms
                grid_pen = QtGui.QPen(QtGui.QColor(THEME["border"]), 1)
                label_color = QtGui.QColor(THEME["muted"])
                font = painter.font()
                font.setPointSize(max(8, font.pointSize() - 2))
                painter.setFont(font)
                painter.setPen(grid_pen)
                tick = first_tick
                while tick <= visible_end_ms:
                    x = int((tick - visible_start_ms) / visible_ms * width)
                    painter.drawLine(x, rect.top(), x, rect.bottom())
                    label = f"{int(tick / 1000)}s"
                    painter.setPen(label_color)
                    painter.drawText(x + 4, rect.top() + 12, label)
                    painter.setPen(grid_pen)
                    tick += tick_ms

        marker_pen = QtGui.QPen(QtGui.QColor(THEME["accent"]), 2)
        painter.setPen(marker_pen)
        painter.drawLine(clip_start_x, rect.top(), clip_start_x, rect.bottom())
        if clip_end_x > clip_start_x:
            painter.drawLine(clip_end_x, rect.top(), clip_end_x, rect.bottom())

        progress_x = _time_to_x(self._progress_ms)
        progress_pen = QtGui.QPen(QtGui.QColor(THEME["text"]), 2)
        painter.setPen(progress_pen)
        painter.drawLine(progress_x, rect.top(), progress_x, rect.bottom())

        hover_ms = self._hover_time_ms()
        if hover_ms is not None:
            hover_x = int(max(0, min(width, self._hover_x)))
            hover_pen = QtGui.QPen(QtGui.QColor(THEME["muted"]), 1)
            painter.setPen(hover_pen)
            painter.drawLine(hover_x, rect.top(), hover_x, rect.bottom())
            label = self._format_time(hover_ms)
            label_rect = QtCore.QRect(hover_x + 6, rect.top() + 2, 60, 16)
            painter.fillRect(label_rect, QtGui.QColor(THEME["surface"]))
            painter.setPen(QtGui.QColor(THEME["text"]))
            painter.drawText(label_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, label)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self._zoom > 1.0:
                self._dragging = True
                self._drag_start_x = event.position().x()
                self._drag_start_ratio = self._view_center_ratio or 0.0
                event.accept()
                return
            self._emit_seek(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover_x = event.position().x()
        if self._dragging and self._zoom > 1.0:
            width = max(1, self.rect().width())
            delta_x = event.position().x() - self._drag_start_x
            count = max(1, len(self._peaks))
            window = max(1, int(count / self._zoom))
            window_ratio = window / max(1, count)
            delta_ratio = -delta_x / width * window_ratio
            self._set_view_center_ratio(self._drag_start_ratio + delta_ratio, window_ratio)
            self.update()
            event.accept()
            return
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        if self._zoom <= 1.0:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().x()
        if delta == 0:
            delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        count = max(1, len(self._peaks))
        window = max(1, int(count / self._zoom))
        window_ratio = window / max(1, count)
        speed = 0.1
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            speed = 0.3
        step_ratio = (delta / 120.0) * (window_ratio * speed)
        self._set_view_center_ratio((self._view_center_ratio or 0.0) - step_ratio, window_ratio)
        self.update()
        event.accept()

    def _emit_seek(self, x_pos):
        width = max(1, self.rect().width())
        count = max(1, len(self._peaks))
        window = max(1, int(count / self._zoom))
        window_ratio = window / max(1, count)
        if self._zoom > 1.0:
            center_ratio = self._view_center_ratio or 0.0
        else:
            center_ratio = self._progress_ms / max(1, self._duration_ms)
        start_ratio = max(0.0, center_ratio - (window_ratio / 2))
        click_ratio = max(0.0, min(1.0, x_pos / width))
        target_ratio = start_ratio + click_ratio * window_ratio
        target_ms = int(target_ratio * max(1, self._duration_ms))
        self.seekRequested.emit(target_ms)

    def _hover_time_ms(self):
        if self._hover_x is None:
            return None
        width = max(1, self.rect().width())
        count = max(1, len(self._peaks))
        window = max(1, int(count / self._zoom))
        window_ratio = window / max(1, count)
        if self._zoom > 1.0:
            center_ratio = self._view_center_ratio or 0.0
        else:
            center_ratio = self._progress_ms / max(1, self._duration_ms)
        start_ratio = max(0.0, center_ratio - (window_ratio / 2))
        hover_ratio = max(0.0, min(1.0, self._hover_x / width))
        target_ratio = start_ratio + hover_ratio * window_ratio
        return int(target_ratio * max(1, self._duration_ms))

    def _format_time(self, ms):
        seconds = int(ms / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"