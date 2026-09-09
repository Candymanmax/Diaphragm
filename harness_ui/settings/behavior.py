"""Capability filtering, presets, and splitting-mode presentation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from harness_ui.settings.controls import GENERATION_PRESETS
from modules.adapters.registry import (
    GENERATION_CONTROL_NAMES,
    LANGUAGE_NAMES,
    get_model_capabilities,
)


@dataclass(frozen=True)
class SettingsCapabilitySnapshot:
    """Immutable model-dependent inspector state."""

    model_id: str
    languages: tuple[str, ...]
    supported_controls: tuple[str, ...]
    presets_supported: bool
    automatic_splitting: bool


class SettingsBehaviorController(QObject):
    """Apply model and splitting capabilities to already-built controls."""

    snapshotChanged = Signal(object)

    def __init__(self, *, panel, model_controller):
        super().__init__(panel)
        self.panel = panel
        self.model_controller = model_controller

    @staticmethod
    def set_form_row_visible(form, field, visible):
        field.setVisible(visible)
        label = form.labelForField(field)

        if label is not None:
            label.setVisible(visible)

    def snapshot(self):
        model_id = self.model_controller.model_id()
        capabilities = get_model_capabilities(model_id)
        presets_supported = all(
            capabilities.supports_control(name)
            for preset in GENERATION_PRESETS.values()
            for name in preset
        )
        return SettingsCapabilitySnapshot(
            model_id=model_id,
            languages=tuple(capabilities.languages),
            supported_controls=tuple(
                name
                for name in GENERATION_CONTROL_NAMES
                if capabilities.supports_control(name)
            ),
            presets_supported=presets_supported,
            automatic_splitting=(
                self.panel.splitting_mode.currentText() == "automatic"
            ),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def model_changed(self, *args):
        del args
        panel = self.panel
        model_id = self.model_controller.model_id()
        capabilities = get_model_capabilities(model_id)
        current_language = panel.language.currentData()
        panel.language.blockSignals(True)
        panel.language.clear()

        for code in capabilities.languages:
            panel.language.addItem(
                f"{LANGUAGE_NAMES.get(code, code)} ({code})",
                code,
            )

        index = panel.language.findData(current_language)
        panel.language.setCurrentIndex(index if index >= 0 else 0)
        panel.language.blockSignals(False)

        self.set_form_row_visible(
            panel.primary_form,
            panel.language,
            len(capabilities.languages) > 1,
        )

        for name in GENERATION_CONTROL_NAMES:
            widget = panel.generation_widgets[name]
            supported = capabilities.supports_control(name)
            widget.setEnabled(supported and panel.job_editable)
            self.set_form_row_visible(
                panel.generation_form,
                widget,
                supported,
            )

        presets_supported = all(
            capabilities.supports_control(name)
            for preset in GENERATION_PRESETS.values()
            for name in preset
        )
        panel.preset.setEnabled(presets_supported and panel.job_editable)
        self.set_form_row_visible(
            panel.primary_form,
            panel.preset,
            presets_supported,
        )

        if not presets_supported:
            panel.preset.setCurrentText("Custom")

        panel.generation_form.invalidate()
        panel.generation_page.updateGeometry()
        panel.schedule_toolbox_fit()

        tags = (
            " · tags: " + " ".join(capabilities.event_tags)
            if capabilities.event_tags
            else ""
        )
        panel.capability_summary.setText(
            f"{capabilities.parameter_count_millions}M parameters · "
            f"recommended {capabilities.recommended_device.upper()}"
            f"{tags}\n{capabilities.description}"
        )
        panel.notify_change()
        self._publish_snapshot()

    def preset_changed(self, name):
        panel = self.panel

        if panel.loading or name not in GENERATION_PRESETS:
            return

        panel.loading = True

        try:
            for key, value in GENERATION_PRESETS[name].items():
                panel.generation_widgets[key].setValue(value)
        finally:
            panel.loading = False

        panel.notify_change()
        self._publish_snapshot()

    def apply_splitting_mode(self, *args):
        del args
        panel = self.panel
        automatic = panel.splitting_mode.currentText() == "automatic"
        self.set_form_row_visible(
            panel.splitting_form,
            panel.generation_max_words,
            not automatic,
        )

        for widget in (
            panel.automatic_min_words,
            panel.automatic_max_words,
            panel.vram_safety_margin_mb,
            panel.adaptive_growth_interval,
        ):
            self.set_form_row_visible(
                panel.splitting_form,
                widget,
                automatic,
            )
            widget.setEnabled(automatic and panel.job_editable)

        panel.generation_max_words.setEnabled(
            not automatic and panel.job_editable
        )
        panel.splitting_form.invalidate()
        panel.splitting_page.updateGeometry()
        panel.schedule_toolbox_fit()
        self._publish_snapshot()


__all__ = ("SettingsBehaviorController", "SettingsCapabilitySnapshot")
