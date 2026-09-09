import unittest

from harness_ui.state import UiStateStore


class UiStateStoreTests(unittest.TestCase):
    def test_changes_are_published_to_general_and_slice_signals(self):
        store = UiStateStore()
        state_events = []
        script_events = []
        panel_events = []

        store.stateChanged.connect(
            lambda name, previous, value: state_events.append(
                (name, previous, value)
            )
        )
        store.scriptChanged.connect(
            lambda previous, value: script_events.append((previous, value))
        )
        store.panelChanged.connect(
            lambda name, previous, value: panel_events.append(
                (name, previous, value)
            )
        )

        self.assertTrue(store.set("script_dirty", True))
        self.assertTrue(store.set("sidebar_visible", False))
        self.assertFalse(store.set("sidebar_visible", False))

        self.assertEqual(state_events[0][0], "script_dirty")
        self.assertEqual(script_events, [(False, True)])
        self.assertEqual(panel_events, [("sidebar_visible", True, False)])
        self.assertFalse(store.get("sidebar_visible"))

    def test_update_applies_multiple_fields_in_order(self):
        store = UiStateStore()
        transitions = []
        store.stateChanged.connect(
            lambda name, previous, value: transitions.append(
                (name, previous, value)
            )
        )

        store.update(current_job_id="job-1", active_tab=2)

        self.assertEqual(store.get("current_job_id"), "job-1")
        self.assertEqual(store.get("active_tab"), 2)
        self.assertEqual(
            transitions,
            [
                ("current_job_id", None, "job-1"),
                ("active_tab", 0, 2),
            ],
        )

    def test_cross_section_state_slices_publish_typed_transitions(self):
        store = UiStateStore()
        generation_events = []
        feedback_events = []
        diagnostic_events = []

        store.generationChanged.connect(
            lambda name, previous, value: generation_events.append(
                (name, previous, value)
            )
        )
        store.feedbackChanged.connect(
            lambda previous, value: feedback_events.append((previous, value))
        )
        store.diagnosticsChanged.connect(
            lambda name, previous, value: diagnostic_events.append(
                (name, previous, value)
            )
        )

        store.set("runtime_summary", "CUDA · 12 words")
        store.set("workspace_error_message", "Worker failed")
        store.set("log_filter", "Errors only")

        self.assertEqual(
            generation_events,
            [
                (
                    "runtime_summary",
                    "Runtime metrics appear after model load",
                    "CUDA · 12 words",
                )
            ],
        )
        self.assertEqual(
            feedback_events,
            [(None, "Worker failed")],
        )
        self.assertEqual(
            diagnostic_events,
            [("log_filter", "All events", "Errors only")],
        )


if __name__ == "__main__":
    unittest.main()
