import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QComboBox, QSpinBox, QMenu, QDialog
from nexus.core import Store, validate_macro
from nexus.studio import StudioWindow
from nexus.timeline import TimelineBlock
from nexus.dialogs import DelayDialog, AddActionDialog
from nexus.macro_engine import MacroEngine, Session


class MacroEditorTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        store = Store(Path(self.directory.name))
        store.active['macros'] = [dict(id='test', name='Espacio', mode='once', standard_delay=False,
            events=[dict(type='key', vk=32, down=True, delay_ms=0), dict(type='key', vk=32, down=False, delay_ms=50)])]
        self.window = StudioWindow(store)
        self.window.load_macro(0)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.window.macro_id = None
        self.window.exit_application()

    def blocks(self):
        return [self.window.timeline.itemAt(i).widget() for i in range(self.window.timeline.count())
                if isinstance(self.window.timeline.itemAt(i).widget(), TimelineBlock)]

    def settle(self):
        for _ in range(5):
            self.app.processEvents()

    def load_long_macro(self, mode):
        actions = [dict(type='text', text=f'K{i}', delay_ms=0, char_delay_ms=0) for i in range(180)]
        macro = dict(id='long', name='Larga', mode=mode, standard_delay=False, events=actions)
        if mode == 'sequence':
            macro.update(events=[], sections=dict(press=actions, hold=actions, release=actions))
        self.window.store.active['macros'] = [macro]
        self.window.load_macro(0)
        self.window.stack.setCurrentIndex(4)
        self.window.resize(1100, 700)
        self.window.show()
        self.settle()

    def test_table_opens_only_on_request_and_reopening_starts_at_top(self):
        for mode in ('once', 'sequence'):
            with self.subTest(mode=mode):
                self.load_long_macro(mode)
                self.assertTrue(self.window.table.isHidden())
                self.window.select_step(0)
                self.assertTrue(self.window.table.isHidden())
                self.window.toggle_table()
                self.assertFalse(self.window.table.isHidden())
                self.window.select_step(1)
                self.assertFalse(self.window.table.isHidden())
                bar = self.window.timeline_scroll.verticalScrollBar()
                bar.setValue(bar.maximum())
                self.assertGreater(bar.value(), 0)
                self.window.load_macro(0)
                self.settle()
                self.assertTrue(self.window.table.isHidden())
                self.assertEqual(bar.value(), 0)

    def test_delete_visible_chip_keeps_scroll_and_supports_repeated_delete(self):
        for mode, phase in (('once', None), ('sequence', 'press'), ('sequence', 'hold'), ('sequence', 'release')):
            with self.subTest(mode=mode, phase=phase):
                self.load_long_macro(mode)
                scroll = self.window.timeline_scroll
                layout = self.window.phase_layouts[phase] if phase else self.window.single_timeline
                track = self.window.phase_tracks[phase] if phase else self.window.single_timeline_content
                scroll.verticalScrollBar().setValue(track.mapTo(self.window.timeline_wrapper, QPoint(0,0)).y()+200)
                self.settle()
                before = scroll.verticalScrollBar().value()
                chips = [layout.itemAt(i).widget() for i in range(layout.count()) if isinstance(layout.itemAt(i).widget(), TimelineBlock)]
                chip = next(c for c in chips if 10 < c.mapTo(scroll.viewport(), c.rect().center()).y() < scroll.viewport().height()-10)
                QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
                self.settle()
                self.assertTrue(self.window.table.isHidden())
                self.assertEqual(scroll.verticalScrollBar().value(), before)
                QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Delete)
                self.settle()
                self.assertEqual(len(self.window.draft), 179)
                self.assertEqual(scroll.verticalScrollBar().value(), before)
                QTest.keyClick(scroll, Qt.Key.Key_Delete)
                self.settle()
                self.assertEqual(len(self.window.draft), 178)
                self.assertEqual(scroll.verticalScrollBar().value(), before)

    def test_deleted_accidental_keys_leave_only_gaps_between_surviving_actions(self):
        for mode in ('once', 'sequence'):
            with self.subTest(mode=mode):
                actions = [dict(type='key', vk=vk, down=down, delay_ms=0)
                           for vk in (65, 66, 67) for down in (True, False)]
                macro = dict(id='gaps', name='Retardos', mode=mode, standard_delay=True, standard_delay_ms=50, events=actions)
                if mode == 'sequence':
                    macro.update(events=[], sections=dict(press=[], hold=actions, release=[]))
                self.window.store.active['macros'] = [macro]
                self.window.load_macro(0)
                if mode == 'sequence':
                    self.window.select_phase('hold')
                for _ in range(2):
                    row = next(i for i,e in enumerate(self.window.draft) if e.get('vk') == 66)
                    self.window.delete_timeline_step(row)
                self.window.standard_delay.setChecked(False)
                self.assertEqual([e['type'] for e in self.window.draft], ['key','wait','key','wait','key','wait','key'])
                self.assertEqual([e['delay_ms'] for e in self.window.draft if e['type']=='wait'], [50,50,50])
                self.assertEqual([e['vk'] for e in self.window.draft if e['type']=='key'], [65,65,67,67])

    def test_deleting_all_standard_actions_removes_all_generated_waits(self):
        self.window.standard_delay.setChecked(True)
        while self.window.draft:
            self.window.delete_timeline_step(0)
        self.window.standard_delay.setChecked(False)
        self.assertEqual(self.window.draft, [])

    def test_added_manual_delay_is_last_and_switches_off_standard_timing(self):
        self.window.standard_delay.setChecked(True)
        self.window.select_step(0)
        self.window.append_actions([dict(type='wait', delay_ms=123)])
        self.assertFalse(self.window.standard_delay.isChecked())
        self.assertEqual(self.window.draft[-1], dict(type='wait', delay_ms=123, manual=True))
        self.assertTrue(self.window.table.isHidden())

    def test_manual_delay_can_move_to_any_position_in_each_sequence_phase(self):
        actions = [dict(type='text', text='A', delay_ms=0), dict(type='text', text='B', delay_ms=0)]
        self.window.store.active['macros'] = [dict(id='positions', name='Posiciones', mode='sequence',
            standard_delay=False, events=[], sections=dict(press=actions, hold=actions, release=actions))]
        self.window.load_macro(0)
        for phase in ('press', 'hold', 'release'):
            self.window.select_phase(phase)
            self.window.append_actions([dict(type='wait', delay_ms=123)])
            self.assertEqual(self.window.draft[-1]['type'], 'wait')
            self.window.reorder_timeline(2, 0)
            self.assertEqual(self.window.draft[0]['type'], 'wait')
            self.window.reorder_timeline(0, 2)
            self.assertEqual(self.window.draft[1]['type'], 'wait')
            self.window.reorder_timeline(1, 3)
            self.assertEqual(self.window.draft[-1]['type'], 'wait')
        self.assertTrue(self.window.commit_draft())
        self.window.load_macro(0)
        for events in self.window.read_sections().values():
            self.assertEqual([e.get('text') for e in events if e['type']=='text'], ['A','B'])
            self.assertEqual(events[-1], dict(type='wait', delay_ms=123, manual=True))

    def test_explicit_edge_delays_survive_action_deletion_and_reload(self):
        self.window.draft = [dict(type='text', text='A', delay_ms=0), dict(type='text', text='B', delay_ms=0)]
        self.window.render_events()
        self.window.append_actions([dict(type='wait', delay_ms=100)])
        self.window.reorder_timeline(2, 0)
        self.window.append_actions([dict(type='wait', delay_ms=200)])
        self.window.delete_timeline_step(1)
        self.assertTrue(self.window.commit_draft())
        self.window.load_macro(0)
        self.assertEqual([e['type'] for e in self.window.draft], ['wait','text','wait'])
        self.assertEqual([e['delay_ms'] for e in self.window.draft], [100,0,200])

    def test_delay_can_be_added_to_an_empty_macro(self):
        self.window.draft = []
        self.window.render_events()
        self.window.append_actions([dict(type='wait', delay_ms=250)])
        self.assertEqual(self.window.draft, [dict(type='wait', delay_ms=250, manual=True)])

    def test_custom_table_has_press_delay_release_and_standard_updates_gap(self):
        self.assertEqual([event['type'] for event in self.window.draft], ['key','wait','key'])
        self.assertEqual([self.window.table.cellWidget(i,3).value() for i in range(3)], [0,50,0])
        self.assertEqual(len(self.blocks()),3)
        self.window.standard_delay.setChecked(True)
        self.window.delay_ms.setValue(85)
        self.assertEqual([e['delay_ms'] for e in self.window.draft], [0,85,0])
        self.window.standard_delay.setChecked(False)
        self.assertEqual([b.delay for b in self.blocks()], [None,85,None])

    def test_selected_delay_is_highlighted_and_delete_removes_only_delay(self):
        chip = self.blocks()[1]
        QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
        self.assertTrue(chip.is_selected)
        self.assertFalse(self.blocks()[0].is_selected)
        QTest.keyClick(chip, Qt.Key.Key_Delete)
        self.assertEqual([e['type'] for e in self.window.draft], ['key','key'])
        self.assertEqual([e['down'] for e in self.window.draft], [True,False])

    def test_table_delete_and_apply_update_visual_blocks(self):
        spin = self.window.table.cellWidget(1,3)
        spin.setValue(125)
        self.window.apply_steps_button.click()
        self.assertEqual(self.blocks()[1].delay,125)
        self.window.table.selectRow(1)
        QTest.keyClick(self.window.table, Qt.Key.Key_Delete)
        self.assertEqual(len(self.window.draft),2)
        self.assertEqual(len(self.blocks()),2)

    def test_delete_from_numeric_cell_removes_selected_row(self):
        spin = self.window.table.cellWidget(1,3)
        self.window.table.selectRow(1)
        QTest.keyClick(spin.lineEdit(), Qt.Key.Key_Delete)
        self.assertEqual([e['type'] for e in self.window.draft], ['key','key'])

    def test_removing_action_does_not_leave_automatic_edge_delay(self):
        self.window.table.selectRow(2)
        QTest.keyClick(self.window.table, Qt.Key.Key_Delete)
        self.assertEqual([event['type'] for event in self.window.draft], ['key'])

    def test_delay_dialog_and_editor_controls(self):
        dialog = DelayDialog(self.window)
        self.assertEqual(dialog.windowTitle(), 'Acción de retardo')
        self.assertEqual(len(dialog.findChildren(QComboBox)),0)
        self.assertEqual(len(dialog.findChildren(QSpinBox)),1)
        dialog.delay.setValue(90)
        self.assertEqual(dialog.events(), [dict(type='wait',delay_ms=90)])
        texts = [control.text() for control in self.window.editor.findChildren(QPushButton)]
        for removed in ('+  AÑADIR','PRUEBA ÚNICA EN 3 S','DETENER'):
            self.assertNotIn(removed,texts)
        self.assertIn('APLICAR',texts)
        action = AddActionDialog(self.window)
        self.assertEqual([e['delay_ms'] for e in action.events()], [0,50,0])

    def test_text_table_timing_survives_save_and_reload(self):
        self.window.draft = [dict(type='text',text='hola',delay_ms=0,char_delay_ms=0)]
        self.window.render_events()
        self.window.table.cellWidget(0,3).setValue(10)
        self.window.apply_steps()
        self.assertEqual(self.window.draft[0]['char_delay_ms'],10)
        self.assertEqual(self.window.draft[0]['delay_ms'],0)
        self.assertTrue(self.window.commit_draft())
        macro = Store(Path(self.directory.name)).active['macros'][0]
        self.assertEqual(macro['events'][0]['char_delay_ms'],10)

    def test_text_can_be_edited_by_double_click_and_context_menu(self):
        self.window.draft = [dict(type='text',text='hola',delay_ms=0,char_delay_ms=10)]
        self.window.render_events()
        with patch('nexus.studio.QInputDialog.getMultiLineText',return_value=('hola mundo',True)):
            self.window.table.cellDoubleClicked.emit(0,2)
        self.assertEqual(self.window.draft[0]['text'],'hola mundo')
        self.assertEqual(self.window.draft[0]['char_delay_ms'],10)
        class EditMenu(QMenu):
            def exec(self,*args):
                self.test_titles = [action.text() for action in self.actions()]
                return self.actions()[0]
        self.window.table.show()
        position = self.window.table.visualItemRect(self.window.table.item(0,2)).center()
        with patch('nexus.studio.QMenu',EditMenu), patch('nexus.studio.QInputDialog.getMultiLineText',return_value=('modificado',True)):
            self.window.table_text_menu(position)
        self.assertEqual(self.window.draft[0]['text'],'modificado')
        with patch('nexus.studio.QInputDialog.getMultiLineText',return_value=('ignorar',False)):
            self.window.edit_table_text(0)
        self.assertEqual(self.window.draft[0]['text'],'modificado')

    def test_new_macro_starts_red_and_colors_remain_individual_in_library(self):
        from types import SimpleNamespace
        from nexus.core import DEFAULT_MACRO_COLOR
        self.window.macro_color = '#23aaff'
        self.window.macro_color_custom = True
        self.assertTrue(self.window.commit_draft())
        with patch('nexus.studio.QInputDialog.getText',return_value=('Nueva',True)), \
             patch('nexus.studio.TypeDialog',return_value=SimpleNamespace(mode='once',macro_name='Nueva',exec=lambda: QDialog.DialogCode.Accepted)):
            new_id = self.window.new_macro()
        self.assertEqual(self.window.macro_color,DEFAULT_MACRO_COLOR)
        with patch('nexus.studio.QColorDialog.getColor',return_value=QColor('#00aa44')):
            self.window.choose_macro_color()
        self.assertTrue(self.window.commit_draft())
        stored = Store(Path(self.directory.name)).active['macros']
        self.assertEqual(stored[0]['color'],'#23aaff')
        self.assertEqual(stored[1]['id'],new_id)
        self.assertEqual(stored[1]['color'],'#00aa44')
        self.assertEqual(self.window.assign_library.item(0).foreground().color().name(),'#ffffff')
        self.assertEqual(self.window.assign_library.item(1).foreground().color().name(),'#ffffff')
        self.assertEqual(self.window.assign_library.item(0).data(Qt.ItemDataRole.UserRole + 3),'#23aaff')
        self.assertEqual(self.window.assign_library.item(1).data(Qt.ItemDataRole.UserRole + 3),'#00aa44')

    def test_default_macro_names_are_white_until_color_is_explicitly_chosen(self):
        from nexus.core import DEFAULT_MACRO_COLOR, macro_label_color
        self.window.refresh_bindings()
        self.assertEqual(self.window.macro_color,DEFAULT_MACRO_COLOR)
        self.assertEqual(self.window.assign_library.item(0).foreground().color().name(),'#ffffff')
        with patch('nexus.studio.QColorDialog.getColor',return_value=QColor(DEFAULT_MACRO_COLOR)):
            self.window.choose_macro_color()
        self.assertTrue(self.window.commit_draft())
        self.assertEqual(self.window.assign_library.item(0).foreground().color().name(),'#ffffff')
        saved = Store(Path(self.directory.name)).active['macros'][0]
        self.assertEqual(self.window.assign_library.item(0).data(Qt.ItemDataRole.UserRole + 3),DEFAULT_MACRO_COLOR)
        self.assertTrue(saved['custom_color'])
        self.assertEqual(macro_label_color(saved),'#ffffff')
        self.assertEqual(macro_label_color(dict(color=DEFAULT_MACRO_COLOR)),'#ffffff')
        self.assertEqual(macro_label_color(dict(color='#00aa44')),'#ffffff')

    def test_sequence_shows_three_sections_and_each_plus_edits_its_own_phase(self):
        self.window.mode_combo.setCurrentIndex(self.window.mode_combo.findData('sequence'))
        self.window.stack.setCurrentIndex(4)
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.window.phase_combo.isHidden())
        for phase in ('press','hold','release'):
            self.assertTrue(self.window.phase_tracks[phase].isVisible())
            self.assertEqual(self.window.phase_plus[phase].text(),'+')
        def append(text):
            self.window.append_actions([dict(type='text',text=text,delay_ms=0,char_delay_ms=10)])
        with patch.object(self.window,'action_menu',side_effect=lambda: append('inicio')):
            self.window.phase_plus['press'].click()
        with patch.object(self.window,'action_menu',side_effect=lambda: append('final')):
            self.window.phase_plus['release'].click()
        sections = self.window.read_sections()
        self.assertEqual(sections['press'][0]['text'],'inicio')
        self.assertEqual(sections['release'][0]['text'],'final')
        self.assertEqual([e['type'] for e in sections['hold']],['key','wait','key'])
        self.assertTrue(self.window.commit_draft())
        saved = Store(Path(self.directory.name)).active['macros'][0]
        self.assertEqual(saved['sections']['press'][0]['text'],'inicio')
        self.assertEqual(saved['sections']['release'][0]['text'],'final')

    def test_sequence_recording_and_delete_remain_scoped_to_each_phase(self):
        self.window.mode_combo.setCurrentIndex(self.window.mode_combo.findData('sequence'))
        self.window.select_phase('press')
        self.window.input_ready = True
        self.window.toggle_record()
        self.window.capture_event(dict(type='key',vk=70,scan=0,extended=False,down=True))
        self.window.capture_event(dict(type='key',vk=70,scan=0,extended=False,down=False))
        self.window.finish_recording()
        self.window.select_phase('release')
        hold_wait = next(self.window.phase_layouts['hold'].itemAt(i).widget()
            for i in range(self.window.phase_layouts['hold'].count())
            if isinstance(self.window.phase_layouts['hold'].itemAt(i).widget(),TimelineBlock)
            and self.window.phase_layouts['hold'].itemAt(i).widget().delay is not None)
        hold_wait.delete_requested.emit(hold_wait.row)
        sections = self.window.read_sections()
        self.assertEqual([e['vk'] for e in sections['press'] if e['type']=='key'],[70,70])
        self.assertEqual([e['type'] for e in sections['hold']],['key','key'])
        self.assertEqual(sections['release'],[])

    def test_color_reset_restores_default_inside_and_white_outside(self):
        from nexus.core import DEFAULT_MACRO_COLOR
        with patch('nexus.studio.QColorDialog.getColor',return_value=QColor('#00aa44')):
            self.window.choose_macro_color()
        self.assertTrue(self.window.commit_draft())
        self.window.reset_color_button.click()
        self.assertEqual(self.window.macro_color,DEFAULT_MACRO_COLOR)
        self.assertFalse(self.window.macro_color_custom)
        self.assertTrue(self.window.commit_draft())
        saved = Store(Path(self.directory.name)).active['macros'][0]
        self.assertFalse(saved['custom_color'])
        self.assertEqual(saved['color'],DEFAULT_MACRO_COLOR)
        self.assertEqual(self.window.assign_library.item(0).foreground().color().name(),'#ffffff')


class TextTimingTests(unittest.TestCase):
    def test_release_interrupts_long_wait_between_text_letters(self):
        first = threading.Event()
        sent = []
        def send(event):
            sent.append(event['text'])
            first.set()
        engine = MacroEngine(send)
        try:
            macro = dict(id='text',name='Texto',mode='hold',events=[dict(
                type='text',text='hola',delay_ms=0,char_delay_ms=60000)])
            engine.press('test',macro)
            self.assertTrue(first.wait(1))
            engine.release('test')
            self.assertTrue(engine.wait_idle(1))
            self.assertEqual(sent,['h'])
        finally:
            engine.close()

    def test_text_sends_first_letter_immediately_and_waits_between_letters(self):
        sent, waits = [], []
        engine = MacroEngine(sent.append)
        try:
            macro = validate_macro(dict(id='text',name='Texto',mode='once',events=[dict(
                type='text',text='hola',delay_ms=0,char_delay_ms=10)]))
            session = Session('test',macro)
            def wait(session, seconds, interrupt=False):
                waits.append(seconds)
                return True
            with patch.object(engine,'_wait',side_effect=wait):
                engine._execute(session)
            self.assertEqual([event['text'] for event in sent],list('hola'))
            self.assertEqual([delay for delay in waits if delay], [.01,.01,.01])
        finally:
            engine.close()

    def test_standard_gap_is_not_applied_twice(self):
        sent, waits = [], []
        engine = MacroEngine(sent.append)
        try:
            macro = dict(mode='once',standard_delay=True,standard_delay_ms=50,events=[
                dict(type='key',vk=32,down=True,delay_ms=0),dict(type='wait',delay_ms=50),
                dict(type='key',vk=32,down=False,delay_ms=0)])
            with patch.object(engine,'_wait',side_effect=lambda session,seconds,interrupt=False: waits.append(seconds) or True):
                engine._execute(Session('test',macro))
            self.assertEqual([delay for delay in waits if delay], [.05])
            self.assertEqual([event['down'] for event in sent],[True,False])
        finally:
            engine.close()
