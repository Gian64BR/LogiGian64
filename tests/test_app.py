import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from nexus.core import Store
from nexus.studio import StudioWindow as MainWindow
from nexus.studio_widgets import STYLE


class ApplicationTests(unittest.TestCase):
    def test_empty_assignment_starts_macro_creation_instead_of_error(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(Path(directory)))
            self.addCleanup(window.exit_application)
            window.open_device(window.devices[0])
            with patch.object(window, 'new_macro', return_value='new') as create, patch.object(window, 'error') as error:
                window.assign_macro_target('G4')
                create.assert_called_once()
                error.assert_not_called()
                self.assertEqual(window._pending_macro_target, (window.device.id, 'G4'))

    def test_g502_assignment_connects_then_resumes_calibration(self):
        from unittest.mock import patch
        from nexus.windows import Device
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active['macros'].append({'id': 'm', 'name': 'Macro', 'events': [{'type': 'wait', 'delay_ms': 50}]})
            window = MainWindow(store)
            self.addCleanup(window.exit_application)
            device = Device('123456789abcdef', 'G502 HERO', 'mouse', 'Logitech', '046D', 'C08B', [], [])
            window.open_device(device)
            def connect():
                window.g502 = SimpleNamespace(ready=False, close=lambda: True)
            with patch.object(window, 'activate_g502', side_effect=connect) as activate:
                window.assign_macro_target('G4', 'm')
                activate.assert_called_once()
            window.g502.ready = True
            window.g502.handle = -1
            with patch('nexus.app.QTimer.singleShot') as later:
                window.hardware_changed({'kind': 'ready', 'device_id': device.id, 'dpi': None})
                self.assertEqual(later.call_count, 1)
                self.assertIsNone(window._pending_binding)
            window.g502 = None

    def test_window_close_keeps_running_until_tray_exit(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QSystemTrayIcon
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(Path(directory)))
            self.addCleanup(lambda: window.exit_application() if not getattr(window, "_closing", False) else None)
            window.show()
            with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True), \
                 patch.object(window.player, "stop", wraps=window.player.stop) as stop, \
                 patch.object(window, "leave_editor", wraps=window.leave_editor) as leave:
                self.assertFalse(window.close())
                self.assertFalse(window.isVisible())
                self.assertTrue(window.tray.isVisible())
                stop.assert_not_called()
                leave.assert_not_called()
                window.restore()
                self.assertTrue(window.isVisible())
                exit_action = next(a for a in window.tray.contextMenu().actions() if a.text() == "Salir")
                exit_action.trigger()
                self.assertFalse(window.isVisible())
                self.assertFalse(window.tray.isVisible())
                stop.assert_called()
                leave.assert_called_once()
            self.doCleanups()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def test_generic_disable_is_immediate_and_persistent(self):
        from unittest.mock import patch
        from nexus.windows import Device
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            macro = {"id": "m", "name": "Click", "events": []}
            store.active["macros"].append(macro)
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            device = Device("b" * 24, "KNUP KP-V84", "mouse", "KNUP", "30FA", "0400", [], [123])
            window.open_device(device)
            store.active["bindings"].append({"device_id": device.id, "macro_id": "m", "slot": "Lateral 4",
                "enabled": True, "trigger": {"type": "mouse", "button": "x1"}})
            with patch.object(window, "error") as error:
                window.set_control_state("Lateral 4", True)
                window.set_control_state("Lateral 5", True)
                error.assert_not_called()
            self.assertEqual(store.active["bindings"], [])
            self.assertEqual(window.canvas.disabled, {"Lateral 4", "Lateral 5"})
            self.assertEqual(len(Store(Path(directory)).active["disabled_controls"]), 2)
            window.set_control_state("Lateral 4", False)
            self.assertEqual(window.canvas.disabled, {"Lateral 5"})
            window.exit_application()

    def test_library_context_rename_delete_and_rail_selection(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active["macros"].append({"id": "m", "name": "Original", "events": []})
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            window.open_device(window.devices[0])
            self.assertEqual(window.assign_library.item(0).text(), "Original")
            with patch.object(QInputDialog, "getText", return_value=("Nuevo", True)):
                window.rename_library_macro(window.assign_library.item(0))
            self.assertEqual(Store(Path(directory)).active["macros"][0]["name"], "Nuevo")
            for index in (3, 2, 0):
                window.rail_buttons[index].click()
                self.assertEqual([k for k, b in window.rail_buttons.items() if b.isChecked()], [index])
            item = window.assign_library.item(0)
            seen = []
            class TestMenu(QMenu):
                def exec(self, *args):
                    seen.extend(a.text() for a in self.actions())
                    return self.actions()[2]
            with patch("nexus.studio.QMenu", TestMenu), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                window.library_context_menu(window.assign_library.visualItemRect(item).center())
            self.assertEqual(seen, ["Editar", "Renombrar", "Eliminar"])
            self.assertEqual(Store(Path(directory)).active["macros"], [])
            window.exit_application()

    def test_save_returns_to_assignments_and_standard_delay_updates_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active["macros"].append({"id": "m", "name": "Macro", "events": []})
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            window.open_device(window.devices[0])
            window.tabs.setCurrentIndex(1)
            window.draft = [{"type": "mouse", "button": "left", "down": down, "delay_ms": 123}
                            for down in (True, False)]
            window.render_events()
            window.standard_delay.setChecked(True)
            self.assertEqual([e["delay_ms"] for e in window.draft], [50, 50])
            self.assertEqual([window.table.cellWidget(i, 3).value() for i in range(2)], [50, 50])
            window.delay_ms.setValue(75)
            self.assertEqual([e["delay_ms"] for e in window.draft], [75, 75])
            window.standard_delay.setChecked(False)
            self.assertTrue(window.table.cellWidget(0, 3).isEnabled())
            window.standard_delay.setChecked(True)
            self.assertFalse(window.table.cellWidget(0, 3).isEnabled())
            window.save_macro()
            self.assertEqual(window.stack.currentIndex(), 1)
            self.assertEqual([e["delay_ms"] for e in Store(Path(directory)).active["macros"][0]["events"]], [75, 75])
            window.exit_application()

    def test_recorder_accepts_clicks_in_nexus_and_preserves_large_handles(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active["macros"].append({"id": "m", "name": "Macro", "events": []})
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            window.open_device(window.devices[0])
            received = []
            window.events.input.connect(lambda handle, event: received.append(handle))
            window.recording = True
            window.draft = []
            window.record_held = {}
            with patch.object(QApplication, "widgetAt", return_value=window.canvas):
                for down in (True, False):
                    window.events.input.emit(2 ** 40, {"type": "mouse", "button": "left", "down": down})
            self.assertEqual(received, [2 ** 40, 2 ** 40])
            self.assertEqual([e["down"] for e in window.draft], [True, False])
            window.finish_recording()
            window.exit_application()

    def test_generic_side_assignment_is_ready_without_learning_and_runs(self):
        from nexus.studio_widgets import LearnBindingDialog
        from nexus.windows import Device
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            macro = {"id": "m", "name": "Macro", "events": [
                {"type": "key", "vk": 65, "scan": 30, "down": down, "delay_ms": 0} for down in (True, False)]}
            store.active["macros"].append(macro)
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            device = Device("b" * 24, "KNUP KP-V84", "mouse", "KNUP", "30FA", "0400", [], [2 ** 40])
            window.devices.append(device)
            window.open_device(device)
            dialog = LearnBindingDialog(window, device, [macro], "Lateral 4")
            self.assertTrue(dialog.save_button.isEnabled())
            self.assertEqual(dialog.trigger, {"type": "mouse", "button": "x1"})
            store.active["bindings"].append(dialog.binding())
            sent = []
            window.player.sender = lambda event: sent.append(event)
            window.events.input.emit(2 ** 40, {"type": "mouse", "button": "x1", "down": True})
            self.assertTrue(window.player.wait_idle())
            self.assertEqual([e["down"] for e in sent], [True, False])
            window.events.input.emit(2 ** 40, {"type": "mouse", "button": "x1", "down": False})
            window.exit_application()

    def test_click_without_macros_opens_control_menu(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMenu
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Store(Path(directory)))
            self.addCleanup(window.player.close)
            window.open_device(__import__("nexus.windows", fromlist=["Device"]).Device("a" * 24, "G502 HERO", "mouse", "Logitech", "046D", "C08B", [], []))
            actions_seen = []
            def choose_default(menu, *args):
                actions_seen.extend(a.text() for a in menu.actions())
                return menu.actions()[0]
            class TestMenu(QMenu):
                def exec(self, *args):
                    return choose_default(self, *args)
            with patch("nexus.studio.QMenu", TestMenu), patch.object(window, "error") as error:
                window.assign_target("G4")
                error.assert_not_called()
            self.assertIn("Usar predeterminada", actions_seen)
            self.assertIn("Desactivar", actions_seen)
            self.assertEqual(window.store.active["macros"], [])
            window.exit_application()

    def test_disable_persists_suppresses_and_default_restores(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            window = MainWindow(store)
            self.addCleanup(window.player.close)
            device = __import__("nexus.windows", fromlist=["Device"]).Device("a" * 24, "G502 HERO", "mouse", "Logitech", "046D", "C08B", [], [])
            window.open_device(device)
            store.active["macros"].append({"id": "m", "name": "Macro", "events": []})
            store.active["bindings"].append({"device_id": device.id, "macro_id": "m", "slot": "G4",
                "enabled": True, "trigger": {"type": "gbutton", "button": 3}})
            session = SimpleNamespace(ready=True, device=device, update_buttons=Mock())
            window.g502 = session
            window.set_control_state("G4", True)
            self.assertEqual(store.active["bindings"], [])
            self.assertIn("G4", window.canvas.disabled)
            self.assertIn(3, session.update_buttons.call_args.args[0])
            self.assertEqual(Store(Path(directory)).active["disabled_controls"][0]["button"], 3)
            window.canvas.overlay.grab()
            self.assertNotIn("G4", window.canvas.label_rects)
            window.set_control_state("G4", False)
            self.assertNotIn("G4", window.canvas.disabled)
            self.assertEqual(Store(Path(directory)).active["disabled_controls"], [])
            self.assertNotIn(3, session.update_buttons.call_args.args[0])
            window.g502 = None
            window.exit_application()

    def test_editor_persistence_recording_and_device_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active["macros"].append({"id": "test", "name": "Original", "events": []})
            window = MainWindow(store)
            sent = []
            window.player.sender = lambda event: sent.append(event.copy())
            self.addCleanup(window.player.close)
            self.assertGreater(len(window.devices), 0, "Native device discovery must work on this workstation")
            window.open_device(window.devices[0])
            window.tabs.setCurrentIndex(1)
            window.macro_name.setText("Edited macro")
            window.draft = [{"type": "key", "vk": 65, "scan": 30, "down": True, "delay_ms": 0},
                            {"type": "key", "vk": 65, "scan": 30, "down": False, "delay_ms": 40}]
            window.render_events()
            self.assertTrue(window.commit_draft())
            self.assertEqual(Store(Path(directory)).active["macros"][0]["name"], "Edited macro")
            # Recorder stops with F8 and adds missing releases to its own capture.
            window.recording = True
            window.draft = []
            window.render_events()
            window.last_record_time = 0
            window.on_input(window.devices[0].handles[0], {"type": "key", "vk": 66, "scan": 48, "extended": False, "down": True})
            window.on_input(window.devices[0].handles[0], {"type": "key", "vk": 119, "scan": 66, "extended": False, "down": True})
            self.assertFalse(window.recording)
            self.assertEqual([e["down"] for e in window.draft], [True, False])
            self.assertTrue(window.commit_draft())
            device = window.devices[0]
            store.active["bindings"].append({"device_id": device.id, "macro_id": "test", "enabled": True,
                                            "trigger": {"type": "mouse", "button": "x1"}})
            window.on_input(device.handles[0], {"type": "mouse", "button": "x1", "down": True})
            self.assertTrue(window.player.wait_idle())
            self.assertEqual([e["down"] for e in sent], [True, False], "Execution must start on press, before physical release")
            window.on_input(device.handles[0], {"type": "mouse", "button": "x1", "down": False})
            window.armed.setChecked(False)
            window.on_input(device.handles[0], {"type": "mouse", "button": "x1", "down": True})
            window.on_input(device.handles[0], {"type": "mouse", "button": "x1", "down": False})
            self.assertTrue(window.player.wait_idle())
            self.assertEqual(len(sent), 2)
            window.exit_application()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
