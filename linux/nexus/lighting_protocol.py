"""HID++ 0x8070 RGB control, volatile writes with readback and restoration."""
import re

EFFECT_NAMES = {0: 'Apagado', 1: 'Color fijo', 10: 'Respiración', 3: 'Ciclo de colores'}


def clean_lighting(value):
    if not isinstance(value, dict):
        raise ValueError('Configuración de iluminación inválida.')
    effect = value.get('effect', 10)
    color = value.get('color', '#ff0000')
    period = value.get('period', 5000)
    brightness = value.get('brightness', 100)
    if type(effect) is not int or effect not in EFFECT_NAMES:
        raise ValueError('Efecto de iluminación no compatible.')
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Color RGB inválido.')
    if type(period) is not int or not 1000 <= period <= 20000:
        raise ValueError('El período debe estar entre 1000 y 20000 ms.')
    if type(brightness) is not int or not 0 <= brightness <= 100:
        raise ValueError('El brillo debe estar entre 0 y 100%.')
    return dict(effect=effect, color=color.lower(), period=period, brightness=brightness)


def effect_params(config):
    config = clean_lighting(config)
    effect, brightness, period = config['effect'], config['brightness'], config['period']
    rgb = [int(config['color'][i:i + 2], 16) for i in (1, 3, 5)]
    params = [0] * 10
    if effect == 1:
        params[:3] = [round(channel * brightness / 100) for channel in rgb]
    elif effect == 10:
        params[:3] = rgb
        params[3:5] = [period >> 8, period & 255]
        params[5], params[6] = 1, brightness
    elif effect == 3:
        params[5:7] = [period >> 8, period & 255]
        params[7] = brightness
    return params


class LightingControl:
    def __init__(self, request, feature_index):
        self.request, self.index = request, feature_index
        self.zones = []
        self.original = {}
        self.dirty = set()
        self.ownership_changed = False
        self.original_owner = None

    def load(self):
        info = self.request(self.index, 0)
        # Older G502 firmware implements readback while advertising zero
        # extended capability flags. Require successful reads below instead.
        if len(info) < 5 or not 1 <= info[0] <= 8:
            raise OSError('El dispositivo no permite leer y restaurar sus efectos RGB.')
        self.original_owner = self.request(self.index, 7)[:2]
        if len(self.original_owner) != 2 or self.original_owner[0] not in (0, 1):
            raise OSError('Estado de control RGB desconocido.')
        for zone in range(info[0]):
            data = self.request(self.index, 1, [zone])
            if len(data) < 5 or data[0] != zone or not 1 <= data[3] <= 32:
                raise OSError('Información de zona RGB inválida.')
            effects = {}
            for ordinal in range(data[3]):
                effect = self.request(self.index, 2, [zone, ordinal])
                if len(effect) < 4 or effect[:2] != [zone, ordinal]:
                    raise OSError('Información de efecto RGB incompleta.')
                effect_id = effect[2] << 8 | effect[3]
                if effect_id in EFFECT_NAMES:
                    effects[effect_id] = ordinal
            self.original[zone] = self.read(zone)
            self.zones.append({'index': zone, 'location': data[1] << 8 | data[2], 'effects': effects})
        return self.zones

    def read(self, zone):
        data = self.request(self.index, 14, [zone, 0])
        if len(data) < 12 or data[0] != zone:
            raise OSError('El ratón no confirmó el efecto RGB de la zona.')
        return data[:12]

    def apply(self, configurations):
        if not isinstance(configurations, dict) or not configurations:
            raise ValueError('Selecciona al menos una zona de iluminación.')
        packets = {}
        for zone, raw in configurations.items():
            if type(zone) is not int or zone not in self.original:
                raise ValueError('Zona de iluminación no disponible.')
            config = clean_lighting(raw)
            effects = self.zones[zone]['effects']
            if config['effect'] not in effects:
                raise ValueError('La zona no admite ese efecto.')
            packets[zone] = [zone, effects[config['effect']]] + effect_params(config)
        self.ownership_changed = True
        self.request(self.index, 8, [1, 0])
        if self.request(self.index, 7)[:2] != [1, 0]:
            raise OSError('El G502 no confirmó el control de iluminación.')
        for zone, packet in packets.items():
            self.dirty.add(zone)
            self.request(self.index, 3, packet + [0])  # RAM only; never EEPROM.
            if self.read(zone) != packet:
                raise OSError('El G502 no confirmó los parámetros RGB enviados.')

    def restore(self):
        failures = []
        for zone in list(self.dirty):
            try:
                packet = self.original[zone]
                self.request(self.index, 3, packet + [0])
                if self.read(zone) != packet:
                    raise OSError('La zona no confirmó su efecto anterior.')
                self.dirty.remove(zone)
            except Exception as error:
                failures.append(f'Zona RGB {zone}: {error}')
        if self.ownership_changed and not self.dirty:
            try:
                self.request(self.index, 8, self.original_owner)
                if self.request(self.index, 7)[:2] != self.original_owner:
                    raise OSError('No se confirmó el control RGB original.')
                self.ownership_changed = False
            except Exception as error:
                failures.append('Control RGB: ' + str(error))
        return failures
