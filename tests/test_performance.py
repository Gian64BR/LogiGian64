"""Regression coverage for the input and editor performance paths."""
import ctypes as C
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from nexus import windows as win
from nexus.core import Store
from nexus.studio import StudioWindow
from nexus.macro_engine import MacroEngine, Session


class RawInputTests(unittest.TestCase):
    def packet(self, payload, kind, padding=0):
        header = win.RAWINPUTHEADER()
        header.kind, header.device = kind, 2 ** 40
        header.size = C.sizeof(header) + C.sizeof(payload) + padding
        return bytes(header) + bytes(payload) + bytes(padding)

    def read(self, packet):
        calls = []
        buffers = []
        def get_data(handle, command, buffer, size, header_size):
            size = C.cast(size, C.POINTER(win.U32))
            calls.append(buffer is None)
            if buffer is None:
                size.contents.value = len(packet)
                return 0
            if size.contents.value < len(packet):
                C.set_last_error(122)
                return 0xFFFFFFFF
            buffers.append(C.addressof(buffer))
            C.memmove(buffer, packet, len(packet))
            size.contents.value = len(packet)
            return len(packet)
        with patch.object(win.user32, 'GetRawInputData', side_effect=get_data):
            first = win.read_input(1)
            second = win.read_input(2)
        self.assertEqual(first, second)
        self.assertEqual(buffers[-1], buffers[-2])
        return first, calls

    def setUp(self):
        if hasattr(win._input_storage, 'buffer'):
            del win._input_storage.buffer

    def test_motion_buttons_wheels_and_large_handles(self):
        for flags in (0, 0xFFF):
            mouse = win.RAWMOUSE()
            mouse.button.split.flags = flags
            mouse.button.split.data = 0xFF88
            (handle, events), calls = self.read(self.packet(mouse, 0))
            self.assertEqual(handle, 2 ** 40)
            self.assertEqual(calls, [False, False])
            self.assertEqual(len(events), 12 if flags else 0)
            if flags:
                self.assertEqual([e['delta'] for e in events[-2:]], [-120, -120])

    def test_keys_and_injected_packets(self):
        key = win.RAWKEYBOARD()
        key.vk, key.scan, key.flags = 65, 30, 3
        result, _ = self.read(self.packet(key, 1))
        self.assertEqual(result[1], [dict(type='key', vk=65, scan=30, extended=True, down=False)])
        key.extra = 0x4E584853
        self.assertIsNone(self.read(self.packet(key, 1))[0])

    def test_larger_packet_grows_once_and_truncated_packet_is_ignored(self):
        result, calls = self.read(self.packet(win.RAWMOUSE(), 0, 512))
        self.assertEqual(result, (2 ** 40, []))
        self.assertEqual(calls, [False, True, False, False])
        self.assertIsNone(self.read(b'bad')[0])


class EditorPerformanceTests(unittest.TestCase):
    def test_lighting_cache_reuses_frames_and_invalidates_on_resize_or_image(self):
        from nexus.lighting import LightingPreview
        app = QApplication.instance() or QApplication([])
        device = win.Device('a' * 24, 'G502', 'mouse', 'Logitech', '046D', 'C08B', [], [])
        preview = LightingPreview(device)
        try:
            preview.picture = QPixmap(800, 600)
            preview.picture.fill(Qt.GlobalColor.white)
            preview.resize(400, 300)
            preview.grab()
            first = preview._fitted_picture.cacheKey()
            preview.grab()
            self.assertEqual(preview._fitted_picture.cacheKey(), first)
            preview.resize(300, 200)
            preview.grab()
            resized = preview._fitted_picture.cacheKey()
            self.assertNotEqual(resized, first)
            preview.picture.fill(Qt.GlobalColor.black)
            preview.grab()
            self.assertNotEqual(preview._fitted_picture.cacheKey(), resized)
        finally:
            preview.close()
            preview.deleteLater()

    def test_full_render_cancels_queued_duplicate(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            try:
                window.draft = [dict(type='key', vk=65, down=True, delay_ms=50)]
                window.render_events()
                chips = [window.timeline.itemAt(i).widget() for i in range(window.timeline.count())]
                app.processEvents()
                self.assertEqual(chips, [window.timeline.itemAt(i).widget() for i in range(window.timeline.count())])
                self.assertFalse(window.timeline_timer.isActive())
            finally:
                window.exit_application()


class EmptySequenceTests(unittest.TestCase):
    def test_empty_hold_sleeps_and_release_or_stop_wakes_it(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                sent, sleeping = [], threading.Event()
                session = Session('test', dict(mode='sequence', sections={
                    'press': [dict(type='key', vk=17, down=True, delay_ms=0)],
                    'hold': [],
                    'release': [dict(type='key', vk=17, down=False, delay_ms=0)]}))
                original_wait = session.wake.wait
                def wait(timeout=None):
                    if timeout is None:
                        sleeping.set()
                    else:
                        self.assertEqual(timeout, 0)
                    return original_wait(timeout)
                engine = MacroEngine(sent.append)
                worker = threading.Thread(target=engine._execute, args=(session,))
                try:
                    with patch.object(session.wake, 'wait', side_effect=wait):
                        worker.start()
                        self.assertTrue(sleeping.wait(1))
                        (session.stop if cancel else session.release)()
                        worker.join(1)
                        self.assertFalse(worker.is_alive())
                        self.assertEqual([e['down'] for e in sent], [True, False])
                finally:
                    session.stop()
                    worker.join(1)
                    engine.close()


if __name__ == '__main__':
    unittest.main()
