import copy
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from nexus import windows as win
from nexus.core import Store, new_profile, validate_profile
from nexus.studio import StudioWindow


class ProfileSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.device = win.Device('hero', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [123])
        for name, value in (('enumerate_devices', [self.device]), ('register_input', None), ('unregister_input', None)):
            guard = patch.object(win, name, return_value=value)
            guard.start()
            self.addCleanup(guard.stop)
        self.window = self.create_window()

    def create_window(self):
        window = StudioWindow(Store(Path(self.directory.name)))
        self.addCleanup(window.exit_application)
        return window

    def session(self, current=800):
        result = SimpleNamespace(device=self.device, ready=True, dpi_state=dict(
            current=current, minimum=100, maximum=25600, step=50),
            set_dpi=Mock(), close=Mock(return_value=True), update_buttons=Mock())
        return result

    def test_close_reopen_reapplies_saved_selection_before_sensor_confirmation(self):
        window = self.window
        window.open_device(self.device)
        panel = window.sensitivity_panel
        panel.track.set_level(1, 1700)
        panel.apply_timer.stop()
        # The user's configuration persists even when shutdown happens before
        # the asynchronous hardware acknowledgement arrives.
        window.exit_application()
        reopened = self.create_window()
        reopened.g502 = self.session(800)
        reopened.hardware_changed(dict(kind='ready', device_id='hero', dpi=reopened.g502.dpi_state))
        reopened.g502.set_dpi.assert_called_once_with(1700, profile_id=reopened.store.active_id)
        reopened.open_device(self.device)
        self.assertEqual(reopened.sensitivity_panel.track.levels[1], 1700)
        self.assertEqual(reopened.sensitivity_panel.track.selected, 1)
        reopened.hardware_changed(dict(kind='dpi', device_id='hero', current=800))
        self.assertEqual(reopened.profile_sensitivity('hero')['dpi'], 1700)

    def test_profile_switch_applies_each_setting_without_late_reply_overwriting_it(self):
        first = self.window.store.active
        first['sensitivity'] = {'hero': dict(dpi=1450, pointer_speed=9)}
        second = new_profile('Juegos')
        second['sensitivity'] = {'hero': dict(dpi=3200, pointer_speed=12)}
        self.window.store.profiles.append(second)
        self.window.g502 = self.session(800)
        self.window.refresh_profiles()
        with patch.object(win, 'pointer_speed', return_value=10), patch.object(win, 'set_pointer_speed') as pointer:
            self.window.profile_combo.setCurrentIndex(1)
            self.window.g502.set_dpi.assert_called_with(3200, profile_id=second['id'])
            pointer.assert_called_with(12)
            self.window.hardware_changed(dict(kind='dpi', device_id='hero', current=1450, profile_id=first['id']))
            self.assertEqual(second['sensitivity']['hero']['dpi'], 3200)
            self.window.profile_combo.setCurrentIndex(0)
            self.window.g502.set_dpi.assert_called_with(1450, profile_id=first['id'])
            pointer.assert_called_with(9)

    def test_legacy_selected_level_migrates_and_profile_export_keeps_settings(self):
        prefs = self.window.preferences()
        prefs.setValue('sensitivity/hero', json.dumps(dict(levels=[800,1700,2400,3200,6400], selected=1)))
        prefs.setValue('dpi/hero', 800)
        self.assertEqual(self.window.profile_sensitivity('hero')['dpi'], 1700)
        self.window.store.save()
        exported = json.loads(json.dumps(self.window.store.active))
        imported = validate_profile(exported)
        self.assertEqual(imported['sensitivity']['hero']['dpi'], 1700)
        self.assertEqual(Store(Path(self.directory.name)).active['sensitivity'], imported['sensitivity'])
        duplicate = copy.deepcopy(imported)
        duplicate['id'] = 'copy'
        self.assertEqual(validate_profile(duplicate)['sensitivity'], imported['sensitivity'])

    def test_windows_pointer_setting_is_saved_and_restored_on_start(self):
        self.window.open_device(self.device)
        with patch.object(win, 'set_pointer_speed') as pointer:
            self.window.speed_slider.setValue(13)
            self.window.apply_speed()
            pointer.assert_called_once_with(13)
        self.window.exit_application()
        reopened = self.create_window()
        with patch.object(win, 'pointer_speed', return_value=10), patch.object(win, 'set_pointer_speed') as pointer:
            reopened.enable_auto_g502()
            reopened.auto_g502_timer.stop()
            pointer.assert_called_once_with(13)

    def test_profile_rejects_invalid_sensitivity_values(self):
        for settings in (dict(dpi=0), dict(pointer_speed=21), dict(selected=6), dict(levels=[800]*5)):
            profile = new_profile()
            profile['sensitivity'] = {'hero': settings}
            with self.assertRaises(ValueError):
                validate_profile(profile)
