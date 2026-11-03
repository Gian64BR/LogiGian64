import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class StartupWindowTests(unittest.TestCase):
    def test_automatic_start_never_shows_window_and_manual_start_does(self):
        script = r'''
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
import nexus.studio
automatic = sys.argv[1] == '1'
directory = sys.argv[2]
shown = []
class Window(nexus.studio.StudioWindow):
    def __init__(self, *args):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        super().__init__(*args)
        self.preferences().setValue('startup_minimized', False)
        QTimer.singleShot(150, self.check)
    def showEvent(self, event):
        shown.append(True)
        super().showEvent(event)
    def check(self):
        good = self.isVisible() == (not automatic) and bool(shown) == (not automatic) and self.tray.isVisible()
        self.exit_application()
        QApplication.instance().exit(0 if good else 3)
nexus.studio.StudioWindow = Window
import main
sys.argv = ['main.py', '--data-dir', directory] + (['--startup'] if automatic else [])
raise SystemExit(main.main())
'''
        for automatic in (True, False):
            with self.subTest(automatic=automatic), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run([sys.executable, '-c', script, str(int(automatic)), directory],
                    cwd=Path(__file__).resolve().parent.parent,
                    env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
