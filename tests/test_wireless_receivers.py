import ctypes
import hashlib
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from nexus import windows as win
from nexus.device_identity import save_identity, load_identities
from nexus.studio_widgets import reference_image, AssignmentCanvas


class WirelessReceiverTests(unittest.TestCase):
    def setUp(self):
        self.activity = win._receiver_mouse_activity.copy()
        self.pending = win._pending_receiver_mouse_handles.copy()
        win._receiver_mouse_activity.clear()
        win._pending_receiver_mouse_handles.clear()
        self.addCleanup(self.restore)

    def restore(self):
        win._receiver_mouse_activity.clear()
        win._receiver_mouse_activity.update(self.activity)
        win._pending_receiver_mouse_handles.clear()
        win._pending_receiver_mouse_handles.update(self.pending)

    def collections(self, identity='receiver', vid='1EA7', pid='0066'):
        return {(identity, kind):win.Device(identity, '2.4G Mouse', kind, 'HID', vid, pid, [kind], [handle])
                for kind, handle in [('mouse', 10), ('keyboard', 20)]}

    def test_unknown_receiver_keeps_keyboard_distinct_and_generic(self):
        devices = win.separate_input_collections(self.collections(), {})
        keyboard = next(d for d in devices if d.kind == 'keyboard')
        mouse = next(d for d in devices if d.kind == 'mouse')
        self.assertNotEqual(keyboard.id, mouse.id)
        self.assertEqual(keyboard.handles, [20])
        self.assertEqual(mouse.handles, [10])
        self.assertEqual(reference_image(keyboard).name, 'generic-keyboard.png')
        again = win.separate_input_collections(self.collections(), {})
        self.assertEqual(keyboard.id, next(d.id for d in again if d.kind == 'keyboard'))

    def test_confirmed_keyboard_hides_mouse_until_real_input(self):
        key_id = hashlib.sha256(b'receiver|keyboard').hexdigest()[:24]
        record = {key_id:dict(vid='1EA7',pid='0066',kind='keyboard',receiver_keyboard_only=True)}
        devices = win.separate_input_collections(self.collections(), record)
        self.assertEqual([d.kind for d in devices], ['keyboard'])
        self.assertFalse(win.confirm_receiver_mouse(20))
        self.assertTrue(win.confirm_receiver_mouse(10))
        self.assertEqual({d.kind for d in win.separate_input_collections(self.collections(), record)}, {'keyboard','mouse'})
        win.separate_input_collections({}, record)
        self.assertEqual([d.kind for d in win.separate_input_collections(self.collections(), record)], ['keyboard'])

    def test_g502_retains_legacy_identity_and_both_handles(self):
        devices = win.separate_input_collections(self.collections('g502','046D','C08B'), {})
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].id, 'g502')
        self.assertEqual(devices[0].kind, 'mouse')
        self.assertEqual(set(devices[0].handles), {10,20})

    def test_receiver_activity_refreshes_devices_without_reaching_macro_recorder(self):
        from ctypes import wintypes
        from nexus.app import NativeInput, Events
        events = Events()
        changed, inputs = [], []
        events.changed.connect(lambda: changed.append(True))
        events.input.connect(lambda handle,event: inputs.append((handle,event)))
        native = NativeInput(events)
        message = wintypes.MSG()
        message.message = 0xFF
        click = dict(type='mouse',button='left',down=True)
        with patch('nexus.app.win.read_input', return_value=(10,[dict(type='device_activity'),click])):
            native.nativeEventFilter(None,ctypes.addressof(message))
        self.assertEqual(changed, [True])
        self.assertEqual(inputs, [(10,click)])

    def test_havit_identity_is_local_and_other_receivers_stay_generic(self):
        with tempfile.TemporaryDirectory() as directory:
            device = next(d for d in win.separate_input_collections(self.collections(), {}) if d.kind=='keyboard')
            path = Path(directory)/'identities.json'
            save_identity(device,'Havit','KB830WB',path,remember_ports=False,receiver_keyboard_only=True)
            records = load_identities(path)
            self.assertTrue(records[device.id]['receiver_keyboard_only'])
            self.assertFalse(records[device.id]['remember_ports'])
            self.assertEqual(reference_image(device).name, 'havit-kb830wb.png')
            other = next(d for d in win.separate_input_collections(self.collections('different-receiver'),records) if d.kind=='keyboard')
            self.assertEqual(reference_image(other).name, 'generic-keyboard.png')

    def test_havit_photo_targets_are_on_keyboard_and_do_not_include_mouse(self):
        app = QApplication.instance() or QApplication([])
        device = win.Device('havit','Havit KB830WB','keyboard','Havit','1EA7','0066',[],[])
        canvas = AssignmentCanvas()
        try:
            for width in (580,1100):
                canvas.resize(width,500)
                canvas.configure(device)
                self.assertEqual((canvas.art.picture.width(),canvas.art.picture.height()),(1020,347))
                self.assertGreater(canvas.art.picture.toImage().pixelColor(300,15).alpha(), 240)
                canvas.overlay.grab()
                for slot,point in canvas.points.items():
                    self.assertEqual(canvas.slot_at(point),slot)
                self.assertEqual(set(canvas.points), {f'F{i}' for i in range(1,13)})
        finally:
            canvas.deleteLater()
