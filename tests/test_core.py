import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from nexus.core import Store, new_profile, validate_events, validate_profile
from nexus.macro_engine import MacroEngine as MacroPlayer


def key(down, delay=0):
    return {"type": "key", "vk": 65, "scan": 30, "extended": False, "down": down, "delay_ms": delay}


class MacroTests(unittest.TestCase):
    def test_repetitions_preserve_actions(self):
        sent = []
        player = MacroPlayer(sent.append)
        player.start([key(True), key(False)], repeats=3)
        self.assertTrue(player.wait_idle(2))
        player.close()
        self.assertFalse(player.busy)
        self.assertEqual([e["down"] for e in sent], [True, False] * 3)

    def test_cancellation_releases_pressed_key_without_waiting_for_long_delay(self):
        sent, started = [], threading.Event()
        def sender(event):
            sent.append(event)
            started.set()
        player = MacroPlayer(sender)
        player.start([key(True), key(False, 60000)])
        self.assertTrue(started.wait(1))
        start = time.monotonic()
        player.close()
        self.assertLess(time.monotonic() - start, 1)
        self.assertFalse(player.busy)
        self.assertEqual([e["down"] for e in sent], [True, False])

    def test_send_failure_releases_prior_input(self):
        sent, finished = [], []
        def sender(event):
            if event.get("type") == "wheel":
                raise OSError("destination blocked")
            sent.append(event)
        player = MacroPlayer(sender, finished.append)
        player.start([key(True), {"type": "wheel", "delta": 120, "delay_ms": 0}, key(False)])
        self.assertTrue(player.wait_idle(2))
        player.close()
        self.assertEqual([e["down"] for e in sent], [True, False])
        self.assertIn("destination blocked", finished[0])

    def test_countdown_cancel_sends_nothing(self):
        sent = []
        player = MacroPlayer(sent.append)
        player.start([key(True), key(False)], start_delay=3)
        player.close()
        self.assertEqual(sent, [])

    def test_parallel_start_is_rejected(self):
        player = MacroPlayer(lambda event: None)
        player.start([key(True), key(False, 1000)])
        with self.assertRaises(ValueError):
            player.start([key(True), key(False)])
        player.close()

    def test_unbalanced_or_invalid_import_is_rejected(self):
        for events in ([key(True)], [key(False)], [{**key(True), "delay_ms": -1}],
                       [{"type": "shell", "command": "anything"}], [{**key(True), "vk": 999}],
                       [{"type": "wheel", "delta": "wrong"}]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                validate_events(events)


class StoreTests(unittest.TestCase):
    def test_profile_roundtrip_keeps_device_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            store.active["macros"].append({"id": "a", "name": "Test", "events": [key(True), key(False)]})
            store.active["bindings"].append({"device_id": "physical-container-1", "macro_id": "a",
                "enabled": True, "trigger": {"type": "mouse", "button": "x1"}})
            store.save()
            reloaded = Store(Path(directory))
            self.assertEqual(reloaded.active, validate_profile(store.active))

    def test_corrupt_library_is_preserved_before_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text("[1,2,3]")
            store = Store(Path(directory))
            self.assertTrue(store.warning)
            backups = list(Path(directory).glob("profiles-recovery-*.json"))
            self.assertEqual(backups[0].read_text(), "[1,2,3]")
            store.save()
            self.assertEqual(json.loads(path.read_text())["version"], 2)

    def test_reserved_stop_key_cannot_be_bound(self):
        profile = new_profile()
        profile["macros"] = [{"id": "a", "name": "Test", "events": []}]
        profile["bindings"] = [{"device_id": "x", "macro_id": "a", "trigger": {"type": "key", "vk": 123, "mods": ["Ctrl", "Alt"]}}]
        with self.assertRaises(ValueError):
            validate_profile(profile)

    def test_missing_macro_reference_is_rejected(self):
        profile = new_profile()
        profile["bindings"] = [{"device_id": "x", "macro_id": "missing", "trigger": {"type": "mouse", "button": "x1"}}]
        with self.assertRaises(ValueError):
            validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
