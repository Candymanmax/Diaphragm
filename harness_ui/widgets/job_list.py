"""Job-list widget with separate mouse-selection and keyboard-focus states."""

from .focus_list import KeyboardFocusListWidget


class JobListWidget(KeyboardFocusListWidget):
    """Display jobs without turning mouse selection into a focus outline."""


__all__ = ("JobListWidget",)
