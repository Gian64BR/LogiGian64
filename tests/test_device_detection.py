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
    def test_assignment_sidebar_preserves_readable_lists_and_scrolls_on_laptops(self):
        app = QApplication.instance() or QApplication([])
        from PySide6.QtGui import QFontDatabase, QFont
        original_font = app.font()
        for filename in ('segoeui.ttf', 'segoeuib.ttf', 'seguisym.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / filename))
        app.setFont(QFont('Segoe UI', 10))
        self.addCleanup(app.setFont, original_font)
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            try:
                device = win.Device('responsive', 'KNUP KP-V84', 'mouse', 'KNUP', '30FA', '0400', [], [], button_count=5)
                window.open_device(device)
                window.show()
                for width, height in [(1280, 660), (1093, 610), (1000, 580), (1920, 1020)]:
                    with self.subTest(width=width, height=height):
                        window.resize(width, height)
                        app.processEvents()
                        app.processEvents()
                        self.assertEqual(window.size().width(), width)
                        self.assertEqual(window.size().height(), height)
                        self.assertGreaterEqual(window.assign_library.height(), 132)
                        self.assertGreaterEqual(window.binding_list.height(), 104)
                        scroll = window.assignment_sidebar
                        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                        self.assertGreaterEqual(window.binding_list.y() - window.assign_library.geometry().bottom() - 1, 5)
                        self.assertTrue(window.device_notice.isHidden())
                        self.assertTrue(window.binding_hint.isHidden())
                        if height == 580:
                            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                        scroll.ensureWidgetVisible(window.remove_binding_button)
                        app.processEvents()
                        button_bottom = window.remove_binding_button.mapTo(scroll.viewport(), window.remove_binding_button.rect().bottomLeft()).y()
                        self.assertLessEqual(button_bottom, scroll.viewport().height())
                        if height == 1020:
                            self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
                        scroll.verticalScrollBar().setValue(0)
                window.tabs.setCurrentIndex(3)
                self.assertTrue(window.assignment_sidebar.isHidden())
                window.tabs.setCurrentIndex(0)
                self.assertFalse(window.assignment_sidebar.isHidden())
            finally:
                window.macro_id = None
                window.exit_application()

    def test_both_mouse_views_share_horizontal_center_without_vertical_shift(self):
        from nexus.studio_widgets import AssignmentCanvas
        app = QApplication.instance() or QApplication([])
        canvas = AssignmentCanvas()
        try:
            for width in (800,1500):
                canvas.resize(width,600)
                for vid,pid in [('046D','C08B'),('30FA','0400')]:
                    device = win.Device(vid+pid,'Mouse','mouse','Mouse',vid,pid,[],[],button_count=5)
                    for side in (False,True):
                        with self.subTest(width=width,vid=vid,pid=pid,side=side):
                            with patch.object(Path,'glob',return_value=[]):
                                canvas.configure(device)
                                canvas.side = side
                                canvas.configure(device)
                            self.assertLessEqual(abs(canvas.art.geometry().center().x()-width/2),1)
                            self.assertEqual(canvas.art.y(),int((600-min(410,600*.72))/2-10))
                            self.assertGreater(canvas.art.height(),canvas.art.width())
        finally:
            canvas.deleteLater()

    def test_mouse_side_views_stay_upright_with_targets_inside_artwork(self):
        from nexus.studio_widgets import AssignmentCanvas
        app = QApplication.instance() or QApplication([])
        canvas = AssignmentCanvas()
        canvas.resize(800,600)
        try:
            for vid,pid in [('046D','C08B'),('30FA','0400')]:
                with self.subTest(vid=vid,pid=pid):
                    device = win.Device(vid+pid,'Mouse','mouse','Mouse',vid,pid,[],[],button_count=5)
                    with patch.object(Path,'glob',return_value=[]):
                        canvas.configure(device)
                        canvas.side = True
                        canvas.configure(device)
                    self.assertGreater(canvas.art.height(),canvas.art.width())
                    for point in canvas.points.values():
                        self.assertTrue(canvas.art.geometry().contains(point.toPoint()))
        finally:
            canvas.deleteLater()

    def test_g502_unreadable_external_picture_uses_bundled_image(self):
        from nexus.studio_widgets import HardwareArt
        app = QApplication.instance() or QApplication([])
        device = win.Device('hero', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [])
        with patch.object(Path, 'glob', return_value=[Path('missing/front_hero.png')]):
            art = HardwareArt(device)
        try:
            self.assertFalse(art.picture.isNull())
            self.assertTrue(art.bundled_g502)
        finally:
            art.deleteLater()

    def test_g502_images_are_bundled_without_ghub_and_in_frozen_build(self):
        import sys
        from PySide6.QtGui import QImage
        from nexus.studio_widgets import reference_image
        device = win.Device('hero', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [], button_count=16)
        root = Path(__file__).resolve().parents[1]
        with patch.object(Path, 'glob', return_value=[]), patch.object(sys, '_MEIPASS', str(root), create=True):
            for side in (False, True):
                path = reference_image(device, side)
                self.assertEqual(path.parent, root / 'assets')
                image = QImage(str(path))
                self.assertFalse(image.isNull())
                self.assertGreater(image.width(), 100)
                self.assertTrue(image.hasAlphaChannel())

    def test_g502_card_uses_physical_controls_without_changing_raw_count(self):
        from PySide6.QtWidgets import QLabel
        from nexus.studio_widgets import HubCard
        app = QApplication.instance() or QApplication([])
        device = win.Device('hero', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [], button_count=16)
        card = HubCard(device)
        try:
            texts = [label.text() for label in card.findChildren(QLabel)]
            self.assertIn('11 controles físicos · G502 HERO', texts)
            self.assertEqual(device.button_count, 16)
        finally:
            card.deleteLater()

    def test_g502_bundled_views_have_correct_aspect_and_button_positions(self):
        from nexus.studio_widgets import AssignmentCanvas
        app = QApplication.instance() or QApplication([])
        device = win.Device('hero', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [])
        canvas = AssignmentCanvas()
        canvas.resize(800, 600)
        try:
            with patch.object(Path, 'glob', return_value=[]):
                canvas.configure(device)
                self.assertTrue(canvas.art.bundled_g502)
                self.assertGreater(canvas.art.height(), canvas.art.width())
                self.assertEqual(set(canvas.points), {'G1','G2','G3','G7','G8','G9','G10','G11'})
                canvas.side = True
                canvas.configure(device)
                self.assertGreater(canvas.art.height(), canvas.art.width())
                self.assertEqual(canvas.art.rotation_degrees, 90)
                self.assertEqual(set(canvas.points), {'G4','G5','G6'})
                for point in canvas.points.values():
                    self.assertTrue(canvas.art.geometry().contains(point.toPoint()))
        finally:
            canvas.deleteLater()

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

    def test_bundled_model_and_photo_without_local_configuration(self):
        from nexus.device_catalog import apply_catalog
        from nexus.studio_widgets import reference_image
        device = keyboard()
        apply_catalog([device])
        self.assertEqual(device.name, 'Redragon K552RGB-1')
        self.assertEqual(Path(reference_image(device)).name, 'redragon-kumara-k552rgb-1.jpg')
        self.assertTrue(Path(reference_image(device)).is_file())

    def test_catalog_preserves_explicit_models_and_other_hardware(self):
        from nexus.device_catalog import apply_catalog
        explicit, other, virtual, named = [keyboard(str(i)) for i in range(4)]
        explicit.name, explicit.identification = 'My keyboard', 'User confirmed'
        other.pid = '5005'
        virtual.virtual = True
        named.name = 'Different specific model'
        apply_catalog([explicit, other, virtual, named])
        self.assertEqual([d.name for d in [explicit,other,virtual,named]],
                         ['My keyboard','USB DEVICE','USB DEVICE','Different specific model'])

    def test_mouse_buttons_are_read_per_raw_input_handle(self):
        import ctypes
        def info(handle, command, pointer, size):
            self.assertEqual(handle, 123)
            self.assertEqual(command, 0x2000000B)
            self.assertEqual(size._obj.value, 32)
            self.assertEqual(pointer._obj.size, 32)
            pointer._obj.kind = 0
            pointer._obj.data.mouse.buttons = 3
            return 32
        with patch.object(win.user32, 'GetRawInputDeviceInfoW', side_effect=info):
            self.assertEqual(win.mouse_button_count(123), 3)
        with patch.object(win.user32, 'GetRawInputDeviceInfoW', return_value=0xFFFFFFFF):
            self.assertIsNone(win.mouse_button_count(123))

    def test_generic_mouse_targets_follow_reported_buttons_and_reset_view(self):
        from nexus.studio_widgets import AssignmentCanvas, reference_image
        app = QApplication.instance() or QApplication([])
        canvas = AssignmentCanvas()
        device = win.Device('simple', 'USB OPTICAL MOUSE', 'mouse', 'HID', '0000', '3825', [], [], button_count=3)
        canvas.configure(device)
        self.assertEqual(set(canvas.points), {'Principal','Secundario','Central'})
        self.assertEqual(reference_image(device).name, 'generic-mouse.png')
        device.button_count = 5
        canvas.configure(device)
        self.assertEqual(set(canvas.points), {'Principal','Secundario','Central','Lateral 4','Lateral 5'})
        canvas.side = True
        simple = win.Device('new', 'Other mouse', 'mouse', 'HID', '1234', '0001', [], [], button_count=2)
        canvas.configure(simple)
        self.assertFalse(canvas.side)
        self.assertEqual(set(canvas.points), {'Principal','Secundario'})
        simple.button_count = None
        canvas.configure(simple)
        self.assertEqual(set(canvas.points), {'Principal','Secundario'})

    def test_basic_mouse_does_not_accept_nonexistent_side_macro_target(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            device = win.Device('simple', 'USB OPTICAL MOUSE', 'mouse', 'HID', '0000', '3825', [], [], button_count=3)
            window.open_device(device)
            with patch.object(window, 'new_macro') as create:
                window.assign_macro_target('Lateral 4')
                create.assert_not_called()
            self.assertTrue(window.direct_button.isHidden())
            self.assertTrue(window.side_view_button.isHidden())
