import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication

from harness_ui.widgets import WaveformWidget


class HarnessWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_waveform_uses_bounded_display_peaks(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "long-output.wav"
            sf.write(path, np.linspace(-1, 1, 48000), 24000)
            widget = WaveformWidget()

            widget.set_file(path)

            self.assertEqual(widget.file, path)
            self.assertGreater(len(widget._peaks), 0)
            self.assertLessEqual(len(widget._peaks), 1200)


if __name__ == "__main__":
    unittest.main()
