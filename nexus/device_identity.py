"""Local, user-confirmed model names; generic USB IDs are not model IDs."""
import json
import os
from pathlib import Path
import uuid


def identity_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'NexusHub' / 'device-identities.json'


def load_identities(path=None):
    try:
        data = json.loads(Path(path or identity_path()).read_text(encoding='utf-8'))
        if data.get('version') == 1 and isinstance(data.get('devices'), dict):
            return data['devices']
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def apply_identity(device, identities):
    record = identities.get(device.id)
    if not isinstance(record, dict) or (record.get('vid'), record.get('pid'), record.get('kind')) != (device.vid, device.pid, device.kind):
        return
    name, maker = record.get('name'), record.get('manufacturer', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(maker, str) or len(maker) > 80:
        return
    if any(ord(c) < 32 for c in name + maker):
        return
    device.name, device.manufacturer = name.strip(), maker.strip() or device.manufacturer
    device.identification = 'Modelo confirmado por el usuario'


def resolve_identities(devices, identities):
    connected = {d.id for d in devices}
    for device in devices:
        apply_identity(device, identities)
    for device in devices:
        if device.identification or device.virtual:
            continue
        signature = (device.vid, device.pid, device.kind)
        if sum((d.vid, d.pid, d.kind) == signature and not d.virtual for d in devices) != 1:
            continue
        records = [record for identity, record in identities.items() if identity not in connected
                   and isinstance(record, dict) and record.get('remember_ports') is True
                   and (record.get('vid'), record.get('pid'), record.get('kind')) == signature]
        models = {(r.get('name'), r.get('manufacturer')) for r in records
                  if isinstance(r.get('name'), str) and isinstance(r.get('manufacturer'), str)}
        if len(models) == 1 and records:
            apply_identity(device, {device.id: records[0]})
            if device.identification:
                device.identification = 'Modelo confirmado y recordado en este equipo'


def save_identity(device, manufacturer, model, path=None, remember_ports=True):
    manufacturer, model = manufacturer.strip(), model.strip()
    if not model or len(model) > 100 or len(manufacturer) > 80 or any(ord(c) < 32 for c in manufacturer + model):
        raise ValueError('Escribe un fabricante y modelo válidos, de hasta 100 caracteres.')
    name = model if not manufacturer or model.casefold().startswith(manufacturer.casefold() + ' ') else manufacturer + ' ' + model
    if len(name) > 100:
        raise ValueError('El nombre completo admite hasta 100 caracteres.')
    target = Path(path or identity_path())
    devices = load_identities(target)
    devices[device.id] = dict(vid=device.vid, pid=device.pid, kind=device.kind,
                              manufacturer=manufacturer, name=name, remember_ports=bool(remember_ports))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(dict(version=1, devices=devices), ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    apply_identity(device, devices)
