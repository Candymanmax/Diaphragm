"""Job-search and keyboard-shortcut dialog shell."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
)

from harness_ui.theme import INLINE_SPACING, MICRO_SPACING


class SearchDialog(QDialog):
    """Shared shell for job search and keyboard-shortcut lookup."""

    queryChanged = Signal(str)
    jobActivated = Signal(object)

    def __init__(self, mode="jobs", parent=None):
        super().__init__(parent)
        self.mode = str(mode)
        shortcuts_mode = self.mode == "shortcuts"
        self.setObjectName("jobSearchDialog")
        self.setWindowTitle("Keyboard shortcuts" if shortcuts_mode else "Search jobs")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(520, 470)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)
        panel = QFrame()
        panel.setObjectName("jobSearchPanel")
        outer_layout.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(INLINE_SPACING)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("jobSearchInput")
        self.search_input.setPlaceholderText(
            "Search shortcuts" if shortcuts_mode else "Search jobs"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName(
            "Search keyboard shortcuts" if shortcuts_mode else "Search jobs by name"
        )
        layout.addWidget(self.search_input)

        section_label = QLabel("Keyboard shortcuts" if shortcuts_mode else "Jobs")
        section_label.setObjectName("jobSearchSection")
        section_label.setProperty("muted", True)
        layout.addWidget(section_label)

        self.results = QListWidget()
        self.results.setObjectName("jobSearchResults")
        self.results.setSpacing(MICRO_SPACING)
        self.results.setAccessibleName(
            "Keyboard shortcuts" if shortcuts_mode else "Matching jobs"
        )
        layout.addWidget(self.results, 1)

        hint = QLabel("Esc to close")
        hint.setObjectName("jobSearchHint")
        hint.setProperty("muted", True)
        layout.addWidget(hint)

        self.search_input.textChanged.connect(self.queryChanged.emit)
        if not shortcuts_mode:
            self.results.itemActivated.connect(self.jobActivated.emit)
            self.results.itemClicked.connect(self.jobActivated.emit)
        self.search_input.setFocus()
