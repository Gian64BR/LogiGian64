import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from nexus.lighting_protocol import LightingControl, effect_params
from nexus.g502 import G502Session
from nexus.core import Store
from nexus.studio import StudioWindow
from nexus.windows import Device


class FakeLighting:
    def __init__(self):
        self.owner = [0, 0]
        self.effects = {0: [0, 1, 255, 220, 0] + [0] * 7, 1: [1, 1, 255, 220, 0] + [0] * 7}
        self.original = copy.deepcopy(self.effects)
        self.calls = []
        self.refuse = False
        self.refuse_restore = False

    def request(self, index, fn, data=()):
        data = list(data)
        self.calls.append((index, fn, data))
        answer = [0] * 16
        if fn == 0:
            answer[:5] = [2, 0, 3, 0, 0]  # Real G502 advertises zero extended flags.
        elif fn == 1:
            answer[:5] = [data[0], 0, data[0] + 1, 4, 0]
        elif fn == 2:
            answer[:4] = data[:2] + [0, [0, 1, 10, 3][data[1]]]
        elif fn == 7:
            answer[:2] = self.owner
        elif fn == 8:
            self.owner = data[:2]
        elif fn == 14:
            answer[:12] = self.effects[data[0]]
        elif fn == 3:
            if self.refuse_restore and data[:12] == self.original[data[0]]:
                raise OSError('Fallo de restauración simulado')
            if not self.refuse:
                self.effects[data[0]] = data[:12]
        else:
            raise OSError('Función no prevista')
        return answer


class LightingProtocolTests(unittest.TestCase):
    def test_effect_parameters_and_volatile_restoration(self):
        fake = FakeLighting()
        control = LightingControl(fake.request, 2)
        zones = control.load()
        self.assertEqual([z['location'] for z in zones], [1, 2])
        self.assertEqual(zones[0]['effects'][10], 2)
        control.apply({0: dict(effect=10, color='#ff0000', period=2000, brightness=60),
                       1: dict(effect=1, color='#00b7ed', period=5000, brightness=50)})
        self.assertEqual(fake.effects[0], [0, 2, 255, 0, 0, 7, 208, 1, 60, 0, 0, 0])
        self.assertEqual(fake.effects[1][2:5], [0, 92, 118])
        control.apply({z: dict(effect=3, color='#ff0000', period=3000, brightness=40) for z in (0, 1)})
        self.assertEqual(fake.effects[0][7:10], [11, 184, 40])
        self.assertEqual(control.restore(), [])
        self.assertEqual(fake.effects, fake.original)
        self.assertEqual(fake.owner, [0, 0])
        writes = [data for _, fn, data in fake.calls if fn == 3]
        self.assertTrue(writes)
        self.assertTrue(all(data[12] == 0 for data in writes))
        self.assertTrue(all(fn in (0, 1, 2, 3, 7, 8, 14) for _, fn, _ in fake.calls))

    def test_invalid_settings_and_unconfirmed_write(self):
        fake = FakeLighting()
        control = LightingControl(fake.request, 2)
        control.load()
        for config in [dict(effect=99), dict(brightness=101), dict(period=0), dict(color='invalid')]:
            with self.assertRaises(ValueError):
                control.apply({0: config})
        self.assertFalse(any(fn in (3, 8) for _, fn, _ in fake.calls))
        fake.refuse = True
        with self.assertRaises(OSError):
            control.apply({0: dict(effect=1, color='#00b7ed')})
        self.assertIn(0, control.dirty)
        self.assertEqual(control.restore(), [])

    def test_failed_restore_retains_ownership_until_retry(self):
        fake = FakeLighting()
        control = LightingControl(fake.request, 2)
        control.load()
        control.apply({0: dict(effect=0)})
        fake.refuse_restore = True
        self.assertTrue(control.restore())
        self.assertEqual(fake.owner, [1, 0])
        self.assertTrue(control.ownership_changed)
        fake.refuse_restore = False
        self.assertEqual(control.restore(), [])
        self.assertEqual(fake.owner, [0, 0])

    def test_worker_applies_and_releases_rgb_without_disconnect(self):
        from test_g502 import FakeHid
        led = FakeLighting()
        fake = FakeHid(lighting=led)
        ready, applied, restored = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def hardware(data):
            if data['kind'] == 'ready': ready.set()
            if data['kind'] == 'lighting': applied.set()
            if data['kind'] == 'lighting_restore': restored.set()
        session = G502Session(SimpleNamespace(id='123456789abcdef'), lambda *a:None, lambda *a:None, errors.append, hardware)
        with patch('nexus.g502.ghub_running', return_value=False), patch('nexus.g502.matches_device', return_value=True), \
             patch('nexus.g502.hid.enumerate', return_value=[{'path':b'test','usage_page':0xff00,'usage':2}]), \
             patch('nexus.g502.hid.device', return_value=fake):
            try:
                session.start()
                self.assertTrue(ready.wait(1))
                session.set_lighting({0: dict(effect=1, color='#ff0000')})
                self.assertTrue(applied.wait(1))
                session.restore_lighting()
                self.assertTrue(restored.wait(1))
                self.assertTrue(session.ready)
                self.assertEqual(led.effects, led.original)
            finally:
                self.assertTrue(session.close())
        self.assertEqual(fake.mapping[:2], [1, 2])
        self.assertEqual(errors, [])


class LightingPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_zone_edit_sync_persistence_and_sensor_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = Device('123456789abcdef', 'G502', 'mouse', 'Logitech', '046D', 'C08B', [], [])
            window.open_device(device)
            window.tabs.setCurrentIndex(2)
            self.assertTrue(window.assignment_sidebar.isHidden())
            panel = window.lighting_panel
            panel.set_color('#00b7ed')
            panel.brightness.setValue(65)
            panel.sync_zones()
            panel.load_device(device)
            self.assertEqual(panel.configs[0], panel.configs[1])
            self.assertEqual(panel.configs[1]['brightness'], 65)
            fake = FakeLighting()
            control = LightingControl(fake.request, 2)
            zones = control.load()
            session = SimpleNamespace(ready=True, device=device, lighting=control,
                set_lighting=Mock(), restore_lighting=Mock(), close=lambda:True)
            window.g502 = session
            panel.hardware_changed({'kind':'ready', 'device_id':device.id, 'lighting':zones})
            panel.control.setChecked(True)
            session.set_lighting.assert_called_once()
            self.assertFalse(panel.active)
            panel.hardware_changed({'kind':'lighting', 'device_id':device.id})
            self.assertTrue(panel.active)
            panel.control.setChecked(False)
            session.restore_lighting.assert_called_once()
            panel.hardware_changed({'kind':'lighting_restore', 'device_id':device.id})
            self.assertFalse(panel.active)
            window.g502 = None

    def test_generic_device_keeps_preview_without_claiming_hardware_control(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            window.open_device(Device('generic', 'Mouse', 'mouse', 'Generic', '', '', [], []))
            panel = window.lighting_panel
            self.assertFalse(panel.control.isEnabled())
            panel.set_color('#aabbcc')
            panel.hex.setText('invalid')
            panel.hex_edited()
            self.assertEqual(panel.hex.text(), '#aabbcc')
            self.assertIn('Vista previa', panel.status_label.text())
