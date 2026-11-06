from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, QSpinBox,
                              QDialogButtonBox, QCheckBox, QHBoxLayout, QLabel)
from . import windows as win
from .widgets import label


def key_choices(combo, reserve=False):
    for vk in list(range(65, 91)) + list(range(48, 58)) + list(range(112, 136)) + list(win.SPECIAL_KEYS):
        if reserve and vk in (119, 120):
            continue
        combo.addItem(win.key_name(vk), vk)


class AddActionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir acción")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for text, value in (("Tecla", "key"), ("Botón del ratón", "mouse"), ("Pausa", "wait"), ("Rueda del ratón", "wheel")):
            self.kind.addItem(text, value)
        self.key = QComboBox()
        key_choices(self.key)
        self.mouse = QComboBox()
        for value, text in win.MOUSE_LABELS.items():
            self.mouse.addItem(text, value)
        self.mode = QComboBox()
        self.mode.addItems(["Pulsar y soltar", "Solo pulsar", "Solo soltar"])
        self.delay = QSpinBox()
        self.delay.setRange(0, 60000)
        self.delay.setValue(0)
        self.delay.setSuffix(" ms")
        self.delta = QSpinBox()
        self.delta.setRange(-12000, 12000)
        self.delta.setSingleStep(120)
        self.delta.setValue(120)
        form.addRow("Acción", self.kind)
        form.addRow("Tecla", self.key)
        form.addRow("Botón", self.mouse)
        form.addRow("Comportamiento", self.mode)
        form.addRow("Espera anterior", self.delay)
        form.addRow("Rueda (+ arriba / − abajo)", self.delta)
        layout.addLayout(form)
        layout.addWidget(label("Pulsar y soltar añade dos pasos con una pulsación de 50 ms.", "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self.update_fields)
        self.update_fields()

    def update_fields(self):
        kind = self.kind.currentData()
        self.key.setEnabled(kind == "key")
        self.mouse.setEnabled(kind == "mouse")
        self.mode.setEnabled(kind in ("key", "mouse"))
        self.delta.setEnabled(kind == "wheel")

    def events(self):
        kind, delay = self.kind.currentData(), self.delay.value()
        if kind == "wait":
            return [{"type": "wait", "delay_ms": delay}]
        if kind == "wheel":
            return [{"type": "wheel", "delta": self.delta.value(), "axis": "vertical", "delay_ms": delay}]
        event = {"type": kind, "delay_ms": delay, "down": self.mode.currentIndex() != 2}
        if kind == "key":
            event.update(vk=self.key.currentData(), scan=0, extended=False)
        else:
            event["button"] = self.mouse.currentData()
        if self.mode.currentIndex() == 0:
            return [event, {'type': 'wait', 'delay_ms': 50}, {**event, "down": False, "delay_ms": 0}]
        return [event]


class DelayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Acción de retardo')
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.delay = QSpinBox()
        self.delay.setRange(0, 60000)
        self.delay.setValue(50)
        self.delay.setSuffix(' ms')
        form.addRow('Milisegundos', self.delay)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def events(self):
        return [dict(type='wait', delay_ms=self.delay.value())]


class BindingDialog(QDialog):
    def __init__(self, device, macros, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asignar macro al periférico")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        layout.addWidget(label(device.name, "sectionTitle", True))
        form = QFormLayout()
        self.macro = QComboBox()
        for macro in macros:
            self.macro.addItem(macro["name"], macro["id"])
        self.trigger = QComboBox()
        if device.kind == "mouse":
            for value in ("x1", "x2", "middle"):
                self.trigger.addItem(win.MOUSE_LABELS[value], ("mouse", value))
        for vk in list(range(112, 136)) + list(range(65, 91)) + list(range(48, 58)):
            if vk not in (119, 120):
                self.trigger.addItem("Tecla " + win.key_name(vk), ("key", vk))
        self.modifiers = [QCheckBox(name) for name in ("Ctrl", "Alt", "Shift", "Win")]
        mods = QHBoxLayout()
        for checkbox in self.modifiers:
            mods.addWidget(checkbox)
        form.addRow("Macro", self.macro)
        form.addRow("Activador", self.trigger)
        form.addRow("Modificadores", mods)
        layout.addLayout(form)
        layout.addWidget(label("El activador se escucha en este periférico. Su acción original se conserva. "
            "Las teclas de un ratón requieren que su firmware las exponga como entrada de teclado. "
            "F8 finaliza la grabación y F9 detiene la reproducción.", "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.trigger.currentIndexChanged.connect(lambda: [box.setEnabled(self.trigger.currentData()[0] == "key") for box in self.modifiers])
        self.trigger.currentIndexChanged.emit(0)

    def binding(self, device_id):
        kind, value = self.trigger.currentData()
        trigger = {"type": kind}
        if kind == "mouse":
            trigger["button"] = value
        else:
            trigger.update(vk=value, mods=sorted(box.text() for box in self.modifiers if box.isChecked()))
        return {"device_id": device_id, "macro_id": self.macro.currentData(), "trigger": trigger, "enabled": True}
