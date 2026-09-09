"""Visual page construction for the Preferences window."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.model_manager import ModelManagerWidget
from harness_ui.theme import (
    ACCENT_COLORS,
    COMPACT_SPACING,
    CONTROL_SPACING,
    PAGE_SPACING,
    SUBTEXT_0,
    SURFACE_2,
    icon_button,
    standard_button,
)
from modules.app_settings import APP_VERSION


def accent_icon(color):
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(SURFACE_2))
    painter.setBrush(QColor(color))
    painter.drawEllipse(1, 1, 12, 12)
    painter.end()
    return QIcon(pixmap)


class DialogTitleBar(QFrame):
    """Small draggable title surface for the frameless Preferences window."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.setObjectName("preferencesTitleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 8, 8)
        title = QLabel("Preferences")
        title.setObjectName("preferencesWindowTitle")
        title.setStyleSheet("font-size: 11pt; font-weight: 650;")
        close_button = icon_button(
            lucide_icon("x", color=SUBTEXT_0, size=16),
            role="ghost",
            parent=self,
            object_name="preferencesCloseButton",
            icon_size=16,
            size=(30, 28),
            accessible_name="Close Preferences",
        )
        close_button.clicked.connect(dialog.close)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.dialog.windowHandle()

            if handle is not None and hasattr(handle, "startSystemMove"):
                handle.startSystemMove()

        super().mousePressEvent(event)


class PreferencesPageBuilder:
    """Build all preference pages while leaving behavior to controllers."""

    def __init__(self, dialog):
        self.dialog = dialog

    def build(self):
        dialog = self.dialog
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(1, 1, 1, 1)
        panel = QFrame()
        panel.setObjectName("preferencesPanel")
        outer.addWidget(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(DialogTitleBar(dialog))

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        panel_layout.addWidget(body, 1)

        dialog.navigation = QListWidget()
        dialog.navigation.setObjectName("preferencesNavigation")
        dialog.navigation.setFixedWidth(210)
        dialog.navigation.setSpacing(COMPACT_SPACING)
        dialog.navigation.setAccessibleName("Preference categories")

        for name in dialog.PAGE_NAMES:
            item = QListWidgetItem(name)
            item.setSizeHint(QSize(0, 38))
            dialog.navigation.addItem(item)

        body_layout.addWidget(dialog.navigation)
        dialog.pages = QStackedWidget()
        dialog.pages.setObjectName("preferencesPages")
        body_layout.addWidget(dialog.pages, 1)
        self._build_general_page()
        self._build_appearance_page()
        self._build_library_page()
        self._build_models_page()
        self._build_storage_page()
        self._build_credentials_page()
        self._build_updates_page()
        dialog.navigation.setCurrentRow(0)

    def _page(self, title, description):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(PAGE_SPACING)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 16pt; font-weight: 650;")
        copy = QLabel(description)
        copy.setProperty("muted", True)
        copy.setWordWrap(True)
        feedback = QLabel()
        feedback.setObjectName("preferencesFeedback")
        feedback.setWordWrap(True)
        feedback.hide()
        layout.addWidget(heading)
        layout.addWidget(copy)
        self.dialog.pages.addWidget(page)
        return page, layout, feedback

    @staticmethod
    def _form_container(layout):
        container = QFrame()
        container.setObjectName("preferencesSection")
        form = QFormLayout(container)
        form.setContentsMargins(14, 14, 14, 14)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addWidget(container)
        return form

    def _build_general_page(self):
        dialog = self.dialog
        page, layout, dialog.general_feedback = self._page(
            "General",
            "Choose how Diaphragm opens and manage application preferences.",
        )
        form = self._form_container(layout)
        dialog.startup_behavior = QComboBox()
        dialog.startup_behavior.addItem(
            "Open most recent active job",
            "recent",
        )
        dialog.startup_behavior.addItem("Open a blank draft", "blank")
        dialog.restore_layout = QCheckBox(
            "Restore the previous window and panels"
        )
        form.addRow("Startup", dialog.startup_behavior)
        form.addRow("Window", dialog.restore_layout)

        actions = QHBoxLayout()
        dialog.open_app_data_button = standard_button(
            "Open application data",
            role="neutral",
            parent=page,
        )
        dialog.reset_preferences_button = standard_button(
            "Reset preferences…",
            role="danger",
            parent=page,
        )
        actions.addWidget(dialog.open_app_data_button)
        actions.addWidget(dialog.reset_preferences_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(dialog.general_feedback)
        layout.addStretch(1)

    def _build_appearance_page(self):
        dialog = self.dialog
        page, layout, dialog.appearance_feedback = self._page(
            "Appearance",
            "Adjust the interface without changing generation behaviour.",
        )
        form = self._form_container(layout)
        dialog.accent = QComboBox()

        for name, color in ACCENT_COLORS.items():
            dialog.accent.addItem(accent_icon(color), name.title(), name)

        dialog.show_line_numbers = QCheckBox("Show editor line numbers")
        dialog.show_sidebar = QCheckBox("Show sidebar")
        dialog.show_settings = QCheckBox("Show settings inspector")
        dialog.show_logs = QCheckBox("Show logs panel")
        form.addRow("Accent colour", dialog.accent)
        form.addRow("Editor", dialog.show_line_numbers)
        form.addRow("Sidebar", dialog.show_sidebar)
        form.addRow("Inspector", dialog.show_settings)
        form.addRow("Diagnostics", dialog.show_logs)
        dialog.reset_layout_button = standard_button(
            "Reset window layout",
            role="neutral",
            parent=page,
        )
        layout.addWidget(
            dialog.reset_layout_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(dialog.appearance_feedback)
        layout.addStretch(1)

    @staticmethod
    def _path_row(accessible_name):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(CONTROL_SPACING)
        value = QLineEdit()
        value.setReadOnly(True)
        value.setAccessibleName(accessible_name)
        change = standard_button(
            "Change…",
            role="neutral",
            parent=container,
        )
        open_button = standard_button(
            "Open",
            role="neutral",
            parent=container,
        )
        row.addWidget(value, 1)
        row.addWidget(change)
        row.addWidget(open_button)
        return container, value, change, open_button

    def _build_library_page(self):
        dialog = self.dialog
        _, layout, dialog.library_feedback = self._page(
            "Library",
            "The personal library contains input scripts, voices, jobs, and final outputs.",
        )
        form = self._form_container(layout)
        row = self._path_row("Personal library folder")
        (
            container,
            dialog.library_path,
            dialog.change_library_button,
            dialog.open_library_button,
        ) = row
        form.addRow("Library folder", container)
        dialog.library_usage = QLabel("Calculating…")
        dialog.library_usage.setProperty("muted", True)
        form.addRow("Current usage", dialog.library_usage)
        dialog.library_progress = QProgressBar()
        dialog.library_progress.setTextVisible(True)
        dialog.library_progress.hide()
        layout.addWidget(dialog.library_progress)
        layout.addWidget(dialog.library_feedback)
        layout.addStretch(1)

    def _build_models_page(self):
        dialog = self.dialog
        _, layout, dialog.models_feedback = self._page(
            "Models",
            "Install and maintain the speech models stored in your selected model cache.",
        )
        dialog.model_manager = ModelManagerWidget(
            dialog.repository.paths,
            dialog.repository.paths.install_root,
            worker_running=dialog.worker_running,
            model_busy=dialog.model_busy,
        )
        dialog.model_manager.modelsChanged.connect(dialog.modelsChanged)
        layout.addWidget(dialog.model_manager, 1)
        layout.addWidget(dialog.models_feedback)

    def _build_storage_page(self):
        dialog = self.dialog
        page, layout, dialog.storage_feedback = self._page(
            "Storage",
            "Review local usage and control model-cache and diagnostic storage.",
        )
        form = self._form_container(layout)
        row = self._path_row("Model cache folder")
        (
            container,
            dialog.model_cache_path,
            dialog.change_model_cache_button,
            dialog.open_model_cache_button,
        ) = row
        form.addRow("Model cache", container)
        dialog.low_disk_warning = QSpinBox()
        dialog.low_disk_warning.setRange(1, 1024)
        dialog.low_disk_warning.setSuffix(" GiB")
        dialog.log_retention = QComboBox()

        for days in (1, 3, 7, 14, 30, 60, 90, 0):
            dialog.log_retention.addItem(
                "Never remove automatically" if days == 0 else f"{days} days",
                days,
            )

        form.addRow("Low-disk warning", dialog.low_disk_warning)
        form.addRow("Diagnostic retention", dialog.log_retention)
        dialog.storage_usage = QLabel("Calculating storage usage…")
        dialog.storage_usage.setWordWrap(True)
        dialog.storage_usage.setProperty("muted", True)
        form.addRow("Usage", dialog.storage_usage)
        actions = QHBoxLayout()
        dialog.refresh_usage_button = standard_button(
            "Refresh usage",
            role="neutral",
            parent=page,
        )
        dialog.clear_logs_button = standard_button(
            "Clear diagnostic logs…",
            role="neutral",
            parent=page,
        )
        dialog.cleanup_temporary_button = standard_button(
            "Clean completed temporary files…",
            role="neutral",
            parent=page,
        )

        for button in (
            dialog.refresh_usage_button,
            dialog.clear_logs_button,
            dialog.cleanup_temporary_button,
        ):
            actions.addWidget(button)

        actions.addStretch(1)
        layout.addLayout(actions)
        dialog.model_cache_progress = QProgressBar()
        dialog.model_cache_progress.hide()
        layout.addWidget(dialog.model_cache_progress)
        layout.addWidget(dialog.storage_feedback)
        layout.addStretch(1)

    def _build_credentials_page(self):
        dialog = self.dialog
        page, layout, dialog.credentials_feedback = self._page(
            "Credentials",
            "An optional Hugging Face token can improve model-download limits. It is stored only in Windows Credential Manager.",
        )

        service_card = QFrame()
        service_card.setObjectName("credentialServiceCard")
        service_layout = QHBoxLayout(service_card)
        service_layout.setContentsMargins(16, 13, 16, 13)
        service_layout.setSpacing(PAGE_SPACING)

        service_details = QVBoxLayout()
        service_details.setContentsMargins(0, 0, 0, 0)
        service_details.setSpacing(COMPACT_SPACING)
        service_name = QLabel("Hugging Face")
        service_name.setObjectName("credentialServiceName")
        service_description = QLabel(
            "Used only for authenticated Hugging Face Hub downloads"
        )
        service_description.setObjectName("credentialServiceDescription")
        service_details.addWidget(service_name)
        service_details.addWidget(service_description)

        dialog.token_status = QLabel()
        dialog.token_status.setObjectName("credentialStatusBadge")
        dialog.token_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.token_status.setMinimumWidth(112)
        service_layout.addLayout(service_details, 1)
        service_layout.addWidget(
            dialog.token_status,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addWidget(service_card)

        actions = QHBoxLayout()
        dialog.set_token_button = standard_button(
            "Set or replace token…",
            role="neutral",
            parent=page,
        )
        dialog.verify_token_button = standard_button(
            "Verify token",
            role="neutral",
            parent=page,
        )
        dialog.clear_token_button = standard_button(
            "Clear token…",
            role="neutral",
            parent=page,
        )

        for button in (
            dialog.set_token_button,
            dialog.verify_token_button,
            dialog.clear_token_button,
        ):
            actions.addWidget(button)

        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(dialog.credentials_feedback)
        layout.addStretch(1)

    def _build_updates_page(self):
        dialog = self.dialog
        page, layout, dialog.updates_feedback = self._page(
            "Updates",
            "Diaphragm never checks for updates in the background.",
        )
        form = self._form_container(layout)
        dialog.version_label = QLabel(APP_VERSION)
        dialog.update_policy_label = QLabel("Manual checks only")
        form.addRow("Version", dialog.version_label)
        form.addRow("Policy", dialog.update_policy_label)
        dialog.open_releases_button = standard_button(
            "Open latest release page",
            role="neutral",
            parent=page,
        )
        layout.addWidget(
            dialog.open_releases_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addWidget(dialog.updates_feedback)
        layout.addStretch(1)


__all__ = ("DialogTitleBar", "PreferencesPageBuilder", "accent_icon")
