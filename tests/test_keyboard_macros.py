import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu
from nexus.core import Store, new_profile, validate_profile
from nexus.keyboard_support import FUNCTION_KEYS
from nexus.studio import StudioWindow
from nexus.studio_widgets import HardwareArt, LearnBindingDialog, reference_image
from nexus.windows import Device


def keyboard(identity='keyboard-a', handles=None):
    return Device(identity, 'Redragon KUMARA K552RGB-1', 'keyboard', 'Redragon', '0C45', '5004', [], handles or [101, 102])


def macro():
    return {'id':'m', 'name':'Prueba', 'mode':'once', 'events':[
        {'type':'key','vk':65,'scan':30,'down':True,'delay_ms':0},
        {'type':'key','vk':65,'scan':30,'down':False,'delay_ms':0}]}


class KeyboardMacroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_original_photo_is_selected_only_for_confirmed_kumara_model(self):
        device = keyboard()
        path = reference_image(device)
        self.assertTrue(path.is_file())
        self.assertEqual(path.suffix, '.jpg')
        art = HardwareArt(device)
        self.assertEqual((art.picture.width(), art.picture.height()), (1500, 607))
        self.assertEqual(art.source_rect().width(), 1396)
        other = keyboard()
        other.name = 'Teclado USB · 0C45:5004'
        self.assertIsNone(reference_image(other))
        other.name = 'Red Dragon K552RGB-1'
        self.assertEqual(reference_image(other), path)
        art.close()

    def test_keyboard_targets_are_only_f1_through_f12_at_all_window_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            window.open_device(keyboard())
            window.show()
            for size in ((1100,790), (1920,1032)):
                window.resize(*size)
                self.app.processEvents()
                window.canvas.arrange()
                window.canvas.overlay.grab()
                self.assertEqual(set(window.canvas.points), set(FUNCTION_KEYS))
                self.assertEqual(set(window.canvas.label_rects), set(FUNCTION_KEYS))
                for slot, point in window.canvas.points.items():
                    self.assertEqual(window.canvas.slot_at(point), slot)
                self.assertEqual(window.canvas.slot_at(QPointF(0,0)), '')
            self.assertTrue(window.side_view_button.isHidden())

    def test_all_function_keys_are_ready_without_physical_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = keyboard()
            for slot, vk in FUNCTION_KEYS.items():
                dialog = LearnBindingDialog(window, device, [macro()], slot, 'm')
                self.assertTrue(dialog.save_button.isEnabled())
                expected = {'type':'key','vk':vk,'mods':[]}
                self.assertEqual(dialog.trigger, expected)
                dialog.observe(101, {'type':'key','vk':65,'down':True})
                self.assertEqual(dialog.trigger, expected)
                dialog.close()

    def test_assignment_persists_and_other_keys_cannot_be_assigned_or_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active['macros'].append(macro())
            window = StudioWindow(store)
            self.addCleanup(window.exit_application)
            window.open_device(keyboard())
            with patch.object(QDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
                window.assign_macro_target('F6', 'm')
            binding = Store(Path(directory)).active['bindings'][0]
            self.assertEqual(binding['slot'], 'F6')
            self.assertEqual(binding['trigger'], {'type':'key','vk':117,'mods':[]})
            with patch.object(window, 'leave_editor') as leave:
                window.assign_macro_target('A', 'm')
                window.assign_target('Tecla', 'm')
                leave.assert_not_called()
            window.set_control_state('A', True)
            window.set_control_state('F6', True)
            self.assertEqual(len(store.active['bindings']), 1)
            window.set_control_state('F6', False)
            self.assertEqual(store.active['bindings'], [])

    def test_fn_macros_are_device_scoped_and_f8_f12_keep_reserved_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active['macros'].append(macro())
            window = StudioWindow(store)
            self.addCleanup(window.exit_application)
            device, other = keyboard(), keyboard('keyboard-b', [201])
            window.devices = [device, other]
            sent = []
            window.player.sender = lambda event:sent.append(event.copy())
            with patch('nexus.windows.modifiers', return_value=set()):
                for slot, vk in FUNCTION_KEYS.items():
                    store.active['bindings'] = [{'device_id':device.id,'macro_id':'m','enabled':True,'slot':slot,
                                                'trigger':{'type':'key','vk':vk,'mods':[]}}]
                    sent.clear()
                    window.on_input(201, {'type':'key','vk':vk,'down':True})
                    window.on_input(201, {'type':'key','vk':vk,'down':False})
                    self.assertEqual(sent, [])
                    window.on_input(101, {'type':'key','vk':vk,'down':True})
                    self.assertTrue(window.player.wait_idle())
                    self.assertEqual([e['down'] for e in sent], [True,False], slot)
                    window.on_input(101, {'type':'key','vk':vk,'down':False})
                sent.clear()
                store.active['bindings'] = [{'device_id':device.id,'macro_id':'m','enabled':True,'slot':'A',
                                            'trigger':{'type':'key','vk':65,'mods':[]}}]
                window.on_input(101, {'type':'key','vk':65,'down':True})
                self.assertEqual(sent, [])
                window.recording = True
                with patch.object(window, 'finish_recording') as stop, patch.object(window, 'restore'):
                    window.on_input(101, {'type':'key','vk':119,'down':True})
                    stop.assert_called_once()
                window.recording = False
            with patch('nexus.windows.modifiers', return_value={'Ctrl','Alt'}), patch.object(window, 'emergency_stop') as emergency:
                window.on_input(101, {'type':'key','vk':123,'down':True})
                emergency.assert_called_once()

    def test_profiles_keep_fn_triggers_and_omit_old_non_function_key_assignments(self):
        profile = new_profile()
        profile['macros'] = [macro()]
        profile['bindings'] = [{'device_id':'keyboard-a','macro_id':'m','slot':'Tecla',
                                'trigger':{'type':'key','vk':vk,'mods':[]}} for vk in (65,112,119,123)]
        profile['disabled_controls'] = [{'device_id':'keyboard-a','slot':'F1','button':None}]
        clean = validate_profile(profile)
        self.assertEqual([b['slot'] for b in clean['bindings']], ['F1','F8','F12'])
        self.assertEqual(clean['disabled_controls'], [])
        self.assertEqual(len(clean['macros']), 1)

    def test_left_panel_can_disable_and_reactivate_without_deleting_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active['macros'].append(macro())
            window = StudioWindow(store)
            self.addCleanup(window.exit_application)
            device = keyboard()
            window.devices = [device]
            window.open_device(device)
            with patch.object(QDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
                window.assign_macro_target('F6', 'm')
            window.canvas.selected = ''
            window.binding_list.setCurrentRow(0)
            self.assertEqual(window.canvas.selected, 'F6')
            self.assertTrue(window.keyboard_macro_button.isEnabled())
            window.keyboard_macro_button.click()
            clean = Store(Path(directory)).active
            self.assertFalse(clean['bindings'][0]['enabled'])
            self.assertEqual(len(clean['macros'][0]['events']), 2)
            self.assertIn('F6', window.canvas.paused)
            self.assertEqual(window.keyboard_macro_button.text(), 'ACTIVAR MACRO')
            sent = []
            window.player.sender = lambda event:sent.append(event.copy())
            with patch('nexus.windows.modifiers', return_value=set()):
                window.on_input(101, {'type':'key','vk':117,'down':True})
                window.on_input(101, {'type':'key','vk':117,'down':False})
                self.assertEqual(sent, [])
                window.keyboard_macro_button.click()
                window.on_input(101, {'type':'key','vk':117,'down':True})
                self.assertTrue(window.player.wait_idle())
                self.assertEqual([e['down'] for e in sent], [True,False])
                window.on_input(101, {'type':'key','vk':117,'down':False})
            self.assertTrue(Store(Path(directory)).active['bindings'][0]['enabled'])
            self.assertNotIn('F6', window.canvas.paused)

    def test_right_click_context_menu_disables_and_reactivates(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active['macros'].append(macro())
            window = StudioWindow(store)
            self.addCleanup(window.exit_application)
            window.open_device(keyboard())
            with patch.object(QDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
                window.assign_macro_target('F6', 'm')
            window.show()
            self.app.processEvents()
            window.canvas.overlay.grab()
            seen = []
            class Menu(QMenu):
                def exec(self, *args):
                    actions = self.actions()
                    seen.append([a.text() for a in actions])
                    return next(a for a in actions if a.text() in ('Desactivar macro','Activar macro'))
            with patch('nexus.studio.QMenu', Menu):
                QTest.mouseClick(window.canvas, Qt.MouseButton.RightButton, pos=window.canvas.points['F6'].toPoint())
                self.assertFalse(store.active['bindings'][0]['enabled'])
                QTest.mouseClick(window.canvas, Qt.MouseButton.RightButton, pos=window.canvas.points['F6'].toPoint())
                self.assertTrue(store.active['bindings'][0]['enabled'])
            self.assertIn('Desactivar macro', seen[0])
            self.assertIn('Activar macro', seen[1])
            self.assertEqual(len(seen), 2)

    def test_disabling_stops_only_the_selected_key_and_releases_held_outputs(self):
        import threading
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            value = macro()
            value['mode'] = 'latch'
            store.active['macros'].append(value)
            window = StudioWindow(store)
            self.addCleanup(window.exit_application)
            device = keyboard()
            window.devices = [device]
            window.open_device(device)
            store.active['bindings'] = [{'device_id':device.id,'macro_id':'m','slot':slot,'enabled':True,
                'trigger':{'type':'key','vk':vk,'mods':[]}} for slot,vk in [('F5',116),('F6',117)]]
            sent = []
            pressed = threading.Event()
            def send(event):
                sent.append(event.copy())
                if event.get('down'): pressed.set()
            window.player.sender = send
            with patch('nexus.windows.modifiers', return_value=set()):
                window.on_input(101, {'type':'key','vk':116,'down':True})
                self.assertTrue(pressed.wait(1))
                window.set_keyboard_macro_enabled('F6', False)
                self.assertTrue(window.player.busy)
                window.set_keyboard_macro_enabled('F5', False)
                self.assertTrue(window.player.wait_idle())
            self.assertEqual([e['down'] for e in sent], [True,False])
