"""Zone lighting workspace and live preview for the G502 HERO."""
import copy
import json
import math
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QSignalBlocker
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QFrame, QHBoxLayout, QVBoxLayout, QTabBar,
                              QComboBox, QSlider, QCheckBox, QLineEdit, QColorDialog)
from .widgets import label, button
from .studio_widgets import HardwareArt
from .lighting_protocol import clean_lighting, EFFECT_NAMES

DEFAULT_LIGHT = dict(effect=10, color='#ff0000', period=5000, brightness=100)


class LightingSwitch(QCheckBox):
    def __init__(self):
        super().__init__('CONTROL DE\nLOGIGIAN64')
        self.setMinimumHeight(42)
        self.setAccessibleName('Control de iluminación de LogiGian64')

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#00b7ed' if self.isEnabled() else '#777777'))
        p.drawText(QRectF(0, 0, self.width() - 60, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        x, y = self.width() - 48, (self.height() - 24) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#00a8ef' if self.isChecked() else '#88888a'))
        p.drawRoundedRect(QRectF(x, y, 48, 24), 12, 12)
        p.setBrush(QColor('white'))
        p.drawEllipse(QRectF(x + (26 if self.isChecked() else 3), y + 3, 18, 18))


class LightingPreview(HardwareArt):
    def __init__(self, device):
        self.settings = {0: DEFAULT_LIGHT.copy(), 1: DEFAULT_LIGHT.copy()}
        super().__init__(device)
        self.animation = QTimer(self)
        self.animation.setInterval(40)
        self.animation.timeout.connect(self.animate)

    def animate(self):
        if self.isVisible():
            self.update()

    def showEvent(self, event):
        self.animation.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def zone_color(self, zone):
        config = self.settings.get(zone, DEFAULT_LIGHT)
        effect = config['effect']
        phase = (time.monotonic() * 1000 % config['period']) / config['period']
        color = QColor.fromHsvF(phase, 1, 1) if effect == 3 else QColor(config['color'])
        level = config['brightness'] / 100
        if effect == 10:
            level *= .08 + .92 * (.5 - .5 * math.cos(phase * 2 * math.pi))
        if effect == 0:
            level = 0
        return QColor(round(color.red() * level), round(color.green() * level), round(color.blue() * level))

    def paintEvent(self, event):
        if self.picture.isNull():
            self.color = self.zone_color(1).name()
            return super().paintEvent(event)
        fitted = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x, y = (self.width() - fitted.width()) / 2, (self.height() - fitted.height()) / 2
        p = QPainter(self)
        # The optional device image has transparent LED cutouts. Paint behind
        # those cutouts, retaining the original body and every button.
        for zone, rect in ((0, (.16, .49, .08, .12)), (1, (.31, .65, .18, .10))):
            p.fillRect(QRectF(x + rect[0] * fitted.width(), y + rect[1] * fitted.height(),
                             rect[2] * fitted.width(), rect[3] * fitted.height()), self.zone_color(zone))
        p.drawPixmap(round(x), round(y), fitted)
        p.end()


class LightingPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.device = None
        self.supported = self.active = self.pending = False
        self.loading = False
        self.zones = []
        self.configs = {0: DEFAULT_LIGHT.copy(), 1: DEFAULT_LIGHT.copy()}
        self.preview = None
        self.apply_timer = QTimer(self)
        self.apply_timer.setSingleShot(True)
        self.apply_timer.setInterval(240)
        self.apply_timer.timeout.connect(self.apply_changes)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(30)
        sidebar = QFrame()
        sidebar.setObjectName('assignmentPanel')
        sidebar.setFixedWidth(300)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(16, 22, 16, 20)
        left.setSpacing(14)
        left.addWidget(label('ILUMINACIÓN RGB', 'sectionTitle'))
        self.control = LightingSwitch()
        self.control.toggled.connect(self.toggle_control)
        left.addWidget(self.control)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.addTab('PRINCIPAL')
        self.tabs.addTab('LOGOTIPO')
        self.tabs.setStyleSheet('QTabBar {background:transparent;} QTabBar::tab {background:transparent; color:#999; border:none; padding:8px 8px;} QTabBar::tab:selected {color:white; border-bottom:2px solid white;}')
        self.tabs.currentChanged.connect(self.show_zone)
        left.addWidget(self.tabs)
        left.addWidget(label('EFECTO', 'eyebrow'))
        self.effect = QComboBox()
        for effect in (10, 1, 3, 0):
            self.effect.addItem(EFFECT_NAMES[effect].upper(), effect)
        self.effect.currentIndexChanged.connect(self.edited)
        left.addWidget(self.effect)
        left.addWidget(label('COLOR', 'eyebrow'))
        colors = QHBoxLayout()
        self.hex = QLineEdit('#ff0000')
        self.hex.setMaxLength(7)
        self.hex.setAccessibleName('Color hexadecimal RGB')
        self.hex.editingFinished.connect(self.hex_edited)
        colors.addWidget(self.hex)
        self.color_button = button('', self.choose_color)
        self.color_button.setFixedSize(30, 30)
        self.color_button.setAccessibleName('Elegir color')
        colors.addWidget(self.color_button)
        left.addLayout(colors)
        palette = QHBoxLayout()
        palette.setSpacing(6)
        for color in ('#ff003d', '#ff9900', '#ffe000', '#00e08b', '#00b7ed', '#9b59ff', '#ffffff'):
            swatch = button('', lambda checked=False, c=color: self.set_color(c))
            swatch.setFixedSize(24, 24)
            swatch.setToolTip(color)
            swatch.setAccessibleName('Color ' + color)
            swatch.setStyleSheet(f'background:{color};border:1px solid #777;border-radius:12px;padding:0;')
            palette.addWidget(swatch)
        left.addLayout(palette)
        left.addWidget(label('VELOCIDAD DEL EFECTO', 'eyebrow'))
        speed_row = QHBoxLayout()
        self.period = QSlider(Qt.Orientation.Horizontal)
        self.period.setRange(1000, 20000)
        self.period.setSingleStep(100)
        self.period.setAccessibleName('Duración del ciclo de iluminación')
        self.period.valueChanged.connect(self.edited)
        speed_row.addWidget(self.period)
        self.period_value = label('5000 ms')
        self.period_value.setMinimumWidth(70)
        speed_row.addWidget(self.period_value)
        left.addLayout(speed_row)
        left.addWidget(label('BRILLO DEL EFECTO', 'eyebrow'))
        brightness_row = QHBoxLayout()
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setAccessibleName('Brillo de iluminación')
        slider_style = 'QSlider {background:transparent;} QSlider::groove:horizontal {height:2px;background:#555;} QSlider::handle:horizontal {background:white;width:12px;height:12px;margin:-5px 0;border-radius:6px;} QSlider::handle:horizontal:disabled {background:#777;}'
        self.period.setStyleSheet(slider_style)
        self.brightness.setStyleSheet(slider_style)
        self.brightness.valueChanged.connect(self.edited)
        brightness_row.addWidget(self.brightness)
        self.brightness_value = label('100%')
        self.brightness_value.setMinimumWidth(45)
        brightness_row.addWidget(self.brightness_value)
        left.addLayout(brightness_row)
        left.addSpacing(12)
        left.addWidget(button('SINCRONIZAR ZONAS', self.sync_zones))
        left.addWidget(button('RESTABLECER ESTA ZONA', self.reset_preview))
        left.addStretch()
        self.status_label = label('Activa el control para aplicar los cambios al ratón.', 'muted', True)
        self.status_label.setMinimumHeight(65)
        left.addWidget(self.status_label)
        row.addWidget(sidebar)
        right = QVBoxLayout()
        right.setContentsMargins(12, 15, 12, 18)
        right.addStretch(1)
        self.preview_row = QHBoxLayout()
        self.preview_row.addStretch()
        right.addLayout(self.preview_row, 7)
        right.addStretch(1)
        self.preview_caption = label('VISTA PREVIA · PRINCIPAL Y LOGOTIPO', 'eyebrow')
        right.addWidget(self.preview_caption, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addWidget(label('Edita cada zona o sincroniza ambas.', 'muted'), 0, Qt.AlignmentFlag.AlignHCenter)
        right.addStretch(1)
        row.addLayout(right, 1)
        self.show_zone()

    def zone(self):
        index = max(0, self.tabs.currentIndex())
        return self.zones[index]['index'] if self.zones and index < len(self.zones) else index

    def load_device(self, device):
        self.apply_timer.stop()
        self.device = device
        self.supported = (device.vid, device.pid) == ('046D', 'C08B')
        self.active = self.pending = False
        self.zones = []
        self.configs = {0: DEFAULT_LIGHT.copy(), 1: DEFAULT_LIGHT.copy()}
        try:
            saved = json.loads(self.window.preferences().value(f'lighting/{device.id}', '{}'))
            if isinstance(saved, dict):
                for z in (0, 1):
                    if str(z) in saved:
                        self.configs[z] = clean_lighting(saved[str(z)])
        except (ValueError, TypeError):
            pass
        if self.preview:
            self.preview_row.removeWidget(self.preview)
            self.preview.hide()
            self.preview.deleteLater()
        self.preview = LightingPreview(device)
        self.preview.setMinimumSize(230, 420)
        self.preview.setMaximumWidth(400)
        self.preview_row.insertWidget(1, self.preview, 1)
        if self.preview_row.count() == 2:
            self.preview_row.addStretch()
        self.control.setEnabled(self.supported)
        with QSignalBlocker(self.control):
            self.control.setChecked(False)
        self.status_label.setText('Activa el control para aplicar el efecto al G502.' if self.supported else 'Vista previa disponible. Este modelo aún no tiene control RGB físico.')
        session = self.window.g502
        if session and session.ready and session.device.id == device.id:
            self.hardware_changed({'kind': 'ready', 'device_id': device.id,
                'lighting': session.lighting.zones if getattr(session, 'lighting', None) else None})
            self.active = bool(getattr(session, 'lighting', None) and session.lighting.ownership_changed)
            with QSignalBlocker(self.control):
                self.control.setChecked(self.active)
        self.show_zone()

    def show_zone(self, *args):
        self.loading = True
        config = self.configs.setdefault(self.zone(), DEFAULT_LIGHT.copy())
        self.effect.setCurrentIndex(self.effect.findData(config['effect']))
        self.hex.setText(config['color'])
        self.period.setValue(config['period'])
        self.brightness.setValue(config['brightness'])
        if self.zones:
            options = self.zones[max(0, self.tabs.currentIndex())]['effects']
            for index in range(self.effect.count()):
                self.effect.model().item(index).setEnabled(self.effect.itemData(index) in options)
        self.loading = False
        self.refresh_preview()

    def refresh_preview(self):
        config = self.configs.get(self.zone(), DEFAULT_LIGHT)
        self.period_value.setText(f"{config['period']} ms")
        self.brightness_value.setText(f"{config['brightness']}%")
        self.color_button.setStyleSheet(f"background:{config['color']};border:1px solid white;border-radius:15px;padding:0;")
        colored = config['effect'] in (1, 10)
        self.hex.setEnabled(colored)
        self.color_button.setEnabled(colored)
        self.period.setEnabled(config['effect'] in (3, 10))
        self.brightness.setEnabled(config['effect'] != 0)
        if self.preview:
            self.preview.settings = copy.deepcopy(self.configs)
            self.preview.update()

    def edited(self, *args):
        if self.loading:
            return
        config = dict(effect=self.effect.currentData(), color=self.hex.text(),
                      period=self.period.value(), brightness=self.brightness.value())
        try:
            self.configs[self.zone()] = clean_lighting(config)
        except ValueError:
            return
        self.saved()

    def saved(self):
        if self.device:
            self.window.preferences().setValue(f'lighting/{self.device.id}', json.dumps(self.configs))
        self.refresh_preview()
        if self.active:
            self.status_label.setText('Aplicando iluminación al ratón…')
            self.apply_timer.start()
        else:
            self.status_label.setText('Vista previa guardada. Activa el control para aplicarla al ratón.')

    def set_color(self, color):
        self.hex.setText(color)
        self.edited()

    def hex_edited(self):
        try:
            clean_lighting({**self.configs[self.zone()], 'color': self.hex.text()})
        except ValueError:
            self.hex.setText(self.configs[self.zone()]['color'])
            return
        self.edited()

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.hex.text()), self, 'Color de iluminación')
        if color.isValid():
            self.set_color(color.name())

    def sync_zones(self):
        config = self.configs[self.zone()].copy()
        for zone in ([z['index'] for z in self.zones] if self.zones else (0, 1)):
            self.configs[zone] = config.copy()
        self.saved()

    def reset_preview(self):
        self.configs[self.zone()] = DEFAULT_LIGHT.copy()
        self.show_zone()
        self.saved()

    def toggle_control(self, enabled):
        self.apply_timer.stop()
        session = self.window.g502
        if not enabled:
            self.active = self.pending = False
            if session and session.ready and session.device.id == self.device.id:
                session.restore_lighting()
                self.status_label.setText('Restaurando la iluminación anterior…')
            return
        if not self.supported:
            return
        self.pending = True
        if session and session.ready and session.device.id == self.device.id:
            self.apply_changes()
        else:
            self.status_label.setText('Conectando el control de iluminación…')
            if not session or not session.thread or not session.thread.is_alive():
                self.window.activate_g502()
            if not self.window.g502:
                self.pending = False
                with QSignalBlocker(self.control):
                    self.control.setChecked(False)
                self.status_label.setText('Control no activado. Vista previa disponible.')

    def apply_changes(self):
        session = self.window.g502
        if not self.device or not session or not session.ready or session.device.id != self.device.id:
            return
        try:
            targets = [z['index'] for z in self.zones]
            if not targets:
                raise OSError('Este dispositivo no ha comunicado zonas RGB compatibles.')
            session.set_lighting({zone: self.configs[zone].copy() for zone in targets})
            self.status_label.setText('Esperando confirmación del ratón…')
        except (OSError, ValueError) as error:
            self.status_label.setText(str(error))
            self.pending = False
            with QSignalBlocker(self.control):
                self.control.setChecked(self.active)

    def hardware_changed(self, data):
        if not self.device or data.get('device_id') != self.device.id:
            return
        kind = data['kind']
        if kind == 'ready':
            self.zones = data.get('lighting') or []
            if self.zones:
                with QSignalBlocker(self.tabs):
                    while self.tabs.count():
                        self.tabs.removeTab(0)
                    for zone in self.zones:
                        name = {1: 'PRINCIPAL', 2: 'LOGOTIPO'}.get(zone['location'], f"ZONA {zone['index'] + 1}")
                        self.tabs.addTab(name)
                        self.configs.setdefault(zone['index'], DEFAULT_LIGHT.copy())
                self.show_zone()
                if self.pending:
                    self.apply_changes()
            elif self.pending:
                self.pending = False
                with QSignalBlocker(self.control):
                    self.control.setChecked(False)
                self.status_label.setText(data.get('lighting_error') or 'Control RGB no disponible en este dispositivo.')
        elif kind == 'lighting':
            self.active, self.pending = True, False
            self.status_label.setText('Iluminación aplicada y confirmada por el G502.')
        elif kind == 'lighting_restore':
            self.active = self.pending = False
            with QSignalBlocker(self.control):
                self.control.setChecked(False)
            self.status_label.setText('Iluminación anterior restaurada. Vista previa disponible.')
        elif kind == 'lighting_error':
            self.pending = False
            self.status_label.setText('No confirmado: ' + data['error'])
            with QSignalBlocker(self.control):
                self.control.setChecked(self.active)
        elif kind == 'disconnected':
            self.active = self.pending = False
            self.apply_timer.stop()
            with QSignalBlocker(self.control):
                self.control.setChecked(False)
            self.status_label.setText('Control desconectado. Activa el control para aplicar iluminación.')
