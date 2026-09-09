"""First-run PyTorch setup shown before the main window is imported."""

from __future__ import annotations

import re

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from harness_ui.dialogs.app_dialog import AppDialog
from harness_ui.theme import TEAL, set_button_role
from modules.runtime_manager import (
    RUNTIME_ARCHITECTURE_BITS,
    RUNTIME_PYTHON_VERSION,
    RuntimeManager,
    RuntimeSetupResult,
)


_PERCENTAGE = re.compile(r"(?<!\d)(\d{1,3})%")


class RuntimeSetupDialog(AppDialog):
    """Show and control the one-time per-user PyTorch installation."""

    def __init__(self, manager, bootstrap, *, parent=None):
        self.manager = manager
        self.bootstrap = bootstrap
        self._stage = None
        self._output_buffer = ""
        self._last_output = []
        self._cancelled_by_user = False
        self.runtime_ready = False

        extra = QWidget()
        extra.setObjectName("runtimeSetupContent")
        extra_layout = QVBoxLayout(extra)
        extra_layout.setContentsMargins(0, 4, 0, 0)
        extra_layout.setSpacing(8)

        self.status_label = QLabel()
        self.status_label.setObjectName("runtimeSetupStatus")
        self.status_label.setWordWrap(True)
        extra_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("runtimeSetupProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        extra_layout.addWidget(self.progress_bar)

        self.detail_label = QLabel(
            "This happens once and keeps the selected runtime in your local "
            "Diaphragm data folder."
        )
        self.detail_label.setObjectName("runtimeSetupDetail")
        self.detail_label.setWordWrap(True)
        extra_layout.addWidget(self.detail_label)

        super().__init__(
            "Preparing Diaphragm",
            (
                f"Downloading the {manager.spec.display_name} speech runtime. "
                "The main window will open when it is ready."
            ),
            parent=parent,
            icon_name="loader-circle",
            icon_color=TEAL,
            primary_text="Cancel",
            primary_role="neutral",
            secondary_text="Retry",
            secondary_role="primary",
            default_action="primary",
            button_order=("secondary", "primary"),
            extra_content=extra,
            primary_accepts=False,
            secondary_rejects=False,
            delete_on_close=False,
            minimum_width=560,
        )
        self.primary_button.clicked.connect(self._handle_primary)
        self.secondary_button.clicked.connect(self._retry)
        self.secondary_button.hide()
        self.secondary_button.setEnabled(False)
        self._set_status(
            f"Preparing the {manager.spec.display_name} runtime…"
        )

    @classmethod
    def ensure(cls, data_root, *, parent=None):
        """Ensure the requested runtime exists before constructing the GUI."""

        manager = RuntimeManager(data_root)
        ready_python = manager.ready_python()
        if ready_python is not None:
            manager.activate(ready_python)
            return RuntimeSetupResult(ready=True)

        dialog = cls(manager, manager.bootstrap_command(), parent=parent)
        dialog._begin_setup()
        dialog.exec_dialog()
        result = RuntimeSetupResult(
            ready=bool(dialog.runtime_ready),
            cancelled=bool(dialog._cancelled_by_user),
        )
        dialog.deleteLater()
        return result

    def _set_status(self, text, *, error=False):
        self.status_label.setText(str(text))
        self.status_label.setProperty("error", bool(error))
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        self.status_label.update()

    def _begin_setup(self):
        if self.bootstrap is None:
            python_version = ".".join(
                str(part) for part in RUNTIME_PYTHON_VERSION
            )
            self._fail(
                f"Install {RUNTIME_ARCHITECTURE_BITS}-bit Python "
                f"{python_version}, then choose Retry.",
                detail=(
                    "The speech runtime must match this Diaphragm build's "
                    "Python version so native PyTorch files can load."
                ),
            )
            return

        self.manager.root.parent.mkdir(parents=True, exist_ok=True)
        self._stage = "venv"
        self._output_buffer = ""
        self._last_output = []
        self.runtime_ready = False
        self.secondary_button.hide()
        self.secondary_button.setEnabled(False)
        self.primary_button.setText("Cancel")
        self.primary_button.setAccessibleName("Cancel runtime setup")
        set_button_role(self.primary_button, "neutral")
        self.message_label.setText(
            (
                f"Downloading the {self.manager.spec.display_name} speech "
                "runtime. The main window will open when it is ready."
            )
        )
        self.detail_label.setText(
            "This happens once and keeps the selected runtime in your local "
            "Diaphragm data folder."
        )
        self.detail_label.setProperty("error", False)
        style = self.detail_label.style()
        if style is not None:
            style.unpolish(self.detail_label)
            style.polish(self.detail_label)
        self.detail_label.update()
        self._set_status(
            f"Preparing the {self.manager.spec.display_name} runtime…"
        )
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(3)
        program, arguments = self.manager.venv_command(
            self.bootstrap,
            clear=self.manager.root.exists(),
        )
        self._start_process(program, arguments)

    def _start_process(self, program, arguments):
        if not hasattr(self, "process"):
            self.process = QProcess(self)
            self.process.setProcessChannelMode(
                QProcess.ProcessChannelMode.MergedChannels
            )
            self.process.readyReadStandardOutput.connect(
                self._read_process_output
            )
            self.process.finished.connect(self._process_finished)
            self.process.errorOccurred.connect(self._process_error)
        self.process.start(
            str(program),
            [str(argument) for argument in arguments],
        )

    def _read_process_output(self):
        text = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )
        self._output_buffer += text.replace("\r", "\n")
        lines = self._output_buffer.split("\n")
        self._output_buffer = lines.pop()
        for line in lines:
            self._handle_output_line(line.strip())

    def _flush_process_output(self):
        self._read_process_output()
        if self._output_buffer.strip():
            self._handle_output_line(self._output_buffer.strip())
        self._output_buffer = ""

    def _handle_output_line(self, line):
        if not line:
            return

        self._last_output.append(line)
        self._last_output = self._last_output[-12:]

        if self._stage != "install":
            return

        match = _PERCENTAGE.search(line)
        if match:
            percentage = max(0, min(100, int(match.group(1))))
            self.progress_bar.setValue(8 + round(percentage * 0.87))

        lowered = line.lower()
        if "collecting torch" in lowered or "downloading torch" in lowered:
            self._set_status("Downloading PyTorch…")
        elif (
            "collecting torchaudio" in lowered
            or "downloading torchaudio" in lowered
        ):
            self._set_status("Downloading TorchAudio…")
        elif "installing collected packages" in lowered:
            self._set_status("Installing the speech runtime…")

    def _process_finished(self, exit_code, _exit_status):
        self._flush_process_output()
        stage = self._stage
        if stage is None or stage in {"failed", "ready"}:
            return

        if int(exit_code) != 0:
            self._fail(
                "The runtime setup did not complete.",
                detail=self._failure_detail(),
            )
            return

        if stage == "venv":
            self._stage = "install"
            self.progress_bar.setValue(8)
            self._set_status(
                f"Downloading PyTorch {self.manager.spec.display_name}…"
            )
            program, arguments = self.manager.install_command()
            self._start_process(program, arguments)
            return

        if stage == "install":
            self._stage = "verify"
            self.progress_bar.setValue(96)
            self._set_status("Verifying the downloaded runtime…")
            program, arguments = self.manager.verify_command()
            self._start_process(program, arguments)
            return

        if stage == "verify":
            try:
                self.manager.activate()
            except RuntimeError as error:
                self._fail(
                    "The runtime was installed but could not be loaded.",
                    detail=str(error),
                )
                return

            self._stage = "ready"
            self.runtime_ready = True
            self.progress_bar.setValue(100)
            self._set_status("Runtime ready. Starting Diaphragm…")
            self.detail_label.setText(
                "The runtime is ready and will be reused on future launches."
            )
            self.message_label.setText(
                "The selected speech runtime is ready."
            )
            QTimer.singleShot(350, self.accept)

    def _process_error(self, error):
        if error != QProcess.ProcessError.FailedToStart:
            return
        if self._stage in {None, "failed", "ready"}:
            return
        self._fail(
            "The runtime setup process could not be started.",
            detail=(
                "Check that Python is installed and that the runtime folder "
                "is writable."
            ),
        )

    def _failure_detail(self):
        if not self._last_output:
            return "Check your internet connection, then choose Retry."
        return "\n".join(self._last_output[-5:])[-900:]

    def _fail(self, message, *, detail):
        self._stage = "failed"
        self.runtime_ready = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_status(message, error=True)
        self.detail_label.setText(str(detail))
        self.detail_label.setProperty("error", True)
        style = self.detail_label.style()
        if style is not None:
            style.unpolish(self.detail_label)
            style.polish(self.detail_label)
        self.detail_label.update()
        self.message_label.setText(
            "Diaphragm needs its speech runtime before it can open."
        )
        self.primary_button.setText("Close")
        self.primary_button.setAccessibleName("Close runtime setup")
        set_button_role(self.primary_button, "neutral")
        self.secondary_button.show()
        self.secondary_button.setEnabled(True)

    def _retry(self):
        if self._stage != "failed":
            return
        self.bootstrap = self.manager.bootstrap_command()
        self._begin_setup()

    def _handle_primary(self):
        if self._stage not in {"failed", "ready", None}:
            self._cancelled_by_user = True
            self._stop_process()
        self.reject()

    def _stop_process(self):
        process = getattr(self, "process", None)
        self._stage = None
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        process.kill()
        process.waitForFinished(2000)

    def reject(self):
        if self._stage not in {None, "failed", "ready"}:
            self._cancelled_by_user = True
            self._stop_process()
        super().reject()

    def closeEvent(self, event):
        if self._stage not in {None, "failed", "ready"}:
            self._cancelled_by_user = True
            self._stop_process()
        super().closeEvent(event)


__all__ = ("RuntimeSetupDialog",)
