"""Black workspace, physical assignment targets and horizontal macro timeline."""
import json
import sys
import math
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QMimeData, QPoint, QSize, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QDrag, QPainterPath, QIcon, QRegion, QFont
from PySide6.QtWidgets import (QWidget, QListWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
                              QPushButton, QDialog, QDialogButtonBox, QComboBox,
                              QStyledItemDelegate, QStyleOptionViewItem, QStyle, QLineEdit)
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
QListWidget#macroLibrary { background: transparent; border: none; padding: 0; }
QListWidget#macroLibrary::item { padding: 6px 0; }
QListWidget#assignedButtons { background: #1c1d20; border: 1px solid #3c3c3f; border-radius: 5px; padding: 4px; }
QLineEdit#macroSearch { background: transparent; border: none; border-bottom: 1px solid #999; border-radius: 0; padding: 6px 0; }
QLineEdit#macroSearch:focus { border-bottom: 1px solid #00b7ed; }
QLabel#macroSection { color: white; font-size: 13px; border-bottom: 2px solid white; padding-bottom: 5px; }
QLabel#macroInstructions { color: #eee; font-size: 12px; font-weight: 600; }
QTableWidget { background: #151515; alternate-background-color: #1c1c1c; border-color: #333; }
QHeaderView::section { background: #282828; color: #aaa; }
QCheckBox::indicator:checked { background: #00b7ed; border: 3px solid #194957; }
QStatusBar { background: #080808; color: #96969b; border-top: 1px solid #222; }
QDialog { background: #171719; }
QListWidget#profileList::item { padding: 0; border: none; background: transparent; }
QListWidget#profileList::item:selected { background: transparent; }
QFrame#profileCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #19c9e9,stop:1 #00afd7); border: 2px solid transparent; border-radius: 16px; }
QFrame#profileCard:hover { border-color: #b6f6ff; }
QFrame#profileCard[selected="true"] { border: 2px solid white; }
QFrame#profileCard QLabel { background: transparent; color: #002d3a; }
QFrame#profileCard QLabel#profileState { background: #003b4d; color: white; border-radius: 9px; padding: 4px 9px; font-size: 11px; }
QPushButton#profileAction { background: transparent; border: none; border-radius: 10px; padding: 0; }
QPushButton#profileAction:hover { background: #315551; }
"""


class ConnectionLabel(QLabel):
    """Color only the status dot, keeping the connection text gray."""
    def __init__(self, connected=True):
        super().__init__()
        self.setObjectName('muted')
        self.setText('● CONECTADO' if connected else '○ DESCONECTADO')

    def setText(self, text):
        connected = 'DESCONECTADO' not in text
        status = 'CONECTADO' if connected else 'DESCONECTADO'
        color = '#49d68a' if connected else '#a2a2a6'
        self.setAccessibleName(status)
        super().setText(f'<span style="color:{color}">●</span>&nbsp; <span style="color:#a2a2a6">{status}</span>')


def profile_action_icon(kind):
    picture = QPixmap(24, 24)
    picture.fill(Qt.GlobalColor.transparent)
    p = QPainter(picture)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#d5eee8'), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == 'rename':
        path = QPainterPath(QPointF(5, 15))
        for point in [(15, 5), (19, 9), (9, 19), (4, 20), (5, 15)]:
            path.lineTo(*point)
        p.drawPath(path)
        p.drawLine(13, 7, 17, 11)
    else:
        p.drawLine(5, 7, 19, 7)
        p.drawLine(9, 4, 15, 4)
        p.drawLine(7, 7, 8, 20)
        p.drawLine(8, 20, 16, 20)
        p.drawLine(16, 20, 17, 7)
        p.drawLine(10, 10, 10, 17)
        p.drawLine(14, 10, 14, 17)
    p.end()
    return QIcon(picture)


class ProfileCard(QFrame):
    selected = Signal()
    activated = Signal()
    rename = Signal()
    remove = Signal()

    def __init__(self, profile, active=False):
        super().__init__()
        self.setObjectName('profileCard')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(label('PERFIL', 'eyebrow'))
        top.addStretch()
        if active:
            top.addWidget(label('EN USO', 'profileState'))
        layout.addLayout(top)
        title = label(profile['name'], 'sectionTitle', True)
        title.setMaximumHeight(60)
        title.setToolTip(profile['name'])
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title, 1)
        description = label(f"{len(profile['macros'])} macros", 'muted')
        description.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout()
        row.addWidget(description, 1)
        layout.addLayout(row)
        for kind, tip, signal in [('rename', 'Renombrar perfil', self.rename), ('delete', 'Eliminar perfil', self.remove)]:
            control = QPushButton()
            control.setObjectName('profileAction')
            control.setIcon(profile_action_icon(kind))
            control.setIconSize(QSize(24, 24))
            control.setFixedSize(40, 40)
            control.setToolTip(tip)
            control.setAccessibleName(tip + ' ' + profile['name'])
            control.clicked.connect(signal.emit)
            row.addWidget(control)

    def set_selected(self, selected):
        self.setProperty('selected', selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseDoubleClickEvent(event)


def reference_image(device, side=False):
    from .keyboard_support import is_kumara
    if is_kumara(device):
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        return root / 'assets' / 'redragon-kumara-k552rgb-1.jpg'
    if device.kind == "mouse" and (device.vid, device.pid) == ("30FA", "0400"):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        return root / "assets" / ("knup-kpv84-side.png" if side else "knup-kpv84-top.png")
    # Retain the previous G HUB artwork when available. The bundled product
    # views keep this model recognizable on a clean install or after uninstall.
    if (device.vid, device.pid) != ("046D", "C08B"):
        if device.kind == 'mouse':
            root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
            return root / 'assets' / 'generic-mouse.png'
        return None
    root = Path("C:/ProgramData/LGHUB/depots")
    name = "side_hero.png" if side else "front_hero.png"
    try:
        candidates = sorted(root.glob(f"*/g502_hero/images/device/{name}"))
        if candidates:
            return candidates[-1]
    except OSError:
        pass
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return root / 'assets' / ('g502-hero-side.png' if side else 'g502-hero-top.png')


class HardwareArt(DeviceArt):
    def __init__(self, device, side=False):
        super().__init__(device.kind, "#00b7ed")
        self.device = device
        self.setToolTip(f"USB {device.vid}:{device.pid}\n" + (device.identification or 'Nombre comunicado por el dispositivo o Windows'))
        self.side = side
        self.reload()

    def reload(self):
        path = reference_image(self.device, self.side)
        self.bundled_g502 = bool(path and path.name in ('g502-hero-top.png', 'g502-hero-side.png'))
        self.picture = QPixmap(str(path)) if path else QPixmap()
        if self.picture.isNull() and (self.device.vid, self.device.pid) == ('046D', 'C08B'):
            root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
            path = root / 'assets' / ('g502-hero-side.png' if self.side else 'g502-hero-top.png')
            self.picture = QPixmap(str(path))
            self.bundled_g502 = True
        self.content_rect = QRectF(QRegion(self.picture.mask()).boundingRect()) if not self.picture.isNull() else QRectF()
        self.rotation_degrees = 90 if self.device.kind == 'mouse' and self.side and self.content_rect.width() > self.content_rect.height() else 0
        self.update()

    def source_rect(self):
        from .keyboard_support import is_kumara
        if self.rotation_degrees and not self.content_rect.isEmpty():
            return self.content_rect
        if self.bundled_g502 and not self.content_rect.isEmpty():
            return self.content_rect
        if is_kumara(self.device) and not self.picture.isNull():
            # Frame the original photograph in the view without editing it.
            return QRectF(52, 78 if self.picture.height() < 1000 else 365, 1396, 498)
        if self.device.kind == 'mouse' and (self.device.vid, self.device.pid) not in [('046D', 'C08B'), ('30FA', '0400')] and not self.picture.isNull():
            return self.content_rect
        return QRectF(self.picture.rect())

    def fitted_rect(self):
        source = self.source_rect()
        if source.width() <= 0 or source.height() <= 0:
            return QRectF(self.rect())
        sw, sh = (source.height(), source.width()) if self.rotation_degrees else (source.width(), source.height())
        scale = min(self.width() / sw, self.height() / sh)
        w, h = sw * scale, sh * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, event):
        if self.picture.isNull():
            if self.device.kind == 'mouse' and (self.device.vid, self.device.pid) != ('046D', 'C08B'):
                return self.paint_generic_mouse()
            return super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        fitted = self.fitted_rect()
        if self.rotation_degrees:
            p.translate(fitted.center())
            p.rotate(self.rotation_degrees)
            p.drawPixmap(QRectF(-fitted.height()/2, -fitted.width()/2, fitted.height(), fitted.width()), self.picture, self.source_rect())
        else:
            p.drawPixmap(fitted, self.picture, self.source_rect())
        p.end()

    def paint_generic_mouse(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width() / 170, self.height() / 320)
        p.scale(scale, scale)
        p.setPen(QPen(QColor('#555c62'), 2))
        p.drawLine(0, -160, 0, -132)
        p.setBrush(QColor('#30353a'))
        p.drawRoundedRect(QRectF(-70, -132, 140, 268), 65, 65)
        p.setPen(QPen(QColor('#14181b'), 2))
        p.drawLine(0, -130, 0, -25)
        p.drawLine(-67, -25, 67, -25)
        p.setBrush(QColor('#111518'))
        p.drawRoundedRect(QRectF(-8, -90, 16, 38), 6, 6)
        p.setPen(QPen(QColor('#8b959b'), 1))
        for y in range(-84, -56, 5):
            p.drawLine(-4, y, 4, y)
        count = self.device.button_count or 2
        if count >= 4:
            p.drawRoundedRect(QRectF(-73, 3, 7, 24), 3, 3)
        if count >= 5:
            p.drawRoundedRect(QRectF(-73, 34, 7, 24), 3, 3)
        p.end()


class BackArrow(QPushButton):
    def __init__(self, callback=None):
        super().__init__()
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        self.icon_scale = 2.5
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(MODES[mode])
        self.setToolTip(MODES[mode])

    def paintEvent(self, event):
        MacroModeButton.paintEvent(self, event)


class MacroModeButton(QPushButton):
    """Vector icons stay sharp at any Windows display scale."""
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.setCheckable(True)
        self.setAccessibleName(MODES[mode])
        self.setToolTip(MODES[mode])
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isChecked()
        color = QColor('#00c6ed' if selected else '#ffffff')
        p.setPen(QPen(QColor('#00b7ed' if selected else '#454549'), 1))
        p.setBrush(QColor('#00232a' if selected else '#252527' if self.underMouse() else '#191919'))
        p.drawRoundedRect(QRectF(.5, .5, self.width()-1, self.height()-1), 3, 3)
        p.translate(self.width()/2, self.height()/2)
        scale = getattr(self, 'icon_scale', 1)
        p.scale(scale, scale)
        p.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.mode == 'once':
            path = QPainterPath(QPointF(-5, -8))
            path.lineTo(8, 0)
            path.lineTo(-5, 8)
            path.closeSubpath()
            p.setBrush(color)
            p.drawPath(path)
        elif self.mode == 'hold':
            p.drawLine(-9, -4, 9, -4)
            p.drawLine(5, -8, 9, -4)
            p.drawLine(9, -4, 5, 0)
            p.drawLine(9, 4, -9, 4)
            p.drawLine(-5, 0, -9, 4)
            p.drawLine(-9, 4, -5, 8)
        elif self.mode == 'toggle':
            p.drawRoundedRect(QRectF(-12, -7, 24, 14), 7, 7)
            p.setBrush(color)
            p.drawEllipse(QPointF(5, 0), 5, 5)
        elif self.mode == 'sequence':
            p.drawLine(-8, 0, 8, 0)
            for x in (-12, -3, 6):
                p.setBrush(QColor('#00232a' if selected else '#191919'))
                p.drawRoundedRect(QRectF(x, -5, 6, 10), 1.5, 1.5)
        else:
            path = QPainterPath(QPointF(-5, -1))
            path.lineTo(-5, -5)
            path.cubicTo(-5, -12, 5, -12, 5, -5)
            path.lineTo(5, -1)
            p.drawPath(path)
            p.drawRoundedRect(QRectF(-8, -1, 16, 12), 2, 2)
            p.drawLine(0, 3, 0, 7)
        if self.hasFocus():
            p.setPen(QPen(color, 1, Qt.PenStyle.DotLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(-self.width()/2+3, -self.height()/2+3, self.width()-6, self.height()-6), 2, 2)
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
        elif self.kind == "settings":
            path = QPainterPath()
            for n in range(64):
                angle = n * math.pi / 32
                radius = 12 if n % 8 in (1, 2, 3, 4) else 9
                point = QPointF(24 + radius * math.cos(angle), 24 + radius * math.sin(angle))
                if n == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            path.closeSubpath()
            p.drawPath(path)
            p.drawEllipse(QPointF(24, 24), 4, 4)
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
        self.setToolTip(f"USB {device.vid}:{device.pid}\n" + (device.identification or 'Nombre comunicado por el dispositivo o Windows'))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 22)
        title = device.name.replace(" Gaming Mouse", "").replace("Logitech · ", "")
        title_label = label(title, "sectionTitle", True)
        title_label.setMinimumHeight(48)
        layout.addWidget(title_label)
        layout.addWidget(ConnectionLabel())
        if device.kind == 'mouse':
            text = ('11 controles físicos · G502 HERO' if (device.vid, device.pid) == ('046D', 'C08B') else
                    f'{device.button_count} botones informados por Windows' if device.button_count else 'Cantidad de botones no disponible')
            layout.addWidget(label(text, 'muted', True))
        art = HardwareArt(device)
        art.setMinimumSize(160, 240)
        layout.addWidget(art, 1)
        layout.addWidget(button("CONFIGURAR", lambda: self.selected.emit(device), True))

    def mouseDoubleClickEvent(self, event):
        self.selected.emit(self.device)


class AssignmentPanel(QFrame):
    def update_minimum_height(self):
        layout = self.layout()
        if layout:
            # Include wrapped labels at the actual scroll viewport width.
            height = max(layout.minimumSize().height(), layout.totalMinimumHeightForWidth(self.width()))
            if self.minimumHeight() != height:
                self.setMinimumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_minimum_height()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.update_minimum_height()
        return result


class MacroSearch(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('macroSearch')
        self.setTextMargins(25, 0, 0, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#eee'), 1.6))
        y = self.height() / 2 - 2
        painter.drawEllipse(QPointF(8, y), 4, 4)
        painter.drawLine(QPointF(11, y + 3), QPointF(15, y + 7))
        painter.end()


class MacroColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        text, option.text = option.text, ''
        style = option.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, option.widget)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.save()
        name = index.data(Qt.ItemDataRole.UserRole + 1)
        slots = index.data(Qt.ItemDataRole.UserRole + 2)
        if name is not None:
            badge = QRectF(rect.left(), rect.center().y() - 9, 18, 18)
            badge_color = QColor(index.data(Qt.ItemDataRole.UserRole + 3) or '#999999')
            painter.fillRect(badge, badge_color)
            luminance = .2126 * badge_color.red() + .7152 * badge_color.green() + .0722 * badge_color.blue()
            painter.setPen(QColor('#202124' if luminance > 180 else 'white'))
            font = QFont(option.font)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, 'M')
            rect.setLeft(rect.left() + 30)
            text = name
            if slots:
                # Reserve a right-aligned column without crowding long names.
                painter.setFont(option.font)
                width = min(option.fontMetrics.horizontalAdvance(slots) + 8, rect.width() // 2)
                slot_rect = QRectF(rect.right() - width, rect.top(), width, rect.height())
                painter.setPen(brush.color() if brush else QColor('white'))
                painter.drawText(slot_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    option.fontMetrics.elidedText(slots, Qt.TextElideMode.ElideRight, int(width)))
                rect.setRight(int(slot_rect.left()) - 12)
        painter.setFont(option.font)
        painter.setPen(brush.color() if brush else QColor('white'))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width()))
        painter.restore()


class MacroLibrary(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(MacroColorDelegate(self))

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
    target_context = Signal(str)
    selection_changed = Signal(str)
    target = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(560, 410)
        self.device = None
        self.side = False
        self.names = {}
        self.name_colors = {}
        self.disabled = set()
        self.paused = set()
        self.label_rects = {}
        self.points = {}
        self.selected = ""
        self.art = None
        self.overlay = TargetsOverlay(self)

    def configure(self, device, names=None):
        if not self.device or self.device.id != device.id:
            self.side = False
            self.selected = ''
        self.label_rects = {}
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
            from .keyboard_support import is_kumara
            width = w * .94
            height = min(h * .56, width / 2.80)
            self.art.setGeometry(int((w - width) / 2), int((h - height) / 2), int(width), int(height))
            rect = self.art.fitted_rect().translated(self.art.pos())
            if is_kumara(self.device):
                positions = [248, 324, 400, 476, 590, 666, 742, 818, 930, 1007, 1083, 1159]
                self.points = {f'F{i + 1}': QPointF(rect.x() + (x - 52) / 1396 * rect.width(),
                                                 rect.y() + 43 / 498 * rect.height())
                               for i, x in enumerate(positions)}
            else:
                self.points = {f'F{i + 1}': QPointF(rect.x() + (.10 + i * .065) * rect.width(),
                                                  rect.y() + .13 * rect.height()) for i in range(12)}
        else:
            height = min(410, h * .72)
            knup = (self.device.vid, self.device.pid) == ("30FA", "0400")
            if not self.art.picture.isNull():
                source = self.art.source_rect()
                ratio = source.height() / source.width() if self.art.rotation_degrees else source.width() / source.height()
                width = height * ratio
            else:
                width = height * (936 / 2700 if self.side else 1391 / 2700)
                if not self.art.picture.isNull() and (self.device.vid, self.device.pid) != ('046D', 'C08B'):
                    source = self.art.source_rect()
                    width = height * source.width() / source.height()
            x, y = (w - width) / 2, (h - height) / 2 - 10
            self.art.setGeometry(int(x), int(y), int(width), int(height))
            # Minimum widget sizes can enlarge a narrow side view. Center the
            # actual geometry, keeping its existing vertical position intact.
            self.art.move((w-self.art.width())//2, self.art.y())
            if self.side:
                # Anchors measured against the original G HUB reference captures.
                coords = {"G4": (.612, .661), "G5": (.526, .509), "G6": (.274, .451)}
            else:
                coords = {"G1": (.392, .226), "G2": (.802, .226), "G3": (.580, .320),
                          "G7": (.226, .364), "G8": (.231, .280), "G9": (.604, .510),
                          "G10": (.651, .320), "G11": (.505, .320)}
            if (self.device.vid, self.device.pid) != ("046D", "C08B"):
                coords = {"Principal": (.3, .2), "Secundario": (.7, .2)}
                count = self.device.button_count or 2
                if count >= 3:
                    coords['Central'] = (.5, .28)
                if count >= 4:
                    coords['Lateral 4'] = (.06, .5)
                if count >= 5:
                    coords['Lateral 5'] = (.06, .36)
            if knup:
                coords = ({"Lateral 4": (.58, .56), "Lateral 5": (.44, .59)} if self.side else
                          {"Principal": (.32, .25), "Secundario": (.68, .25), "Central": (.50, .24)})
            if self.art.bundled_g502:
                # Positions in the bundled product renders, normalized to the
                # visible source rectangle (transparent padding is excluded).
                source = self.art.source_rect()
                pixels = ({'G4': (754, 486), 'G5': (595, 513), 'G6': (527, 605)} if self.side else
                          {'G1': (525, 254), 'G2': (735, 257), 'G3': (635, 313),
                           'G7': (452, 363), 'G8': (462, 284), 'G9': (638, 501),
                           'G10': (690, 313), 'G11': (582, 313)})
                coords = {slot: ((px - source.x()) / source.width(), (py - source.y()) / source.height())
                          for slot, (px, py) in pixels.items()}
            if self.art.rotation_degrees:
                if not self.art.bundled_g502:
                    source = self.art.source_rect()
                    coords = {slot: ((px*self.art.picture.width()-source.x())/source.width(),
                                     (py*self.art.picture.height()-source.y())/source.height())
                              for slot, (px, py) in coords.items()}
                coords = {slot: (1-py, px) for slot, (px, py) in coords.items()}
            # Use the actual integer widget rectangle used to paint the image.
            rect = self.art.geometry()
            self.points = {slot: QPointF(rect.x() + px * rect.width(), rect.y() + py * rect.height())
                           for slot, (px, py) in coords.items()}
        self.update()
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.overlay.update()

    def resizeEvent(self, event):
        self.arrange()

    def slot_at(self, point):
        for slot, rect in self.label_rects.items():
            if rect.contains(QPointF(point)):
                return slot
        distances = sorted(((pos - QPointF(point)).manhattanLength(), slot) for slot, pos in self.points.items())
        return distances[0][1] if distances and distances[0][0] < 22 else ""

    def mousePressEvent(self, event):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            return
        slot = self.slot_at(event.position())
        if slot:
            self.selected = slot
            self.overlay.update()
            self.selection_changed.emit(slot)
            if event.button() == Qt.MouseButton.RightButton:
                self.target_context.emit(slot)
            else:
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
        if self.canvas.device.kind == 'keyboard':
            self.canvas.label_rects = {}
            font = p.font()
            font.setBold(True)
            font.setPixelSize(12)
            p.setFont(font)
            for slot, pos in self.canvas.points.items():
                rect = QRectF(pos.x() - 14, pos.y() - 13, 28, 26)
                self.canvas.label_rects[slot] = rect
                assigned = slot in self.canvas.names
                selected = slot == self.canvas.selected
                paused = slot in self.canvas.paused
                p.setPen(QPen(QColor('#888888' if paused else '#00c6ed' if assigned or selected else '#cccccc'), 1.5))
                p.setBrush(QColor('#292929' if paused else '#004657' if assigned or selected else '#171719'))
                p.drawRoundedRect(rect, 3, 3)
                p.setPen(QColor('white'))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, slot)
            slot = self.canvas.selected
            text = f"{slot} · {self.canvas.names.get(slot, 'Función original')}" + (' · MACRO DESACTIVADA' if slot in self.canvas.paused else '') if slot else 'SOLO F1–F12 · Selecciona una tecla o arrastra una macro'
            p.setPen(QColor('#00c6ed'))
            p.drawText(QRectF(15, art.top() - 55, self.width() - 30, 45), Qt.AlignmentFlag.AlignCenter, text)
            p.end()
            return
        # Keep callouts anchored to the device, even in a maximized window.
        gap = 42
        label_width = min(180, max(112, (self.width() - art.width()) / 2 - gap - 18))
        left = max(18, art.left() - gap - label_width)
        right = min(self.width() - label_width - 18, art.right() + gap)
        defaults = {
            "G1": "Clic principal\nPROTEGIDO", "G2": "Clic secundario\nPROTEGIDO",
            "G3": "Clic con el botón\ncentral", "G4": "Atrás", "G5": "Adelante",
            "G6": "Cambio de DPI", "G7": "Reducir DPI", "G8": "Aumentar DPI",
            "G9": "Ciclo de perfiles\nintegrados", "G10": "Sin asignar",
            "G11": "Desplazar a la\nizquierda",
            "Principal": "Clic principal\nPROTEGIDO", "Secundario": "Clic secundario\nPROTEGIDO",
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
            p.setBrush(QColor("#00b7ed" if active else "#222326" if slot in ("G4", "G5", "G6", "G7", "G8") or text == "Sin asignar" else "#f4f4f5"))
            p.drawEllipse(pos, 5, 5)
            p.setPen(QColor(self.canvas.name_colors.get(slot, "#00c6ed" if active else "#f0f0f2")))
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
        self.setMinimumSize(900, 540)
        if parent:
            self.resize(parent.size())
            self.move(parent.mapToGlobal(QPoint(0, 0)))
        else:
            self.resize(1100, 790)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 28)
        layout.addWidget(BackArrow(self.reject), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(32)
        self.default_name = macro_name
        self.name_edit = QLineEdit(macro_name)
        self.name_edit.setMaxLength(100)
        self.name_edit.setAccessibleName('Nombre de la macro')
        self.name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_edit.setStyleSheet('QLineEdit {font-size:24px; font-weight:600; color:white; background:transparent; border:none; border-bottom:1px solid #555; padding:8px;} QLineEdit:focus {border-bottom:1px solid #00afd7;}')
        self.name_edit.setMaximumWidth(560)
        layout.addWidget(self.name_edit, 0, Qt.AlignmentFlag.AlignHCenter)
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

    @property
    def macro_name(self):
        return self.name_edit.text().strip() or self.default_name

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
        if device.kind == 'keyboard':
            from .keyboard_support import FUNCTION_KEYS
            if slot in FUNCTION_KEYS:
                self.trigger = {'type': 'key', 'vk': FUNCTION_KEYS[slot], 'mods': []}
                self.save_button.setEnabled(True)
                self.hint.setText(slot + ' de este teclado está lista. Guarda la asignación; su función original también permanece activa.')
            else:
                self.hint.setText('Solo se permite asignar macros a F1–F12.')

    def observe(self, handle, event):
        from .safety import protected_trigger
        if protected_trigger(event):
            # Keep an already identified safe button while clicking Save/Cancel.
            # The primary click must never become the trigger itself.
            if self.trigger is None:
                self.pending_trigger = None
                self.save_button.setEnabled(False)
                self.hint.setText("Clic izquierdo y derecho protegidos. Pulsa otro botón del ratón.")
            return
        g = self.owner.g502
        if self.require_g:
            if not g or handle != g.handle or event["type"] != "gbutton":
                return
        elif handle not in self.device.handles or event["type"] not in ("key", "mouse"):
            return
        if self.device.kind == 'keyboard':
            from .keyboard_support import FUNCTION_KEYS
            if event.get('type') != 'key' or event.get('vk') != FUNCTION_KEYS.get(self.slot):
                return
            # F1–F12 have known virtual-key codes. Keep the selected key and
            # unmodified trigger; Save does not require physical calibration.
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
