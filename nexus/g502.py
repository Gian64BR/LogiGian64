"""G502 HERO volatile host control through HID++ 0x8100 / 0x8110.

No flash or onboard profile writes. Maps and mode are snapshotted and restored.
Only activated by an explicit user action and only while G HUB's agent is absent.
"""
from __future__ import annotations

import queue
import subprocess
import sys
from pathlib import Path
import threading
import time
import hashlib

try:
    import hid
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor"))
    import hid


def ghub_running():
    try:
        result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq lghub_agent.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="replace", timeout=4, creationflags=0x08000000)
    except subprocess.SubprocessError as error:
        raise OSError("Windows no respondió al comprobar el agente de G HUB.") from error
    if result.returncode:
        raise OSError("No se pudo comprobar si G HUB tiene el control del ratón.")
    return '"lghub_agent.exe"' in result.stdout.lower()


def close_ghub():
    """Called only after the user accepts the explicit takeover dialog."""
    for name in ("lghub.exe", "lghub_system_tray.exe", "lghub_agent.exe"):
        try:
            subprocess.run(["taskkill.exe", "/IM", name, "/T", "/F"], capture_output=True,
                           timeout=5, creationflags=0x08000000)
        except subprocess.SubprocessError as error:
            raise OSError("Windows no respondió al cerrar G HUB.") from error
    if ghub_running():
        raise OSError("No se pudo cerrar el agente de G HUB. Ciérralo desde su bandeja o el Administrador de tareas y vuelve a intentarlo.")


def decode_buttons(report, feature_index, previous, count):
    if len(report) < 6 or report[0] != 0x11 or report[1] != 255 or report[2] != feature_index or report[3] != 0:
        return previous, []
    mask = ((report[4] << 8) | report[5]) & ((1 << count) - 1)
    changed = mask ^ previous
    return mask, [{"type": "gbutton", "button": bit, "down": bool(mask & (1 << bit))}
                  for bit in range(count) if changed & (1 << bit)]


def matches_device(item, device):
    from .windows import container_id
    path = item["path"].decode("utf-8") if isinstance(item["path"], bytes) else item["path"]
    identity = hashlib.sha256(container_id(path).upper().encode()).hexdigest()[:24]
    return identity == device.id


class G502Session:
    def __init__(self, device, on_event, on_status, on_error):
        self.device = device
        self.handle = -int(device.id[:12], 16)
        self.on_event, self.on_status, self.on_error = on_event, on_status, on_error
        self.commands = queue.Queue()
        self.stop_requested = threading.Event()
        self.thread = None
        self.ready = False
        self.needs_restore = False
        self.channel = None
        self.spy = self.profiles = 0
        self.count = 0
        self.original_mode = None
        self.original_map = None
        self.changed_mode = False
        self.started_spy = False
        self.changed_map = False
        self.previous = 0
        self.request_id = 0
        self.monitor_error = None

    def _monitor(self):
        while not self.stop_requested.wait(4):
            try:
                conflict = ghub_running()
                reason = "G HUB volvió a abrirse. Se detuvo el control directo para evitar dos controladores simultáneos."
            except OSError as error:
                conflict, reason = True, str(error)
            if conflict and not self.stop_requested.is_set():
                self.monitor_error = reason
                self.stop_requested.set()
                return

    def start(self, buttons=()):
        self.thread = threading.Thread(target=self._run, args=(set(buttons),), daemon=True, name="G502HID")
        self.thread.start()

    def update_buttons(self, buttons):
        self.commands.put(set(buttons))

    def close(self):
        self.stop_requested.set()
        if self.thread:
            self.thread.join(timeout=4)
        if self.thread and self.thread.is_alive():
            self.on_error("El G502 aún está restaurando su configuración. Espera antes de cerrar.")
            return False
        if self.needs_restore:
            failures = self._restore()
            self.needs_restore = bool(failures)
            if failures:
                self.on_error("No se pudo restaurar todavía: " + "; ".join(failures))
                return False
            self.discard()
        return True

    def discard(self):
        if self.channel:
            self.channel.close()
            self.channel = None

    def _report(self, report):
        self.previous, events = decode_buttons(report, self.spy, self.previous, self.count)
        for event in events:
            self.on_event(self.handle, event)

    def request(self, index, function, data=(), timeout=.65):
        # Distinct IDs prevent an old delayed reply from satisfying a new request.
        self.request_id = self.request_id % 7 + 8
        address = (function << 4) | self.request_id
        packet = [0x11, 255, index, address] + list(data)
        packet += [0] * (20 - len(packet))
        if len(packet) != 20:
            raise ValueError("Paquete HID++ fuera de rango.")
        self.channel.write(packet)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            report = self.channel.read(64, 30)
            if not report:
                continue
            if len(report) >= 4 and report[1:4] == [255, index, address]:
                return report[4:]
            if len(report) >= 6 and report[1:5] == [255, 255, index, address]:
                raise OSError(f"El G502 rechazó la operación HID++ ({report[5]}).")
            if self.spy:
                self._report(report)
        raise TimeoutError("El G502 no confirmó la operación. Comprueba que G HUB esté cerrado.")

    def feature(self, feature_id):
        index = self.request(0, 0, [feature_id >> 8, feature_id & 255])[0]
        if not index:
            raise OSError(f"El G502 no expone la función {feature_id:04X}.")
        return index

    def _apply_map(self, buttons):
        desired = list(self.original_map)
        for bit in buttons:
            if 0 <= bit < self.count:
                desired[bit] = 0
        if self.request(self.spy, 3)[:self.count] == desired:
            return
        # Mark before sending: a missing acknowledgement can still mean a write.
        self.changed_map = True
        self.request(self.spy, 4, desired)
        if self.request(self.spy, 3)[:self.count] != desired:
            raise OSError("El G502 no confirmó el mapa temporal de botones.")

    def _restore(self):
        failures = []
        for needed, index, fn, data, description in (
            (self.changed_map, self.spy, 4, self.original_map or [], "mapa de botones"),
            (self.started_spy, self.spy, 2, [], "captura de botones"),
            (self.changed_mode, self.profiles, 1, [self.original_mode or 1], "modo del ratón")):
            if needed:
                try:
                    self.request(index, fn, data)
                    if description == "mapa de botones" and self.request(self.spy, 3)[:self.count] != self.original_map:
                        raise OSError("El mapa original no se confirmó por lectura.")
                    if description == "modo del ratón" and self.request(self.profiles, 2)[0] != self.original_mode:
                        raise OSError("El modo original no se confirmó por lectura.")
                    if description == "mapa de botones":
                        self.changed_map = False
                    elif description == "modo del ratón":
                        self.changed_mode = False
                    else:
                        self.started_spy = False
                except Exception as error:
                    failures.append(description + ": " + str(error))
        return failures

    def _run(self, buttons):
        problem = None
        try:
            if ghub_running():
                raise OSError("G HUB está controlando el G502. Cierra G HUB y su agente antes de activar el control directo en LogiGian64; "
                              "así no se ejecutarán dos macros para el mismo botón.")
            info = next((item for item in hid.enumerate(0x046D, 0xC08B)
                         if item.get("usage_page") == 0xFF00 and item.get("usage") == 2 and matches_device(item, self.device)), None)
            if not info:
                raise OSError("No se encontró la interfaz HID++ del G502 HERO.")
            self.channel = hid.device()
            self.channel.open_path(info["path"])
            self.spy, self.profiles = self.feature(0x8110), self.feature(0x8100)
            self.count = self.request(self.spy, 0)[0]
            if not 1 <= self.count <= 16:
                raise OSError("El número de botones comunicado por el ratón no es válido.")
            self.original_mode = self.request(self.profiles, 2)[0]
            if self.original_mode not in (1, 2):
                raise OSError("El modo actual del ratón es desconocido; no se cambiará.")
            self.original_map = self.request(self.spy, 3)[:self.count]
            if len(self.original_map) != self.count:
                raise OSError("No se pudo guardar el mapa original de botones.")
            if self.original_mode != 2:
                self.changed_mode = True
                self.request(self.profiles, 1, [2])
                if self.request(self.profiles, 2)[0] != 2:
                    raise OSError("El G502 no confirmó el modo host.")
            self.started_spy = True
            self.request(self.spy, 1)
            self._apply_map(buttons)
            self.ready = True
            self.on_status(f"G502 conectado directamente · {self.count} botones físicos · Ctrl+Alt+F12 detiene macros")
            threading.Thread(target=self._monitor, name="G502Ownership", daemon=True).start()
            while not self.stop_requested.is_set():
                try:
                    newest = self.commands.get_nowait()
                    while not self.commands.empty():
                        newest = self.commands.get_nowait()
                    self._apply_map(newest)
                except queue.Empty:
                    pass
                report = self.channel.read(64, 50)
                if report:
                    self._report(report)
        except Exception as error:
            problem = str(error)
        finally:
            self.stop_requested.set()
            problem = problem or self.monitor_error
            self.ready = False
            # Deliver releases even after cable loss so a held macro cannot continue.
            for bit in range(self.count):
                if self.previous & (1 << bit):
                    self.on_event(self.handle, {"type": "gbutton", "button": bit, "down": False})
            if self.channel:
                failures = self._restore()
                self.needs_restore = bool(failures)
                if not failures:
                    self.discard()
                if failures:
                    problem = (problem + "\n" if problem else "") + "Restauración pendiente: " + "; ".join(failures)
            if problem:
                self.on_error(problem)
            else:
                self.on_status("Control directo del G502 desconectado; configuración temporal restaurada.")
