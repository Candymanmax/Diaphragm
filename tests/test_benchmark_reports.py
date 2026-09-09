"""Protect benchmark interpretation without running performance tests in CI."""

from copy import deepcopy
import unittest

from benchmarks.run import compare, measure, summarize


class BenchmarkReportTests(unittest.TestCase):
    def report(self):
        return {
            "schema": 1, "fixture_version": 1, "harness_sha256": "same",
            "environment": {"python": "3.12"}, "settings": {"samples": 20},
            "results": {"example": {"wall": summarize(list(range(1, 21)))}},
        }

    def test_p95_uses_nearest_rank_and_keeps_raw_samples(self):
        samples = list(reversed(range(1, 21)))
        result = summarize(samples)
        self.assertEqual(result["median_ms"], 10.5)
        self.assertEqual(result["p95_ms"], 19)
        self.assertEqual(result["samples_ms"], samples)

    def test_comparison_reports_improvement_and_rejects_incompatible_runs(self):
        before = self.report()
        after = deepcopy(before)
        after["results"]["example"]["wall"] = summarize([value / 2 for value in range(1, 21)])
        self.assertIn("-50.0%", compare(before, after))
        for key in ("schema", "fixture_version", "harness_sha256", "environment", "settings", "results"):
            with self.subTest(key=key):
                changed = deepcopy(after)
                changed[key] = {} if isinstance(changed[key], dict) else "different"
                with self.assertRaises(ValueError):
                    compare(before, changed)

    def test_warmups_are_excluded_and_every_timed_operation_is_checked(self):
        calls, checked = [], []

        def operation():
            calls.append(1)
            return len(calls)

        result = measure(operation, prepare=lambda: None, drain=lambda: None,
                         verify=checked.append, samples=3, warmups=2)
        self.assertEqual(len(result["wall"]["samples_ms"]), 3)
        self.assertEqual(checked, [1, 2, 3, 4, 5])
        self.assertEqual(len(calls), 6)  # Additional untimed call-count pass.


if __name__ == "__main__":
    unittest.main()
