from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from harness_ui.dialogs import AppDialog
from modules.adapters.registry import (
    GENERATION_CONTROL_LABELS,
    MODEL_ADAPTER_NAMES,
)
from modules.config import GENERATION_CONTROL_LIMITS
from harness_ui.theme import CONTROL_SPACING, SECTION_SPACING, standard_button

from harness_ui.settings.behavior import SettingsBehaviorController
from harness_ui.settings.configuration import SettingsConfigMapper
from harness_ui.settings.controls import (
    GENERATION_CONTROL_HELP,
    GENERATION_PRESETS,
    ModelComboBox,
    NoWheelComboBox,
    _LeftTooltipFilter,
    _decimal,
    _generation_help_tooltip,
    _inspector_model_label,
    _integer,
)
from harness_ui.settings.models import SettingsModelController

class SettingsPanel(QWidget):
    configSaved = Signal(object)
    configChanged = Signal(object)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self._loading = False
        self._job_editable = True
        self._left_tooltip_filter = _LeftTooltipFilter(self)
        self._build_ui()
        self.model_controller = SettingsModelController(
            panel=self,
            service=self.service,
            model_combo=self.model,
            install_button=self.model_install_button,
        )
        self.behavior_controller = SettingsBehaviorController(
            panel=self,
            model_controller=self.model_controller,
        )
        self.config_mapper = SettingsConfigMapper(
            panel=self,
            service=self.service,
            behavior=self.behavior_controller,
        )
        self._connect_changes()

    @property
    def loading(self):
        return self._loading

    @loading.setter
    def loading(self, value):
        self._loading = bool(value)

    def schedule_toolbox_fit(self):
        self._schedule_toolbox_fit()

    @property
    def job_editable(self):
        return self._job_editable

    def set_job_scope(self, manifest, *, editable, running=False):
        """Render the scope and editability of the selected job settings."""

        if running:
            message = (
                "This job is running. Its settings are locked; "
                "resume uses the saved job settings."
            )
        elif manifest is None:
            message = (
                "These settings apply to the next new job. "
                "Save them as defaults for future jobs."
            )
        elif manifest.get("temporary"):
            message = (
                "These settings apply to this job. "
                "Save them as defaults for future jobs."
            )
        elif str(manifest.get("status", "pending")) in {
            "running",
            "pausing",
            "cancelling",
        }:
            message = (
                "This job is running. Its settings are locked; "
                "resume uses the saved job settings."
            )
        else:
            message = (
                "This job uses its saved settings. "
                "Create a new job to use different settings."
            )

        self.scope_hint.setText(message)
        self.set_job_editable(editable)

    def set_job_editable(self, editable):
        """Enable only settings that may change for the current job."""

        self._job_editable = bool(editable)
        was_loading = self.loading
        self.loading = True

        try:
            if self._job_editable:
                for widget in self._job_setting_widgets():
                    widget.setEnabled(True)

            # Re-apply capability and splitting rules after changing the
            # scope. Suppressing notifications keeps a context switch from
            # being mistaken for a user edit.
            self.behavior_controller.model_changed()
            self.behavior_controller.apply_splitting_mode()
        finally:
            self.loading = was_loading

        for widget in self._job_setting_widgets():
            if not self._job_editable:
                widget.setEnabled(False)

        # Model installation is independent from editing a job snapshot and
        # remains available for the selected model.
        self.reset_button.setEnabled(self._job_editable)

    def _job_setting_widgets(self):
        return (
            self.model,
            self.voice,
            self.language,
            self.preset,
            self.import_voice,
            self.splitting_mode,
            *self.generation_widgets.values(),
            self.generation_max_words,
            self.automatic_min_words,
            self.automatic_max_words,
            self.vram_safety_margin_mb,
            self.adaptive_growth_interval,
            self.chunk_size,
            self.min_chunk_size,
            self.retry_attempts,
            self.sample_rate,
            self.output_format,
            self.merge_audio,
            self.normalize_audio,
            self.retain_job_artifacts,
            self.pause_min_ms,
            self.pause_max_ms,
            self.pause_mean_ms,
            self.pause_std_ms,
            self.loudness_target_lufs,
            self.cpu_fallback,
            self.device_preference,
        )

    def notify_change(self):
        self._notify_change()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("settingsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        outer.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("settingsContent")
        content.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 20)
        layout.setSpacing(SECTION_SPACING)
        self.scroll.setWidget(content)

        subtitle = QLabel(
            "These settings apply to the next new job. "
            "Save them as defaults for future jobs."
        )
        subtitle.setObjectName("settingsScopeHint")
        subtitle.setProperty("muted", True)
        subtitle.setWordWrap(True)
        self.scope_hint = subtitle
        layout.addWidget(subtitle)

        primary = QWidget()
        primary_form = QFormLayout(primary)
        self.primary_form = primary_form
        primary_form.setContentsMargins(0, 4, 0, 0)
        primary_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        primary_form.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapLongRows
        )

        self.model = ModelComboBox()

        for model_id in MODEL_ADAPTER_NAMES:
            self.model.addItem(_inspector_model_label(model_id), model_id)

        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(CONTROL_SPACING)
        self.model_install_button = standard_button(
            "Install",
            role="neutral",
            parent=model_row,
            object_name="modelInstallButton",
            accessible_name="Install selected model",
        )
        model_action_width = 88
        model_action_height = self.model.sizeHint().height()
        self.model_install_button.setFixedSize(
            model_action_width,
            model_action_height,
        )
        model_layout.addWidget(self.model, 1)
        model_layout.addWidget(self.model_install_button)
        primary_form.addRow("Model", model_row)
        voice_row = QWidget()
        voice_layout = QHBoxLayout(voice_row)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(CONTROL_SPACING)
        self.voice = NoWheelComboBox()
        self.voice.setAccessibleName("Voice reference")
        self.import_voice = standard_button(
            "Import…",
            role="neutral",
            parent=voice_row,
            tool_tip=(
                "Copy a WAV voice reference into the private voices folder"
            ),
        )
        self.import_voice.setFixedSize(
            model_action_width,
            model_action_height,
        )
        voice_layout.addWidget(self.voice, 1)
        voice_layout.addWidget(self.import_voice)
        primary_form.addRow("Voice", voice_row)

        self.language = NoWheelComboBox()
        primary_form.addRow("Language", self.language)

        self.preset = NoWheelComboBox()
        self.preset.addItems(("Custom", *GENERATION_PRESETS))
        primary_form.addRow("Preset", self.preset)
        layout.addWidget(primary)

        self.capability_summary = QLabel()
        self.capability_summary.setWordWrap(True)
        self.capability_summary.setProperty("muted", True)
        layout.addWidget(self.capability_summary)

        self.toolbox = QToolBox()
        self.toolbox.setObjectName("settingsToolbox")
        self.toolbox.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.toolbox)
        self._build_generation_page()
        self._build_splitting_page()
        self._build_audio_page()
        self._stabilize_toolbox_headers()
        self.toolbox.currentChanged.connect(
            self._schedule_toolbox_fit
        )
        self._schedule_toolbox_fit()

        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setProperty("error", True)
        self.validation.hide()
        layout.addWidget(self.validation)

        actions = QHBoxLayout()
        self.reset_button = standard_button(
            "Reset defaults",
            role="neutral",
            parent=self,
        )
        self.save_button = standard_button(
            "Save as defaults",
            role="primary",
            parent=self,
        )
        self.reset_button.setAccessibleName("Reset settings to defaults")
        self.save_button.setAccessibleName("Save settings as defaults")
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        layout.addStretch(1)

    def _page(self):
        page = QWidget()
        page.setObjectName("settingsSectionPage")
        form = QFormLayout(page)
        form.setContentsMargins(8, 10, 8, 10)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return page, form

    @staticmethod
    def _add_helper_text(form, text):
        helper = QLabel(text)
        helper.setObjectName("settingsHelper")
        helper.setProperty("muted", True)
        helper.setWordWrap(True)
        form.addRow("", helper)
        return helper

    def _stabilize_toolbox_headers(self):
        for button in self.toolbox.findChildren(QAbstractButton):
            if button.parent() is self.toolbox:
                button.setMinimumHeight(36)
                button.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )

    def _schedule_toolbox_fit(self, *args):
        del args
        QTimer.singleShot(0, self._fit_toolbox_to_current_page)

    def _fit_toolbox_to_current_page(self):
        page = self.toolbox.currentWidget()

        if page is None:
            return

        page_layout = page.layout()

        if page_layout is not None:
            page_layout.invalidate()
            page_layout.activate()
            page_height = page_layout.sizeHint().height()
        else:
            page_height = page.sizeHint().height()

        headers = [
            button
            for button in self.toolbox.findChildren(QAbstractButton)
            if button.parent() is self.toolbox
        ]
        header_height = sum(
            max(button.minimumHeight(), button.sizeHint().height())
            for button in headers
        )
        target_height = page_height + header_height + 4
        self.toolbox.setFixedHeight(target_height)
        self.toolbox.updateGeometry()

    def _build_generation_page(self):
        page, form = self._page()
        self.generation_page = page
        self.generation_form = form
        self.exaggeration = _decimal(
            *GENERATION_CONTROL_LIMITS["exaggeration"],
            0.05,
        )
        self.cfg_weight = _decimal(
            *GENERATION_CONTROL_LIMITS["cfg_weight"],
            0.05,
        )
        self.temperature = _decimal(
            *GENERATION_CONTROL_LIMITS["temperature"],
            0.05,
        )
        self.repetition_penalty = _decimal(
            *GENERATION_CONTROL_LIMITS["repetition_penalty"],
            0.05,
        )
        self.min_p = _decimal(
            *GENERATION_CONTROL_LIMITS["min_p"],
            0.01,
        )
        self.top_p = _decimal(
            *GENERATION_CONTROL_LIMITS["top_p"],
            0.01,
        )
        self.top_k = _integer(
            *GENERATION_CONTROL_LIMITS["top_k"],
            10,
        )
        self.generation_widgets = {
            "exaggeration": self.exaggeration,
            "cfg_weight": self.cfg_weight,
            "temperature": self.temperature,
            "repetition_penalty": self.repetition_penalty,
            "min_p": self.min_p,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        for name, widget in self.generation_widgets.items():
            minimum, maximum = GENERATION_CONTROL_LIMITS[name]
            label = GENERATION_CONTROL_LABELS[name]
            help_text = _generation_help_tooltip(
                label,
                GENERATION_CONTROL_HELP[name],
                minimum,
                maximum,
            )
            widget.setAccessibleName(label)
            form.addRow(label, widget)
            field_label = form.labelForField(widget)
            field_label.setToolTip(help_text)
            field_label.setMouseTracking(True)
            field_label.installEventFilter(self._left_tooltip_filter)

        self.toolbox.addItem(page, "Voice Generation")

    def _build_splitting_page(self):
        page, form = self._page()
        self.splitting_page = page
        self.splitting_form = form
        self.splitting_mode = NoWheelComboBox()
        self.splitting_mode.addItems(("automatic", "manual"))
        self.device_preference = NoWheelComboBox()
        self.device_preference.addItems(("auto", "cuda", "cpu"))
        self.cpu_fallback = QCheckBox("Use CPU after CUDA OOM")
        self.cpu_fallback.setToolTip(
            "Continue generation on the CPU if CUDA runs out of memory."
        )
        self.generation_max_words = _integer(1, 2000)
        self.automatic_min_words = _integer(1, 2000)
        self.automatic_max_words = _integer(1, 4000)
        self.vram_safety_margin_mb = _integer(0, 65536, 128, " MiB")
        self.adaptive_growth_interval = _integer(1, 100)
        self.chunk_size = _integer(1, 4000)
        self.min_chunk_size = _integer(1, 4000)
        self.retry_attempts = _integer(1, 20)
        form.addRow("Mode", self.splitting_mode)
        self._add_helper_text(
            form,
            "Automatic adapts section sizes; manual uses the limit below.",
        )
        form.addRow("Device", self.device_preference)
        self._add_helper_text(
            form,
            "Auto uses CUDA when available; CPU is the fallback.",
        )
        form.addRow("Fallback", self.cpu_fallback)
        form.addRow("Manual section limit", self.generation_max_words)
        form.addRow("Automatic minimum", self.automatic_min_words)
        form.addRow("Automatic maximum", self.automatic_max_words)
        form.addRow("VRAM reserve", self.vram_safety_margin_mb)
        form.addRow("Grow after successes", self.adaptive_growth_interval)
        form.addRow("Persistent chunk target", self.chunk_size)
        form.addRow("Minimum persistent chunk", self.min_chunk_size)
        form.addRow("Retry attempts", self.retry_attempts)
        self.toolbox.addItem(page, "Text Splitting")

    def _build_audio_page(self):
        page, form = self._page()
        self.sample_rate = _integer(8000, 192000, 1000, " Hz")
        self.output_format = NoWheelComboBox()
        self.output_format.addItem("WAV", "wav")
        self.merge_audio = QCheckBox("Merge chunks")
        self.merge_audio.setToolTip(
            "Merge generated chunks into one output file."
        )
        self.normalize_audio = QCheckBox("Normalize loudness")
        self.normalize_audio.setToolTip(
            "Normalize the loudness of the final output."
        )
        self.retain_job_artifacts = QCheckBox(
            "Keep segments for review"
        )
        self.retain_job_artifacts.setToolTip(
            "Uses more disk space. Required for editing or regenerating "
            "individual segments after completion."
        )
        self.pause_min_ms = _integer(0, 10000, 10, " ms")
        self.pause_max_ms = _integer(0, 10000, 10, " ms")
        self.pause_mean_ms = _decimal(0, 10000, 10, 1, " ms")
        self.pause_std_ms = _decimal(0, 5000, 5, 1, " ms")
        self.loudness_target_lufs = _decimal(-60, 0, 0.5, 1, " LUFS")
        form.addRow("Sample rate", self.sample_rate)
        form.addRow("Output format", self.output_format)
        form.addRow("Merge", self.merge_audio)
        form.addRow("Normalize", self.normalize_audio)
        form.addRow("Segment review", self.retain_job_artifacts)
        self._add_helper_text(
            form,
            "Keeps individual segments available for editing after generation.",
        )
        form.addRow("Minimum pause", self.pause_min_ms)
        form.addRow("Maximum pause", self.pause_max_ms)
        form.addRow("Mean pause", self.pause_mean_ms)
        form.addRow("Pause spread", self.pause_std_ms)
        form.addRow("Loudness target", self.loudness_target_lufs)
        self.toolbox.addItem(page, "Audio Output")

    def _connect_changes(self):
        self.model.currentIndexChanged.connect(
            self.behavior_controller.model_changed
        )
        self.preset.currentTextChanged.connect(
            self.behavior_controller.preset_changed
        )
        self.splitting_mode.currentTextChanged.connect(
            self.behavior_controller.apply_splitting_mode
        )
        self.import_voice.clicked.connect(self._import_voice)
        self.save_button.clicked.connect(self.save)
        self.reset_button.clicked.connect(self.reset_defaults)

        widgets = (
            self.voice,
            self.language,
            self.splitting_mode,
            self.device_preference,
            self.output_format,
        )

        for widget in widgets:
            widget.currentTextChanged.connect(self._notify_change)

        for widget in (
            *self.generation_widgets.values(),
            self.generation_max_words,
            self.automatic_min_words,
            self.automatic_max_words,
            self.vram_safety_margin_mb,
            self.adaptive_growth_interval,
            self.chunk_size,
            self.min_chunk_size,
            self.retry_attempts,
            self.sample_rate,
            self.pause_min_ms,
            self.pause_max_ms,
            self.pause_mean_ms,
            self.pause_std_ms,
            self.loudness_target_lufs,
        ):
            widget.valueChanged.connect(self._notify_change)

        for widget in (
            self.cpu_fallback,
            self.merge_audio,
            self.normalize_audio,
            self.retain_job_artifacts,
        ):
            widget.toggled.connect(self._notify_change)

    def refresh_voices(self, selected=None):
        selected = selected if selected is not None else self.voice.currentText()
        self.voice.blockSignals(True)
        self.voice.clear()

        for path in self.service.list_voices():
            self.voice.addItem(path.name, path.name)

        if selected:
            index = self.voice.findText(str(selected))

            if index >= 0:
                self.voice.setCurrentIndex(index)
            else:
                self.voice.addItem(str(selected), str(selected))
                self.voice.setCurrentIndex(self.voice.count() - 1)

        self.voice.blockSignals(False)

    def _import_voice(self):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Import voice reference",
            str(self.service.paths.voices_root),
            "WAV audio (*.wav)",
        )

        if not selected:
            return

        try:
            imported = self.service.import_voice(selected)
        except Exception as error:
            AppDialog.critical(self, "Could not import voice", str(error))
            return

        self.refresh_voices(imported.name)
        self._notify_change()

    def _notify_change(self, *args):
        del args

        if self._loading:
            return

        try:
            config = self.to_config()
        except (TypeError, ValueError):
            return

        self.configChanged.emit(config)

    def set_config(self, config):
        return self.config_mapper.set_config(config)

    def to_config(self):
        return self.config_mapper.to_config()

    def current_config(self):
        """Return current controls after validation without saving defaults."""

        try:
            config = self.to_config()
        except (TypeError, ValueError) as error:
            self.validation.setText(str(error))
            self.validation.show()
            return None

        self.validation.hide()
        return config

    def save(self):
        return self.config_mapper.save()

    def reset_defaults(self):
        return self.config_mapper.reset_defaults()

    def summary(self):
        return self.config_mapper.summary()
