"""Linux evdev/uinput adapter. Profiles keep portable VK identifiers; input is never grabbed."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import importlib
import logging
import os
import select
import subprocess
import threading
import time

VIRTUAL_NAME = 'LogiGian64 Virtual Input'
MOUSE_LABELS = {'left':'Clic izquierdo','right':'Clic derecho','middle':'Rueda / central','x1':'Boton lateral 4','x2':'Boton lateral 5'}
SPECIAL_KEYS = {8:'Retroceso',9:'Tab',13:'Enter',16:'Shift',17:'Ctrl',18:'Alt',20:'Bloq. Mayus',27:'Esc',32:'Espacio',33:'Re Pag',34:'Av Pag',35:'Fin',36:'Inicio',37:'Izquierda',38:'Arriba',39:'Derecha',40:'Abajo',45:'Insert',46:'Supr',91:'Super',92:'Super der.',160:'Shift izq.',161:'Shift der.',162:'Ctrl izq.',163:'Ctrl der.',164:'Alt izq.',165:'Alt der.',173:'Silenciar',174:'Bajar volumen',175:'Subir volumen',176:'Pista siguiente',177:'Pista anterior',178:'Detener',179:'Reproducir / pausar'}
VK_TO_EV = {8:14,9:15,13:28,16:42,17:29,18:56,20:58,27:1,32:57,33:104,34:109,35:107,36:102,37:105,38:103,39:106,40:108,45:110,46:111,91:125,92:126,144:69,145:70,160:42,161:54,162:29,163:97,164:56,165:100,173:113,174:114,175:115,176:163,177:165,178:166,179:164,186:39,187:13,188:51,189:12,190:52,191:53,192:41,219:26,220:43,221:27,222:40,106:55,107:78,109:74,110:83,111:98}
VK_TO_EV.update({ord(c):n for c,n in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',[30,48,46,32,18,33,34,35,23,36,37,38,50,49,24,25,16,19,31,20,22,47,17,45,21,44])})
VK_TO_EV.update({ord(c):n for c,n in zip('1234567890',range(2,12))})
VK_TO_EV.update({112+i:n for i,n in enumerate([*range(59,69),87,88,*range(183,195)])})
VK_TO_EV.update({96+i:n for i,n in enumerate([82,79,80,81,75,76,77,71,72,73])})
EV_TO_VK = {code:vk for vk,code in VK_TO_EV.items()}
BUTTONS = {'left':272,'right':273,'middle':274,'x1':275,'x2':276}
BUTTON_NAMES = {v:k for k,v in BUTTONS.items()}
PERMISSION_HELP = 'Sin acceso a los dispositivos. Ejecuta enable-device-access.sh con sudo, cierra la sesion y vuelve a entrar. No ejecutes la interfaz como root.'
_state_lock = threading.RLock()
_active_keys = set()
_last_errors = []
_callbacks = None
_service = None
_writer = None
_writer_lock = threading.RLock()

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
    button_count: int | None = None
    def to_dict(self):
        return asdict(self)


def _evdev():
    try:
        return importlib.import_module('evdev')
    except ImportError as error:
        raise OSError('Falta python-evdev. Ejecuta install.sh desde el paquete Linux.') from error


def _context():
    try:
        return importlib.import_module('pyudev').Context()
    except ImportError as error:
        raise OSError('Falta pyudev. Ejecuta install.sh desde el paquete Linux.') from error


def _udev(path):
    pyudev = importlib.import_module('pyudev')
    try:
        return pyudev.Devices.from_device_file(_context(), os.fsdecode(path))
    except pyudev.DeviceNotFoundError as error:
        raise OSError('El dispositivo fue desconectado: '+os.fsdecode(path)) from error


def container_id(path):
    node = _udev(path)
    parent = node.find_parent('usb', 'usb_device') or node.find_parent('hid')
    if parent is None:
        parent = node.find_parent('input')
        parent = parent.parent if parent is not None and parent.parent is not None else node
    return str(parent.sys_path).upper()


def _identity(path, kind):
    base = container_id(path)
    return hashlib.sha256((base + ('|KEYBOARD' if kind == 'keyboard' else '')).encode()).hexdigest()[:24]


def _handle(path):
    return int(hashlib.sha256(str(path).encode()).hexdigest()[:12],16)


def key_name(vk, scan=0, extended=False):
    if vk in SPECIAL_KEYS:
        return SPECIAL_KEYS[vk]
    if 112 <= vk <= 135:
        return 'F'+str(vk-111)
    if 65 <= vk <= 90 or 48 <= vk <= 57:
        return chr(vk)
    if 96 <= vk <= 105:
        return 'Num '+str(vk-96)
    return {186:';',187:'=',188:',',189:'-',190:'.',191:'/',192:'`',219:'[',220:chr(92),221:']',222:"'"}.get(vk, f'Tecla {vk}')


def enumerate_devices(include_virtual=False):
    from .device_identity import load_identities, resolve_identities
    from .device_catalog import apply_catalog
    evdev = _evdev()
    devices = {}
    errors = []
    for path in sorted(Path('/dev/input').glob('event*')):
        node = None
        dev = None
        try:
            node = _udev(str(path))
            props = node.properties
            try:
                name = (Path('/sys/class/input')/path.name/'device/name').read_text().strip()
            except OSError:
                name = props.get('ID_MODEL', 'Dispositivo Linux')
            virtual = name.startswith(VIRTUAL_NAME) or '/devices/virtual/input/' in node.sys_path
            if virtual and not include_virtual:
                continue
            kind = 'mouse' if props.get('ID_INPUT_MOUSE') == '1' else 'keyboard' if props.get('ID_INPUT_KEYBOARD') == '1' else None
            if not kind:
                continue
            try:
                dev = evdev.InputDevice(str(path))
                name = dev.name
                info = dev.info
                vid, pid = f'{info.vendor:04X}', f'{info.product:04X}'
                count = len(set(dev.capabilities().get(1,[])) & set(BUTTON_NAMES)) if kind=='mouse' else None
            except PermissionError:
                errors.append(str(path))
                vid, pid = props.get('ID_VENDOR_ID','').upper(), props.get('ID_MODEL_ID','').upper()
                count = None
            identity = _identity(str(path),kind)
            if kind == 'keyboard' and 'mouse' in name.casefold():
                name = f'Teclado USB - {vid}:{pid}'
            if identity in devices:
                devices[identity].paths.append(str(path));devices[identity].handles.append(_handle(path))
                if count is not None:
                    devices[identity].button_count = max(devices[identity].button_count or 0, count)
            else:
                devices[identity] = Device(identity,name,kind,props.get('ID_VENDOR_FROM_DATABASE',props.get('ID_VENDOR','HID')),vid,pid,[str(path)],[_handle(path)],virtual,button_count=count)
        except (OSError, ValueError, KeyError) as error:
            errors.append(f'{path}: {error}')
        finally:
            if dev:
                dev.close()
    _last_errors[:] = errors
    result = list(devices.values())
    # The G502 auxiliary keyboard collection is part of its mouse firmware.
    result = [d for d in result if not (d.kind=='keyboard' and (d.vid,d.pid)==('046D','C08B'))]
    resolve_identities(result,load_identities())
    apply_catalog(result)
    return sorted(result,key=lambda d:(d.kind!='mouse',d.name.casefold(),d.id))


def modifiers():
    with _state_lock:
        keys = _active_keys.copy()
    return [label for label,codes in [('Ctrl',{29,97}),('Alt',{56,100}),('Shift',{42,54}),('Win',{125,126})] if keys & codes]


def translate_event(event):
    """Translate only physical key/button/wheel reports; repeats are ignored."""
    if event.type == 1 and event.value in (0,1):
        if event.code in BUTTON_NAMES:
            return dict(type='mouse',button=BUTTON_NAMES[event.code],down=bool(event.value))
        vk = EV_TO_VK.get(event.code)
        if vk is not None:
            return dict(type='key',vk=vk,scan=0,extended=False,down=bool(event.value))
    if event.type == 2 and event.code in (6,8) and event.value:
        return dict(type='wheel',axis='horizontal' if event.code==6 else 'vertical',delta=event.value*120)
    return None


class InputService:
    def __init__(self, on_input, on_change, on_error):
        self.on_input,self.on_change,self.on_error = on_input,on_change,on_error
        self.stop = threading.Event()
        self.thread = None
        self.nodes = {}
        self.signature = set()

    def rescan(self):
        physical = [d for d in enumerate_devices() if not d.virtual]
        paths = {p for d in physical for p in d.paths}
        self.signature = {(d.id, d.name, tuple(d.paths)) for d in physical}
        for path in set(self.nodes)-paths:
            self.nodes.pop(path).close()
        evdev = _evdev()
        for path in paths-set(self.nodes):
            try:
                dev = evdev.InputDevice(path)
                if dev.name.startswith(VIRTUAL_NAME):
                    dev.close()
                    continue
                self.nodes[path] = dev
            except OSError:
                pass
        return paths

    def start(self):
        paths = self.rescan()
        if paths and not self.nodes:
            raise OSError(PERMISSION_HELP)
        get_writer()  # Verify injection rights before saying recording is ready.
        self.thread = threading.Thread(target=self.run,name='LinuxInput',daemon=True)
        self.thread.start()

    def run(self):
        previous = self.signature.copy()
        next_scan = 0
        try:
            while not self.stop.is_set():
                if time.monotonic() >= next_scan:
                    self.rescan();next_scan=time.monotonic()+2
                    current = self.signature.copy()
                    if current != previous:
                        with _state_lock:
                            _active_keys.clear()
                        self.on_change();previous=current
                readers = list(self.nodes.values())
                if not readers:
                    self.stop.wait(.1);continue
                try:
                    ready,_,_ = select.select(readers,[],[],.1)
                except (OSError, ValueError):
                    next_scan=0;continue
                for dev in ready:
                    try:
                        for event in dev.read():
                            if event.type==1:
                                with _state_lock:
                                    if event.value: _active_keys.add(event.code)
                                    else: _active_keys.discard(event.code)
                            translated = translate_event(event)
                            if translated:
                                self.on_input(_handle(dev.path),translated)
                    except BlockingIOError:
                        pass
                    except OSError:
                        self.nodes.pop(dev.path,None);dev.close();next_scan=0
        except Exception as error:
            logging.exception('Linux input')
            self.on_error(str(error))
        finally:
            for dev in self.nodes.values():dev.close()
            self.nodes.clear()
            with _state_lock: _active_keys.clear()

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=3)
        else:
            for dev in self.nodes.values():dev.close()
            self.nodes.clear()


def set_callbacks(on_input,on_change,on_error):
    global _callbacks
    _callbacks=(on_input,on_change,on_error)


def register_input(hwnd=0):
    global _service
    if _service:
        if _service.thread and _service.thread.is_alive():
            return
        _service.close()
        _service=None
    if _callbacks is None:
        raise OSError('No hay callbacks de entrada configurados.')
    service=InputService(*_callbacks)
    try:service.start()
    except Exception:
        service.close();raise
    _service=service


def unregister_input():
    global _service,_writer
    if _service:
        _service.close();_service=None
    with _writer_lock:
        if _writer:
            try:
                for code in list(_writer.pressed):
                    _writer.ui.write(1,code,0)
                _writer.ui.syn()
            except OSError:
                logging.exception('Liberacion del dispositivo virtual')
            finally:
                _writer.ui.close()
                _writer=None


class Writer:
    def __init__(self,ui):
        self.ui=ui
        self.pressed=set()
    def key(self,code,down):
        self.ui.write(1,code,int(down));self.ui.syn()
        if down:self.pressed.add(code)
        else:self.pressed.discard(code)


def get_writer():
    global _writer
    with _writer_lock:
        if _writer is None:
            evdev=_evdev()
            try:
                ui=evdev.UInput({1:sorted(set(VK_TO_EV.values())|set(BUTTONS.values())),2:[6,8,11,12]},name=VIRTUAL_NAME,phys='logigian64/uinput',bustype=6)
            except OSError as error:
                raise OSError('No se pudo abrir /dev/uinput. '+PERMISSION_HELP) from error
            _writer=Writer(ui)
        return _writer


def _text_keys(text):
    """Validate a whole chunk before injecting; US punctuation uses Shift."""
    shifted='!@#$%^&*()_+{}|:"<>?~'
    plain='1234567890-=[]'+chr(92)+";',./`"
    result=[]
    for char in text:
        if char in '\n\r':vk,shift=13,False
        elif char=='\t':vk,shift=9,False
        elif char==' ':vk,shift=32,False
        elif char.isascii() and char.isalnum():vk,shift=ord(char.upper()),char.isupper()
        else:
            need_shift=char in shifted
            target=plain[shifted.index(char)] if need_shift else char
            punctuation={';':186,'=':187,',':188,'-':189,'.':190,'/':191,'`':192,'[':219,chr(92):220,']':221,"'":222}
            if target not in punctuation and not target.isascii():
                raise OSError('Este texto requiere Unicode. La primera version Linux admite texto ASCII con distribucion US; usa acciones de teclas para tu distribucion.')
            vk=ord(target) if target.isdigit() else punctuation.get(target)
            shift=need_shift
            if vk is None:raise OSError('Caracter de texto no compatible.')
        result.append((VK_TO_EV[vk],shift))
    return result


def send_event(event):
    kind=event['type']
    if kind=='launch':
        path=Path(event['path'])
        if not path.is_file():raise OSError('La aplicacion ya no existe: '+str(path))
        command=['gio','launch',str(path)] if path.suffix=='.desktop' else [str(path)]
        subprocess.Popen(command,close_fds=True,start_new_session=True)
        return
    text_keys=_text_keys(event['text']) if kind=='text' else None
    with _writer_lock:
        writer=get_writer()
        if kind=='key':
            code=VK_TO_EV.get(event['vk'])
            if code is None:raise OSError('Tecla no compatible en Linux: '+str(event['vk']))
            writer.key(code,event['down'])
        elif kind=='mouse':writer.key(BUTTONS[event['button']],event['down'])
        elif kind=='wheel':
            horizontal=event.get('axis')=='horizontal'
            writer.ui.write(2,12 if horizontal else 11,event['delta'])
            steps=int(event['delta']/120)
            if steps:writer.ui.write(2,6 if horizontal else 8,steps)
            writer.ui.syn()
        elif kind=='text':
            for code,shift in text_keys:
                if shift:writer.key(42,True)
                try:writer.key(code,True);writer.key(code,False)
                finally:
                    if shift:writer.key(42,False)


def pointer_speed():
    return 10


def set_pointer_speed(value):
    raise OSError('La velocidad global se configura en las preferencias del escritorio Linux. El DPI fisico del G502 se puede configurar aqui.')


def active_hid_controllers():
    names=set()
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            name=path.read_text().strip().casefold()
            if name in ('ratbagd','solaar','openrgb'):names.add(name)
        except OSError:pass
    return sorted(names)


def diagnostics():
    try:devices=enumerate_devices()
    except OSError as error:return dict(devices=[],error=str(error),permission_help=PERMISSION_HELP)
    return dict(devices=[d.to_dict() for d in devices],permission_errors=list(_last_errors),uinput_readable=os.access('/dev/uinput',os.R_OK|os.W_OK),session=os.environ.get('XDG_SESSION_TYPE','unknown'),conflicting_controllers=active_hid_controllers(),permission_help=PERMISSION_HELP)
