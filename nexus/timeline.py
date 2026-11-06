"""Draggable action and delay blocks for the macro editor."""
import copy
import json

from PySide6.QtCore import Qt, Signal, QMimeData, QPointF, QRectF, QRect, QSize
from PySide6.QtGui import QDrag, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget, QApplication, QInputDialog, QLayout

MIME = "application/x-logigian-timeline"


def editor_events(events, standard=None, trim_leading=False):
    """Represent timing as separate rows; never invent a leading/trailing gap."""
    result = []
    for event in events:
        event = copy.deepcopy(event)
        if event['type'] == 'wait':
            if standard is not None:
                event['delay_ms'] = standard
            result.append(event)
            continue
        delay = event.get('delay_ms', 0)
        if result and result[-1]['type'] != 'wait':
            delay = standard if standard is not None else delay
            if delay:
                result.append(dict(type='wait', delay_ms=delay))
        elif result and delay and standard is None:
            result.append(dict(type='wait', delay_ms=delay))
        event['delay_ms'] = delay if not result and standard is None and not trim_leading else 0
        if event['type'] == 'text' and standard is not None:
            event['char_delay_ms'] = standard
        result.append(event)
    return result


def timeline_tokens(events):
    tokens = []
    for row, event in enumerate(events):
        if event['type'] == 'wait':
            tokens.append((row, 'delay', copy.deepcopy(event)))
        else:
            if row and event.get('delay_ms', 0):
                tokens.append((row, 'delay', {'type': 'wait', 'delay_ms': event['delay_ms']}))
            action = copy.deepcopy(event)
            action['delay_ms'] = 0
            tokens.append((row, 'action', action))
    return tokens


def reorder_tokens(events, source, destination):
    tokens = timeline_tokens(events)
    token = tokens.pop(source)
    tokens.insert(destination - (destination > source), token)
    return [entry[2] for entry in tokens]


class FlowLayout(QLayout):
    """Left-to-right rows with height determined by the viewport width."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(8, 16, 8, 16)
        self.setSpacing(12)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), True)

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, False)

    def arrange(self, rect, measure):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self.items:
            size = item.sizeHint()
            if line_height and x + size.width() > area.right() + 1:
                x = area.x()
                y += line_height + self.spacing()
                line_height = 0
            if not measure:
                item.setGeometry(QRect(x, y, size.width(), size.height()))
            x += size.width() + self.spacing()
            line_height = max(line_height, size.height())
        return y + line_height - rect.y() + margins.bottom()


class TimelineBlock(QWidget):
    selected = Signal(int)
    delay_changed = Signal(int, int)
    delete_requested = Signal(int)

    def __init__(self, index, row, text, color, delay=None, down=None, draggable=True):
        super().__init__()
        self.index, self.row, self.text, self.color = index, row, text, color
        self.delay, self.down, self.draggable = delay, down, draggable
        self.origin = None
        self.is_selected = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(66 if delay is not None else max(48, self.fontMetrics().horizontalAdvance(text) + 26), 72)
        self.setCursor(Qt.CursorShape.OpenHandCursor if draggable else Qt.CursorShape.PointingHandCursor)
        self.setToolTip('Arrastra para mover. Doble clic para editar los milisegundos.' if delay is not None else 'Arrastra para mover. Clic para seleccionar el paso.')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.is_selected:
            p.setPen(QPen(QColor('#00c7f1'), 2))
            p.setBrush(QColor(0, 199, 241, 45))
            p.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), 5, 5)
        p.setPen(QColor('white'))
        font = p.font(); font.setBold(True); p.setFont(font)
        if self.delay is not None:
            p.drawText(QRectF(0, 11, self.width(), 27), Qt.AlignmentFlag.AlignCenter, str(self.delay))
            p.setPen(QPen(QColor('#b8b8be'), 1))
            p.drawLine(12, 39, self.width() - 12, 39)
            font.setBold(False); font.setPointSize(9); p.setFont(font)
            p.drawText(QRectF(0, 40, self.width(), 22), Qt.AlignmentFlag.AlignCenter, 'ms')
        else:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self.color).lighter(150) if self.is_selected else QColor(self.color))
            p.drawRoundedRect(QRectF(0, 18, self.width(), 36), 4, 4)
            p.setPen(QColor('white'))
            p.drawText(QRectF(5, 18, self.width() - 10, 36), Qt.AlignmentFlag.AlignCenter, self.text)
            if self.down is not None:
                x = self.width() / 2
                points = [(x-7, 60), (x+7, 60), (x, 67)] if self.down else [(x-7, 12), (x+7, 12), (x, 5)]
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('white'))
                p.drawPolygon(QPolygonF([QPointF(*point) for point in points]))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.origin = event.position().toPoint()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit(self.row)
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        if self.draggable and self.origin is not None and (event.position().toPoint() - self.origin).manhattanLength() >= QApplication.startDragDistance():
            self.origin = None
            drag = QDrag(self); mime = QMimeData()
            mime.setData(MIME, json.dumps(self.index).encode())
            drag.setMimeData(mime); drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            self.selected.emit(self.row)
        self.origin = None

    def mouseDoubleClickEvent(self, event):
        self.origin = None
        if self.delay is not None:
            value, ok = QInputDialog.getInt(self, 'Retardo', 'Milisegundos', self.delay, 0, 60000)
            if ok:
                self.delay_changed.emit(self.row, value)


class TimelineTrack(QWidget):
    moved = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.insertion = None

    def insertion_at(self, x, y):
        blocks = [self.layout().itemAt(i).widget() for i in range(self.layout().count())]
        blocks = [block for block in blocks if isinstance(block, TimelineBlock)]
        if not blocks:
            return 0, QRect(8, 16, 2, 72)
        # Select the nearest visual row, then an insertion point within it.
        nearest = min(blocks, key=lambda block: abs(block.geometry().center().y() - y))
        row = [block for block in blocks if block.y() == nearest.y()]
        for block in row:
            if x < block.geometry().center().x():
                return block.index, QRect(block.x() - 6, block.y(), 2, block.height())
        last = row[-1]
        return last.index + 1, QRect(last.geometry().right() + 6, last.y(), 2, last.height())

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            _, self.insertion = self.insertion_at(event.position().x(), event.position().y())
            self.update(); event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.insertion = None; self.update()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            destination, _ = self.insertion_at(event.position().x(), event.position().y())
            self.insertion = None; self.update()
            self.moved.emit(int(bytes(event.mimeData().data(MIME))), destination)
            event.acceptProposedAction()

    def paintEvent(self, event):
        if self.insertion is not None:
            p = QPainter(self); p.setPen(QPen(QColor('#00b7ed'), 2))
            p.drawLine(self.insertion.topLeft(), self.insertion.bottomLeft()); p.end()
