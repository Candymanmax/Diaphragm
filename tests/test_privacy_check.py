from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from privacy_check import audit_files, audit_history


class PrivacyCheckTests(unittest.TestCase):
    def test_private_paths_and_credentials_are_reported_without_values(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "input").mkdir()
            (root / "input" / "private.txt").write_text(
                "private narration",
                encoding="utf-8",
            )
            (root / "module.py").write_text(
                "token = '" + "hf_" + ("a" * 26) + "'\n",
                encoding="utf-8",
            )

            findings = audit_files(
                root,
                ("input/private.txt", "module.py"),
            )

            reasons = {(finding.path, finding.reason) for finding in findings}
            self.assertIn(
                ("input/private.txt", "private directory"),
                reasons,
            )
            self.assertIn(("module.py", "Hugging Face token"), reasons)
            self.assertNotIn("a" * 26, repr(findings))

    def test_public_project_files_pass(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "module.py").write_text("value = 1\n", encoding="utf-8")
            (root / "config.default.yaml").write_text(
                "voice: example.wav\n",
                encoding="utf-8",
            )

            findings = audit_files(
                root,
                ("module.py", "config.default.yaml"),
            )

            self.assertEqual(findings, [])

    def test_history_audit_reports_private_paths(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            subprocess.run(("git", "init", "-q"), cwd=root, check=True)
            subprocess.run(
                (
                    "git",
                    "config",
                    "user.email",
                    "test" + "@" + "invalid.example",
                ),
                cwd=root,
                check=True,
            )
            subprocess.run(
                ("git", "config", "user.name", "Privacy Test"),
                cwd=root,
                check=True,
            )
            (root / "config.yaml").write_text(
                "voice: private.wav\n",
                encoding="utf-8",
            )
            subprocess.run(("git", "add", "config.yaml"), cwd=root, check=True)
            subprocess.run(
                ("git", "commit", "-qm", "private fixture"),
                cwd=root,
                check=True,
            )
            (root / "config.yaml").unlink()
            subprocess.run(
                ("git", "commit", "-qam", "remove fixture"),
                cwd=root,
                check=True,
            )

            findings = audit_history(root)

            self.assertIn(
                ("config.yaml", "historical private file"),
                {(finding.path, finding.reason) for finding in findings},
            )


if __name__ == "__main__":
    unittest.main()
