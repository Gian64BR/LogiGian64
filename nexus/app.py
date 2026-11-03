from __future__ import annotations

import copy
import ctypes as C
from ctypes import wintypes as W
import json
import logging
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, QObject, Signal, QAbstractNativeEventFilter, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap, QPainter, QFont, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea, QComboBox, QTabWidget,
    QListWidget, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpinBox, QCheckBox, QInputDialog, QMessageBox, QFileDialog, QDialog, QColorDialog,
    QSlider, QSystemTrayIcon, QMenu, QSplitter)

from .core import Store, new_id, new_profile, validate_profile, validate_events, validate_macro, held_after, MODES, MAX_EVENTS
from .macro_engine import MacroEngine
from . import windows as win
from .widgets import STYLE, ACCENT, DeviceArt, DeviceCard, label, button
from .dialogs import AddActionDialog, BindingDialog


class Events(QObject):
    input = Signal(object, object)
    changed = Signal()
    finished = Signal(str)
    error = Signal(str)
    plugin_error = Signal(str)


class NativeInput(QAbstractNativeEventFilter):
    def __init__(self, events):
        super().__init__()
        self.events = events
        self.last_error = ""

    def nativeEventFilter(self, event_type, message):
        try:
            msg = W.MSG.from_address(int(message))
            if msg.message == 0xFF:
                data = win.read_input(msg.lParam)
                if data:
                    handle, events = data
                    for event in events:
                        self.events.input.emit(handle, event)
            elif msg.message == 0xFE:
                self.events.changed.emit()
        except Exception as error:
            logging.exception("Raw Input")
            if str(error) != self.last_error:
                self.last_error = str(error)
                self.events.error.emit("Entrada de Windows: " + str(error))
        return False, 0


def panel():
    frame = QFrame()
    frame.setObjectName("panel")
    return frame


def app_icon():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return QIcon(str(root / "assets" / "logigian64.ico"))


class MainWindow(QMainWindow):
    def __init__(self, store=None):
        super().__init__()
        self.setWindowTitle("LogiGian64 — Peripheral Studio")
        self.resize(1300, 900)
        self.setMinimumSize(1100, 790)
        self.setWindowIcon(app_icon())
        self.store = store or Store()
        self.events = Events()
        self.player = MacroEngine(win.send_event, self.events.finished.emit)
        self.events.finished.connect(self.playback_finished)
        self.events.error.connect(self.status)
        self.events.input.connect(self.on_input)
        self.events.changed.connect(self.schedule_refresh)
        self.events.plugin_error.connect(self.g502_error)
        self.g502 = None
        self.learning = None
        self.devices = []
        self.device = None
        self.macro_id = None
        self.draft = []
        self.recording = False
        self.record_held = {}
        self.physical_held = set()
        self.last_record_time = 0
        self.record_start = 0
        self._loading = False
        self._closing = False
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh_devices)
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(250)
        self.record_timer.timeout.connect(self.record_tick)
        self.build_ui()
        self.refresh_profiles()
        self.refresh_devices()
        self.native = NativeInput(self.events)
        QApplication.instance().installNativeEventFilter(self.native)
        try:
            win.register_input(int(self.winId()))
            self.input_ready = True
        except OSError as error:
            self.input_ready = False
            self.status("No se pudo activar la entrada: " + str(error))
        self.build_tray()
        if self.store.warning:
            QTimer.singleShot(400, lambda: self.error(self.store.warning))

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(84)
        top = QHBoxLayout(header)
        top.setContentsMargins(27, 16, 28, 16)
        logo = label("G")
        logo.setStyleSheet("font-size:24px; font-weight:800; letter-spacing:2px")
        top.addWidget(logo)
        top.addSpacing(24)
        top.addWidget(label("PERIPHERAL STUDIO", "muted"))
        top.addStretch()
        top.addWidget(label("PERFIL ACTIVO", "muted"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed)
        top.addWidget(self.profile_combo)
        top.addWidget(button("+", self.add_profile))
        self.armed = QCheckBox("Asignaciones activas")
        self.armed.setChecked(True)
        self.armed.toggled.connect(self.armed_changed)
        top.addSpacing(15)
        top.addWidget(self.armed)
        outer.addWidget(header)
        row = QHBoxLayout()
        row.setSpacing(0)
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(88)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 20, 0, 16)
        self.nav_buttons = []
        for text, callback in (("⌂\n\nEQUIPO", self.go_home), ("◇\n\nPERFILES", self.go_profiles), ("?\n\nAYUDA", self.go_help)):
            nav = button(text, callback)
            nav.setObjectName("nav")
            nav.setCheckable(True)
            rail_layout.addWidget(nav)
            self.nav_buttons.append(nav)
        rail_layout.addStretch()
        rail_layout.addWidget(label("  0.1\n\n  LOCAL", "muted"))
        row.addWidget(rail)
        self.stack = QStackedWidget()
        row.addWidget(self.stack, 1)
        outer.addLayout(row, 1)
        self.build_home()
        self.build_detail()
        self.build_profiles()
        self.build_help()
        self.select_nav(0)
        self.statusBar().showMessage("Listo · F8 finaliza grabación · F9 detiene macros · Los datos se guardan localmente")

    def build_home(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 24)
        layout.setSpacing(17)
        heading = QHBoxLayout()
        text = QVBoxLayout()
        text.addWidget(label("TU ESPACIO DE CONTROL", "eyebrow"))
        text.addWidget(label("Tu equipo. Tus reglas.", "title"))
        text.addWidget(label("Selecciona un periférico para configurar sus macros y asignaciones.", "muted"))
        heading.addLayout(text)
        heading.addStretch()
        heading.addWidget(button("↻  Detectar dispositivos", self.refresh_devices))
        layout.addLayout(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards_widget = QWidget()
        self.cards = QGridLayout(self.cards_widget)
        self.cards.setContentsMargins(0, 10, 0, 10)
        self.cards.setSpacing(20)
        for column in range(3):
            self.cards.setColumnStretch(column, 1)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll, 1)
        note = panel()
        nl = QHBoxLayout(note)
        nl.setContentsMargins(20, 15, 20, 15)
        nl.addWidget(label("●", "eyebrow"))
        nl.addWidget(label("MACROS EN TU PC", "eyebrow"))
        nl.addWidget(label("Sin cuenta. Sin nube. Los perfiles permanecen en este equipo.", "muted", True), 1)
        self.device_count = label("", "muted")
        nl.addWidget(self.device_count)
        layout.addWidget(note)
        self.stack.addWidget(page)

    def build_detail(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 14, 32, 12)
        layout.setSpacing(8)
        back = button("←  Todos los periféricos", self.go_home)
        back.setObjectName("link")
        layout.addWidget(back, 0, Qt.AlignmentFlag.AlignLeft)
        hero = QHBoxLayout()
        self.hero_art = DeviceArt()
        self.hero_art.setFixedSize(230, 177)
        hero.addWidget(self.hero_art)
        info = QVBoxLayout()
        self.device_type = label("PERIFÉRICO", "eyebrow")
        self.device_title = label("", "title", True)
        self.device_meta = label("", "muted", True)
        info.addWidget(self.device_type)
        info.addWidget(self.device_title)
        info.addWidget(self.device_meta)
        hero.addLayout(info, 1)
        connection = QVBoxLayout()
        self.connection_label = label("●  CONECTADO", "eyebrow")
        connection.addWidget(self.connection_label)
        connection.addWidget(label("Motor de macros de Windows\nPerfil en el equipo", "muted"))
        hero.addLayout(connection)
        layout.addLayout(hero)
        self.tabs = QTabWidget()
        self.build_assignments()
        self.build_macros()
        self.build_lighting()
        self.build_sensitivity()
        layout.addWidget(self.tabs, 1)
        self.stack.addWidget(page)

    def build_assignments(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.addWidget(label("Asigna una acción a tu periférico", "sectionTitle"))
        layout.addWidget(label("Las macros se ejecutan en el PC mientras LogiGian64 está abierto. El activador conserva su acción original.", "muted", True))
        row = QHBoxLayout()
        row.addWidget(button("+  Asignar macro", self.add_binding, True))
        row.addWidget(button("Crear una macro", lambda: self.tabs.setCurrentIndex(1)))
        row.addStretch()
        row.addWidget(button("Quitar asignación", self.remove_binding))
        layout.addLayout(row)
        self.binding_list = QListWidget()
        layout.addWidget(self.binding_list, 1)
        self.binding_hint = label("", "muted", True)
        layout.addWidget(self.binding_hint)
        self.tabs.addTab(page, "ASIGNACIONES")

    def build_macros(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        split = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 15, 0)
        ll.addWidget(label("BIBLIOTECA DE MACROS", "eyebrow"))
        ll.addWidget(button("+  Nueva macro", self.new_macro, True))
        self.macro_list = QListWidget()
        self.macro_list.currentRowChanged.connect(self.macro_selected)
        ll.addWidget(self.macro_list, 1)
        ll.addWidget(button("Duplicar", self.duplicate_macro))
        ll.addWidget(button("Eliminar macro", self.delete_macro))
        split.addWidget(left)
        self.editor = QWidget()
        el = QVBoxLayout(self.editor)
        el.setContentsMargins(3, 0, 0, 0)
        title_row = QHBoxLayout()
        self.macro_name = QLineEdit()
        self.macro_name.setPlaceholderText("Nombre de la macro")
        title_row.addWidget(self.macro_name, 1)
        title_row.addWidget(button("Guardar", self.save_macro, True))
        el.addLayout(title_row)
        actions = QHBoxLayout()
        self.record_button = button("●  Grabar", self.toggle_record)
        actions.addWidget(self.record_button)
        self.record_mouse = QCheckBox("Incluir clics")
        actions.addWidget(self.record_mouse)
        actions.addStretch()
        actions.addWidget(button("+ Acción", self.add_action))
        actions.addWidget(button("− Paso", self.remove_step))
        actions.addWidget(button("↑", lambda: self.move_step(-1)))
        actions.addWidget(button("↓", lambda: self.move_step(1)))
        el.addLayout(actions)
        self.record_label = label("Graba teclas de cualquier teclado. F8 termina la grabación.", "muted", True)
        el.addWidget(self.record_label)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "ACCIÓN", "ENTRADA", "ESPERA · MS"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 105)
        self.table.setColumnWidth(3, 125)
        el.addWidget(self.table, 1)
        playback = QHBoxLayout()
        playback.addWidget(label("Repeticiones", "muted"))
        self.repeats = QSpinBox()
        self.repeats.setRange(1, 100)
        playback.addWidget(self.repeats)
        self.sequence_stats = label("0 pasos", "muted")
        playback.addWidget(self.sequence_stats)
        playback.addStretch()
        playback.addWidget(button("■  Detener · F9", self.stop_all, danger=True))
        playback.addWidget(button("▶  Probar en 3 s", self.play_current, True))
        el.addLayout(playback)
        split.addWidget(self.editor)
        split.setSizes([225, 780])
        layout.addWidget(split, 1)
        self.tabs.addTab(page, "MACROS")

    def build_lighting(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 23, 6, 15)
        layout.addWidget(label("Iluminación", "sectionTitle"))
        layout.addWidget(label("VISTA PREVIA DEL PERFIL", "eyebrow"))
        layout.addWidget(label("Elige un color para identificar este periférico en LogiGian64. Se guarda en el perfil y actualiza la ilustración.", "muted", True))
        layout.addWidget(button("Elegir color de vista previa", self.choose_color), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        notice = panel()
        nl = QVBoxLayout(notice)
        nl.setContentsMargins(22, 20, 22, 20)
        nl.addWidget(label("Control RGB del hardware: sin plugin", "sectionTitle"))
        nl.addWidget(label("Esta versión no envía colores al dispositivo. El control RGB real requiere un adaptador verificado "
            "para el modelo y su protocolo. Los ajustes de G HUB y del firmware permanecen bajo su control.", "muted", True))
        layout.addWidget(notice)
        self.tabs.addTab(page, "ILUMINACIÓN")

    def build_sensitivity(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 23, 6, 15)
        layout.addWidget(label("Sensibilidad y dispositivo", "sectionTitle"))
        layout.addWidget(label("DPI del sensor y frecuencia de sondeo: sin plugin de hardware", "muted", True))
        layout.addSpacing(16)
        box = panel()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(22, 20, 22, 20)
        bl.addWidget(label("Velocidad del puntero de Windows", "sectionTitle"))
        bl.addWidget(label("Ajuste global para todos los ratones del equipo. No cambia el DPI del sensor.", "muted", True))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_value = label("10 / 20", "eyebrow")
        self.speed_slider.valueChanged.connect(lambda n: self.speed_value.setText(f"{n} / 20"))
        bl.addWidget(self.speed_slider)
        bl.addWidget(self.speed_value)
        bl.addWidget(button("Aplicar a Windows", self.apply_speed), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(box)
        layout.addStretch()
        self.hardware_info = label("", "muted", True)
        self.hardware_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.hardware_info)
        self.tabs.addTab(page, "SENSIBILIDAD")

    def build_profiles(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.addWidget(label("TU BIBLIOTECA LOCAL", "eyebrow"))
        layout.addWidget(label("Perfiles", "title"))
        layout.addWidget(label("Cada perfil reúne macros, activadores por periférico y colores de vista previa. La selección es manual.", "muted", True))
        self.profile_list = QListWidget()
        self.profile_list.itemDoubleClicked.connect(lambda: self.activate_profile())
        layout.addWidget(self.profile_list, 1)
        actions = QHBoxLayout()
        for text, callback, primary in (("+ Nuevo", self.add_profile, True), ("Activar", self.activate_profile, False),
            ("Renombrar", self.rename_profile, False), ("Duplicar", self.duplicate_profile, False),
            ("Importar JSON", self.import_profile, False), ("Exportar JSON", self.export_profile, False),
            ("Eliminar", self.delete_profile, False)):
            actions.addWidget(button(text, callback, primary))
        layout.addLayout(actions)
        self.stack.addWidget(page)

    def build_help(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 30)
        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(96, 96))
        layout.addWidget(logo)
        layout.addWidget(label("LogiGian64 / 0.2", "eyebrow"))
        layout.addWidget(label("Del periférico a la acción.", "title"))
        text = label("1. Selecciona tu periférico en EQUIPO.\n\n"
            "2. Abre MACROS, crea una y añade acciones o pulsa Grabar. Cambia a la aplicación que quieras y usa F8 para terminar. "
            "No se graban movimientos del puntero.\n\n"
            "3. Guarda la macro. En ASIGNACIONES elige el botón o tecla que la ejecutará desde ese periférico. "
            "El activador mantiene su acción original; LogiGian64 añade la macro cuando lo sueltas.\n\n"
            "4. Para probar manualmente, pulsa Probar en 3 s y cambia a una ventana de texto. F9 cancela en cualquier momento. "
            "Windows puede bloquear la entrada a aplicaciones con más privilegios.\n\n"
            "5. Mantén LogiGian64 abierto o minimízalo a la bandeja. Cerrar la aplicación detiene las macros. "
            "Los perfiles se guardan localmente y se pueden exportar en JSON.\n\n"
            "COMPATIBILIDAD\n"
            "Detección y macros: dispositivos de entrada que Windows expone por Raw Input. DPI, RGB, polling y memoria integrada: "
            "requieren plugins por modelo y no están implementados en esta versión. La selección de un periférico no implica soporte de firmware.\n\n"
            "Aplicación independiente, con código fuente incluido. No es un producto oficial de Logitech.", "muted", True)
        text.setStyleSheet("font-size:14px; line-height:1.4")
        layout.addWidget(text)
        layout.addStretch()
        layout.addWidget(button("Abrir carpeta de perfiles", self.open_data_folder), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(button("Minimizar a la bandeja", self.to_tray), 0, Qt.AlignmentFlag.AlignLeft)
        self.stack.addWidget(page)

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("LogiGian64 · Macros y perfiles")
        menu = QMenu()
        menu.addAction("Abrir LogiGian64", self.restore)
        menu.addAction("Detener y restaurar · Ctrl+Alt+F12", self.emergency_stop)
        menu.addAction("Activar / pausar asignaciones", lambda: self.armed.setChecked(not self.armed.isChecked()))
        menu.addSeparator()
        menu.addAction("Salir", self.exit_application)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def to_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.showMessage("LogiGian64", "Las asignaciones siguen activas. Doble clic en el icono para volver.")
        else:
            self.showMinimized()

    def restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def exit_application(self):
        self._exit_requested = True
        try:
            if self.close():
                QApplication.instance().quit()
        finally:
            self._exit_requested = False

    def status(self, text):
        self.statusBar().showMessage(text)

    def error(self, text):
        QMessageBox.warning(self, "LogiGian64", str(text))

    def persist(self):
        try:
            self.store.save()
            return True
        except (OSError, ValueError) as error:
            self.error("No se pudo guardar: " + str(error))
            return False

    def select_nav(self, index):
        for n, nav in enumerate(self.nav_buttons):
            nav.setChecked(n == index)

    def leave_editor(self):
        if self.recording:
            self.finish_recording()
        return self.commit_draft()

    def go_home(self):
        if self.leave_editor():
            self.stack.setCurrentIndex(0)
            self.select_nav(0)

    def go_profiles(self):
        if self.leave_editor():
            self.refresh_profiles()
            self.stack.setCurrentIndex(2)
            self.select_nav(1)

    def go_help(self):
        if self.leave_editor():
            self.stack.setCurrentIndex(3)
            self.select_nav(2)

    def schedule_refresh(self):
        self.refresh_timer.start(350)

    def refresh_devices(self):
        try:
            devices = win.enumerate_devices()
        except OSError as error:
            self.status("No se pudieron consultar los periféricos: " + str(error))
            return
        self.devices = devices
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for n, device in enumerate(devices):
            card = DeviceCard(device)
            card.selected.connect(self.open_device)
            self.cards.addWidget(card, n // 3, n % 3)
        if not devices:
            self.cards.addWidget(label("No se detectaron ratones o teclados. Conecta un periférico y pulsa Detectar dispositivos.", "muted", True), 0, 0)
        self.device_count.setText(f"{len(devices)} periférico{'s' if len(devices) != 1 else ''}")
        if self.device:
            current = next((d for d in devices if d.id == self.device.id), None)
            self.connection_label.setText("●  CONECTADO" if current else "○  DESCONECTADO")
            if current:
                self.device = current
            else:
                self.stop_all()
                if self.recording:
                    self.finish_recording()

    def open_device(self, device):
        if not self.leave_editor():
            return
        self.device = device
        self.device_title.setText(device.name)
        self.device_type.setText("RATÓN / CONTROL LOCAL" if device.kind == "mouse" else "TECLADO / CONTROL LOCAL")
        self.device_meta.setText(f"{device.manufacturer}   ·   VID {device.vid or '—'} / PID {device.pid or '—'}   ·   {len(device.paths)} interfaz(es) de entrada")
        self.connection_label.setText("●  CONECTADO")
        self.hero_art.kind = device.kind
        self.update_color()
        self.hardware_info.setText("INTERFACES DETECTADAS\n" + "\n".join(device.paths))
        try:
            self.speed_slider.setValue(win.pointer_speed())
        except OSError as error:
            self.status(str(error))
        self.speed_slider.setEnabled(device.kind == "mouse")
        if hasattr(self, "sensitivity_panel"):
            self.sensitivity_panel.load_device(device)
        self.refresh_macros()
        self.refresh_bindings()
        self.tabs.setCurrentIndex(0)
        self.stack.setCurrentIndex(1)
        self.select_nav(0)

    def refresh_profiles(self):
        self._loading = True
        self.profile_combo.clear()
        self.profile_list.clear()
        for profile in self.store.profiles:
            self.profile_combo.addItem(profile["name"], profile["id"])
            suffix = "   ● ACTIVO" if profile["id"] == self.store.active_id else ""
            self.profile_list.addItem(f"{profile['name']}{suffix}     ·     {len(profile['macros'])} macros")
        index = next(i for i, p in enumerate(self.store.profiles) if p["id"] == self.store.active_id)
        self.profile_combo.setCurrentIndex(index)
        self.profile_list.setCurrentRow(index)
        self._loading = False

    def profile_changed(self, index):
        if self._loading or index < 0:
            return
        if not self.leave_editor():
            self.refresh_profiles()
            return
        self.stop_all()
        self.store.active_id = self.profile_combo.itemData(index)
        self.persist()
        self.macro_id = None
        self.draft = []
        self.refresh_profiles()
        self.refresh_macros()
        self.refresh_bindings()
        self.update_color()
        self.status("Perfil activo: " + self.store.active["name"])

    def chosen_profile(self):
        row = self.profile_list.currentRow()
        return self.store.profiles[row] if 0 <= row < len(self.store.profiles) else self.store.active

    def add_profile(self):
        if not self.leave_editor():
            return
        if len(self.store.profiles) >= 100:
            return self.error("La biblioteca admite hasta 100 perfiles.")
        name, ok = QInputDialog.getText(self, "Nuevo perfil", "Nombre del perfil")
        if ok and name.strip():
            profile = new_profile(name.strip()[:100])
            self.store.profiles.append(profile)
            self.store.active_id = profile["id"]
            self.macro_id = None
            self.draft = []
            self.stop_all()
            self.persist()
            self.refresh_profiles()
            self.refresh_macros()
            self.refresh_bindings()

    def activate_profile(self):
        profile = self.chosen_profile()
        self.profile_combo.setCurrentIndex(next(i for i, p in enumerate(self.store.profiles) if p["id"] == profile["id"]))

    def rename_profile(self):
        profile = self.chosen_profile()
        name, ok = QInputDialog.getText(self, "Renombrar perfil", "Nombre", text=profile["name"])
        if ok and name.strip():
            profile["name"] = name.strip()[:100]
            self.persist()
            self.refresh_profiles()

    def duplicate_profile(self):
        if not self.leave_editor():
            return
        if len(self.store.profiles) >= 100:
            return self.error("La biblioteca admite hasta 100 perfiles.")
        profile = copy.deepcopy(self.chosen_profile())
        profile["id"] = new_id()
        profile["name"] = (profile["name"] + " · copia")[:100]
        self.store.profiles.append(profile)
        self.persist()
        self.refresh_profiles()

    def delete_profile(self):
        if len(self.store.profiles) == 1:
            return self.error("Debe existir al menos un perfil.")
        if not self.leave_editor():
            return
        profile = self.chosen_profile()
        if QMessageBox.question(self, "Eliminar perfil", f"¿Eliminar «{profile['name']}» y sus macros?") != QMessageBox.StandardButton.Yes:
            return
        self.store.profiles.remove(profile)
        if profile["id"] == self.store.active_id:
            self.stop_all()
            self.store.active_id = self.store.profiles[0]["id"]
            self.macro_id = None
            self.draft = []
        self.persist()
        self.refresh_profiles()
        self.refresh_macros()
        self.refresh_bindings()

    def import_profile(self):
        if not self.leave_editor():
            return
        if len(self.store.profiles) >= 100:
            return self.error("La biblioteca admite hasta 100 perfiles.")
        path, _ = QFileDialog.getOpenFileName(self, "Importar perfil", "", "Perfil LogiGian64 (*.json)")
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("El perfil supera los 8 MB.")
            data = json.loads(source.read_text(encoding="utf-8-sig"))
            profile = validate_profile(data.get("profile", data))
            profile["id"] = new_id()
            self.store.profiles.append(profile)
            self.persist()
            self.refresh_profiles()
            self.status("Perfil importado. Actívalo desde la biblioteca cuando quieras usarlo.")
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.error("No se pudo importar: " + str(error))

    def export_profile(self):
        if not self.leave_editor():
            return
        profile = self.chosen_profile()
        path, _ = QFileDialog.getSaveFileName(self, "Exportar perfil", "perfil-logigian64.json", "Perfil LogiGian64 (*.json)")
        if path:
            try:
                Path(path).write_text(json.dumps({"format": "nexus-profile", "version": 2, "profile": profile}, ensure_ascii=False, indent=2), encoding="utf-8")
                self.status("Perfil exportado: " + path)
            except OSError as error:
                self.error(error)

    def current_macro(self):
        return next((m for m in self.store.active["macros"] if m["id"] == self.macro_id), None)

    def refresh_macros(self, select_id=None):
        self._loading = True
        self.macro_list.clear()
        for macro in self.store.active["macros"]:
            self.macro_list.addItem(macro["name"])
        target = select_id or self.macro_id
        index = next((i for i, m in enumerate(self.store.active["macros"]) if m["id"] == target), 0)
        self.macro_list.setCurrentRow(index if self.store.active["macros"] else -1)
        self._loading = False
        self.load_macro(index)

    def macro_selected(self, row):
        if self._loading:
            return
        old = self.macro_id
        if self.recording:
            self.finish_recording()
        if not self.commit_draft():
            self._loading = True
            self.macro_list.setCurrentRow(next((i for i, m in enumerate(self.store.active["macros"]) if m["id"] == old), -1))
            self._loading = False
            return
        self.load_macro(row)

    def load_macro(self, row):
        macros = self.store.active["macros"]
        macro = macros[row] if 0 <= row < len(macros) else None
        self.macro_id = macro["id"] if macro else None
        self.macro_name.setText(macro["name"] if macro else "")
        self.draft = copy.deepcopy(macro["events"]) if macro else []
        self.repeats.setValue(macro.get("repeats", 1) if macro else 1)
        self.editor.setEnabled(macro is not None)
        self.render_events()

    def commit_draft(self):
        macro = self.current_macro()
        if macro is None:
            return True
        if self.recording:
            return False
        try:
            name = self.macro_name.text().strip()[:100]
            if not name:
                raise ValueError("La macro necesita un nombre.")
            events = validate_events(self.read_draft())
            if macro["name"] == name and macro["events"] == events and macro.get("repeats", 1) == self.repeats.value():
                return True
            previous = copy.deepcopy(macro)
            macro.update(name=name, events=events, repeats=self.repeats.value())
            if not self.persist():
                macro.clear()
                macro.update(previous)
                return False
            self._loading = True
            item = self.macro_list.item(self.macro_list.currentRow())
            if item:
                item.setText(name)
            self._loading = False
            self.refresh_bindings()
            return True
        except ValueError as error:
            self.error(error)
            return False

    def save_macro(self):
        if self.recording:
            self.finish_recording()
        if self.commit_draft():
            self.status("Macro guardada en el perfil «" + self.store.active["name"] + "»")

    def new_macro(self):
        if not self.leave_editor():
            return
        if len(self.store.active["macros"]) >= 200:
            return self.error("Un perfil admite hasta 200 macros.")
        name, ok = QInputDialog.getText(self, "Nueva macro", "Nombre de la macro", text="Mi macro")
        if ok and name.strip():
            macro = {"id": new_id(), "name": name.strip()[:100], "events": []}
            self.store.active["macros"].append(macro)
            self.persist()
            self.refresh_macros(macro["id"])
            self.tabs.setCurrentIndex(1)

    def duplicate_macro(self):
        if not self.leave_editor():
            return
        macro = self.current_macro()
        if not macro:
            return
        if len(self.store.active["macros"]) >= 200:
            return self.error("Un perfil admite hasta 200 macros.")
        clone = copy.deepcopy(macro)
        clone.update(id=new_id(), name=(macro["name"] + " · copia")[:100])
        self.store.active["macros"].append(clone)
        self.persist()
        self.refresh_macros(clone["id"])

    def delete_macro(self):
        macro = self.current_macro()
        if not macro or self.recording:
            return
        if QMessageBox.question(self, "Eliminar macro", f"¿Eliminar «{macro['name']}» y sus asignaciones?") != QMessageBox.StandardButton.Yes:
            return
        self.stop_all()
        self.store.active["macros"].remove(macro)
        self.store.active["bindings"] = [b for b in self.store.active["bindings"] if b["macro_id"] != self.macro_id]
        self.macro_id = None
        self.draft = []
        self.persist()
        self.refresh_macros()
        self.refresh_bindings()

    def read_draft(self):
        for row, event in enumerate(self.draft):
            spin = self.table.cellWidget(row, 3)
            if spin:
                event["delay_ms"] = spin.value()
        return self.draft

    def render_event(self, row, event):
        self.table.insertRow(row)
        kind = event["type"]
        action = {"wait": "Pausa", "wheel": "Rueda", "text": "Texto", "launch": "Aplicación"}.get(kind)
        if action is None:
            action = "Pulsar" if event["down"] else "Soltar"
        key = (win.key_name(event["vk"], event.get("scan", 0), event.get("extended", False)) if kind == "key"
               else win.MOUSE_LABELS[event["button"]] if kind == "mouse" else f"{event['delta']:+d}" if kind == "wheel"
               else event["text"][:70] if kind == "text" else Path(event["path"]).name if kind == "launch" else "—")
        for col, text in enumerate((str(row + 1), action, key)):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)
        spin = QSpinBox()
        spin.setRange(0, 60000)
        spin.setValue(event.get("delay_ms", 0))
        spin.valueChanged.connect(self.update_stats)
        self.table.setCellWidget(row, 3, spin)
        self.table.setRowHeight(row, 38)

    def render_events(self):
        self.table.setRowCount(0)
        for row, event in enumerate(self.draft):
            self.render_event(row, event)
        self.update_stats()

    def update_stats(self, *_):
        total = sum(self.table.cellWidget(row, 3).value() for row in range(self.table.rowCount()) if self.table.cellWidget(row, 3))
        self.sequence_stats.setText(f"{len(self.draft)} pasos · {total / 1000:.2f} s")

    def add_action(self):
        if self.recording:
            return
        dialog = AddActionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.read_draft()
            additions = dialog.events()
            if len(self.draft) + len(additions) > MAX_EVENTS:
                return self.error(f"Se permiten hasta {MAX_EVENTS} pasos.")
            self.draft.extend(additions)
            self.render_events()
            self.table.scrollToBottom()

    def remove_step(self):
        if self.recording:
            return
        self.read_draft()
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            del self.draft[row]
        self.render_events()

    def move_step(self, delta):
        if self.recording:
            return
        row = self.table.currentRow()
        if 0 <= row < len(self.draft) and 0 <= row + delta < len(self.draft):
            self.read_draft()
            self.draft[row], self.draft[row + delta] = self.draft[row + delta], self.draft[row]
            self.render_events()
            self.table.selectRow(row + delta)

    def toggle_record(self):
        if self.recording:
            self.finish_recording()
            return
        if not self.input_ready:
            return self.error("No está disponible la captura de entrada de Windows.")
        if not self.current_macro() or not self.commit_draft():
            return
        if self.draft and QMessageBox.question(self, "Grabar macro", "¿Reemplazar la secuencia actual con una nueva grabación?") != QMessageBox.StandardButton.Yes:
            return
        self.stop_all()
        self.draft = []
        self.record_held = {}
        self.render_events()
        self.recording = True
        self.record_start = self.last_record_time = time.monotonic()
        self.record_button.setText("■  Finalizar · F8")
        self.record_button.setObjectName("danger")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.record_timer.start()
        self.record_tick()

    def record_tick(self):
        if not self.recording:
            return
        elapsed = time.monotonic() - self.record_start
        self.record_label.setText(f"● GRABANDO · {elapsed:.0f} s · Cambia de aplicación. F8 para terminar; Ctrl+Alt+F12 detiene macros.")
        if elapsed >= 120 or len(self.draft) >= 2000:
            self.finish_recording()
            self.status("Grabación finalizada al alcanzar 2 minutos o 2000 entradas.")

    def capture_event(self, event):
        identity = None
        if event["type"] in ("key", "mouse"):
            identity = (event["type"], event.get("vk"), event.get("scan"), event.get("extended"), event.get("button"))
            if event["down"]:
                if identity in self.record_held:
                    return
                self.record_held[identity] = event.copy()
            else:
                if identity not in self.record_held:
                    return
                self.record_held.pop(identity)
        now = time.monotonic()
        event = {**event, "delay_ms": min(60000, max(0, round((now - self.last_record_time) * 1000)))}
        if not self.draft:
            event["delay_ms"] = 0
        self.last_record_time = now
        self.draft.append(event)
        self.render_event(len(self.draft) - 1, event)
        self.table.scrollToBottom()
        self.update_stats()
        if len(self.draft) >= 2000:
            self.finish_recording()

    def finish_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.record_timer.stop()
        self.physical_held.clear()
        for event in reversed(list(self.record_held.values())):
            self.draft.append({**event, "down": False, "delay_ms": 0})
        self.record_held.clear()
        self.record_button.setText("●  Grabar")
        self.record_button.setObjectName("")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.render_events()
        self.record_label.setText("Grabación finalizada. Revisa los pasos y pulsa Guardar.")
        self.status("Grabación finalizada · " + str(len(self.draft)) + " pasos")

    def play_current(self):
        if self.recording:
            self.finish_recording()
        if self.commit_draft() and self.current_macro():
            self.start_macro(self.current_macro(), self.repeats.value(), 3)

    def start_macro(self, macro, repeats=None, delay=0):
        try:
            normalized = validate_macro(macro)
            events = (sum((normalized["sections"][phase] for phase in ("press", "hold", "release")), [])
                      if normalized["mode"] == "sequence" else normalized["events"])
            if normalized["mode"] == "latch":
                from .core import latched_actions
                events = latched_actions(events)
            # Finite previews complete any intentionally held output at the end.
            from .core import event_identity
            outputs = {}
            for event in events:
                identity = event_identity(event)
                if identity:
                    if event["down"]:
                        outputs[identity] = event
                    else:
                        outputs.pop(identity, None)
            events += [{**event, "down": False, "delay_ms": 50} for event in reversed(list(outputs.values()))]
            self.player.start(events, 1 if repeats is None else repeats, delay)
            self.status(f"Prueba de «{macro['name']}» {'en 3 s; cambia al destino' if delay else 'en ejecución'} · Ctrl+Alt+F12 detiene")
        except ValueError as error:
            self.status(str(error))

    def stop_all(self):
        self.player.stop()
        self.status("Macros detenidas · Ctrl+Alt+F12")

    def emergency_stop(self):
        self.stop_all()
        self.physical_held.clear()
        self.armed.setChecked(False)
        if self.g502:
            self.g502.close()
            self.g502 = None
        self.status("Parada de emergencia · asignaciones pausadas y control directo restaurado")

    def g502_error(self, message):
        self.stop_all()
        self.status(message)
        self.error(message)

    def activate_g502(self):
        if not self.device or (self.device.vid, self.device.pid) != ("046D", "C08B"):
            return self.error("El control directo disponible corresponde al G502 HERO 046D:C08B.")
        if self.g502 and self.g502.thread and self.g502.thread.is_alive():
            self.stop_all()
            if self.g502.close():
                self.g502 = None
            return
        if self.g502 and self.g502.needs_restore and not self.g502.close():
            return
        from .g502 import G502Session, ghub_running, close_ghub
        try:
            if ghub_running():
                answer = QMessageBox.question(self, "Tomar control del G502",
                    "G HUB tiene el control del ratón. Para usar sus botones físicos, LogiGian64 debe cerrar la interfaz, la bandeja y el agente de G HUB.\n\n"
                    "Guarda cualquier edición pendiente en G HUB antes de continuar. No se modifican sus perfiles ni el servicio de actualización.\n\n"
                    "¿Cerrar G HUB y activar el control directo?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
                close_ghub()
        except (OSError, TimeoutError) as error:
            return self.error(error)
        self.g502 = G502Session(self.device, self.events.input.emit, self.events.error.emit, self.events.plugin_error.emit)
        buttons = {b["trigger"]["button"] for b in self.store.active["bindings"]
                   if b["device_id"] == self.device.id and b["trigger"]["type"] == "gbutton" and b["enabled"]}
        buttons |= {c["button"] for c in self.store.active.get("disabled_controls", [])
                    if self.armed.isChecked() and c["device_id"] == self.device.id and type(c["button"]) is int}
        self.g502.start(buttons if self.armed.isChecked() else set())
        self.status("Conectando con los botones físicos del G502…")

    def sync_g502(self):
        if self.g502 and self.g502.ready:
            self.g502.update_buttons({b["trigger"]["button"] for b in self.store.active["bindings"]
                if b["device_id"] == self.g502.device.id and b["trigger"]["type"] == "gbutton" and b["enabled"]})

    def armed_changed(self, armed):
        if not armed:
            self.stop_all()
        self.status("Asignaciones activas" if armed else "Asignaciones pausadas")

    def playback_finished(self, text):
        if not self._closing and not self.player.busy:
            self.status(text)

    def refresh_bindings(self):
        self.binding_list.clear()
        if not self.device:
            return
        macros = {m["id"]: m["name"] for m in self.store.active["macros"]}
        for binding in self.store.active["bindings"]:
            if binding["device_id"] != self.device.id:
                continue
            trigger = binding["trigger"]
            text = win.MOUSE_LABELS[trigger["button"]] if trigger["type"] == "mouse" else " + ".join(trigger["mods"] + [win.key_name(trigger["vk"])])
            self.binding_list.addItem(f"{text}     →     {macros.get(binding['macro_id'], 'Macro no disponible')}")
        self.binding_hint.setText("No hay asignaciones para este periférico en el perfil actual. Crea una macro y pulsa Asignar macro."
                                  if self.binding_list.count() == 0 else "Activas mientras LogiGian64 está abierto y «Asignaciones activas» está marcado. F9 detiene la reproducción.")

    def add_binding(self):
        if not self.leave_editor() or not self.device:
            return
        macros = [m for m in self.store.active["macros"] if m["events"]]
        if not macros:
            self.tabs.setCurrentIndex(1)
            return self.error("Crea y guarda una macro con acciones antes de asignarla.")
        dialog = BindingDialog(self.device, macros, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            binding = dialog.binding(self.device.id)
            bindings = self.store.active["bindings"]
            bindings[:] = [b for b in bindings if not (b["device_id"] == binding["device_id"] and b["trigger"] == binding["trigger"])]
            bindings.append(binding)
            self.persist()
            self.refresh_bindings()

    def remove_binding(self):
        if not self.device:
            return
        matches = [b for b in self.store.active["bindings"] if b["device_id"] == self.device.id]
        row = self.binding_list.currentRow()
        if 0 <= row < len(matches):
            self.store.active["bindings"].remove(matches[row])
            self.persist()
            self.refresh_bindings()

    def on_input(self, handle, event):
        if event["type"] == "key":
            vk = event["vk"]
            if event["down"] and vk == 123 and {"Ctrl", "Alt"}.issubset(win.modifiers()):
                self.emergency_stop()
                return
            if vk == 119 and self.recording:
                if event["down"]:
                    self.finish_recording()
                    self.restore()
                return
        if self.learning:
            self.learning.observe(handle, event)
            return
        if self.recording:
            if event["type"] == "gbutton":
                return
            if event["type"] != "key":
                if not self.record_mouse.isChecked():
                    return
                # Only the start/stop control is excluded, not the entire app.
                widget = QApplication.widgetAt(QCursor.pos())
                if widget and (widget is self.record_button or self.record_button.isAncestorOf(widget)):
                    return
            self.capture_event(event)
            return
        if event["type"] not in ("key", "mouse", "gbutton"):
            return
        device = (self.g502.device if self.g502 and handle == self.g502.handle else
                  next((d for d in self.devices if handle in d.handles), None))
        if not device:
            return
        identity = (device.id, event["type"], event.get("vk"), event.get("button"))
        if event["down"]:
            if identity in self.physical_held:
                return
            self.physical_held.add(identity)
        else:
            self.physical_held.discard(identity)
            # Releases are processed even while a macro runs, a tab changes, or
            # a different binding is selected. They belong to the pressed input.
            self.player.release(identity)
            return
        if not self.armed.isChecked() or self._closing:
            return
        for binding in self.store.active["bindings"]:
            if not binding["enabled"] or binding["device_id"] != device.id:
                continue
            trigger = binding["trigger"]
            match = trigger["type"] == event["type"]
            if match and event["type"] == "key":
                match = trigger["vk"] == event["vk"] and sorted(trigger["mods"]) == sorted(win.modifiers())
            elif match:
                match = trigger["button"] == event["button"]
            if match:
                macro = next((m for m in self.store.active["macros"] if m["id"] == binding["macro_id"]), None)
                if macro:
                    try:
                        self.player.press(identity, macro)
                        self.status(f"{macro['name']} · {MODES.get(macro.get('mode', 'once'))} · Ctrl+Alt+F12 detiene")
                    except ValueError as error:
                        self.status(str(error))
                break

    def choose_color(self):
        if not self.device:
            return
        color = QColorDialog.getColor(QColor(self.hero_art.color), self, "Color de vista previa")
        if color.isValid():
            self.store.active["colors"][self.device.id] = color.name()
            self.persist()
            self.update_color()
            self.status("Color de vista previa guardado. No se envió ningún comando RGB al periférico.")

    def update_color(self):
        if self.device:
            self.hero_art.color = self.store.active["colors"].get(self.device.id, ACCENT)
            self.hero_art.update()

    def apply_speed(self):
        try:
            win.set_pointer_speed(self.speed_slider.value())
            self.status("Velocidad global del puntero aplicada a Windows. El DPI del sensor no cambió.")
        except (OSError, ValueError) as error:
            self.error(error)

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.directory)))

    def closeEvent(self, event):
        if not getattr(self, "_exit_requested", False):
            event.ignore()
            self.to_tray()
            return
        if not self.leave_editor():
            result = QMessageBox.question(self, "Cambios sin guardar", "La secuencia no es válida. ¿Salir descartando los cambios sin guardar?")
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
        self.player.stop()
        if self.g502 and not self.g502.close():
            self._closing = False
            event.ignore()
            return
        self.player.close()
        win.unregister_input()
        QApplication.instance().removeNativeEventFilter(self.native)
        self.tray.hide()
        event.accept()
