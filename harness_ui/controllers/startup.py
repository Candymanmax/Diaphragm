"""Initial configuration and script-library loading."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from harness_ui.dialogs import AppDialog


@dataclass(frozen=True)
class StartupSnapshot:
    """Immutable result of loading the initial workspace inputs."""

    configuration_loaded: bool
    scripts_loaded: int
    configuration_error: str | None


class StartupController(QObject):
    """Load private configuration and publish startup hydration intents."""

    snapshotChanged = Signal(object)
    configurationLoaded = Signal(object)

    def __init__(
        self,
        *,
        parent,
        project_root,
        service,
        script_controller,
        show_configuration_error=None,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.project_root = project_root
        self.service = service
        self.script_controller = script_controller
        self._show_configuration_error = (
            show_configuration_error or AppDialog.critical
        )
        self._snapshot = StartupSnapshot(False, 0, None)

    def snapshot(self):
        return self._snapshot

    def initialize(self):
        error_message = None

        try:
            config = self.service.load_config()
        except Exception as error:
            error_message = str(error)
            self._show_configuration_error(
                self.parent_window,
                "Configuration error",
                error_message,
            )
            config = None

        if config is not None:
            self.configurationLoaded.emit(config)

        scripts = sorted((self.project_root / "input").glob("*.txt"))
        self.script_controller.add_paths(scripts)
        self._snapshot = StartupSnapshot(
            configuration_loaded=config is not None,
            scripts_loaded=len(scripts),
            configuration_error=error_message,
        )
        self.snapshotChanged.emit(self._snapshot)
        return self._snapshot


__all__ = ("StartupController", "StartupSnapshot")
