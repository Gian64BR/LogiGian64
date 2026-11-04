"""One owner for press/hold/toggle/sequence execution and output cleanup."""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import threading
import time

from .core import validate_macro, validate_events, event_identity, latched_actions


@dataclass
class Session:
    owner: object
    macro: dict
    delay: float = 0
    repeats: int = 1
    cancel: threading.Event = field(default_factory=threading.Event)
    released: threading.Event = field(default_factory=threading.Event)
    wake: threading.Event = field(default_factory=threading.Event)

    def stop(self):
        self.cancel.set()
        self.wake.set()

    def release(self):
        self.released.set()
        self.wake.set()


class MacroEngine:
    """Serial worker prevents a replacement macro racing the previous cleanup."""
    def __init__(self, sender, finished=lambda message: None):
        self.sender = sender
        self.finished = finished
        self.condition = threading.Condition()
        self.current = None
        self.pending = None
        self.closed = False
        self.thread = threading.Thread(target=self._worker, name="NexusMacros", daemon=True)
        self.thread.start()

    @property
    def busy(self):
        with self.condition:
            return self.current is not None or self.pending is not None

    def _submit(self, session):
        if self.closed:
            raise ValueError("El motor está cerrado.")
        if self.current:
            self.current.stop()
        if self.pending:
            self.pending.stop()
        self.pending = session
        self.condition.notify_all()

    def press(self, owner, macro):
        macro = validate_macro(copy.deepcopy(macro))
        if not self.has_actions(macro):
            raise ValueError("La macro no tiene acciones.")
        with self.condition:
            active = self.pending or self.current
            if active and active.owner == owner and active.macro["mode"] in ("toggle", "latch") and not active.cancel.is_set():
                active.stop()
                if self.pending is active:
                    self.pending = None
                return
            self._submit(Session(owner, macro))

    def release(self, owner):
        with self.condition:
            for session in (self.current, self.pending):
                if session and session.owner == owner:
                    session.release()

    def stop_owner(self, owner):
        with self.condition:
            if self.current and self.current.owner == owner:
                self.current.stop()
            if self.pending and self.pending.owner == owner:
                self.pending.stop()
                self.pending = None
            self.condition.notify_all()

    def start(self, events, repeats=1, start_delay=0):
        """Manual preview is always finite; physical activation uses press/release."""
        events = validate_events(copy.deepcopy(events))
        if not events:
            raise ValueError("Añade pasos a la macro primero.")
        if type(repeats) is not int or not 1 <= repeats <= 100:
            raise ValueError("Repeticiones fuera del rango 1–100.")
        with self.condition:
            if self.busy:
                raise ValueError("Detén la macro actual antes de probar otra.")
            self._submit(Session("manual-preview", {"mode": "once", "events": events,
                "standard_delay": False}, start_delay, repeats))

    @staticmethod
    def has_actions(macro):
        if macro.get("mode") == "latch":
            return bool(latched_actions(macro.get("events", [])))
        return any(macro.get("sections", {}).values()) if macro.get("mode") == "sequence" else bool(macro.get("events"))

    def stop(self):
        with self.condition:
            if self.current:
                self.current.stop()
            if self.pending:
                self.pending.stop()
                self.pending = None
            self.condition.notify_all()

    def close(self):
        self.stop()
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.thread.join(timeout=3)

    def wait_idle(self, timeout=2):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.busy:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
        return True

    def _worker(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.pending is not None)
                if self.closed:
                    return
                session, self.pending = self.pending, None
                self.current = session
            message = self._execute(session)
            with self.condition:
                self.current = None
                self.condition.notify_all()
            self.finished(message)

    def _wait(self, session, seconds, interrupt_release=False):
        if session.cancel.is_set() or (interrupt_release and session.released.is_set()):
            return False
        if interrupt_release:
            session.wake.wait(max(0, seconds))
            return not (session.cancel.is_set() or session.released.is_set())
        return not session.cancel.wait(max(0, seconds))

    def _execute(self, session):
        held = {}
        macro = session.macro
        mode = macro["mode"]
        message = "Macro completada"

        def run(events, interrupt=False):
            for index, event in enumerate(events):
                delay = event["delay_ms"]
                if macro.get("standard_delay") and event["type"] != "wait" and index:
                    delay = macro.get("standard_delay_ms", 50)
                if mode == "latch":
                    delay = 0
                if not self._wait(session, delay / 1000, interrupt):
                    return False
                if event["type"] == "wait":
                    continue
                if event["type"] == "text":
                    for offset in range(0, len(event["text"]), 32):
                        if not self._wait(session, 0, interrupt):
                            return False
                        self.sender({**event, "text": event["text"][offset:offset + 32]})
                    continue
                identity = event_identity(event)
                # A quick release can interrupt the press section before its down.
                # Never synthesize an unmatched up against the user's real input.
                if identity and not event["down"] and identity not in held:
                    continue
                self.sender(event)
                if identity:
                    if event["down"]:
                        held[identity] = event
                    else:
                        held.pop(identity, None)
            return True

        try:
            if not self._wait(session, session.delay):
                return "Macro detenida"
            if mode == "once":
                for _ in range(session.repeats):
                    if not run(macro["events"]):
                        break
            elif mode == "latch":
                if run(latched_actions(macro["events"])):
                    session.cancel.wait()
            elif mode in ("hold", "toggle"):
                while run(macro["events"], mode == "hold"):
                    if not self._wait(session, .01, mode == "hold"):
                        break
            else:
                sections = macro["sections"]
                run(sections["press"], True)
                press_held = set(held)
                if not sections["hold"]:
                    # Nothing to repeat: wake only for release/cancellation.
                    session.wake.wait()
                while not session.cancel.is_set() and not session.released.is_set():
                    if sections["hold"]:
                        if not run(sections["hold"], True):
                            break
                    if not self._wait(session, .01, True):
                        break
                if session.released.is_set() and not session.cancel.is_set():
                    # Stop a partially played held cycle before executing release
                    # actions, while retaining outputs intentionally held on press.
                    for identity in reversed(list(held)):
                        if identity not in press_held:
                            self.sender({**held[identity], "down": False})
                            held.pop(identity)
                    run(sections["release"])
            if session.cancel.is_set() or (mode == "hold" and session.released.is_set()):
                message = "Macro detenida"
        except Exception as error:
            message = "Error de reproducción: " + str(error)
        finally:
            failures = []
            for event in reversed(list(held.values())):
                try:
                    self.sender({**event, "down": False})
                except Exception as error:
                    failures.append(str(error))
            if failures:
                message += " · Windows no confirmó todas las liberaciones"
        return message
