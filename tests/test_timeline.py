import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import copy
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from nexus.timeline import timeline_tokens,reorder_tokens,TimelineBlock
from nexus.core import Store
from nexus.studio import StudioWindow

def key(vk,down,delay=0):
    return {'type':'key','vk':vk,'scan':0,'down':down,'delay_ms':delay}

class TimelineTests(unittest.TestCase):
    def test_delay_can_move_after_last_key_without_moving_keys(self):
        events=[key(32,True),key(32,False,104)]
        original=copy.deepcopy(events)
        result=reorder_tokens(events,1,3)
        self.assertEqual([e.get('down') for e in result if e['type']=='key'],[True,False])
        self.assertEqual(result[-1],{'type':'wait','delay_ms':104})
        self.assertEqual(sum(e['delay_ms'] for e in result),104)
        self.assertEqual(events,original)

    def test_key_and_delay_move_independently(self):
        events=[key(17,True),key(17,False,127),key(81,True,999),key(81,False,86)]
        result=reorder_tokens(events,2,5)
        self.assertEqual([e.get('vk') for e in result if e['type']=='key'],[17,81,17,81])
        self.assertEqual(sum(e['delay_ms'] for e in result),1212)

    def test_recording_space_enter_escape_do_not_activate_back_button(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window=StudioWindow(Store(Path(directory)))
            window.store.active['macros'].append({'id':'test','name':'Test','mode':'once','events':[]})
            window.load_macro(0)
            window.stack.setCurrentIndex(4)
            window.input_ready=True
            window.toggle_record()
            for widget in window.findChildren(__import__('nexus.studio_widgets',fromlist=['BackArrow']).BackArrow):
                widget.setFocus()
                for keycode in (Qt.Key.Key_Space,Qt.Key.Key_Return,Qt.Key.Key_Escape):
                    QTest.keyClick(widget,keycode)
                    self.assertEqual(window.stack.currentIndex(),4)
                    self.assertTrue(window.recording)
            window.finish_recording()
            window.exit_application()

    def test_inline_delay_edit_and_move_survive_save(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            window=StudioWindow(Store(Path(directory)))
            window.store.active['macros']=[{'id':'test','name':'Combo','mode':'once','standard_delay':False,'events':[key(32,True),key(32,False,104)]}]
            window.load_macro(0)
            window.edit_timeline_delay(1,120)
            self.assertEqual(window.read_draft()[1]['delay_ms'],120)
            window.reorder_timeline(1,3)
            window.save_macro()
            events=Store(Path(directory)).active['macros'][0]['events']
            self.assertEqual(events[-1],{'type':'wait','delay_ms':120})
            self.assertEqual([e['down'] for e in events if e['type']=='key'],[True,False])
            window.exit_application()

    def test_wrapping_scroll_and_drop_position_use_visual_rows(self):
        from PySide6.QtWidgets import QScrollArea
        from nexus.timeline import TimelineTrack,FlowLayout
        app=QApplication.instance() or QApplication([])
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        track=TimelineTrack()
        layout=FlowLayout(track)
        for index in range(100):
            layout.addWidget(TimelineBlock(index,index,'A','#790028'))
        scroll.setWidget(track)
        scroll.resize(500,250)
        scroll.show()
        for _ in range(4):app.processEvents()
        first=layout.itemAt(0).widget()
        second_row=next(layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget().y()>first.y())
        self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
        self.assertGreater(scroll.verticalScrollBar().maximum(),0)
        destination,marker=track.insertion_at(second_row.x(),second_row.geometry().center().y())
        self.assertEqual(destination,second_row.index)
        self.assertEqual(marker.y(),second_row.y())
        scroll.resize(800,250)
        for _ in range(4):app.processEvents()
        self.assertLess(layout.heightForWidth(800),layout.heightForWidth(500))
        scroll.close()
