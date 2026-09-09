import unittest

from modules.events import EventStreamWriter, HarnessEvent, emit_event


class HarnessEventTests(unittest.TestCase):
    def test_event_round_trip_preserves_structured_fields(self):
        event = HarnessEvent(
            kind="chunk.completed",
            message="Completed chunk0001",
            job_id="job-1",
            script_id="script-1",
            chunk_id="chunk0001",
            payload={"elapsed_seconds": 1.5},
        )

        restored = HarnessEvent.from_dict(event.to_dict())

        self.assertEqual(restored, event)

    def test_event_rejects_non_objects_and_unknown_schema_versions(self):
        invalid_values = (
            None,
            [],
            "event",
            {"schema_version": 999, "kind": "worker.started"},
        )

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                HarnessEvent.from_dict(value)

    def test_stream_writer_emits_complete_lines(self):
        events = []
        writer = EventStreamWriter(events.append, job_id="job-1")

        writer.write("first half")
        writer.write(" and second\nnext line\n")
        writer.flush()

        self.assertEqual(
            [event.message for event in events],
            ["first half and second", "next line"],
        )
        self.assertTrue(all(event.kind == "log" for event in events))

    def test_emit_event_is_optional(self):
        self.assertIsNone(emit_event(None, "job.started"))

    def test_stream_writer_drops_tqdm_redraws_and_ansi_controls(self):
        events = []
        writer = EventStreamWriter(events.append, job_id="job-1")

        writer.write("\x1b[A\r")
        writer.write(
            "Sampling: 4%| | 38/1000 [00:01<00:44, 21.39it/s]\r"
        )
        writer.write("Useful pipeline message\n")
        writer.write("100%|##########| 26/26 [07:57<00:00, 18.37s/it]\n")
        writer.flush()

        self.assertEqual(
            [event.message for event in events],
            ["Useful pipeline message"],
        )


if __name__ == "__main__":
    unittest.main()
