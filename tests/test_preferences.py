import unittest
from unittest.mock import patch, MagicMock
from nexus import preferences

class StartupTests(unittest.TestCase):
    def test_enable_quotes_executable_and_passes_startup_flag(self):
        key = MagicMock()
        with patch.object(preferences.winreg, 'CreateKey', return_value=key), patch.object(preferences.winreg, 'SetValueEx') as write, patch.object(preferences.sys, 'frozen', True, create=True), patch.object(preferences.sys, 'executable', r'C:\Program Files\LogiGian64\LogiGian64.exe'):
            preferences.set_startup(True)
            self.assertEqual(write.call_args.args[-1], '"C:\\Program Files\\LogiGian64\\LogiGian64.exe" --startup')

    def test_disable_only_removes_our_entry_and_is_idempotent(self):
        with patch.object(preferences.winreg, 'CreateKey', return_value=MagicMock()), patch.object(preferences.winreg, 'DeleteValue', side_effect=FileNotFoundError) as delete:
            preferences.set_startup(False)
            self.assertEqual(delete.call_args.args[1], 'LogiGian64')

    def test_absent_registration_is_disabled(self):
        with patch.object(preferences.winreg, 'OpenKey', side_effect=FileNotFoundError):
            self.assertFalse(preferences.startup_enabled())
