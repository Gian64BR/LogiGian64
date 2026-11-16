import os
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import Mock, patch

from nexus import linux_backend as b
from nexus import preferences


class FakeUI:
    def __init__(self): self.events=[]; self.closed=False
    def write(self,*event): self.events.append(event)
    def syn(self): self.events.append(('syn',))
    def close(self): self.closed=True


class LinuxInputTests(unittest.TestCase):
    def tearDown(self):
        b.unregister_input()
        b._active_keys.clear()

    def test_translation_uses_profile_keys_and_ignores_repeat_motion(self):
        self.assertEqual(b.translate_event(NS(type=1,code=30,value=1))['vk'],65)
        self.assertFalse(b.translate_event(NS(type=1,code=30,value=0))['down'])
        self.assertEqual(b.translate_event(NS(type=1,code=275,value=1))['button'],'x1')
        self.assertEqual(b.translate_event(NS(type=2,code=6,value=-1)),dict(type='wheel',axis='horizontal',delta=-120))
        for event in [NS(type=1,code=30,value=2),NS(type=2,code=0,value=50),NS(type=0,code=0,value=0)]:
            self.assertIsNone(b.translate_event(event))

    def test_modifier_state_and_sided_keys(self):
        b._active_keys.update([97,54])
        self.assertEqual(b.modifiers(),['Ctrl','Shift'])
        self.assertEqual(b.translate_event(NS(type=1,code=97,value=1))['vk'],163)

    def test_all_ascii_punctuation_and_shift(self):
        import string
        self.assertEqual(len(b._text_keys(string.printable[:-5])),len(string.printable[:-5]))
        self.assertEqual(b._text_keys('aA!~'),[(30,False),(30,True),(2,True),(41,True)])

    def test_unicode_is_rejected_before_any_output(self):
        with patch.object(b,'get_writer') as writer:
            with self.assertRaisesRegex(OSError,'Unicode'): b.send_event(dict(type='text',text='hola ñ'))
            writer.assert_not_called()

    def test_output_and_exit_release_held_keys(self):
        ui=FakeUI(); b._writer=b.Writer(ui)
        b.send_event(dict(type='key',vk=65,down=True))
        b.send_event(dict(type='mouse',button='x1',down=True))
        b.unregister_input()
        self.assertIn((1,30,0),ui.events);self.assertIn((1,275,0),ui.events)
        self.assertTrue(ui.closed);self.assertIsNone(b._writer)

    def test_wheel_emits_matching_high_and_low_resolution(self):
        ui=FakeUI();b._writer=b.Writer(ui)
        b.send_event(dict(type='wheel',axis='horizontal',delta=-240))
        self.assertEqual(ui.events,[(2,12,-240),(2,6,-2),('syn',)])

    def test_virtual_output_is_closed_even_if_release_fails(self):
        ui=FakeUI();b._writer=b.Writer(ui);b._writer.pressed.add(30)
        ui.write=Mock(side_effect=OSError('removed'))
        with self.assertLogs(level='ERROR'): b.unregister_input()
        self.assertTrue(ui.closed);self.assertIsNone(b._writer)

    def test_identity_is_stable_across_nodes_but_roles_are_separate(self):
        with patch.object(b,'container_id',return_value='/SYS/DEVICES/USB/1-2'):
            self.assertEqual(b._identity('/dev/input/event1','mouse'),b._identity('/dev/hidraw3','mouse'))
            self.assertNotEqual(b._identity('/dev/input/event1','mouse'),b._identity('/dev/input/event2','keyboard'))

    def test_usb_and_hidraw_use_same_physical_parent(self):
        parent=NS(sys_path='/sys/devices/usb1/1-2')
        node=Mock();node.find_parent.return_value=parent
        with patch.object(b,'_udev',return_value=node):
            self.assertEqual(b.container_id('/dev/hidraw0'),parent.sys_path.upper())

    def test_enumeration_merges_collections_separates_roles_and_ignores_virtual(self):
        from contextlib import ExitStack
        paths=[Path('/dev/input/event'+str(i)) for i in range(4)]
        def node(path):
            index=int(path[-1])
            return NS(properties={'ID_INPUT_MOUSE' if index<2 else 'ID_INPUT_KEYBOARD':'1'},
                      sys_path='/sys/devices/virtual/input/input8' if index==3 else '/sys/devices/usb1/1-2/input'+str(index))
        def opened(path):
            index=int(path[-1]);device=Mock()
            device.name='Wireless Receiver';device.info=NS(vendor=0x258a,product=0x1007)
            device.capabilities.return_value={1:[272,273,274,275,276] if index==1 else []}
            return device
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{'XDG_DATA_HOME':directory}))
            stack.enter_context(patch.object(Path,'glob',return_value=paths))
            stack.enter_context(patch.object(Path,'read_text',side_effect=OSError('missing')))
            stack.enter_context(patch.object(b,'_udev',side_effect=node))
            stack.enter_context(patch.object(b,'container_id',return_value='/SYS/USB/1-2'))
            stack.enter_context(patch.object(b,'_evdev',return_value=NS(InputDevice=opened)))
            stack.enter_context(patch('nexus.device_catalog.apply_catalog'))
            stack.enter_context(patch('nexus.device_identity.load_identities',return_value={}))
            result=b.enumerate_devices()
        self.assertEqual(len(result),2)
        mouse=next(d for d in result if d.kind=='mouse')
        self.assertEqual(mouse.button_count,5);self.assertEqual(len(mouse.paths),2)
        self.assertNotEqual(result[0].id,result[1].id)

    def test_removed_input_is_closed_and_virtual_feedback_is_excluded(self):
        old=Mock();new=Mock(name='device');new.name=b.VIRTUAL_NAME
        service=b.InputService(Mock(),Mock(),Mock());service.nodes={'/dev/input/event0':old}
        dev=b.Device('abc','keyboard','keyboard','','','','/dev/input/event1'.split(),[])
        with patch.object(b,'enumerate_devices',return_value=[dev]),patch.object(b,'_evdev',return_value=NS(InputDevice=Mock(return_value=new))):
            service.rescan()
        old.close.assert_called_once();new.close.assert_called_once()
        self.assertEqual(service.nodes,{})

    def test_uinput_has_only_keyboard_mouse_wheel_capabilities(self):
        factory=Mock(return_value=FakeUI())
        with patch.object(b,'_evdev',return_value=NS(UInput=factory)):
            b.get_writer()
        caps=factory.call_args.args[0]
        self.assertEqual(set(caps),{1,2});self.assertIn(30,caps[1]);self.assertIn(275,caps[1])
        self.assertEqual(factory.call_args.kwargs['name'],b.VIRTUAL_NAME)

    def test_start_without_physical_nodes_still_monitors_hotplug(self):
        service=b.InputService(Mock(),Mock(),Mock())
        with patch.object(service,'rescan',return_value=set()),patch.object(b,'get_writer'),patch('threading.Thread') as thread:
            service.start();thread.return_value.start.assert_called_once()

    def test_permission_denial_prevents_recording_ready(self):
        service=b.InputService(Mock(),Mock(),Mock())
        with patch.object(service,'rescan',return_value={'/dev/input/event1'}):
            with self.assertRaisesRegex(OSError,'Sin acceso'):service.start()

    def test_autostart_is_per_user_and_escapes_desktop_field_codes(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'XDG_CONFIG_HOME':directory}):
            preferences.set_startup(True)
            self.assertTrue(preferences.startup_enabled())
            text=(Path(directory)/'autostart/logigian64.desktop').read_text()
            self.assertIn('--startup',text)
            self.assertEqual(preferences._quote('a%b'),'"a%%b"')
            preferences.set_startup(False);self.assertFalse(preferences.startup_enabled())

    def test_g502_hidraw_identity_matches_evdev(self):
        from nexus.g502 import matches_device
        with patch.object(b,'container_id',return_value='/SYS/USB/1-2'):
            device=NS(id=b._identity('/dev/input/event4','mouse'))
            self.assertTrue(matches_device(dict(path=b'/dev/hidraw0'),device))

if __name__=='__main__':unittest.main()
