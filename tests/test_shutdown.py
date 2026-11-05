"""Run the actual tray Exit callback in a separate Python process."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ShutdownTests(unittest.TestCase):
    def test_tray_exit_ends_process_visible_or_hidden_with_failed_restoration(self):
        script = r'''
import sys, threading
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from nexus.core import Store
from nexus.studio import StudioWindow
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
directory = Path(sys.argv[1])
window = StudioWindow(Store(directory))
failed = sys.argv[3] == '1'
if sys.argv[2] == '1':
    window.show()
if failed:
    def fail_close():
        window.g502_error('El transporte USB ya no responde')
        return False
    window.g502 = SimpleNamespace(device=SimpleNamespace(id='test'), thread=None,
        close=fail_close, discard=lambda: None, needs_restore=True)
exit_action = next(action for action in window.tray.contextMenu().actions() if action.text() == 'Salir')
QTimer.singleShot(50, exit_action.trigger)
QTimer.singleShot(8000, lambda: app.exit(9))
code = app.exec()
assert not window.player.thread.is_alive()
assert not window.tray.isVisible()
assert (directory / 'g502-restoration-pending.json').exists() == failed
raise SystemExit(code)
'''
        for visible in (False, True):
            for failed in (False, True):
                with self.subTest(visible=visible, failed=failed), tempfile.TemporaryDirectory() as directory:
                    result = subprocess.run([sys.executable, '-c', script, directory, str(int(visible)), str(int(failed))],
                        cwd=Path(__file__).resolve().parents[1],
                        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                        capture_output=True, text=True, timeout=12)
                    self.assertEqual(result.returncode, 0, result.stderr[-3000:])
