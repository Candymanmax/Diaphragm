from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import soundfile as sf
from PySide6.QtCore import QFileInfo, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from harness_ui.theme import BASE, OVERLAY_0, SURFACE_0, active_accent_color


class WaveformWidget(QWidget):
    seekRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setAccessibleName("Audio waveform")
        self._peaks = np.array([], dtype=np.float32)
        self._position = 0.0
        self._file = None

    @property
    def file(self):
        return self._file

    def clear(self):
        self._file = None
        self._peaks = np.array([], dtype=np.float32)
        self._position = 0.0
        self.update()

    def set_file(self, file_path):
        path = Path(file_path)

        if not path.is_file():
            self.clear()
            return

        info = sf.info(path)

        if info.frames <= 0:
            self.clear()
            return

        bins = min(1200, info.frames)
        frames_per_bin = max(1, math.ceil(info.frames / bins))
        peak_values = []

        # Stream display bins so long outputs never load fully into the GUI.
        with sf.SoundFile(path) as audio:
            for block in audio.blocks(
                blocksize=frames_per_bin,
                dtype="float32",
                always_2d=True,
            ):
                peak_values.append(float(np.max(np.abs(block))))

        peaks = np.asarray(peak_values, dtype=np.float32)
        maximum = float(np.max(peaks)) if len(peaks) else 0.0

        if maximum > 0:
            peaks = peaks / maximum

        self._file = path
        self._peaks = peaks.astype(np.float32, copy=False)
        self._position = 0.0
        self.setToolTip(QFileInfo(str(path)).fileName())
        self.update()

    def set_position(self, fraction):
        self._position = max(0.0, min(1.0, float(fraction)))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            fraction = event.position().x() / self.width()
            self.seekRequested.emit(max(0.0, min(1.0, fraction)))

        super().mousePressEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BASE))
        painter.setPen(QPen(QColor(SURFACE_0), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 7, 7)

        if not len(self._peaks):
            painter.setPen(QColor(OVERLAY_0))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Select an audio output to preview its waveform",
            )
            return

        width = max(1, self.width() - 16)
        height = max(1, self.height() - 20)
        center = self.height() / 2
        step = width / max(1, len(self._peaks) - 1)
        path = QPainterPath()

        for index, peak in enumerate(self._peaks):
            x = 8 + index * step
            y = center - float(peak) * height * 0.43

            if index == 0:
                path.moveTo(QPointF(x, y))
            else:
                path.lineTo(QPointF(x, y))

        for index in range(len(self._peaks) - 1, -1, -1):
            peak = self._peaks[index]
            x = 8 + index * step
            y = center + float(peak) * height * 0.43
            path.lineTo(QPointF(x, y))

        path.closeSubpath()
        accent = active_accent_color()
        waveform_color = QColor(accent)
        waveform_color.setAlpha(165)
        painter.fillPath(path, waveform_color)
        progress_x = int(8 + self._position * width)
        painter.setPen(QPen(QColor(accent), 2))
        painter.drawLine(progress_x, 5, progress_x, self.height() - 5)
