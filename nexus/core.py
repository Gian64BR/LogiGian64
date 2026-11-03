"""Portable profile format, atomic persistence and cancellable macro execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid
from .safety import protected_control

MAX_EVENTS = 5000


def new_id() -> str:
    return uuid.uuid4().hex


def new_profile(name: str = "Escritorio") -> dict:
    return {"id": new_id(), "name": name, "macros": [], "bindings": [], "colors": {}}


def validate_events(events: list, *, initial_held=None, balanced=True) -> list[dict]:
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError(f"Una macro admite hasta {MAX_EVENTS} pasos.")
    result = []
    held = set(initial_held or ())
    total = 0
    for n, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ValueError(f"Paso {n}: formato incorrecto.")
        delay = event.get("delay_ms", 0)
        if type(delay) is not int or not 0 <= delay <= 60000:
            raise ValueError(f"Paso {n}: la espera debe estar entre 0 y 60000 ms.")
        total += delay
        kind = event.get("type")
        clean = {"type": kind, "delay_ms": delay}
        identity = None
        if kind == "key":
            vk, scan = event.get("vk"), event.get("scan", 0)
            if type(vk) is not int or not 1 <= vk <= 254 or type(scan) is not int or not 0 <= scan <= 65535:
                raise ValueError(f"Paso {n}: tecla incorrecta.")
            if type(event.get("down")) is not bool:
                raise ValueError(f"Paso {n}: falta el estado pulsar/soltar.")
            clean.update(vk=vk, scan=scan, extended=bool(event.get("extended", False)), down=event["down"])
            identity = ("key", vk, scan, clean["extended"])
        elif kind == "mouse":
            if event.get("button") not in ("left", "right", "middle", "x1", "x2") or type(event.get("down")) is not bool:
                raise ValueError(f"Paso {n}: botón incorrecto.")
            clean.update(button=event["button"], down=event["down"])
            identity = ("mouse", clean["button"])
        elif kind == "wheel":
            delta = event.get("delta")
            if type(delta) is not int or not -12000 <= delta <= 12000:
                raise ValueError(f"Paso {n}: desplazamiento incorrecto.")
            if event.get("axis", "vertical") not in ("vertical", "horizontal"):
                raise ValueError(f"Paso {n}: eje incorrecto.")
            clean.update(delta=delta, axis=event.get("axis", "vertical"))
        elif kind == "text":
            text = event.get("text")
            if not isinstance(text, str) or not 1 <= len(text) <= 5000 or "\x00" in text:
                raise ValueError(f"Paso {n}: el texto debe contener entre 1 y 5000 caracteres.")
            clean["text"] = text
        elif kind == "launch":
            path = event.get("path")
            if not isinstance(path, str) or "\x00" in path or not Path(path).is_absolute() or Path(path).suffix.lower() != ".exe":
                raise ValueError(f"Paso {n}: selecciona una ruta absoluta a una aplicación .exe.")
            clean["path"] = path
        elif kind != "wait":
            raise ValueError(f"Paso {n}: tipo de acción desconocido.")
        if identity:
            if clean["down"]:
                held.add(identity)
            elif identity not in held:
                raise ValueError(f"Paso {n}: se suelta una tecla o botón que no se ha pulsado.")
            else:
                held.remove(identity)
        result.append(clean)
    if balanced and held:
        raise ValueError("Hay teclas o botones sin soltar. Añade su acción de liberación.")
    if total > 1800000:
        raise ValueError("La duración de una macro no puede superar 30 minutos.")
    return result


MODES = {"once": "Sin repetición", "hold": "Repetir durante pulsación", "toggle": "Alternante", "sequence": "Secuencia", "latch": "Mantener pulsado"}


def held_after(events, initial=()):
    held = set(initial)
    for event in events:
        identity = event_identity(event)
        if identity:
            if event["down"]:
                held.add(identity)
            else:
                held.discard(identity)
    return held


def event_identity(event):
    if event["type"] == "key":
        return ("key", event["vk"], event.get("scan", 0), bool(event.get("extended", False)))
    if event["type"] == "mouse":
        return ("mouse", event["button"])
    return None


def latched_actions(events):
    """Each distinct output goes down once; release is owned by the session."""
    actions = {}
    for event in events:
        identity = event_identity(event)
        if identity and event["down"]:
            actions.setdefault(identity, {**event, "delay_ms": 0})
    return list(actions.values())


def validate_macro(macro):
    if not isinstance(macro, dict) or not isinstance(macro.get("name"), str) or not macro["name"].strip():
        raise ValueError("Cada macro necesita un nombre.")
    mode = macro.get("mode", "once")
    if mode not in MODES:
        raise ValueError("Tipo de macro desconocido.")
    repeats = macro.get("repeats", 1)
    if type(repeats) is not int or not 1 <= repeats <= 100:
        raise ValueError("Las repeticiones deben estar entre 1 y 100.")
    delay = macro.get("standard_delay_ms", 50)
    if type(delay) is not int or not 0 <= delay <= 60000:
        raise ValueError("El retardo estándar debe estar entre 0 y 60000 ms.")
    color = macro.get("color", "#9b0037")
    import re
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Color de macro incorrecto.")
    clean = {"id": str(macro.get("id") or new_id())[:100], "name": macro["name"].strip()[:100],
             "mode": mode, "repeats": repeats, "standard_delay": bool(macro.get("standard_delay", False)),
             "standard_delay_ms": delay, "color": color}
    if mode == "sequence":
        sections = macro.get("sections", {})
        if not isinstance(sections, dict):
            raise ValueError("La secuencia necesita sus tres secciones.")
        press = validate_events(sections.get("press", []), balanced=False)
        held = held_after(press)
        loop = validate_events(sections.get("hold", []), initial_held=held, balanced=False)
        if held_after(loop, held) != held:
            raise ValueError("La sección Durante pulsación debe dejar las mismas teclas pulsadas al terminar cada ciclo.")
        release = validate_events(sections.get("release", []), initial_held=held)
        if sum(map(len, (press, loop, release))) > MAX_EVENTS:
            raise ValueError(f"Se permiten hasta {MAX_EVENTS} pasos en total.")
        clean.update(events=[], sections={"press": press, "hold": loop, "release": release})
    else:
        clean["events"] = validate_events(macro.get("events", []), balanced=mode == "once")
        if mode == "latch" and any(e["type"] not in ("key", "mouse", "wait") for e in clean["events"]):
            raise ValueError("Mantener pulsado admite teclas y botones del mouse.")
    return clean


def validate_profile(value: dict) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or not value["name"].strip():
        raise ValueError("El perfil necesita un nombre.")
    profile = new_profile(value["name"].strip()[:100])
    profile["id"] = str(value.get("id") or new_id())[:100]
    macros = value.get("macros", [])
    if not isinstance(macros, list) or len(macros) > 200:
        raise ValueError("Un perfil admite hasta 200 macros.")
    ids = set()
    for macro in macros:
        if not isinstance(macro, dict) or not isinstance(macro.get("name"), str) or not macro["name"].strip():
            raise ValueError("Cada macro necesita un nombre.")
        mid = str(macro.get("id") or new_id())[:100]
        if mid in ids:
            raise ValueError("El perfil contiene IDs de macros duplicados.")
        ids.add(mid)
        profile["macros"].append(validate_macro({**macro, "id": mid}))
    bindings = value.get("bindings", [])
    if not isinstance(bindings, list) or len(bindings) > 500:
        raise ValueError("Demasiadas asignaciones.")
    for binding in bindings:
        if isinstance(binding, dict) and protected_control(binding):
            continue
        if not isinstance(binding, dict) or binding.get("macro_id") not in ids:
            raise ValueError("Una asignación apunta a una macro inexistente.")
        device_id = binding.get("device_id")
        trigger = binding.get("trigger")
        if not isinstance(device_id, str) or not isinstance(trigger, dict):
            raise ValueError("Asignación de dispositivo incorrecta.")
        kind = trigger.get("type")
        if kind == "key":
            vk = trigger.get("vk")
            if type(vk) is not int or not 1 <= vk <= 254:
                raise ValueError("Tecla incorrecta.")
            mods = trigger.get("mods", [])
            if not isinstance(mods, list) or any(m not in ("Ctrl", "Alt", "Shift", "Win") for m in mods):
                raise ValueError("Modificadores incorrectos.")
            clean_trigger = {"type": "key", "vk": vk, "mods": sorted(set(mods))}
            if vk == 123 and {"Ctrl", "Alt"}.issubset(mods):
                raise ValueError("Ctrl+Alt+F12 está reservado para detener las macros.")
        elif kind == "mouse" and trigger.get("button") in ("middle", "x1", "x2"):
            clean_trigger = {"type": "mouse", "button": trigger["button"]}
        elif kind == "gbutton" and type(trigger.get("button")) is int and 0 <= trigger["button"] < 16:
            clean_trigger = {"type": "gbutton", "button": trigger["button"]}
        else:
            raise ValueError("Activador incorrecto.")
        profile["bindings"].append({"device_id": device_id, "trigger": clean_trigger, "macro_id": binding["macro_id"],
                                    "enabled": bool(binding.get("enabled", True)), "slot": str(binding.get("slot", ""))[:40]})
    disabled = value.get("disabled_controls", [])
    if not isinstance(disabled, list) or len(disabled) > 500:
        raise ValueError("Controles desactivados incorrectos.")
    profile["disabled_controls"] = []
    for control in disabled:
        if isinstance(control, dict) and protected_control(control):
            continue
        if (not isinstance(control, dict) or not isinstance(control.get("device_id"), str)
                or control.get("slot") not in ({f"G{n}" for n in range(1, 12)} | {"Principal", "Secundario", "Central", "Lateral 4", "Lateral 5", "Tecla"})
                or not (control.get("button") is None or (type(control.get("button")) is int and 0 <= control["button"] < 16))):
            raise ValueError("Control desactivado incorrecto.")
        profile["disabled_controls"].append({k: control[k] for k in ("device_id", "slot", "button")})
    colors = value.get("colors", {})
    if isinstance(colors, dict):
        import re
        profile["colors"] = {str(k)[:100]: v for k, v in colors.items() if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}
    return profile


class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NexusHub"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "profiles.json"
        self.warning = ""
        self.profiles = [new_profile()]
        self.active_id = self.profiles[0]["id"]
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("version") not in (1, 2) or not isinstance(data.get("profiles"), list) or not 1 <= len(data["profiles"]) <= 100:
                    raise ValueError("Formato de biblioteca desconocido.")
                self.profiles = [validate_profile(p) for p in data["profiles"]]
                if len({p["id"] for p in self.profiles}) != len(self.profiles):
                    raise ValueError("Perfiles duplicados.")
                self.active_id = data.get("active_id")
                if not any(p["id"] == self.active_id for p in self.profiles):
                    self.active_id = self.profiles[0]["id"]
                if data["version"] == 1:
                    backup = self.directory / f"profiles-v1-backup-{time.time_ns()}.json"
                    backup.write_bytes(self.path.read_bytes())
            except (OSError, ValueError, TypeError, KeyError) as error:
                # Preserve the source before the next successful write.
                backup = self.directory / f"profiles-recovery-{time.time_ns()}.json"
                backup.write_bytes(self.path.read_bytes())
                self.warning = f"Se conservó la biblioteca original en {backup.name}: {error}"
                self.profiles = [new_profile()]
                self.active_id = self.profiles[0]["id"]

    @property
    def active(self) -> dict:
        return next(p for p in self.profiles if p["id"] == self.active_id)

    def save(self):
        profiles = [validate_profile(p) for p in self.profiles]
        payload = json.dumps({"version": 2, "active_id": self.active_id, "profiles": profiles}, indent=2, ensure_ascii=False)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

