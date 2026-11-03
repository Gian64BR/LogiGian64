import queue
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from nexus.g502 import G502Session


class FakeHid:
    def __init__(self, refuse_start=False, fail_first_restore=False, dpi=False, refuse_dpi=False, lighting=None):
        self.responses = queue.Queue()
        self.mode = 1
        self.mapping = list(range(1, 12))
        self.closed = False
        self.requests = []
        self.refuse_start = refuse_start
        self.fail_first_restore = fail_first_restore
        self.has_changed = False
        self.supports_dpi = dpi
        self.dpi = 3200
        self.refuse_dpi = refuse_dpi
        self.lighting = lighting

    def open_path(self, path):
        pass

    def write(self, packet):
        index, address, data = packet[2], packet[3], packet[4:]
        fn = address >> 4
        self.requests.append((index, fn, data))
        answer = [0] * 16
        if index == 0:
            answer[0] = {0x8110: 13, 0x8100: 12, 0x2201: 10 if self.supports_dpi else 0,
                         0x8070: 2 if self.lighting else 0}.get((data[0] << 8) | data[1], 0)
        elif index == 2 and self.lighting:
            answer = self.lighting.request(index, fn, data)
        elif index == 10:
            if fn == 0:
                answer[0] = 1
            elif fn == 1:
                answer[:7] = [0, 0, 100, 0xE0, 50, 100, 0]
            elif fn == 2:
                answer[:5] = [0, self.dpi >> 8, self.dpi & 255, 3, 232]
            elif fn == 3 and not self.refuse_dpi:
                self.dpi = (data[1] << 8) | data[2]
        elif index == 12 and fn == 2:
            answer[0] = self.mode
        elif index == 12 and fn == 1:
            self.mode = data[0]
        elif index == 13 and fn == 0:
            answer[0] = 11
        elif index == 13 and fn == 3:
            answer[:11] = self.mapping
        elif index == 13 and fn == 4:
            if self.fail_first_restore and self.has_changed and data[:11] == list(range(1, 12)):
                self.fail_first_restore = False
                self.responses.put([0x11, 255, 255, index, address, 1] + [0] * 14)
                return
            self.mapping = data[:11]
            self.has_changed = True
        elif index == 13 and fn == 1 and self.refuse_start:
            self.responses.put([0x11, 255, 255, index, address, 1] + [0] * 14)
            return
        self.responses.put([0x11, 255, index, address] + answer)

    def read(self, size, timeout):
        try:
            return self.responses.get(timeout=min(timeout / 1000, .01))
        except queue.Empty:
            return []

    def close(self):
        self.closed = True


class G502Tests(unittest.TestCase):
    def test_primary_buttons_can_never_be_suppressed_in_hardware(self):
        fake = FakeHid()
        fake.mapping[:2] = [0, 0]
        session, ready, errors, _ = self.launch(fake)
        self.assertTrue(ready.wait(1))
        session.update_buttons({0, 1, 4})
        import time
        deadline = time.monotonic() + 1
        while fake.mapping[4] != 0 and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(fake.mapping[:2], [1, 2])
        self.assertEqual(fake.mapping[4], 0)
        self.assertTrue(session.close())
        writes = [data for index, fn, data in fake.requests if index == 13 and fn == 4]
        self.assertTrue(writes)
        self.assertTrue(all(data[:2] == [1, 2] for data in writes))
        self.assertEqual(errors, [])

    def launch(self, fake, running=False):
        ready = threading.Event()
        errors = []
        device = SimpleNamespace(id="123456789abcdef", name="Test mouse")
        session = G502Session(device, lambda handle, event: None,
            lambda status: ready.set() if "conectado directamente" in status else None, errors.append)
        self.addCleanup(patch.stopall)
        patch("nexus.g502.ghub_running", return_value=running).start()
        patch("nexus.g502.hid.enumerate", return_value=[{"path": b"test", "usage_page": 0xFF00, "usage": 2}]).start()
        factory = patch("nexus.g502.hid.device", return_value=fake).start()
        patch("nexus.g502.matches_device", return_value=True).start()
        self.addCleanup(session.close)
        session.start({3, 5})
        return session, ready, errors, factory

    def test_volatile_assignment_restores_original_mode_and_map(self):
        fake = FakeHid()
        session, ready, errors, _ = self.launch(fake)
        self.assertTrue(ready.wait(1))
        self.assertEqual(fake.mode, 2)
        self.assertEqual((fake.mapping[3], fake.mapping[5]), (0, 0))
        self.assertTrue(session.close())
        self.assertEqual(fake.mapping, list(range(1, 12)))
        self.assertEqual(fake.mode, 1)
        self.assertTrue(fake.closed)
        self.assertEqual(errors, [])
        self.assertTrue(all(index in (0, 12, 13) for index, _, _ in fake.requests), "No flash/DFU requests allowed")

    def test_failed_start_restores_mode_before_releasing_handle(self):
        fake = FakeHid(refuse_start=True)
        session, _, errors, _ = self.launch(fake)
        session.thread.join(1)
        self.assertFalse(session.ready)
        self.assertEqual(fake.mode, 1)
        self.assertTrue(fake.closed)
        self.assertTrue(errors)

    def test_competing_ghub_agent_is_refused_without_opening_hardware(self):
        fake = FakeHid()
        session, _, errors, factory = self.launch(fake, running=True)
        session.thread.join(1)
        factory.assert_not_called()
        self.assertTrue(errors)
        self.assertEqual(fake.requests, [])

    def test_failed_restore_retains_ownership_for_retry(self):
        fake = FakeHid(fail_first_restore=True)
        session, ready, errors, _ = self.launch(fake)
        self.assertTrue(ready.wait(1))
        session.stop_requested.set()
        session.thread.join(1)
        self.assertTrue(session.needs_restore)
        self.assertFalse(fake.closed)
        self.assertTrue(session.close())
        self.assertFalse(session.needs_restore)
        self.assertTrue(fake.closed)
        self.assertEqual(fake.mapping, list(range(1, 12)))

    def test_sensor_dpi_write_readback_and_restore(self):
        fake = FakeHid(dpi=True)
        session, ready, errors, _ = self.launch(fake)
        self.assertTrue(ready.wait(1))
        self.assertEqual(session.dpi_state['minimum'], 100)
        self.assertEqual(session.dpi_state['maximum'], 25600)
        self.assertEqual(session.dpi_state['step'], 50)
        confirmed = threading.Event()
        updates = []
        session.on_hardware = lambda data: (updates.append(data), confirmed.set() if data['kind'] == 'dpi' else None)
        session.set_dpi(1450)
        self.assertTrue(confirmed.wait(1))
        self.assertEqual(fake.dpi, 1450)
        self.assertEqual(updates[-1]['current'], 1450)
        with self.assertRaises(ValueError):
            session.set_dpi(1451)
        with self.assertRaises(ValueError):
            session.set_dpi(30000)
        self.assertTrue(session.close())
        self.assertEqual(fake.dpi, 3200)
        self.assertEqual(fake.mode, 1)
        self.assertEqual(errors, [])
        self.assertTrue(all(index != 12 or fn in (1, 2) for index, fn, _ in fake.requests))

    def test_unconfirmed_dpi_is_never_reported_as_applied(self):
        fake = FakeHid(dpi=True, refuse_dpi=True)
        session, ready, _, _ = self.launch(fake)
        self.assertTrue(ready.wait(1))
        received = threading.Event()
        updates = []
        session.on_hardware = lambda data: (updates.append(data), received.set() if data['kind'] == 'dpi_error' else None)
        session.set_dpi(1450)
        self.assertTrue(received.wait(1))
        self.assertEqual(fake.dpi, 3200)
        self.assertFalse(any(data['kind'] == 'dpi' for data in updates))
        self.assertIn('3200', updates[-1]['error'])


if __name__ == "__main__":
    unittest.main()
