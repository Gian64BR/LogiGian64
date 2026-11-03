"""Editable DPI levels with confirmed, volatile G502 HERO sensor control."""
import json

from PySide6.QtCore import Qt, QPointF, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QSlider, QInputDialog

from .widgets import label, button

DEFAULT_LEVELS = [800, 1450, 2400, 3200, 6400]


class DpiTrack(QWidget):
    changed = Signal()
    editRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.levels = DEFAULT_LEVELS.copy()
        self.selected = 1
        self.dragging = False
        self.setMinimumSize(360, 160)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Niveles DPI de referencia: arrastra un punto o haz doble clic para editar")

    def value_x(self, value):
        ratio = (value - 100) / 3900 * (2 / 3) if value <= 4000 else 2 / 3 + (value - 4000) / 21600 / 3
        return 28 + ratio * (self.width() - 56)

    def x_value(self, x):
        ratio = max(0, min(1, (x - 28) / (self.width() - 56)))
        raw = 100 + ratio * 3900 * 1.5 if ratio <= 2 / 3 else 4000 + (ratio - 2 / 3) * 64800
        return max(100, min(25600, round(raw / 50) * 50))

    def axis_y(self):
        return self.height() / 2

    def set_level(self, index, value):
        low = self.levels[index - 1] + 50 if index else 100
        high = self.levels[index + 1] - 50 if index < 4 else 25600
        self.levels[index] = max(low, min(high, int(value)))
        self.selected = index
        self.update()
        self.changed.emit()

    def hit(self, position):
        for index, value in enumerate(self.levels):
            if abs(position.x() - self.value_x(value)) < 17 and abs(position.y() - self.axis_y()) < 20:
                return index
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.hit(event.position())
        if index is not None:
            self.selected, self.dragging = index, True
            self.changed.emit()
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.set_level(self.selected, self.x_value(event.position().x()))
        else:
            self.setCursor(Qt.CursorShape.SizeHorCursor if self.hit(event.position()) is not None else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.set_level(self.selected, self.x_value(event.position().x()))
        self.dragging = False

    def mouseDoubleClickEvent(self, event):
        index = self.hit(event.position())
        if index is None:
            index = next((i for i, value in enumerate(self.levels) if abs(event.position().x() - self.value_x(value)) < 25 and abs(event.position().y() - (self.axis_y() - 34)) < 18), None)
        if index is not None:
            self.dragging = False
            self.editRequested.emit(index)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.set_level(self.selected, self.levels[self.selected] + (50 if event.key() == Qt.Key.Key_Right else -50))
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.editRequested.emit(self.selected)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.axis_y()
        p.setPen(QPen(QColor('#555555'), 3))
        p.drawLine(QPointF(28, y), QPointF(self.width() - 28, y))
        for value in [100, 1000, 2000, 3000, 4000, 14800, 25600]:
            x = self.value_x(value)
            p.setPen(QPen(QColor('#888888'), 1))
            p.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
            p.drawText(int(x - 27), int(y + 28), 54, 22, Qt.AlignmentFlag.AlignCenter, str(value))
        for value in range(5000, 25000, 1000):
            x = self.value_x(value)
            p.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
        for index, value in enumerate(self.levels):
            x = self.value_x(value)
            color = QColor('#ffcc00' if index == self.selected else '#ffffff')
            p.setPen(color)
            p.setBrush(color)
            font = p.font()
            font.setBold(True)
            font.setUnderline(index == self.selected)
            p.setFont(font)
            p.drawText(int(x - 30), int(y - 49), 60, 26, Qt.AlignmentFlag.AlignCenter, str(value))
            if index == self.selected:
                p.drawPolygon(QPolygonF([QPointF(x, y - 8), QPointF(x + 8, y), QPointF(x, y + 8), QPointF(x - 8, y)]))
            else:
                p.drawEllipse(QPointF(x, y), 5, 5)


class SensitivityPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.device_id = None
        self.supported = False
        self.connected = False
        self.pending_dpi = None
        self.current_dpi = None
        self.apply_timer = QTimer(self)
        self.apply_timer.setSingleShot(True)
        self.apply_timer.setInterval(220)
        self.apply_timer.timeout.connect(self.apply_dpi)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)
        sidebar = QFrame()
        sidebar.setObjectName('assignmentPanel')
        sidebar.setFixedWidth(300)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(16, 22, 16, 22)
        left.addWidget(label('Sensibilidad (DPI)', 'sectionTitle'))
        left.addWidget(label('Organiza tus niveles de sensibilidad. Arrastra cada punto o pulsa su valor para editarlo.', 'muted', True))
        left.addSpacing(14)
        left.addWidget(label('VELOCIDADES DE DPI', 'eyebrow'))
        self.values = QHBoxLayout()
        self.value_buttons = []
        for index in range(5):
            control = button('', lambda checked=False, i=index: self.edit_level(i))
            control.setStyleSheet('QPushButton { background:transparent; border:none; padding:3px; }')
            self.values.addWidget(control)
            self.value_buttons.append(control)
        left.addLayout(self.values)
        left.addSpacing(15)
        left.addWidget(label('El nivel seleccionado aparece en amarillo y subrayado. Los niveles se guardan por dispositivo.', 'muted', True))
        self.notice = label('', 'muted', True)
        self.notice.setStyleSheet('color:#ffcc00; font-size:12px;')
        left.addWidget(self.notice)
        self.dpi_button = button('ACTIVAR CONTROL Y APLICAR DPI', self.apply_dpi)
        left.addWidget(self.dpi_button)
        left.addSpacing(20)
        left.addWidget(label('VELOCIDAD DE RESPUESTA\n(POR SEGUNDO)', 'eyebrow'))
        left.addWidget(label('1000     500     250     125 Hz\nControl de frecuencia no disponible.', 'muted', True))
        left.addSpacing(20)
        left.addWidget(button('RESTABLECER NIVELES\nPREDETERMINADOS', self.reset_levels))
        left.addStretch()
        row.addWidget(sidebar)
        right = QVBoxLayout()
        right.setContentsMargins(12, 18, 12, 20)
        right.addWidget(label('VELOCIDADES DE DPI', 'sectionTitle'), 0, Qt.AlignmentFlag.AlignHCenter)
        legend = label('NIVEL SELECCIONADO', 'eyebrow')
        legend.setStyleSheet('color:#ffcc00;')
        right.addWidget(legend, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addWidget(label('Arrastra los puntos. Haz doble clic en un punto para introducir su valor.', 'muted', True), 0, Qt.AlignmentFlag.AlignHCenter)
        right.addStretch(2)
        self.track = DpiTrack()
        self.track.changed.connect(self.save_levels)
        self.track.editRequested.connect(self.edit_level)
        right.addWidget(self.track)
        right.addStretch(1)
        self.confirmed_label = label('DPI físico sin consultar', 'muted', True)
        right.addWidget(self.confirmed_label, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addStretch(1)
        right.addWidget(label('VELOCIDAD DEL PUNTERO DE WINDOWS', 'eyebrow'))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_value = label('', 'muted')
        self.speed_slider.valueChanged.connect(lambda n: self.speed_value.setText(f'{n}/20 · Ajuste global; no cambia el DPI del sensor.'))
        right.addWidget(self.speed_slider)
        right.addWidget(self.speed_value)
        right.addWidget(button('APLICAR A WINDOWS', window.apply_speed), 0, Qt.AlignmentFlag.AlignLeft)
        self.hardware_info = label('', 'muted', True)
        self.hardware_info.hide()
        row.addLayout(right, 1)
        self.refresh_values()

    def load_device(self, device):
        self.apply_timer.stop()
        self.pending_dpi = None
        self.device_id = device.id
        self.supported = (device.vid, device.pid) == ('046D', 'C08B')
        self.connected = False
        self.current_dpi = None
        self.track.levels, self.track.selected = DEFAULT_LEVELS.copy(), 1
        try:
            data = json.loads(self.window.preferences().value(f'sensitivity/{device.id}', '{}'))
            levels = data.get('levels', []) if isinstance(data, dict) else []
            if len(levels) == 5 and all(type(v) is int and 100 <= v <= 25600 for v in levels) and all(b - a >= 50 for a, b in zip(levels, levels[1:])):
                self.track.levels = levels
                selected = data.get('selected', 1)
                self.track.selected = selected if type(selected) is int and 0 <= selected < 5 else 1
        except (TypeError, ValueError):
            pass
        self.track.setEnabled(device.kind == 'mouse')
        for control in self.value_buttons:
            control.setEnabled(device.kind == 'mouse')
        self.refresh_values()
        session = self.window.g502
        self.dpi_button.setEnabled(self.supported)
        self.notice.setText('G502 HERO: activa el control directo para aplicar DPI al sensor. No modifica la memoria integrada.' if self.supported else 'Niveles de referencia: este modelo aún no tiene control físico de DPI.')
        self.confirmed_label.setText('DPI físico sin consultar' if self.supported else 'DPI físico no disponible para este modelo')
        if session and session.ready and session.device.id == device.id:
            self.hardware_changed({'kind': 'ready', 'device_id': device.id, 'dpi': session.dpi_state})

    def hardware_changed(self, data):
        if data.get('device_id') != self.device_id:
            return
        kind = data['kind']
        if kind == 'ready':
            state = data.get('dpi')
            self.connected = bool(state)
            if state:
                self.current_dpi = state['current']
                self.confirmed_label.setText(f"DPI físico leído del sensor: {self.current_dpi}")
                self.notice.setText(f"CONTROL REAL ACTIVO\n{state['minimum']}–{state['maximum']} DPI · paso {state['step'] or 'según sensor'}. Arrastra o elige un punto para aplicarlo. Al salir se restaura el DPI anterior.")
                self.dpi_button.setText('APLICAR DPI AL SENSOR')
                if self.pending_dpi is not None:
                    self.apply_timer.start()
                elif self.current_dpi in self.track.levels:
                    self.track.selected = self.track.levels.index(self.current_dpi)
                    self.refresh_values()
            else:
                self.notice.setText('DPI no disponible: ' + str(data.get('dpi_error') or 'el sensor no respondió'))
        elif kind == 'dpi':
            self.current_dpi = data['current']
            self.confirmed_label.setText(f'DPI físico confirmado por el sensor: {self.current_dpi}')
        elif kind == 'dpi_error':
            self.current_dpi = None
            self.confirmed_label.setText('DPI NO confirmado: ' + data['error'])
        elif kind == 'disconnected':
            self.connected = False
            self.pending_dpi = None
            self.apply_timer.stop()
            self.confirmed_label.setText('Control directo desconectado; DPI seleccionado no aplicado.')
            self.notice.setText('Activa el control directo para cambiar el DPI físico del G502.')
            self.dpi_button.setText('ACTIVAR CONTROL Y APLICAR DPI')

    def apply_dpi(self):
        if not self.supported or not self.device_id:
            return
        session = self.window.g502
        self.pending_dpi = self.track.levels[self.track.selected]
        if not session or not session.ready or session.device.id != self.device_id:
            if session and session.thread and session.thread.is_alive():
                return
            self.window.activate_g502()
            if not self.window.g502:
                self.pending_dpi = None
            return
        try:
            value = self.pending_dpi
            session.set_dpi(value)
            self.pending_dpi = None
            self.confirmed_label.setText(f'Solicitando {value} DPI al sensor…')
        except (OSError, ValueError) as error:
            self.pending_dpi = None
            self.confirmed_label.setText('DPI no aplicado: ' + str(error))

    def refresh_values(self):
        for index, control in enumerate(self.value_buttons):
            control.setText(str(self.track.levels[index]))
            control.setStyleSheet('QPushButton {background:transparent; border:none; padding:3px; color:' + ('#ffcc00; text-decoration:underline;' if index == self.track.selected else '#ffffff;') + '}')
        self.track.update()

    def save_levels(self):
        if self.device_id:
            self.window.preferences().setValue(f'sensitivity/{self.device_id}', json.dumps({'levels': self.track.levels, 'selected': self.track.selected}))
        self.refresh_values()
        if self.connected:
            self.confirmed_label.setText('Cambio pendiente de confirmación del sensor…')
            self.apply_timer.start()

    def edit_level(self, index):
        low = self.track.levels[index - 1] + 50 if index else 100
        high = self.track.levels[index + 1] - 50 if index < 4 else 25600
        value, accepted = QInputDialog.getInt(self, 'Nivel DPI', 'Valor DPI del G502:' if self.supported else 'Valor de referencia (sin control físico):', self.track.levels[index], low, high, 50)
        if accepted:
            self.track.set_level(index, value)

    def reset_levels(self):
        self.track.levels, self.track.selected = DEFAULT_LEVELS.copy(), 1
        self.save_levels()
