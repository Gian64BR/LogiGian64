import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog
from nexus.core import Store, new_profile
from nexus.studio import StudioWindow
from nexus.studio_widgets import TypeDialog

class CreationAndProfileTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_creation_skips_name_prompt_and_avoids_existing_numbered_names(self):
        with tempfile.TemporaryDirectory() as directory:
            window = StudioWindow(Store(Path(directory)))
            try:
                window.store.active['macros'] = [dict(id=str(i), name=name, mode='once', events=[]) for i, name in enumerate(['Macro 1', 'macro 2', 'Personalizada'])]
                with patch('nexus.studio.QInputDialog.getText') as prompt, patch('nexus.studio.TypeDialog') as dialog:
                    dialog.return_value = SimpleNamespace(mode='hold', macro_name='Mi macro', exec=lambda: QDialog.DialogCode.Accepted)
                    window.new_macro()
                    prompt.assert_not_called()
                    self.assertEqual(dialog.call_args.args[1], 'Macro 3')
                    self.assertEqual(window.store.active['macros'][-1]['name'], 'Mi macro')
                    self.assertEqual(window.store.active['macros'][-1]['mode'], 'hold')
                    dialog.return_value = SimpleNamespace(exec=lambda: QDialog.DialogCode.Rejected)
                    window.new_macro()
                    self.assertEqual(len(window.store.active['macros']), 4)
            finally:
                window.macro_id = None
                window.exit_application()

    def test_type_dialog_uses_editable_name_and_default_when_empty(self):
        dialog = TypeDialog(None, 'Macro 7')
        dialog.name_edit.setText('  Saltar  ')
        self.assertEqual(dialog.macro_name, 'Saltar')
        dialog.name_edit.clear()
        self.assertEqual(dialog.macro_name, 'Macro 7')
        dialog.choose('sequence')
        self.assertEqual(dialog.mode, 'sequence')
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.deleteLater()

    def test_profile_cards_reflow_and_activate_the_selected_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.profiles[:] = [new_profile(n) for n in ['Escritorio', 'Juegos', 'Trabajo', 'Otros']]
            store.active_id = store.profiles[0]['id']
            window = StudioWindow(store)
            try:
                window.go_profiles()
                window.resize(1280, 760)
                window.show()
                self.app.processEvents()
                wide = window.profile_list.visualItemRect(window.profile_list.item(2)).y()
                window.resize(1000, 700)
                self.app.processEvents()
                narrow = window.profile_list.visualItemRect(window.profile_list.item(2)).y()
                self.assertGreater(narrow, wide)
                target = store.profiles[1]['id']
                window.profile_card_action(1, window.activate_profile)
                self.assertEqual(store.active_id, target)
                self.assertEqual(window.profile_list.item(1).data(256), target)
            finally:
                window.macro_id = None
                window.exit_application()
