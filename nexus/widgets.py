from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

ACCENT = "#68e2c4"

STYLE = """
QWidget { background: #12151c; color: #e9eef6; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background: #12151c; }
QLabel { background: transparent; }
QLabel#muted { color: #8b96a9; }
QLabel#eyebrow { color: #68e2c4; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { font-size: 32px; font-weight: 700; }
QLabel#sectionTitle { font-size: 20px; font-weight: 600; }
QFrame#header { background: #171b24; border-bottom: 1px solid #29303d; }
QFrame#rail { background: #171b24; border-right: 1px solid #29303d; }
QFrame#panel { background: #1b202b; border: 1px solid #2c3443; border-radius: 12px; }
QFrame#deviceCard { background: #1b202b; border: 1px solid #30394a; border-radius: 14px; }
QFrame#deviceCard:hover { border: 1px solid #68e2c4; background: #202734; }
QPushButton { background: #272f3e; border: 1px solid #374357; border-radius: 7px; padding: 9px 15px; font-weight: 600; }
QPushButton:hover { background: #344057; border-color: #63738c; }
QPushButton:pressed { background: #3d4c64; }
QPushButton:disabled { color: #596477; background: #1e2530; border-color: #293140; }
QPushButton#primary { background: #68e2c4; color: #10251f; border: none; }
QPushButton#primary:hover { background: #94f3dc; }
QPushButton#danger { color: #ffb0b8; background: #39252d; border-color: #67404c; }
QPushButton#nav { background: transparent; color: #8390a6; border: none; padding: 14px 2px; font-size: 11px; }
QPushButton#nav:checked { color: #68e2c4; background: #223730; border-left: 3px solid #68e2c4; border-radius: 0; }
QPushButton#link { background: transparent; border: none; padding: 7px; color: #aab9cf; }
QLineEdit, QComboBox, QSpinBox { background: #121823; border: 1px solid #374357; border-radius: 6px; padding: 7px 10px; selection-background-color: #3a6f68; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #68e2c4; }
QSpinBox { padding: 4px 6px; min-height: 20px; }
QSpinBox QLineEdit { padding: 0; border: none; background: transparent; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #202936; selection-background-color: #345249; }
QTabWidget::pane { border: none; border-top: 1px solid #30394a; }
QTabBar::tab { color: #929fb3; background: transparent; padding: 14px 20px; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #68e2c4; border-bottom: 2px solid #68e2c4; }
QTabBar::tab:hover { color: #e9eef6; }
QListWidget { background: #171d27; border: 1px solid #30394a; border-radius: 8px; outline: none; padding: 5px; }
QListWidget::item { padding: 12px 10px; border-radius: 5px; }
QListWidget::item:selected { background: #2a4540; color: #91f0d8; }
QTableWidget { background: #161c26; alternate-background-color: #1b2330; border: 1px solid #30394a; border-radius: 8px; gridline-color: #293242; outline: none; selection-background-color: #304c47; }
QHeaderView::section { background: #242d3b; color: #9eacc0; border: none; padding: 10px; font-size: 11px; font-weight: 600; }
QTableWidget::item { padding: 7px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: #141a24; margin: 1px; }
QScrollBar::handle:vertical { background: #3d4a5d; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #63718a; border-radius: 4px; background: #1c2531; }
QCheckBox::indicator:checked { background: #68e2c4; border: 3px solid #264c41; }
QSlider::groove:horizontal { background: #354153; height: 5px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #68e2c4; }
QSlider::handle:horizontal { background: #e1fff7; width: 16px; margin: -6px 0; border-radius: 8px; }
QStatusBar { background: #171b24; color: #9aa9bd; border-top: 1px solid #29303d; }
QDialog { background: #1b202b; }
QToolTip { background: #29384a; border: 1px solid #496078; color: white; padding: 6px; }
"""


def label(text: str, name: str = "", wrap=False) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback=None, primary=False, danger=False) -> QPushButton:
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setObjectName("primary")
    if danger:
        widget.setObjectName("danger")
    if callback:
        widget.clicked.connect(callback)
    return widget


class DeviceArt(QWidget):
    def __init__(self, kind="mouse", color=ACCENT, parent=None):
        super().__init__(parent)
        self.kind, self.color = kind, color
        self.setMinimumSize(200, 170)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width() / 340, self.height() / 270)
        p.scale(scale, scale)
        color = QColor(self.color)
        glow = QRadialGradient(0, 20, 140)
        glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 35))
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-155, -120, 310, 255))
        if self.kind == "mouse":
            self._mouse(p, color)
        else:
            self._keyboard(p, color)
        p.end()

    def _mouse(self, p, color):
        p.rotate(-14)
        p.setPen(QPen(QColor("#2e3c50"), 3))
        p.setBrush(QColor("#0b1018"))
        body = QPainterPath(QPointF(0, -111))
        body.cubicTo(-65, -111, -69, -65, -73, 6)
        body.cubicTo(-84, 81, -49, 118, 0, 119)
        body.cubicTo(58, 119, 82, 72, 71, 1)
        body.cubicTo(66, -68, 62, -111, 0, -111)
        gradient = QLinearGradient(-70, 0, 70, 30)
        gradient.setColorAt(0, QColor("#1e293a"))
        gradient.setColorAt(.55, QColor("#303c4e"))
        gradient.setColorAt(1, QColor("#101722"))
        p.setBrush(gradient)
        p.drawPath(body)
        p.setPen(QPen(QColor("#0c121c"), 3))
        p.drawLine(0, -108, 0, -23)
        p.drawLine(-66, -21, -5, -15)
        p.drawLine(5, -15, 67, -21)
        p.setPen(QPen(color, 2.5))
        p.drawLine(-68, 17, -59, 68)
        p.drawLine(66, 21, 58, 68)
        p.setPen(QPen(QColor("#080e18"), 2))
        p.setBrush(QColor("#080e18"))
        p.drawRoundedRect(QRectF(-9, -85, 18, 37), 7, 7)
        p.setPen(QPen(color, 1.2))
        for y in range(-79, -49, 5):
            p.drawLine(-5, y, 5, y)
        p.setBrush(QColor("#141e2b"))
        p.setPen(QPen(QColor("#496079"), 1))
        p.drawRoundedRect(QRectF(-75, -4, 10, 23), 3, 3)
        p.drawRoundedRect(QRectF(-75, 23, 10, 23), 3, 3)
        p.setPen(QPen(color, 3))
        path = QPainterPath(QPointF(-13, 48))
        path.lineTo(0, 35)
        path.lineTo(13, 48)
        path.moveTo(-13, 65)
        path.lineTo(0, 52)
        path.lineTo(13, 65)
        p.drawPath(path)

    def _keyboard(self, p, color):
        p.rotate(-9)
        p.setPen(QPen(QColor("#384b62"), 2))
        gradient = QLinearGradient(0, -70, 0, 80)
        gradient.setColorAt(0, QColor("#29364a"))
        gradient.setColorAt(1, QColor("#0e1520"))
        p.setBrush(gradient)
        p.drawRoundedRect(QRectF(-153, -72, 306, 148), 10, 10)
        p.setPen(QPen(color, 2))
        p.drawLine(-140, 77, 140, 77)
        for row in range(5):
            for col in range(14):
                if row == 4 and 3 <= col <= 8:
                    if col == 3:
                        rect = QRectF(-143 + col * 20, -61 + row * 26, 116, 21)
                    else:
                        continue
                else:
                    rect = QRectF(-143 + col * 20, -61 + row * 26, 17, 21)
                tint = QColor.fromHsv((color.hue() + col * 5 + row * 8) % 360, 115, 185)
                p.setPen(QPen(QColor("#405168"), .7))
                p.setBrush(QColor("#101a28"))
                p.drawRoundedRect(rect, 2, 2)
                p.setPen(QPen(tint, 1))
                p.drawLine(QPointF(rect.left() + 4, rect.bottom() - 3), QPointF(rect.right() - 4, rect.bottom() - 3))


class DeviceCard(QFrame):
    selected = Signal(object)

    def __init__(self, device):
        super().__init__()
        self.device = device
        self.setObjectName("deviceCard")
        self.setMinimumWidth(250)
        self.setMaximumWidth(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        top = QHBoxLayout()
        top.addWidget(label("●  CONECTADO", "eyebrow"))
        top.addStretch()
        top.addWidget(label("USB / HID" if device.vid else "RAW INPUT", "muted"))
        layout.addLayout(top)
        art = DeviceArt(device.kind, "#68e2c4" if device.kind == "mouse" else "#a7a1ff")
        art.setMinimumHeight(225)
        layout.addWidget(art)
        layout.addWidget(label("RATÓN" if device.kind == "mouse" else "TECLADO", "muted"))
        name = label(device.name, "sectionTitle", True)
        name.setMinimumHeight(58)
        layout.addWidget(name)
        layout.addWidget(label(f"{device.manufacturer}  ·  {device.vid or '—'}:{device.pid or '—'}", "muted"))
        layout.addSpacing(14)
        layout.addWidget(button("CONFIGURAR   →", lambda: self.selected.emit(device), True))

    def mouseDoubleClickEvent(self, event):
        self.selected.emit(self.device)
        super().mouseDoubleClickEvent(event)
