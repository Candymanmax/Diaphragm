"""Output selection, playback, seeking, and folder actions."""

from pathlib import Path

import soundfile as sf
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from harness_ui.icons import lucide_icon
from harness_ui.theme import TEXT

from harness_ui.controllers.output_review.state import (
    format_media_time,
    is_playing_state,
)


class OutputPlaybackCommands:
    """Control the selected published output and media player."""

    def select_output(self, current, previous):
        del previous
        if current is None:
            return
        self.view.output_stack.setCurrentWidget(self.view.output_content)
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        try:
            info = sf.info(path)
            duration = info.frames / info.samplerate if info.samplerate else 0
            self.view.output_metadata.setText(
                f"{duration:.1f}s · {info.samplerate:,} Hz · "
                f"{info.channels} channel{'s' if info.channels != 1 else ''} · "
                f"{path.stat().st_size / (1024 * 1024):.1f} MiB"
            )
            self.view.waveform.set_file(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.view.output_metadata.setText(f"Could not inspect output: {error}")
            self.view.waveform.clear()
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.view.play_button.setEnabled(True)
        self.set_playback_button_state(self.media_player.playbackState())
        self._publish_snapshot()

    def toggle_playback(self):
        if self._worker_running():
            return
        if is_playing_state(self.media_player.playbackState()):
            self.media_player.pause()
        else:
            self.media_player.play()

    def playback_state_changed(self, state):
        self.set_playback_button_state(state)
        self._publish_snapshot()

    def set_playback_button_state(self, state):
        playing = is_playing_state(state)
        icon_name = "pause" if playing else "play"
        label = "Pause audio" if playing else "Play audio"
        self.view.play_button.setIcon(lucide_icon(icon_name, color=TEXT, size=17))
        self.view.play_button.setAccessibleName(label)

    def position_changed(self, position):
        duration = self.media_player.duration()
        fraction = position / duration if duration > 0 else 0
        if not self.view.position_slider.isSliderDown():
            self.view.position_slider.setValue(int(fraction * 1000))
        self.view.waveform.set_position(fraction)
        self.view.position_text.setText(
            f"{format_media_time(position)} / {format_media_time(duration)}"
        )
        self._publish_snapshot()

    def duration_changed(self, duration):
        self.view.position_text.setText(
            f"{format_media_time(self.media_player.position())} / "
            f"{format_media_time(duration)}"
        )
        self._publish_snapshot()

    def seek_slider(self, value):
        self.seek_fraction(value / 1000)

    def seek_fraction(self, fraction):
        duration = self.media_player.duration()
        if duration > 0:
            self.media_player.setPosition(int(duration * float(fraction)))

    def playback_error(self, error, error_string):
        del error
        if error_string:
            self._append_log(f"Audio playback error: {error_string}", "error")

    def open_selected_output(self):
        if self._worker_running():
            return
        item = self.view.output_list.currentItem()
        if item is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(item.data(Qt.ItemDataRole.UserRole)))

    def open_output_folder(self):
        self.outputs_root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.outputs_root)))

    def release_media_source(self):
        """Release Windows handles before replacing retained/output WAVs."""

        release = getattr(self.media_player, "release", None)
        if callable(release):
            release()
        else:
            self.media_player.stop()
            self.media_player.setSource(QUrl())
        self.set_playback_button_state(self.media_player.playbackState())
        self.view.play_button.setEnabled(False)
        self.view.position_slider.setValue(0)
        self.view.position_text.setText("0:00 / 0:00")
        self.view.waveform.clear()
        self._process_events()
        self._publish_snapshot()
