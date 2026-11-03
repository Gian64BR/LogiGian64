"""Bundled defaults for confirmed hardware with generic USB descriptors.

USB IDs may be shared. Explicit local identification always takes precedence.
"""
import json
from pathlib import Path
import sys


def apply_catalog(devices):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    data = json.loads((root / 'assets' / 'device-models.json').read_text(encoding='utf-8'))
    for device in devices:
        if device.virtual or device.identification:
            continue
        generic = device.name.casefold().strip() in ('usb device', 'usb keyboard', 'usb gaming keyboard') or device.name.startswith('Teclado USB · ')
        if not generic:
            continue
        matches = [m for m in data['models'] if (m['vid'], m['pid'], m['kind']) == (device.vid, device.pid, device.kind)]
        if len(matches) == 1:
            model = matches[0]
            device.name, device.manufacturer = model['name'], model['manufacturer']
            device.identification = 'Perfil incluido para descriptor USB genérico; puedes cambiarlo en Identificar modelo'
