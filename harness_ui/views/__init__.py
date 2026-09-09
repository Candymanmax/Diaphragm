"""Composable Qt views used by the Diaphragm desktop shell."""

from harness_ui.views.appearance import AppearanceViewAdapter
from harness_ui.views.commands import CommandViewBuilder
from harness_ui.views.feedback import WorkspaceFeedbackViewAdapter
from harness_ui.views.workspace import WorkspaceViewBuilder

__all__ = (
    "AppearanceViewAdapter",
    "CommandViewBuilder",
    "WorkspaceFeedbackViewAdapter",
    "WorkspaceViewBuilder",
)
