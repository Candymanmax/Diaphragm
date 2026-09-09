from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from harness_ui.theme import INLINE_SPACING, standard_button


class EmptyStateWidget(QFrame):
    """Reusable centered state with concise guidance and optional actions."""

    actionRequested = Signal()
    secondaryActionRequested = Signal()

    def __init__(
        self,
        title="Nothing here yet",
        message="",
        action_text=None,
        parent=None,
        *,
        icon,
        action_role="neutral",
        secondary_action_text=None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.action_key = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(INLINE_SPACING)
        layout.addStretch(1)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("emptyStateIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel()
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.message_label = QLabel()
        self.message_label.setObjectName("emptyStateMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(520)
        message_row = QHBoxLayout()
        message_row.addStretch(1)
        message_row.addWidget(self.message_label)
        message_row.addStretch(1)
        layout.addLayout(message_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 3, 0, 0)
        action_row.addStretch(1)
        self.action_button = standard_button(
            parent=self,
            role=action_role,
        )
        self.action_button.setObjectName("emptyStateAction")
        self.action_button.setAccessibleName("Empty-state primary action")
        self.action_button.clicked.connect(self.actionRequested)
        action_row.addWidget(self.action_button)
        self.secondary_action_button = standard_button(
            parent=self,
            role="neutral",
        )
        self.secondary_action_button.setObjectName("emptyStateSecondaryAction")
        self.secondary_action_button.setAccessibleName(
            "Empty-state secondary action"
        )
        self.secondary_action_button.clicked.connect(
            self.secondaryActionRequested
        )
        action_row.addWidget(self.secondary_action_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        layout.addStretch(1)

        self.set_state(
            title,
            message,
            action_text,
            icon=icon,
            secondary_action_text=secondary_action_text,
        )

    def set_state(
        self,
        title,
        message,
        action_text=None,
        *,
        icon,
        action_key=None,
        secondary_action_text=None,
    ):
        self.icon_label.clear()

        if not isinstance(icon, QIcon):
            raise TypeError("Empty-state icons must be bundled Lucide QIcons")

        self.icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
        self.icon_label.setAccessibleName(str(title))
        self.title_label.setText(str(title))
        self.message_label.setText(str(message))
        self.action_button.setText(str(action_text or ""))
        self.action_button.setAccessibleName(
            str(action_text or "Empty-state primary action")
        )
        self.action_button.setVisible(bool(action_text))
        self.secondary_action_button.setText(str(secondary_action_text or ""))
        self.secondary_action_button.setAccessibleName(
            str(secondary_action_text or "Empty-state secondary action")
        )
        self.secondary_action_button.setVisible(bool(secondary_action_text))
        self.action_key = action_key
