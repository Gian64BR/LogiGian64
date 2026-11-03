"""Windows Raw Input enumeration and input synthesis. No device firmware writes."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass, asdict
import hashlib
import re
import winreg

U32 = C.c_uint32
U16 = C.c_uint16
UPTR = C.c_size_t
user32 = C.WinDLL("user32", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)
hid = C.WinDLL("hid", use_last_error=True)
cfgmgr32 = C.WinDLL('cfgmgr32', use_last_error=True)


class RAWINPUTDEVICELIST(C.Structure):
    _fields_ = [("handle", W.HANDLE), ("kind", U32)]


class RAWINPUTDEVICE(C.Structure):
    _fields_ = [("usage_page", U16), ("usage", U16), ("flags", U32), ("target", W.HWND)]


class RAWINPUTHEADER(C.Structure):
    _fields_ = [("kind", U32), ("size", U32), ("device", W.HANDLE), ("wparam", UPTR)]


class RAWKEYBOARD(C.Structure):
    _fields_ = [("scan", U16), ("flags", U16), ("reserved", U16), ("vk", U16),
                ("message", U32), ("extra", U32)]


class BUTTONS(C.Structure):
    _fields_ = [("flags", U16), ("data", U16)]


class MOUSEBUTTONS(C.Union):
    _fields_ = [("buttons", U32), ("split", BUTTONS)]


class RAWMOUSE(C.Structure):
    _fields_ = [("flags", U16), ("button", MOUSEBUTTONS), ("raw_buttons", U32),
                ("x", C.c_int32), ("y", C.c_int32), ("extra", U32)]


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", C.c_int32), ("dy", C.c_int32), ("data", U32), ("flags", U32),
                ("time", U32), ("extra", UPTR)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("vk", U16), ("scan", U16), ("flags", U32), ("time", U32), ("extra", UPTR)]


class INPUTUNION(C.Union):
    _fields_ = [("mouse", MOUSEINPUT), ("key", KEYBDINPUT)]


class INPUT(C.Structure):
    _fields_ = [("kind", U32), ("value", INPUTUNION)]


user32.GetRawInputDeviceList.argtypes = [C.POINTER(RAWINPUTDEVICELIST), C.POINTER(U32), U32]
user32.GetRawInputDeviceList.restype = U32
user32.GetRawInputDeviceInfoW.argtypes = [W.HANDLE, U32, W.LPVOID, C.POINTER(U32)]
user32.GetRawInputDeviceInfoW.restype = U32
user32.GetRawInputData.argtypes = [W.HANDLE, U32, W.LPVOID, C.POINTER(U32), U32]
user32.GetRawInputData.restype = U32
user32.RegisterRawInputDevices.argtypes = [C.POINTER(RAWINPUTDEVICE), U32, U32]
user32.RegisterRawInputDevices.restype = W.BOOL
user32.SendInput.argtypes = [U32, C.POINTER(INPUT), C.c_int]
user32.SendInput.restype = U32
user32.MapVirtualKeyW.argtypes = [U32, U32]
user32.MapVirtualKeyW.restype = U32
user32.GetKeyNameTextW.argtypes = [C.c_int32, W.LPWSTR, C.c_int]
user32.GetKeyNameTextW.restype = C.c_int
user32.GetAsyncKeyState.argtypes = [C.c_int]
user32.GetAsyncKeyState.restype = C.c_short
user32.GetForegroundWindow.restype = W.HWND
user32.GetAncestor.argtypes = [W.HWND, U32]
user32.GetAncestor.restype = W.HWND
kernel32.CreateFileW.argtypes = [W.LPCWSTR, U32, U32, W.LPVOID, U32, U32, W.HANDLE]
kernel32.CreateFileW.restype = W.HANDLE
kernel32.CloseHandle.argtypes = [W.HANDLE]
for func in (hid.HidD_GetProductString, hid.HidD_GetManufacturerString):
    func.argtypes = [W.HANDLE, W.LPVOID, U32]
    func.restype = W.BOOL
cfgmgr32.CM_Locate_DevNodeW.argtypes = [C.POINTER(U32), W.LPWSTR, U32]
cfgmgr32.CM_Get_Parent.argtypes = [C.POINTER(U32), U32, U32]
cfgmgr32.CM_Get_Device_ID_Size.argtypes = [C.POINTER(U32), U32, U32]
cfgmgr32.CM_Get_Device_IDW.argtypes = [U32, W.LPWSTR, U32, U32]
for func in (cfgmgr32.CM_Locate_DevNodeW, cfgmgr32.CM_Get_Parent,
             cfgmgr32.CM_Get_Device_ID_Size, cfgmgr32.CM_Get_Device_IDW):
    func.restype = U32

MOUSE_FLAGS = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40),
               "x1": (0x80, 0x100), "x2": (0x80, 0x100)}
MOUSE_LABELS = {"left": "Clic izquierdo", "right": "Clic derecho", "middle": "Rueda / central",
                "x1": "Botón lateral 4", "x2": "Botón lateral 5"}
SPECIAL_KEYS = {8: "Retroceso", 9: "Tab", 13: "Enter", 16: "Shift", 17: "Ctrl", 18: "Alt",
                20: "Bloq. Mayús", 27: "Esc", 32: "Espacio", 33: "Re Pág", 34: "Av Pág",
                35: "Fin", 36: "Inicio", 37: "Izquierda", 38: "Arriba", 39: "Derecha", 40: "Abajo",
                45: "Insert", 46: "Supr", 91: "Win", 160: "Shift izq.", 161: "Shift der.",
                162: "Ctrl izq.", 163: "Ctrl der.", 164: "Alt izq.", 165: "Alt der."}


def key_name(vk: int, scan: int = 0, extended: bool = False) -> str:
    if vk in SPECIAL_KEYS:
        return SPECIAL_KEYS[vk]
    if 112 <= vk <= 135:
        return f"F{vk - 111}"
    buf = C.create_unicode_buffer(128)
    sc = scan or user32.MapVirtualKeyW(vk, 0)
    if user32.GetKeyNameTextW((sc << 16) | (int(extended) << 24), buf, 128):
        return buf.value
    return f"VK {vk:02X}"


def raw_name(handle: int) -> str:
    size = U32()
    if user32.GetRawInputDeviceInfoW(handle, 0x20000007, None, C.byref(size)) == 0xFFFFFFFF:
        return ""
    buf = C.create_unicode_buffer(size.value + 1)
    if user32.GetRawInputDeviceInfoW(handle, 0x20000007, buf, C.byref(size)) == 0xFFFFFFFF:
        return ""
    return buf.value


def device_strings(path: str) -> tuple[str, str]:
    handle = kernel32.CreateFileW(path, 0, 3, None, 3, 0, None)
    if handle in (None, C.c_void_p(-1).value):
        return "", ""
    try:
        values = []
        for func in (hid.HidD_GetProductString, hid.HidD_GetManufacturerString):
            buf = C.create_unicode_buffer(256)
            values.append(buf.value if func(handle, buf, C.sizeof(buf)) else "")
        return tuple(values)
    finally:
        kernel32.CloseHandle(handle)


def registry_label(path: str) -> str:
    parts = path.replace("\\??\\", "").replace("\\\\?\\", "").split("#")
    if len(parts) < 3:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Enum\\" + "\\".join(parts[:3])) as key:
            for field in ("FriendlyName", "DeviceDesc"):
                try:
                    value = winreg.QueryValueEx(key, field)[0]
                    if value:
                        return str(value).split(";")[-1]
                except OSError:
                    pass
    except OSError:
        pass
    return ""


def container_id(path: str) -> str:
    parts = path.replace("\\\\?\\", "").split("#")
    if len(parts) >= 3:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Enum\\" + "\\".join(parts[:3])) as key:
                return str(winreg.QueryValueEx(key, "ContainerID")[0])
        except OSError:
            pass
    return path.upper()


def device_ancestry(path):
    parts = path.replace('\\??\\', '').replace('\\\\?\\', '').split('#')
    if len(parts) < 3:
        return []
    node = U32()
    if cfgmgr32.CM_Locate_DevNodeW(C.byref(node), '\\'.join(parts[:3]), 0):
        return []
    result, visited = [], set()
    for _ in range(16):
        if node.value in visited:
            break
        visited.add(node.value)
        size = U32()
        if cfgmgr32.CM_Get_Device_ID_Size(C.byref(size), node, 0) or size.value > 32767:
            break
        buf = C.create_unicode_buffer(size.value + 1)
        if cfgmgr32.CM_Get_Device_IDW(node, buf, len(buf), 0):
            break
        result.append(buf.value.upper())
        parent = U32()
        if cfgmgr32.CM_Get_Parent(C.byref(parent), node, 0):
            break
        node = parent
    return result


def virtual_ancestry(ancestry):
    # Do not blacklist a vendor, all ROOT nodes, or every software component:
    # physical USB/Bluetooth/PS2 devices also have a system root ancestor.
    prefixes = ('LGHUBDEVICE\\', 'LOGIDEVICE\\', 'ROOT\\LGVIRHID\\',
                'ROOT\\VIRTUALHID\\', 'ROOT\\VIRTUALKEYBOARD\\', 'ROOT\\VIRTUALMOUSE\\')
    return any(instance.upper().startswith(prefixes) for instance in ancestry)


@dataclass
class Device:
    id: str
    name: str
    kind: str
    manufacturer: str
    vid: str
    pid: str
    paths: list[str]
    handles: list[int]
    virtual: bool = False
    identification: str = ''

    def to_dict(self):
        return asdict(self)


def enumerate_devices(include_virtual=False) -> list[Device]:
    from .device_identity import load_identities, resolve_identities
    # Retry the documented enumeration race when a device arrives during the call.
    for _ in range(4):
        count = U32()
        if user32.GetRawInputDeviceList(None, C.byref(count), C.sizeof(RAWINPUTDEVICELIST)) == 0xFFFFFFFF:
            raise C.WinError(C.get_last_error())
        array = (RAWINPUTDEVICELIST * (count.value + 8))()
        count.value += 8
        result = user32.GetRawInputDeviceList(array, C.byref(count), C.sizeof(RAWINPUTDEVICELIST))
        if result != 0xFFFFFFFF:
            break
        if C.get_last_error() != 122:
            raise C.WinError(C.get_last_error())
    else:
        raise OSError("Los dispositivos cambian continuamente. Vuelve a actualizar.")
    devices: dict[str, Device] = {}
    identities = load_identities()
    for item in array[:result]:
        if item.kind not in (0, 1):
            continue
        path = raw_name(item.handle)
        if not path:
            continue
        virtual = virtual_ancestry(device_ancestry(path))
        if virtual and not include_virtual:
            continue
        kind = "mouse" if item.kind == 0 else "keyboard"
        match = re.search(r"vid_([0-9a-f]{4}).*?pid_([0-9a-f]{4})", path, re.I)
        vid, pid = (x.upper() for x in match.groups()) if match else ("", "")
        product, maker = device_strings(path)
        brand = {"046D": "Logitech", "1532": "Razer", "1B1C": "Corsair", "1038": "SteelSeries",
                 "0951": "HyperX", "258A": "Dispositivo HID", "05AC": "Apple"}.get(vid, "HID")
        name = product or registry_label(path) or ("Ratón HID" if kind == "mouse" else "Teclado HID")
        if name.casefold().strip() in ('usb device', 'usb keyboard', 'usb gaming keyboard'):
            name = f"{'Ratón' if kind == 'mouse' else 'Teclado'} USB · {vid}:{pid}"
        if name.lower() in ("hid-compliant mouse", "mouse compatible con hid", "hid keyboard device", "dispositivo de teclado hid") and vid:
            name = f"{brand} · {'Ratón' if kind == 'mouse' else 'Teclado'} {pid}"
        # User-identified KNUP on this workstation; USB descriptors are generic.
        if kind == "mouse" and (vid, pid) == ("30FA", "0400"):
            name = "KNUP KP-V84"
            maker = "KNUP"
        # Container ID groups composite collections without merging identical units.
        identity = hashlib.sha256(container_id(path).upper().encode()).hexdigest()[:24]
        if identity not in devices:
            devices[identity] = Device(identity, name, kind, maker or brand, vid, pid, [path], [int(item.handle)], virtual)
        else:
            device = devices[identity]
            device.paths.append(path)
            device.handles.append(int(item.handle))
            if kind == "mouse":
                device.kind, device.name = kind, name
    resolve_identities(list(devices.values()), identities)
    return sorted(devices.values(), key=lambda d: (d.kind != "mouse", d.name.casefold(), d.id))


def register_input(hwnd: int):
    registrations = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, 0x2100, hwnd), RAWINPUTDEVICE(1, 6, 0x2100, hwnd))
    if not user32.RegisterRawInputDevices(registrations, 2, C.sizeof(RAWINPUTDEVICE)):
        raise C.WinError(C.get_last_error())


def unregister_input():
    registrations = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, 1, None), RAWINPUTDEVICE(1, 6, 1, None))
    user32.RegisterRawInputDevices(registrations, 2, C.sizeof(RAWINPUTDEVICE))


def read_input(lparam: int) -> tuple[int, list[dict]] | None:
    size = U32()
    header_size = C.sizeof(RAWINPUTHEADER)
    if user32.GetRawInputData(lparam, 0x10000003, None, C.byref(size), header_size) == 0xFFFFFFFF:
        return None
    if size.value < header_size or size.value > 65536:
        return None
    buf = C.create_string_buffer(size.value)
    if user32.GetRawInputData(lparam, 0x10000003, buf, C.byref(size), header_size) == 0xFFFFFFFF:
        return None
    header = RAWINPUTHEADER.from_buffer_copy(buf)
    pointer = C.addressof(buf) + header_size
    events = []
    if header.kind == 1 and size.value >= header_size + C.sizeof(RAWKEYBOARD):
        key = RAWKEYBOARD.from_address(pointer)
        if key.extra == 0x4E584853:
            return None
        if key.vk not in (0, 255):
            events.append({"type": "key", "vk": key.vk, "scan": key.scan, "extended": bool(key.flags & 2), "down": not bool(key.flags & 1)})
    elif header.kind == 0 and size.value >= header_size + C.sizeof(RAWMOUSE):
        mouse = RAWMOUSE.from_address(pointer)
        if mouse.extra == 0x4E584853:
            return None
        flags = mouse.button.split.flags
        for bit, button, down in ((1, "left", True), (2, "left", False), (4, "right", True), (8, "right", False),
                                   (16, "middle", True), (32, "middle", False), (64, "x1", True), (128, "x1", False),
                                   (256, "x2", True), (512, "x2", False)):
            if flags & bit:
                events.append({"type": "mouse", "button": button, "down": down})
        for bit, axis in ((0x400, "vertical"), (0x800, "horizontal")):
            if flags & bit:
                events.append({"type": "wheel", "delta": C.c_short(mouse.button.split.data).value, "axis": axis})
    return int(header.device or 0), events


def send_event(event: dict):
    packet = INPUT()
    kind = event["type"]
    if kind == "text":
        raw = event["text"].encode("utf-16-le")
        packets = (INPUT * len(raw))()
        for n in range(len(raw) // 2):
            code = int.from_bytes(raw[n * 2:n * 2 + 2], "little")
            for up in (0, 1):
                packets[n * 2 + up].kind = 1
                packets[n * 2 + up].value.key = KEYBDINPUT(0, code, 4 | (2 if up else 0), 0, 0x4E584853)
        if user32.SendInput(len(packets), packets, C.sizeof(INPUT)) != len(packets):
            raise OSError("Windows no permitió escribir todo el texto.")
        return
    if kind == "launch":
        import subprocess
        from pathlib import Path
        if not Path(event["path"]).is_file():
            raise OSError("La aplicación asignada ya no existe: " + event["path"])
        subprocess.Popen([event["path"]], close_fds=True)
        return
    if kind == "key":
        packet.kind = 1
        scan = int(event.get("scan", 0))
        packet.value.key = KEYBDINPUT(0 if scan else int(event["vk"]), scan,
            (8 if scan else 0) | (0 if event["down"] else 2) | (1 if event.get("extended") else 0), 0, 0x4E584853)
    elif kind in ("mouse", "wheel"):
        packet.kind = 0
        if kind == "wheel":
            packet.value.mouse = MOUSEINPUT(0, 0, int(event["delta"]) & 0xFFFFFFFF, 0x1000 if event.get("axis") == "horizontal" else 0x800, 0, 0x4E584853)
        else:
            button = event["button"]
            flags = MOUSE_FLAGS[button][0 if event["down"] else 1]
            packet.value.mouse = MOUSEINPUT(0, 0, 1 if button == "x1" else 2 if button == "x2" else 0, flags, 0, 0x4E584853)
    else:
        return
    if user32.SendInput(1, C.byref(packet), C.sizeof(INPUT)) != 1:
        raise OSError("Windows no permitió enviar la entrada. Comprueba que el destino no se ejecute con más privilegios.")


def modifiers() -> list[str]:
    result = [name for vk, name in ((17, "Ctrl"), (18, "Alt"), (16, "Shift")) if user32.GetAsyncKeyState(vk) & 0x8000]
    if any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (91, 92)):
        result.append("Win")
    return result


def pointer_speed() -> int:
    value = U32()
    if not user32.SystemParametersInfoW(0x70, 0, C.byref(value), 0):
        raise C.WinError(C.get_last_error())
    return value.value


def set_pointer_speed(value: int):
    if not 1 <= value <= 20:
        raise ValueError("La velocidad debe estar entre 1 y 20")
    if not user32.SystemParametersInfoW(0x71, 0, C.c_void_p(value), 3):
        raise C.WinError(C.get_last_error())
