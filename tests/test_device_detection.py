import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit
from nexus import windows as win
from nexus.device_identity import save_identity, load_identities, apply_identity, resolve_identities
from nexus.core import Store
from nexus.studio import StudioWindow


def keyboard(identity='unit-a'):
    return win.Device(identity, 'USB DEVICE', 'keyboard', 'SONiX', '0C45', '5004', [], [])


class DeviceDetectionTests(unittest.TestCase):
    def test_user_model_is_bound_to_unit_and_matching_usb_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'identities.json'
            device = keyboard()
            save_identity(device, 'Redragon', 'KUMARA K552RGB-1', path)
            self.assertEqual(device.name, 'Redragon KUMARA K552RGB-1')
            self.assertEqual(device.id, 'unit-a')
            saved = load_identities(path)
            same = keyboard()
            apply_identity(same, saved)
            self.assertEqual(same.name, device.name)
            other = keyboard('unit-b')
            apply_identity(other, saved)
            self.assertEqual(other.name, 'USB DEVICE')
            replacement = keyboard()
            replacement.pid = '5005'
            apply_identity(replacement, saved)
            self.assertEqual(replacement.name, 'USB DEVICE')

    def test_invalid_identity_data_is_ignored_or_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'identities.json'
            path.write_text('[]')
            self.assertEqual(load_identities(path), {})
            with self.assertRaises(ValueError):
                save_identity(keyboard(), 'Redragon', 'in\nvalid', path)
            with self.assertRaises(ValueError):
                save_identity(keyboard(), 'Redragon', 'x' * 101, path)

    def test_composite_keyboard_groups_interfaces_without_merging_other_units(self):
        handles = [100, 101, 102, 103]
        paths = {h: f'path-{h}' for h in handles}
        def enumerate_raw(array, count, size):
            count._obj.value = len(handles)
            if array is None:
                return 0
            for index, handle in enumerate(handles):
                array[index].handle, array[index].kind = handle, 1
            return len(handles)
        def ancestry(path):
            return ['HID\\VIRTUAL', 'LGHUBDEVICE\\VID_046D&PID_C232', 'ROOT\\SYSTEM\\1'] if path == 'path-103' else ['HID\\PHYSICAL', 'USB\\PHYSICAL', 'ROOT\\SYSTEM\\1']
        def container(path):
            return 'physical-one' if path in ('path-100', 'path-101') else path
        with patch.object(win.user32, 'GetRawInputDeviceList', side_effect=enumerate_raw), \
             patch.object(win, 'raw_name', side_effect=lambda h: paths[int(h)]), \
             patch.object(win, 'device_strings', return_value=('USB DEVICE', 'SONiX')), \
             patch.object(win, 'device_ancestry', side_effect=ancestry), \
             patch.object(win, 'container_id', side_effect=container), \
             patch('nexus.device_identity.load_identities', return_value={}):
            devices = win.enumerate_devices()
            self.assertEqual(len(devices), 2)
            self.assertEqual(sorted(len(d.handles) for d in devices), [1, 2])
            self.assertEqual({h for d in devices for h in d.handles}, {100, 101, 102})
            diagnostic = win.enumerate_devices(include_virtual=True)
            self.assertEqual(len(diagnostic), 3)
            self.assertEqual([d.handles for d in diagnostic if d.virtual], [[103]])

    def test_unknown_and_physical_root_ancestors_are_not_hidden(self):
        self.assertFalse(win.virtual_ancestry([]))
        self.assertFalse(win.virtual_ancestry(['HID\\VID_046D&PID_C232', 'USB\\VID_046D&PID_C232', 'ROOT\\SYSTEM\\1']))
        self.assertFalse(win.virtual_ancestry(['BTHENUM\\KEYBOARD', 'ROOT\\SYSTEM\\1']))
        self.assertTrue(win.virtual_ancestry(['HID\\KEYBOARD', 'lghubdevice\\virtual']))

    def test_native_parent_walk_uses_present_nodes_and_reaches_virtual_parent(self):
        nodes = {1: 'HID\\LEAF\\INSTANCE', 2: 'LGHUBDEVICE\\VIRTUAL\\INSTANCE', 3: 'ROOT\\SYSTEM\\1'}
        flags = []
        def locate(pointer, name, flag):
            flags.append(flag)
            self.assertEqual(name, 'HID\\LEAF\\INSTANCE')
            pointer._obj.value = 1
            return 0
        def size(pointer, node, flag):
            pointer._obj.value = len(nodes[node.value])
            return 0
        def get_id(node, buf, length, flag):
            buf.value = nodes[node.value]
            return 0
        def parent(pointer, node, flag):
            if node.value == 3:
                return 13
            pointer._obj.value = node.value + 1
            return 0
        fake = SimpleNamespace(CM_Locate_DevNodeW=locate, CM_Get_Device_ID_Size=size,
                               CM_Get_Device_IDW=get_id, CM_Get_Parent=parent)
        with patch.object(win, 'cfgmgr32', fake):
            chain = win.device_ancestry(r'\\?\HID#LEAF#INSTANCE#{GUID}')
        self.assertEqual(chain, list(nodes.values()))
        self.assertEqual(flags, [0])
        self.assertTrue(win.virtual_ancestry(chain))

    def test_model_dialog_saves_name_for_selected_device(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = keyboard()
            window.open_device(device)
            def fill(dialog):
                fields = dialog.findChildren(QLineEdit)
                fields[0].setText('Redragon')
                fields[1].setText('KUMARA K552RGB-1')
                dialog.findChild(QDialogButtonBox).accepted.emit()
                return dialog.result()
            with patch.object(QDialog, 'exec', new=fill), patch('nexus.device_identity.save_identity') as save, patch.object(window, 'refresh_devices'):
                window.identify_device_model()
                save.assert_called_once_with(device, 'Redragon', 'KUMARA K552RGB-1', remember_ports=True)

    def test_confirmed_model_survives_port_change_without_guessing_ambiguous_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'identities.json'
            save_identity(keyboard('old-port'), 'Redragon', 'K552RGB-1', path)
            records = load_identities(path)
            moved = keyboard('new-port')
            resolve_identities([moved], records)
            self.assertEqual(moved.name, 'Redragon K552RGB-1')
            self.assertEqual(moved.id, 'new-port')
            first, second = keyboard('port-a'), keyboard('port-b')
            resolve_identities([first, second], records)
            self.assertEqual([first.name, second.name], ['USB DEVICE','USB DEVICE'])
            records['other'] = {**records['old-port'], 'name':'Other model'}
            unknown = keyboard('port-c')
            resolve_identities([unknown], records)
            self.assertEqual(unknown.name, 'USB DEVICE')
            records.pop('other')
            records['old-port']['remember_ports'] = False
            resolve_identities([unknown], records)
            self.assertEqual(unknown.name, 'USB DEVICE')
