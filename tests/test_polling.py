import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from nexus.polling import PollingControl
from nexus.core import Store, validate_sensitivity
from nexus.studio import StudioWindow
from nexus.windows import Device


class PollingTests(unittest.TestCase):
    def control(self):
        self.interval, self.refuse, self.calls = 1, False, []
        def request(index, fn, data=()):
            self.calls.append((fn, list(data)))
            if fn == 0:
                return [0x8B]
            if fn == 1:
                return [self.interval]
            if not self.refuse:
                self.interval = data[0]
            return [0]
        control = PollingControl(request, 9)
        control.load()
        return control

    def test_supported_rates_are_decoded_and_every_rate_is_confirmed(self):
        control = self.control()
        self.assertEqual(control.state(), dict(values=[1000, 500, 250, 125], current=1000))
        for hz, ms in [(125, 8), (250, 4), (500, 2), (1000, 1)]:
            self.assertEqual(control.apply(hz)['current'], hz)
            self.assertEqual(self.interval, ms)
        control.apply(125)
        control.restore()
        self.assertEqual(self.interval, 1)
        self.assertFalse(control.dirty)

    def test_invalid_rate_never_writes_and_unconfirmed_write_is_reported(self):
        control = self.control()
        for value in (8000, 333, True, '500'):
            with self.assertRaises(ValueError):
                control.apply(value)
        self.assertFalse(any(fn == 2 for fn, _ in self.calls))
        self.refuse = True
        with self.assertRaises(OSError):
            control.apply(125)
        self.assertTrue(control.dirty)
        control.restore()
        self.assertFalse(control.dirty)

    def test_restore_failure_retains_retry_and_mode_changes_are_restored(self):
        control = self.control()
        control.apply(125)
        self.refuse = True
        with self.assertRaises(OSError):
            control.restore()
        self.assertTrue(control.dirty)
        self.refuse = False
        control.restore()
        self.interval = 8
        control.restore(after_mode_change=True)
        self.assertEqual(self.interval, 1)

    def test_worker_applies_rate_without_changing_dpi_and_restores_on_exit(self):
        from test_g502 import FakeHid, G502Tests
        fake = FakeHid(dpi=True, polling=True)
        fixture = G502Tests()
        self.addCleanup(fixture.doCleanups)
        session, ready, errors, _ = fixture.launch(fake)
        try:
            self.assertTrue(ready.wait(1))
            confirmed = threading.Event()
            updates = []
            def hardware(data):
                updates.append(data)
                if data['kind'] == 'polling':
                    confirmed.set()
            session.on_hardware = hardware
            session.set_polling(250, profile_id='profile-test')
            self.assertTrue(confirmed.wait(1))
            self.assertEqual(fake.report_interval, 4)
            self.assertEqual(fake.dpi, 3200)
            self.assertEqual(updates[0]['profile_id'], 'profile-test')
        finally:
            self.assertTrue(session.close())
        self.assertEqual(fake.report_interval, 1)
        self.assertEqual(errors, [])

    def test_ui_waits_for_confirmation_and_profile_keeps_rate(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            try:
                device = Device('polling-test', 'G502', 'mouse', 'Logitech', '046D', 'C08B', [], [])
                window.open_device(device)
                state = dict(values=[1000, 500, 250, 125], current=1000)
                polling = SimpleNamespace(state=lambda:state)
                session = SimpleNamespace(device=device, ready=True, dpi_state=None, polling=polling,
                    set_polling=Mock(), close=lambda:True)
                window.g502 = session
                panel = window.sensitivity_panel
                panel.load_device(device)
                self.assertTrue(panel.polling_combo.isEnabled())
                panel.polling_combo.setCurrentIndex(panel.polling_combo.findData(250))
                panel.apply_polling()
                session.set_polling.assert_called_with(250, profile_id=window.store.active_id)
                self.assertIn('Solicitando', panel.polling_notice.text())
                self.assertEqual(Store(Path(directory)).active['sensitivity'][device.id]['polling_hz'], 250)
                panel.hardware_changed(dict(kind='polling', device_id=device.id, values=state['values'], current=250))
                self.assertIn('confirmada: 250', panel.polling_notice.text())
                session.set_polling.reset_mock()
                window.apply_profile_sensitivity()
                session.set_polling.assert_called_with(250, profile_id=window.store.active_id)
                panel.hardware_changed(dict(kind='disconnected', device_id=device.id))
                self.assertFalse(panel.polling_combo.isEnabled())
            finally:
                window.g502 = None
                window.exit_application()
        with self.assertRaises(ValueError):
            validate_sensitivity(dict(polling_hz=999))
