import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from nexus.core import Store
from nexus.studio import StudioWindow
from nexus.sensitivity import DpiTrack, DEFAULT_LEVELS
from nexus.windows import Device


class SensitivityTests(unittest.TestCase):
    def test_physical_dpi_needs_sensor_confirmation(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = Device('test-g502', 'G502', 'mouse', 'Logitech', '046D', 'C08B', [], [])
            window.open_device(device)
            state = {'minimum': 100, 'maximum': 25600, 'step': 50, 'current': 3200}
            window.g502 = SimpleNamespace(ready=True, device=device, set_dpi=Mock(), close=lambda: True)
            panel = window.sensitivity_panel
            panel.hardware_changed({'kind': 'ready', 'device_id': device.id, 'dpi': state})
            self.assertEqual(panel.track.selected, 3)
            panel.track.set_level(3, 3300)
            panel.apply_timer.stop()
            panel.apply_dpi()
            window.g502.set_dpi.assert_called_once_with(3300)
            self.assertIn('Solicitando', panel.confirmed_label.text())
            self.assertEqual(panel.current_dpi, 3200)
            panel.hardware_changed({'kind': 'dpi', 'device_id': device.id, 'current': 3300})
            self.assertEqual(panel.current_dpi, 3300)
            self.assertIn('confirmado', panel.confirmed_label.text())
            panel.hardware_changed({'kind': 'dpi_error', 'device_id': device.id, 'error': 'Sin respuesta'})
            self.assertIsNone(panel.current_dpi)
            panel.hardware_changed({'kind': 'disconnected', 'device_id': device.id})
            self.assertFalse(panel.connected)
            window.g502 = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_track_drag_and_keyboard_keep_levels_ordered(self):
        track = DpiTrack()
        track.resize(1000, 200)
        track.show()
        start = QPoint(round(track.value_x(1450)), 100)
        end = QPoint(round(track.value_x(1800)), 100)
        QTest.mousePress(track, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(track, end)
        QTest.mouseRelease(track, Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual(track.levels[1], 1800)
        QTest.keyClick(track, Qt.Key.Key_Right)
        self.assertEqual(track.levels[1], 1850)
        track.set_level(1, 25600)
        self.assertEqual(track.levels[1], 2350)
        track.set_level(1, -100)
        self.assertEqual(track.levels[1], 850)
        self.assertEqual(track.x_value(-100), 100)
        self.assertEqual(track.x_value(10000), 25600)
        for value in [100, 1000, 4000, 14800, 25600]:
            self.assertEqual(track.x_value(track.value_x(value)), value)
        track.close()

    def test_save_reload_reset_and_no_sensor_or_windows_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = Device('test-mouse', 'Mouse', 'mouse', 'Generic', '', '', [], [])
            window.open_device(device)
            window.tabs.setCurrentIndex(3)
            self.assertTrue(window.assignment_sidebar.isHidden())
            panel = window.sensitivity_panel
            with patch('nexus.windows.set_pointer_speed') as apply:
                with patch('nexus.sensitivity.QInputDialog.getInt', return_value=(1700, True)):
                    panel.value_buttons[1].click()
                panel.load_device(device)
                self.assertEqual(panel.track.levels[1], 1700)
                other = Device('other-mouse', 'Other', 'mouse', 'Generic', '', '', [], [])
                panel.load_device(other)
                self.assertEqual(panel.track.levels, DEFAULT_LEVELS)
                panel.load_device(device)
                self.assertEqual(panel.track.levels[1], 1700)
                panel.reset_levels()
                self.assertEqual(panel.track.levels, DEFAULT_LEVELS)
                apply.assert_not_called()
            with patch('nexus.windows.set_pointer_speed') as apply:
                panel.speed_slider.setValue(12)
                window.apply_speed()
                apply.assert_called_once_with(12)
            window.preferences().setValue('sensitivity/test-mouse', '[]')
            panel.load_device(device)
            self.assertEqual(panel.track.levels, DEFAULT_LEVELS)
            window.tabs.setCurrentIndex(0)
            self.assertFalse(window.assignment_sidebar.isHidden())
