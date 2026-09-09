"""Model status and one-click installation for the settings inspector."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QProcess, Qt, Signal
from harness_ui.dialogs import AppDialog
from harness_ui.settings.controls import _inspector_model_label
from harness_ui.theme import set_button_role
from modules.adapters.registry import (
    get_model_capabilities,
)
from modules.model_inventory import inspect_model_inventory
from modules.model_operations import model_download_arguments


class SettingsModelController(QObject):
    """Own the selected model's local status and download subprocess."""

    statusChanged = Signal(str, bool)

    def __init__(self, *, panel, service, model_combo, install_button):
        super().__init__(panel)
        self.panel = panel
        self.service = service
        self.model_combo = model_combo
        self.install_button = install_button
        self.process = QProcess(panel)
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.installing_model_id = None
        self.installing_operation = None
        self.external_operation_busy = False
        self.model_combo.aboutToShowPopup.connect(self.refresh)
        # Keep the action state owned by this controller.  The button must
        # update even when a caller changes the combo without going through
        # the rest of the settings behavior pipeline.
        self.model_combo.currentIndexChanged.connect(self.refresh)
        self.install_button.clicked.connect(self.install)
        self.process.finished.connect(self.install_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.refresh()

    def model_id(self):
        return str(self.model_combo.currentData() or "original")

    def busy(self):
        return self.external_operation_busy or (
            self.process.state() != QProcess.ProcessState.NotRunning
        )

    def set_external_busy(self, busy):
        """Reflect a model operation owned by the Preferences page."""

        self.external_operation_busy = bool(busy)
        self.refresh()

    def refresh(self):
        hub_cache = self.service.paths.hub_cache_root

        for index in range(self.model_combo.count()):
            model_id = str(self.model_combo.itemData(index))
            inventory = inspect_model_inventory(model_id, hub_cache)
            installed = inventory.installed
            self.model_combo.setItemText(
                index,
                _inspector_model_label(model_id),
            )
            self.model_combo.setItemData(
                index,
                (
                    "Model files are available in the private model cache."
                    if installed
                    else "Downloads automatically from Hugging Face when "
                    "first used. Internet access is required."
                ),
                Qt.ItemDataRole.ToolTipRole,
            )

        model_id = self.model_id()
        inventory = inspect_model_inventory(model_id, hub_cache)
        installed = inventory.installed
        process_busy = self.busy()
        downloading = self.installing_model_id == model_id
        partial = inventory.state == "partial"
        action = (
            "Repairing…"
            if downloading and self.installing_operation == "repair"
            else "Installing…"
            if downloading
            else "Installed"
            if installed
            else "Repair"
            if partial
            else "Install"
        )
        state = (
            "repairing"
            if downloading and self.installing_operation == "repair"
            else "installing"
            if downloading
            else "installed"
            if installed
            else "repair"
            if partial
            else "install"
        )
        set_button_role(self.install_button, "neutral")
        self.install_button.setAccessibleName(
            f"{action} selected model"
        )
        self.install_button.setText(action)
        self.install_button.setEnabled(
            not installed and not process_busy and not downloading
        )
        self.install_button.setProperty("modelState", state)
        self.install_button.setToolTip(
            "Model files are available locally."
            if installed
            else "The selected model is currently downloading."
            if downloading
            else "Some model files are missing; repair the local snapshot."
            if partial
            else "Download this model into the private model cache."
        )
        style = self.install_button.style()

        if style is not None:
            style.unpolish(self.install_button)
            style.polish(self.install_button)

        self.statusChanged.emit(model_id, installed)

    def install(self):
        if self.busy():
            return

        model_id = self.model_id()
        capability = get_model_capabilities(model_id)
        inventory = inspect_model_inventory(
            model_id,
            self.service.paths.hub_cache_root,
        )
        operation = "repair" if inventory.state == "partial" else "install"
        action = "Repair" if operation == "repair" else "Install"

        if not AppDialog.confirm(
            self.panel,
            f"{action} model",
            f"{action} \"{capability.display_name}\" in the model cache?"
            "\n\nModel downloads can be several gigabytes.",
            confirm_text=f"{action} model",
            cancel_text="Cancel",
            default_action="secondary",
        ):
            return

        self.installing_model_id = model_id
        self.installing_operation = operation
        self.process.setWorkingDirectory(str(self.service.install_root))
        self.process.start(
            sys.executable,
            model_download_arguments(
                model_id,
                self.service.paths.hub_cache_root,
                operation,
            ),
        )
        self.refresh()

    def install_finished(self, exit_code, exit_status):
        del exit_status
        model_id = self.installing_model_id
        if model_id is None:
            return

        output = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        ).strip()
        self.installing_model_id = None
        operation = self.installing_operation or "install"
        self.installing_operation = None
        self.refresh()
        hub_cache = self.service.paths.hub_cache_root
        installed = bool(model_id) and inspect_model_inventory(
            model_id,
            hub_cache,
        ).installed

        if exit_code == 0 and installed:
            AppDialog.information(
                self.panel,
                f"Model {'repaired' if operation == 'repair' else 'installed'}",
                f"{get_model_capabilities(model_id).display_name} is ready to use.",
            )
            return

        detail = output[-1200:] if output else "The download process stopped."
        AppDialog.critical(
            self.panel,
            "Model installation failed",
            detail,
        )

    def _process_error(self, error):
        if error != QProcess.ProcessError.FailedToStart:
            return

        # Some Qt versions report FailedToStart without emitting finished.
        # Clear the transient state immediately so the button cannot remain
        # stuck on Installing… after a launch failure.
        if self.installing_model_id is None:
            return

        self.install_finished(-1, QProcess.ExitStatus.CrashExit)


__all__ = ("SettingsModelController",)
