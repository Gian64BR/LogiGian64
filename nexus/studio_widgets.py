"""Black workspace, physical assignment targets and horizontal macro timeline."""
import json
import sys
import math
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QMimeData, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QDrag, QPainterPath
from PySide6.QtWidgets import (QWidget, QListWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
                              QPushButton, QDialog, QDialogButtonBox, QComboBox)
from .widgets import DeviceArt, label, button, STYLE
from .core import MODES

STYLE = STYLE + """
QWidget { background: #000000; color: #f5f5f7; }
QLabel { background: transparent; }
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background: #000; }
QFrame#header { background: #000000; border-bottom: 1px solid #292929; }
QFrame#panel, QFrame#deviceCard, QFrame#assignmentPanel { background: #222326; border: none; border-radius: 12px; }
QFrame#rail { background: #000; border: none; }
QPushButton { background: #333436; border: 1px solid transparent; border-radius: 2px; padding: 8px 14px; }
QPushButton:hover { background: #454649; border-color: #606166; }
QPushButton#primary { background: #00afd7; color: white; border-radius: 1px; }
QPushButton#primary:hover { background: #00c7f1; }
QPushButton#nav { background: #000; color: #999; padding: 15px; font-size: 13px; border-radius: 0; }
QPushButton#nav:checked { background: #000; border: none; border-bottom: 2px solid #00b7ed; color: #00b7ed; }
QPushButton#mode { background: #191919; border: 1px solid #414141; border-radius: 3px; }
QPushButton#mode:checked { color: #00c6ed; border-color: #00c6ed; background: #00232a; }
QLabel#eyebrow { color: #00b7ed; }
QLabel#muted { color: #a2a2a6; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLineEdit, QComboBox, QSpinBox { background: #222326; border: 1px solid #414146; border-radius: 3px; }
QListWidget { background: transparent; border: none; border-radius: 0; }
QListWidget::item { border-bottom: 1px solid #3c3c3f; padding: 11px 0; border-radius: 0; }
QListWidget::item:selected { background: #36383c; color: white; }
QTableWidget { background: #151515; alternate-background-color: #1c1c1c; border-color: #333; }
QHeaderView::section { background: #282828; color: #aaa; }
QCheckBox::indicator:checked { background: #00b7ed; border: 3px solid #194957; }
QStatusBar { background: #080808; color: #96969b; border-top: 1px solid #222; }
QDialog { background: #171719; }
"""


def reference_image(device, side=False):
    if device.kind == "mouse" and (device.vid, device.pid) == ("30FA", "0400"):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        return root / "assets" / ("knup-kpv84-side.png" if side else "knup-kpv84-top.png")
    # Read an optional image from the user's existing installation at runtime.
    # These proprietary files are never copied into the source or release.
    if (device.vid, device.pid) != ("046D", "C08B"):
        return None
    root = Path("C:/ProgramData/LGHUB/depots")
    name = "side_hero.png" if side else "front_hero.png"
    try:
        candidates = sorted(root.glob(f"*/g502_hero/images/device/{name}"))
        return candidates[-1] if candidates else None
    except OSError:
        return None


class HardwareArt(DeviceArt):
    def __init__(self, device, side=False):
        super().__init__(device.kind, "#00b7ed")
        self.device = device
        self.side = side
        self.reload()

    def reload(self):
        path = reference_image(self.device, self.side)
        self.picture = QPixmap(str(path)) if path else QPixmap()
        self.update()

    def paintEvent(self, event):
        if self.picture.isNull():
            return super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        fitted = self.picture.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((self.width() - fitted.width()) // 2, (self.height() - fitted.height()) // 2, fitted)
        p.end()


class BackArrow(QPushButton):
    def __init__(self, callback=None):
        super().__init__()
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Volver")
        self.setAccessibleName("Volver")
        if callback:
            self.clicked.connect(callback)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#ffffff"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(34, 24, 13, 24)
        p.drawLine(13, 24, 20, 17)
        p.drawLine(13, 24, 20, 31)
        p.end()


class MacroTypeButton(QPushButton):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.setFixedSize(120, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(MODES[mode])
        self.setToolTip(MODES[mode])

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#252527" if self.underMouse() or self.hasFocus() else "#191919"))
        p.drawRoundedRect(QRectF(0, 0, 120, 120), 3, 3)
        p.translate(60, 60)
        p.setPen(QPen(QColor("#ffffff"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.mode == "once":
            p.drawLine(-13, 0, 12, 0)
            p.drawLine(5, -8, 13, 0)
            p.drawLine(13, 0, 5, 8)
        elif self.mode == "hold":
            p.drawArc(QRectF(-11, -12, 22, 24), -70 * 16, 300 * 16)
            p.drawLine(4, 11, -1, 9)
            p.drawLine(4, 11, 2, 16)
        elif self.mode == "toggle":
            p.drawRoundedRect(QRectF(-17, -10, 34, 20), 10, 10)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(7, 0), 7, 7)
        elif self.mode == "latch":
            p.drawRoundedRect(QRectF(-15, -12, 30, 24), 4, 4)
            p.drawLine(-5, -6, -5, 6)
            p.drawLine(5, -6, 5, 6)
        else:
            for x, y in ((0, 0), (-8, -3), (-16, -6)):
                p.setBrush(QColor("#ffffff") if x == -16 else QColor("#191919"))
                p.drawRoundedRect(QRectF(x, y, 15, 15), 3, 3)
        p.end()


class RailButton(QPushButton):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.setCheckable(True)
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#109cfa" if self.isChecked() else "#18181a" if self.underMouse() else "#000000"))
        p.drawRoundedRect(QRectF(0, 0, 48, 48), 12, 12)
        p.setPen(QPen(QColor("#ffffff" if self.isChecked() else "#939396"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.kind == "assignments":
            p.drawRoundedRect(QRectF(13, 13, 22, 22), 2, 2)
            p.drawLine(24, 19, 24, 29)
            p.drawLine(19, 24, 29, 24)
        elif self.kind == "lighting":
            p.drawEllipse(QPointF(24, 24), 5, 5)
            for n in range(8):
                angle = n * math.pi / 4
                p.drawLine(QPointF(24 + 10 * math.cos(angle), 24 + 10 * math.sin(angle)),
                           QPointF(24 + 14 * math.cos(angle), 24 + 14 * math.sin(angle)))
        else:
            p.drawEllipse(QPointF(24, 24), 2, 2)
            for n in range(4):
                p.save()
                p.translate(24, 24)
                p.rotate(n * 90)
                p.drawLine(-4, -10, 0, -14)
                p.drawLine(0, -14, 4, -10)
                p.restore()
        p.end()


class HubCard(QFrame):
    selected = Signal(object)

    def __init__(self, device):
        super().__init__()
        self.setObjectName("deviceCard")
        self.setFixedSize(280, 435)
        self.device = device
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 22)
        title = device.name.replace(" Gaming Mouse", "").replace("Logitech · ", "")
        title_label = label(title, "sectionTitle", True)
        title_label.setMinimumHeight(48)
        layout.addWidget(title_label)
        layout.addWidget(label("●  CONECTADO", "muted"))
        art = HardwareArt(device)
        art.setMinimumSize(160, 240)
        layout.addWidget(art, 1)
        layout.addWidget(button("CONFIGURAR", lambda: self.selected.emit(device), True))

    def mouseDoubleClickEvent(self, event):
        self.selected.emit(self.device)


class MacroLibrary(QListWidget):
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if not item:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-nexus-macro", str(item.data(Qt.ItemDataRole.UserRole)).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class AssignmentCanvas(QWidget):
    target = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(560, 410)
        self.device = None
        self.side = False
        self.names = {}
        self.disabled = set()
        self.label_rects = {}
        self.points = {}
        self.selected = ""
        self.art = None
        self.overlay = TargetsOverlay(self)

    def configure(self, device, names=None):
        self.device = device
        self.names = names or {}
        if self.art:
            self.art.hide()
            self.art.deleteLater()
        self.art = HardwareArt(device, self.side)
        self.art.setParent(self)
        self.art.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.art.show()
        self.arrange()

    def arrange(self):
        if not self.device:
            return
        w, h = self.width(), self.height()
        if self.device.kind == "keyboard":
            self.art.setGeometry(int(w * .23), int(h * .24), int(w * .55), int(h * .5))
            self.points = {"Tecla": QPointF(w * .5, h * .5)}
        else:
            height = min(410, h * .72)
            knup = (self.device.vid, self.device.pid) == ("30FA", "0400")
            if knup and not self.art.picture.isNull():
                ratio = self.art.picture.width() / self.art.picture.height()
                if self.side:
                    width = min(490, w * .48)
                    height = width / ratio
                else:
                    width = height * ratio
            else:
                width = height * (936 / 2700 if self.side else 1391 / 2700)
            x, y = w * .56 - width / 2, (h - height) / 2 - 10
            self.art.setGeometry(int(x), int(y), int(width), int(height))
            if self.side:
                coords = {"G4": (.62, .667), "G5": (.534, .519), "G6": (.288, .463)}
            else:
                coords = {"G1": (.387, .227), "G2": (.798, .227), "G3": (.575, .322),
                          "G7": (.227, .366), "G8": (.230, .281), "G9": (.600, .514),
                          "G10": (.647, .322), "G11": (.503, .322)}
            if (self.device.vid, self.device.pid) != ("046D", "C08B"):
                coords = {"Principal": (.3, .2), "Secundario": (.7, .2), "Central": (.5, .35),
                          "Lateral 4": (.06, .5), "Lateral 5": (.06, .36)}
            if knup:
                coords = ({"Lateral 4": (.58, .56), "Lateral 5": (.44, .59)} if self.side else
                          {"Principal": (.32, .25), "Secundario": (.68, .25), "Central": (.50, .24)})
            self.points = {slot: QPointF(x + px * width, y + py * height) for slot, (px, py) in coords.items()}
        self.update()
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.overlay.update()

    def resizeEvent(self, event):
        self.arrange()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.device:
            return
        # Paint the reference before the overlay, not as a sibling that covers it.
        p = QPainter(self)
        p.setPen(QColor("#aaa"))
        p.drawText(QRectF(30, 12, self.width() - 60, 50), Qt.AlignmentFlag.AlignCenter,
                   "Arrastra una macro a un botón, o haz clic en un objetivo para asignarla.")
        p.end()

    def slot_at(self, point):
        for slot, rect in self.label_rects.items():
            if rect.contains(QPointF(point)):
                return slot
        distances = sorted(((pos - QPointF(point)).manhattanLength(), slot) for slot, pos in self.points.items())
        return distances[0][1] if distances and distances[0][0] < 22 else ""

    def mousePressEvent(self, event):
        slot = self.slot_at(event.position())
        if slot:
            self.selected = slot
            self.target.emit(slot, "")

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-nexus-macro"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self.slot_at(event.position()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        slot = self.slot_at(event.position())
        if slot:
            self.target.emit(slot, bytes(event.mimeData().data("application/x-nexus-macro")).decode())
            event.acceptProposedAction()


class TargetsOverlay(QWidget):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.show()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.canvas.art or not self.canvas.device:
            p.end()
            return
        art = self.canvas.art.geometry()
        # Keep callouts anchored to the device, even in a maximized window.
        gap = 42
        label_width = min(180, max(112, (self.width() - art.width()) / 2 - gap - 18))
        left = max(18, art.left() - gap - label_width)
        right = min(self.width() - label_width - 18, art.right() + gap)
        defaults = {
            "G1": "Clic principal", "G2": "Clic secundario",
            "G3": "Clic con el botón\ncentral", "G4": "Atrás", "G5": "Adelante",
            "G6": "Cambio de DPI", "G7": "Reducir DPI", "G8": "Aumentar DPI",
            "G9": "Ciclo de perfiles\nintegrados", "G10": "Sin asignar",
            "G11": "Desplazar a la\nizquierda",
            "Principal": "Clic principal", "Secundario": "Clic secundario",
            "Central": "Clic con el botón\ncentral", "Lateral 4": "Atrás", "Lateral 5": "Adelante",
        }
        rows = {"G1": (False, .10), "G2": (True, .10),
                "G8": (False, .25), "G11": (False, .40),
                "G7": (False, .55), "G10": (True, .34), "G9": (True, .55),
                "G4": (True, .72), "G5": (True, .48), "G6": (False, .32),
                "Principal": (False, .10), "Secundario": (True, .10),
                "Lateral 4": (False, .60), "Lateral 5": (False, .40)}
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        self.canvas.label_rects = {}
        for slot, pos in self.canvas.points.items():
            assigned = slot in self.canvas.names
            text = self.canvas.names.get(slot, defaults.get(slot, "Sin asignar"))
            if slot in ("G3", "Central", "Tecla"):
                yy = art.top() - 38
                rect = QRectF(pos.x() - 100, yy - 38, 200, 34)
                start = QPointF(pos.x(), yy)
                elbow = start
                alignment = Qt.AlignmentFlag.AlignHCenter
            else:
                right_side, row = rows.get(slot, (False, .75))
                yy = art.top() + art.height() * row
                xx = right if right_side else left
                rect = QRectF(xx, yy - 40, label_width, 35)
                start = QPointF(xx + label_width if right_side else xx, yy)
                elbow = QPointF(art.right() + 12 if right_side else art.left() - 12, yy)
                alignment = Qt.AlignmentFlag.AlignRight if right_side else Qt.AlignmentFlag.AlignLeft
            if slot in self.canvas.disabled:
                p.setPen(QPen(QColor("#aaaaad"), 1.5))
                p.setBrush(QColor("#222326"))
                p.drawEllipse(pos, 5, 5)
                continue
            self.canvas.label_rects[slot] = rect
            p.setPen(QPen(QColor("#505053"), 1))
            p.drawLine(pos, elbow)
            p.drawLine(elbow, start)
            active = assigned or slot == self.canvas.selected
            p.setPen(QPen(QColor("#00b7ed" if active else "#aaaaad"), 1.5))
            p.setBrush(QColor("#00b7ed" if active else "#f4f4f5" if text != "Sin asignar" else "#222326"))
            p.drawEllipse(pos, 5, 5)
            p.setPen(QColor("#00c6ed" if active else "#f0f0f2"))
            text = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width())) if "\n" not in text else text
            p.drawText(rect, alignment | Qt.AlignmentFlag.AlignBottom, text)
        p.end()


class TypeDialog(QDialog):
    def __init__(self, parent=None, macro_name="Nueva macro"):
        super().__init__(parent)
        self.mode = "once"
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Selecciona el tipo de macro")
        self.setStyleSheet("QDialog { background: #000000; }")
        self.setMinimumSize(900, 640)
        if parent:
            self.resize(parent.size())
            self.move(parent.mapToGlobal(QPoint(0, 0)))
        else:
            self.resize(1100, 790)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 28)
        layout.addWidget(BackArrow(self.reject), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(32)
        title = label(macro_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:600; color:white; background:transparent;")
        layout.addWidget(title)
        layout.addStretch(2)
        prompt = label("SELECCIONA EL TIPO DE MACRO QUE CREAR")
        prompt.setStyleSheet("font-size:13px; font-weight:700; letter-spacing:0.4px; background:transparent;")
        layout.addWidget(prompt, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(46)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        captions = {"once": "SIN REPETICIÓN", "hold": "REPETIR DURANTE\nPULSACIÓN",
                    "toggle": "ALTERNANTE", "sequence": "SECUENCIA", "latch": "MANTENER PULSADO"}
        self.mode_controls = {}
        for key in ("once", "hold", "toggle", "sequence", "latch"):
            column = QVBoxLayout()
            column.setSpacing(22)
            control = MacroTypeButton(key)
            control.clicked.connect(lambda checked=False, value=key: self.choose(value))
            self.mode_controls[key] = control
            column.addWidget(control, 0, Qt.AlignmentFlag.AlignHCenter)
            caption = label(captions[key])
            caption.setFixedSize(160, 46)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            caption.setStyleSheet("font-size:13px; font-weight:700; letter-spacing:0.3px; color:white; background:transparent;")
            column.addWidget(caption)
            row.addLayout(column)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch(3)

    def choose(self, mode):
        self.mode = mode
        self.accept()


class LearnBindingDialog(QDialog):
    def __init__(self, owner, device, macros, slot, selected_id=""):
        super().__init__(owner)
        self.owner, self.device, self.slot = owner, device, slot
        self.trigger = None
        self.pending_trigger = None
        self.setWindowTitle("Asignar " + slot)
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.addWidget(label(device.name + " · " + slot, "sectionTitle", True))
        self.macro = QComboBox()
        for macro in macros:
            self.macro.addItem(macro["name"] + " · " + MODES[macro.get("mode", "once")], macro["id"])
        index = self.macro.findData(selected_id)
        if index >= 0:
            self.macro.setCurrentIndex(index)
        layout.addWidget(self.macro)
        is_g502 = (device.vid, device.pid) == ("046D", "C08B")
        self.require_g = is_g502
        self.hint = label("Pulsa y suelta ahora el botón físico " + slot + "." if device.kind == "mouse" else
                          "Pulsa y suelta la tecla que quieres asignar en este teclado.", "eyebrow", True)
        layout.addWidget(self.hint)
        layout.addWidget(label("Se detecta el control físico; no se deduce a partir de la macro que G HUB pudiera tener asignada.", "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("GUARDAR ASIGNACIÓN")
        self.save_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        standard = {"Lateral 4": "x1", "Lateral 5": "x2", "Central": "middle"}
        if not is_g502 and device.kind == "mouse" and slot in standard:
            self.trigger = {"type": "mouse", "button": standard[slot]}
            self.save_button.setEnabled(True)
            self.hint.setText("Botón estándar de Windows listo. Puedes guardar directamente o pulsar otro botón para identificarlo.")

    def observe(self, handle, event):
        g = self.owner.g502
        if self.require_g:
            if not g or handle != g.handle or event["type"] != "gbutton":
                return
        elif handle not in self.device.handles or event["type"] not in ("key", "mouse"):
            return
        if event["type"] == "mouse" and event["button"] not in ("middle", "x1", "x2"):
            self.hint.setText("Este modelo genérico permite asignar los botones central y laterales. Para G1/G2 hace falta un adaptador con supresión física.")
            return
        kind = event["type"]
        trigger = {"type": kind}
        if kind == "key":
            from .windows import modifiers, key_name
            trigger.update(vk=event["vk"], mods=sorted(modifiers()))
            text = key_name(event["vk"])
        else:
            trigger["button"] = event["button"]
            text = f"Control físico {event['button'] + 1}" if kind == "gbutton" else event["button"]
        if event["down"]:
            self.pending_trigger = trigger
            self.hint.setText(text + " detectado. Suéltalo para confirmar.")
        elif self.pending_trigger and all(trigger[k] == self.pending_trigger[k] for k in trigger if k != "mods"):
            self.trigger = self.pending_trigger
            self.save_button.setEnabled(True)
            self.hint.setText("✓  " + text + " identificado. Guarda la asignación.")

    def binding(self):
        return {"device_id": self.device.id, "macro_id": self.macro.currentData(),
                "trigger": self.trigger, "slot": self.slot, "enabled": True}
