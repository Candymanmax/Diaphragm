"""Focused workspace sections used by the main desktop view."""

from harness_ui.sections.jobs_sidebar import JobsSidebarSection
from harness_ui.sections.job_header import JobHeaderSection
from harness_ui.sections.logs import LogsSection
from harness_ui.sections.output import OutputTabSection
from harness_ui.sections.queue import QueueTabSection
from harness_ui.sections.scripts import ScriptsTabSection
from harness_ui.sections.settings_inspector import SettingsInspectorSection

__all__ = (
    "JobHeaderSection",
    "JobsSidebarSection",
    "LogsSection",
    "OutputTabSection",
    "QueueTabSection",
    "ScriptsTabSection",
    "SettingsInspectorSection",
)
