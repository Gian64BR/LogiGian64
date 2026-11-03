import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from nexus.core import Store, new_profile, validate_profile
from nexus.studio import StudioWindow
from nexus.studio_widgets import LearnBindingDialog
from nexus.windows import Device


class MouseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_old_profiles_remove_primary_bindings_without_losing_macros(self):
        profile = new_profile()
        profile['macros'] = [{'id': 'm', 'name': 'Macro', 'events': []}]
        def binding(slot, bit):
            return {'device_id':'mouse', 'macro_id':'m', 'slot':slot, 'trigger':{'type':'gbutton','button':bit}}
        profile['bindings'] = [binding('G1', 3), binding('G4', 0), binding('G5', 1), binding('G4', 3)]
        profile['disabled_controls'] = [{'device_id':'mouse','slot':slot,'button':bit} for slot,bit in [('G1',0),('G2',1),('G4',1),('G5',4)]]
        clean = validate_profile(profile)
        self.assertEqual(len(clean['macros']), 1)
        self.assertEqual([b['trigger']['button'] for b in clean['bindings']], [3])
        self.assertEqual([c['button'] for c in clean['disabled_controls']], [4])

    def test_primary_targets_and_physical_calibration_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = Device('123456789abcdef', 'G502', 'mouse', 'Logitech','046D','C08B',[],[])
            window.open_device(device)
            with patch.object(window, 'new_macro') as create, patch.object(window, 'activate_g502') as connect:
                for slot in ['G1','G2','Principal','Secundario']:
                    window.assign_target(slot)
                    window.assign_macro_target(slot, 'm')
                    window.set_control_state(slot, True)
                create.assert_not_called()
                connect.assert_not_called()
            self.assertEqual(window.store.active.get('disabled_controls', []), [])
            window.g502 = SimpleNamespace(handle=-1, device=device, close=lambda: True)
            window.store.active['bindings'].append({'device_id':device.id, 'macro_id':'m', 'slot':'G4',
                'enabled':True, 'trigger':{'type':'gbutton','button':0}})
            with patch.object(window.player, 'press') as play:
                window.on_input(-1, {'type':'gbutton','button':0,'down':True})
                play.assert_not_called()
            dialog = LearnBindingDialog(window, device, [{'id':'m','name':'Macro'}], 'G4')
            for bit in (0,1):
                dialog.observe(-1, {'type':'gbutton','button':bit,'down':True})
                dialog.observe(-1, {'type':'gbutton','button':bit,'down':False})
                self.assertIsNone(dialog.trigger)
                self.assertFalse(dialog.save_button.isEnabled())
            dialog.observe(-1, {'type':'gbutton','button':3,'down':True})
            dialog.observe(-1, {'type':'gbutton','button':3,'down':False})
            self.assertEqual(dialog.trigger, {'type':'gbutton','button':3})
            self.assertTrue(dialog.save_button.isEnabled())
            for down in (True, False):
                dialog.observe(-1, {'type':'gbutton','button':0,'down':down})
                dialog.observe(-1, {'type':'mouse','button':'left','down':down})
            self.assertEqual(dialog.trigger, {'type':'gbutton','button':3})
            self.assertTrue(dialog.save_button.isEnabled())
            dialog.close()
            window.g502 = None
