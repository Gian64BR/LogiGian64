import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from nexus import windows as win
from nexus.core import Store
from nexus.studio import StudioWindow


class AutomaticG502Tests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.device = win.Device('a' * 24, 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [123])
        enumeration = patch.object(win, 'enumerate_devices', return_value=[self.device])
        enumeration.start()
        self.addCleanup(enumeration.stop)
        self.window = StudioWindow(Store(Path(directory.name)))
        self.window.input_ready = True
        self.addCleanup(self.window.exit_application)
        self.sessions = []
        def session(device, *callbacks):
            result = SimpleNamespace(device=device, thread=SimpleNamespace(is_alive=lambda: True),
                ready=False, needs_restore=False, start=Mock(), close=Mock(return_value=True),
                update_buttons=Mock(), callbacks=callbacks)
            self.sessions.append(result)
            return result
        factory = patch('nexus.g502.G502Session', side_effect=session)
        self.factory = factory.start()
        self.addCleanup(factory.stop)

    def enable(self):
        self.window.enable_auto_g502()
        self.window.auto_g502_timer.stop()
        self.window.auto_connect_g502()

    def test_background_start_needs_no_selected_device_and_uses_saved_bindings(self):
        self.window.store.active['bindings'] = [dict(device_id=self.device.id, enabled=True,
            macro_id='macro', trigger=dict(type='gbutton', button=3))]
        self.assertIsNone(self.window.device)
        self.assertFalse(self.window.isVisible())
        self.enable()
        self.factory.assert_called_once()
        self.sessions[0].start.assert_called_once_with({3})
        self.assertIsNone(self.window.device)
        self.window.auto_connect_g502()
        self.factory.assert_called_once()

    def test_paused_unsupported_and_input_unavailable_do_not_start(self):
        self.window.armed.setChecked(False)
        self.enable()
        self.factory.assert_not_called()
        self.window.input_ready = False
        self.window.armed.setChecked(True)
        self.window.auto_connect_g502()
        self.factory.assert_not_called()
        self.window.input_ready = True
        self.device.pid = 'C08D'
        self.window.auto_connect_g502()
        self.factory.assert_not_called()

    def test_emergency_stop_and_manual_disconnect_are_respected(self):
        for emergency in (True, False):
            with self.subTest(emergency=emergency):
                self.window._auto_g502_suspended = False
                self.window._auto_g502_attempted.clear()
                self.window.armed.setChecked(True)
                self.enable()
                calls = self.factory.call_count
                if emergency:
                    self.window.emergency_stop()
                    self.window.armed.setChecked(True)
                else:
                    self.window.device = self.device
                    self.window.activate_g502()
                self.window.schedule_auto_g502()
                self.window.auto_connect_g502()
                self.assertEqual(self.factory.call_count, calls)
                self.assertIsNone(self.window.g502)

    def test_reconnect_starts_once_but_failed_restore_is_not_replaced(self):
        self.enable()
        self.window.g502 = SimpleNamespace(thread=None, needs_restore=True, ready=False, close=Mock(return_value=True))
        self.window.devices = []
        self.window.schedule_auto_g502()
        self.window.devices = [self.device]
        self.window.auto_connect_g502()
        self.factory.assert_called_once()
        self.window.g502 = None
        self.window.auto_connect_g502()
        self.assertEqual(self.factory.call_count, 2)

    def test_background_error_does_not_show_dialog_or_retry(self):
        self.enable()
        with patch.object(self.window, 'error') as dialog:
            self.sessions[0].callbacks[2]('G HUB tiene el control del ratón')
            self.window.auto_connect_g502()
            dialog.assert_not_called()
            self.factory.assert_called_once()
            self.assertTrue(self.window._auto_g502_suspended)


if __name__ == '__main__':
    unittest.main()
