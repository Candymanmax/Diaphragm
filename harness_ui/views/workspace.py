"""Build and expose the typed workspace section graph."""

from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Qt, Signal
from PySide6.QtWidgets import QSplitter, QStatusBar

from harness_ui.sections import (
    JobHeaderSection,
    JobsSidebarSection,
    LogsSection,
    OutputTabSection,
    QueueTabSection,
    ScriptsTabSection,
    SettingsInspectorSection,
)


class LazyMediaPlayer(QObject):
    """Defer Qt Multimedia backend startup until audio is actually played."""

    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playbackStateChanged = Signal(object)
    errorOccurred = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._audio_output = None
        self._source = QUrl()

    @property
    def initialized(self):
        return self._player is not None

    def _ensure_player(self):
        if self._player is not None:
            return self._player

        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        audio_output = QAudioOutput(self)
        audio_output.setVolume(0.8)
        player = QMediaPlayer(self)
        player.setAudioOutput(audio_output)
        player.positionChanged.connect(self._forward_position)
        player.durationChanged.connect(self._forward_duration)
        player.playbackStateChanged.connect(self._forward_playback_state)
        player.errorOccurred.connect(self._forward_error)
        self._audio_output = audio_output
        self._player = player

        if not self._source.isEmpty():
            player.setSource(self._source)
        return player

    def _forward_position(self, value):
        self.positionChanged.emit(int(value))

    def _forward_duration(self, value):
        self.durationChanged.emit(int(value))

    def _forward_playback_state(self, value):
        self.playbackStateChanged.emit(value)

    def _forward_error(self, error, message):
        self.errorOccurred.emit(error, str(message))

    def setSource(self, source):
        if isinstance(source, QUrl):
            self._source = QUrl(source)
        else:
            self._source = QUrl(str(source))

        if self._player is not None:
            self._player.setSource(self._source)

    def source(self):
        return QUrl(self._source)

    def playbackState(self):
        if self._player is None:
            return "StoppedState"
        return self._player.playbackState()

    def position(self):
        return self._player.position() if self._player is not None else 0

    def duration(self):
        return self._player.duration() if self._player is not None else 0

    def play(self):
        self._ensure_player().play()

    def pause(self):
        if self._player is not None:
            self._player.pause()

    def stop(self):
        if self._player is not None:
            self._player.stop()

    def setPosition(self, position):
        if self._player is not None:
            self._player.setPosition(int(position))

    def release(self):
        """Release backend objects and Windows media handles when idle."""

        player = self._player
        audio_output = self._audio_output
        self._player = None
        self._audio_output = None
        self._source = QUrl()

        if player is not None:
            player.stop()
            player.setSource(QUrl())
            player.deleteLater()
        if audio_output is not None:
            audio_output.deleteLater()


class WorkspaceViewBuilder:
    """Construct and retain every workspace section without host aliases."""

    def __init__(self, window, state, settings_store, service):
        self.window = window
        self.state = state
        self.settings_store = settings_store
        self.service = service

    def build(self):
        window = self.window
        window.setStatusBar(QStatusBar())
        self.central_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.central_splitter.setChildrenCollapsible(False)
        window.setCentralWidget(self.central_splitter)

        self.jobs = JobsSidebarSection(self.state, window)
        self.scripts = ScriptsTabSection(
            self.state,
            self.settings_store,
            window,
        )
        self.queue = QueueTabSection(self.state, window)
        self.output = OutputTabSection(self.state, window)
        self.header = JobHeaderSection(
            self.state,
            self.scripts.widget,
            self.queue.widget,
            self.output.widget,
            window,
        )
        self.workbench_layout = self.header.layout

        self.central_splitter.addWidget(self.jobs.sidebar_panel)
        self.central_splitter.addWidget(self.header.widget)
        self.central_splitter.setSizes((285, 1000))

        self.settings = SettingsInspectorSection(
            self.state,
            self.service,
            window,
        )
        window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.settings.settings_dock,
        )
        self.logs = LogsSection(self.state, window)
        window.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self.logs.logs_dock,
        )

        self.media_player = LazyMediaPlayer(window)
        self.audio_output = None
        self.state.set(
            "line_numbers_visible",
            self.scripts.script_line_numbers_action.isChecked(),
        )
        return self


__all__ = ("LazyMediaPlayer", "WorkspaceViewBuilder")
