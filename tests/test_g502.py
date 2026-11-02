import queue
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from nexus.g502 import G502Session


class FakeHid:
    def __init__(self, refuse_start=False, fail_first_restore=False):
        self.responses = queue.Queue()
        self.mode = 1
        self.mapping = list(range(1, 12))
        self.closed = False
        self.requests = []
        self.refuse_start = refuse_start
        self.fail_first_restore = fail_first_restore
        self.has_changed = False

    def open_path(self, path):
        pass

    def write(self, packet):
        index, address, data = packet[2], packet[3], packet[4:]
        fn = address >> 4
        self.requests.append((index, fn, data))
        answer = [0] * 16
        if index == 0:
            answer[0] = {0x8110: 13, 0x8100: 12}[(data[0] << 8) | data[1]]
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


if __name__ == "__main__":
    unittest.main()
