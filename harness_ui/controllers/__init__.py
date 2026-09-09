"""Feature controllers for Diaphragm's desktop interface."""

from harness_ui.controllers.appearance import (
    AppearanceController,
    AppearanceSnapshot,
    WINDOW_LAYOUT_KEYS,
    WINDOW_LAYOUT_SCHEMA_VERSION,
)
from harness_ui.controllers.diagnostics import (
    DiagnosticsController,
    DiagnosticsSnapshot,
)
from harness_ui.controllers.generation import (
    GenerationController,
    GenerationSnapshot,
)
from harness_ui.controllers.jobs import JobController, JobSnapshot, relative_time
from harness_ui.controllers.output_review import (
    OutputReviewController,
    OutputReviewSnapshot,
    format_media_time,
)
from harness_ui.controllers.preferences import (
    PreferencesController,
    PreferencesSnapshot,
)
from harness_ui.controllers.search import SearchController, SearchSnapshot
from harness_ui.controllers.shutdown import ShutdownController, ShutdownSnapshot
from harness_ui.controllers.startup import StartupController, StartupSnapshot
from harness_ui.controllers.script_documents import (
    SCRIPT_TEXT_ROLE,
    ScriptDocumentController,
    ScriptDocumentSnapshot,
)

__all__ = (
    "AppearanceController",
    "AppearanceSnapshot",
    "DiagnosticsController",
    "DiagnosticsSnapshot",
    "GenerationController",
    "GenerationSnapshot",
    "JobController",
    "JobSnapshot",
    "OutputReviewController",
    "OutputReviewSnapshot",
    "PreferencesController",
    "PreferencesSnapshot",
    "SCRIPT_TEXT_ROLE",
    "ScriptDocumentController",
    "ScriptDocumentSnapshot",
    "SearchController",
    "SearchSnapshot",
    "ShutdownController",
    "ShutdownSnapshot",
    "StartupController",
    "StartupSnapshot",
    "WINDOW_LAYOUT_KEYS",
    "WINDOW_LAYOUT_SCHEMA_VERSION",
    "format_media_time",
    "relative_time",
)
