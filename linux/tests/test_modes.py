import threading
import time
import unittest

from nexus.core import validate_macro, validate_profile, new_profile, held_after
from nexus.macro_engine import MacroEngine
from nexus.g502 import decode_buttons


def key(vk, down, delay=0):
    return {"type": "key", "vk": vk, "down": down, "delay_ms": delay}


def macro(mode, events=None, **fields):
    return {"id": "test", "name": "Test", "mode": mode, "events": events or [], **fields}


class ModeTests(unittest.TestCase):
    def setup_engine(self, sender=None):
        self.sent = []
        self.started = threading.Event()
        def send(event):
            self.sent.append(event.copy())
            self.started.set()
            if sender:
                sender(event)
        self.engine = MacroEngine(send)
        self.addCleanup(self.engine.close)

    def test_latch_holds_key_and_mouse_without_repeating_until_second_press(self):
        ready = threading.Event()
        extra = threading.Event()
        def observe(event):
            if len(self.sent) == 2:
                ready.set()
            if len(self.sent) > 2:
                extra.set()
        self.setup_engine(observe)
        definition = macro("latch", [key(17, True, 60000), key(17, False),
            {"type": "mouse", "button": "left", "down": True, "delay_ms": 60000},
            {"type": "mouse", "button": "left", "down": False, "delay_ms": 0},
            key(17, True), key(17, False)], standard_delay=True, standard_delay_ms=60000)
        self.engine.press("G4", definition)
        self.assertTrue(ready.wait(.5), "Latch must ignore all recorded and standard delays")
        self.engine.release("G4")
        self.assertFalse(extra.wait(.05), "No repeated downs or recorded ups may be sent")
        self.assertTrue(self.engine.busy)
        self.assertEqual([e["down"] for e in self.sent], [True, True])
        self.engine.press("G4", definition)
        self.assertTrue(self.engine.wait_idle(.5))
        self.assertEqual([e["down"] for e in self.sent], [True, True, False, False])
        self.assertEqual(self.sent[2]["button"], "left")
        self.assertEqual(self.sent[3]["vk"], 17)

    def test_latch_stop_and_close_release_held_output(self):
        for method in ("stop", "close"):
            with self.subTest(method=method):
                self.setup_engine()
                self.engine.press("G4", macro("latch", [key(65, True), key(65, False)]))
                self.assertTrue(self.started.wait(.5))
                getattr(self.engine, method)()
                self.assertTrue(self.engine.wait_idle(.5))
                self.assertEqual([e["down"] for e in self.sent], [True, False])

    def test_latch_second_press_cancels_pending_activation(self):
        self.setup_engine()
        definition = macro("latch", [key(65, True)])
        with self.engine.condition:
            self.engine.press("G4", definition)
            self.engine.release("G4")
            self.engine.press("G4", definition)
        self.assertTrue(self.engine.wait_idle(.5))
        self.assertEqual(self.sent, [])

    def test_latch_profile_roundtrip_and_unsupported_actions(self):
        profile = new_profile()
        profile["macros"] = [macro("latch", [key(65, True), key(65, False)])]
        self.assertEqual(validate_profile(profile)["macros"][0]["mode"], "latch")
        with self.assertRaises(ValueError):
            validate_macro(macro("latch", [{"type": "text", "text": "Hello", "delay_ms": 0}]))

    def test_once_starts_on_press_and_release_does_not_cancel(self):
        self.setup_engine()
        self.engine.press("G4", macro("once", [key(65, True), key(65, False, 40)]))
        self.assertTrue(self.started.wait(1))
        self.engine.release("G4")
        self.assertTrue(self.engine.wait_idle())
        self.assertEqual([e["down"] for e in self.sent], [True, False])

    def test_hold_repeats_and_stops_when_released(self):
        two_cycles = threading.Event()
        self.setup_engine(lambda e: two_cycles.set() if len(self.sent) >= 4 else None)
        self.engine.press("G4", macro("hold", [key(65, True), key(65, False, 5)]))
        self.assertTrue(two_cycles.wait(1))
        self.engine.release("G4")
        self.assertTrue(self.engine.wait_idle(.5))
        count = len(self.sent)
        self.assertGreaterEqual(count, 4)
        self.assertFalse(self.sent[-1]["down"])
        self.assertFalse(self.engine.busy)

    def test_release_interrupts_long_delay_and_releases_key(self):
        self.setup_engine()
        self.engine.press("G8", macro("hold", [key(32, True), key(32, False, 60000)]))
        self.assertTrue(self.started.wait(1))
        start = time.monotonic()
        self.engine.release("G8")
        self.assertTrue(self.engine.wait_idle(.3))
        self.assertLess(time.monotonic() - start, .3)
        self.assertEqual([e["down"] for e in self.sent], [True, False])

    def test_toggle_ignores_release_and_stops_on_next_press(self):
        self.setup_engine()
        definition = macro("toggle", [key(65, True), key(65, False, 10)])
        self.engine.press("G5", definition)
        self.assertTrue(self.started.wait(1))
        self.engine.release("G5")
        self.assertTrue(self.engine.busy)
        self.engine.press("G5", definition)
        self.assertTrue(self.engine.wait_idle(.5))
        self.assertFalse(self.sent[-1]["down"])

    def test_sequence_preserves_modifier_across_phases_and_runs_release(self):
        loop_seen = threading.Event()
        self.setup_engine(lambda e: loop_seen.set() if e.get("vk") == 65 else None)
        definition = macro("sequence", sections={"press": [key(17, True)],
            "hold": [key(65, True), key(65, False, 10)], "release": [key(17, False), key(66, True), key(66, False)]})
        self.engine.press("G6", definition)
        self.assertTrue(loop_seen.wait(1))
        self.engine.release("G6")
        self.assertTrue(self.engine.wait_idle())
        self.assertEqual((self.sent[0]["vk"], self.sent[0]["down"]), (17, True))
        self.assertIn((17, False), [(e["vk"], e["down"]) for e in self.sent])
        self.assertIn((66, True), [(e["vk"], e["down"]) for e in self.sent])
        self.assertEqual((self.sent[-1]["vk"], self.sent[-1]["down"]), (66, False))
        self.assertEqual(held_after(self.sent), set())
        pairs = [(e["vk"], e["down"]) for e in self.sent]
        self.assertLess(pairs.index((65, False)), pairs.index((17, False)))

    def test_fast_release_before_worker_starts_does_not_start_hold(self):
        self.setup_engine()
        with self.engine.condition:
            self.engine.press("G4", macro("hold", [key(65, True), key(65, False)]))
            self.engine.release("G4")
        self.assertTrue(self.engine.wait_idle())
        self.assertEqual(self.sent, [])

    def test_rapid_repress_serializes_cleanup_before_replacement(self):
        self.setup_engine()
        definition = macro("hold", [key(65, True), key(65, False, 60000)])
        self.engine.press("G4", definition)
        self.assertTrue(self.started.wait(1))
        self.engine.release("G4")
        self.engine.press("G4", macro("once", [key(66, True), key(66, False)]))
        self.assertTrue(self.engine.wait_idle())
        self.assertEqual([(e["vk"], e["down"]) for e in self.sent], [(65, True), (65, False), (66, True), (66, False)])

    def test_release_of_other_button_does_not_cancel(self):
        self.setup_engine()
        self.engine.press("G4", macro("hold", [key(65, True), key(65, False, 60000)]))
        self.assertTrue(self.started.wait(1))
        self.engine.release("G5")
        self.assertTrue(self.engine.busy)
        self.engine.release("G4")
        self.assertTrue(self.engine.wait_idle())

    def test_sequence_rejects_loop_that_changes_pressed_state(self):
        with self.assertRaises(ValueError):
            validate_macro(macro("sequence", sections={"press": [key(17, True)],
                "hold": [key(65, True)], "release": [key(17, False)]}))

    def test_f9_is_a_valid_trigger_and_action(self):
        profile = new_profile()
        profile["macros"] = [macro("once", [key(120, True), key(120, False)])]
        profile["bindings"] = [{"device_id": "keyboard", "macro_id": "test", "trigger": {"type": "key", "vk": 120, "mods": []}}]
        self.assertEqual(validate_profile(profile)["bindings"][0]["trigger"]["vk"], 120)

    def test_spy_bitmap_exposes_press_and_release_of_firmware_only_buttons(self):
        previous, events = decode_buttons([0x11, 255, 13, 0, 1, 8], 13, 0, 11)
        self.assertEqual(events, [{"type": "gbutton", "button": 3, "down": True}, {"type": "gbutton", "button": 8, "down": True}])
        previous, events = decode_buttons([0x11, 255, 13, 0, 0, 0], 13, previous, 11)
        self.assertEqual([e["down"] for e in events], [False, False])


if __name__ == "__main__":
    unittest.main()
