import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from harness_ui.icons import lucide_icon


class LucideIconTests(unittest.TestCase):
    ICON_NAMES = (
        "arrow-right",
        "archive",
        "check",
        "ellipsis",
        "info",
        "list",
        "loader-circle",
        "music-2",
        "plus",
        "refresh-cw",
        "search",
        "trash-2",
        "triangle-alert",
    )

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_bundled_check_icon_renders_at_requested_size(self):
        icon = lucide_icon("check", color="#8BD5CA", size=18)
        pixmap = icon.pixmap(QSize(18, 18))

        self.assertFalse(icon.isNull())
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.size(), QSize(18, 18))
        self.assertTrue(pixmap.hasAlphaChannel())

    def test_every_bundled_interface_icon_renders(self):
        for name in self.ICON_NAMES:
            with self.subTest(name=name):
                icon = lucide_icon(name, color="#CAD3F5", size=20)
                self.assertFalse(icon.isNull())
                self.assertFalse(icon.pixmap(QSize(20, 20)).isNull())

    def test_unknown_or_unsafe_icon_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not bundled"):
            lucide_icon("missing")

        with self.assertRaisesRegex(ValueError, "Invalid Lucide icon name"):
            lucide_icon("../check")


if __name__ == "__main__":
    unittest.main()
