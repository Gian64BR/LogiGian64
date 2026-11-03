from __future__ import annotations

import copy
from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, QSettings, QEvent
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget,
    QScrollArea, QComboBox, QCheckBox, QLineEdit, QSpinBox, QTableWidget, QAbstractItemView,
    QHeaderView, QListWidget, QInputDialog, QDialog, QMessageBox, QColorDialog, QSlider,
    QFileDialog, QMenu, QPushButton, QApplication)

from .app import MainWindow, panel
from .core import MODES, MAX_EVENTS, new_id, validate_macro
from .widgets import label, button
from .studio_widgets import HubCard, MacroLibrary, AssignmentCanvas, TypeDialog, LearnBindingDialog, RailButton, BackArrow, MacroModeButton
from .timeline import TimelineBlock, TimelineTrack, FlowLayout, timeline_tokens, reorder_tokens
from .dialogs import AddActionDialog
from . import windows as win


class Router:
    def __init__(self, window):
        self.window = window

    def setCurrentIndex(self, index):
        if index == 1:
            self.window.stack.setCurrentIndex(4)
        else:
            self.window.stack.setCurrentIndex(1)
            self.window.device_panels.setCurrentIndex({0: 0, 2: 1, 3: 2}.get(index, 0))
        if hasattr(self.window, "assignment_sidebar"):
            self.window.assignment_sidebar.setVisible(index != 3)
        for key, control in getattr(self.window, "rail_buttons", {}).items():
            control.setChecked(key == (0 if index == 1 else index))


class StudioWindow(MainWindow):
    def __init__(self, store=None):
        self.phase = "press"
        self.phase_drafts = {phase: [] for phase in ("press", "hold", "release")}
        self._editor_loading = False
        self.macro_color = "#9b0037"
        self.timeline_pending = False
        super().__init__(store)
        from . import __version__
        self.setWindowTitle(f"LogiGian64 {__version__} — Macros y asignaciones")

    def eventFilter(self, watched, event):
        # Raw Input records keys separately. Do not let Qt activate focused
        # navigation buttons, defaults, menus or shortcuts while recording.
        if self.recording and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.ShortcutOverride, QEvent.Type.Shortcut):
            if isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def status(self, text):
        super().status(text)
        if hasattr(self, "direct_button"):
            self.direct_button.setText("DESCONECTAR BOTONES G" if self.g502 and self.g502.ready else "ACTIVAR BOTONES G")

    def build_ui(self):
        self.tabs = Router(self)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(82)
        row = QHBoxLayout(header)
        row.setContentsMargins(25, 14, 30, 14)
        brand = label("G", "title")
        brand.setToolTip("LogiGian64 · Aplicación independiente")
        row.addWidget(brand)
        row.addSpacing(24)
        self.nav_buttons = []
        for text, callback in (("Dispositivos", self.go_home), ("Perfiles", self.go_profiles), ("Ayuda", self.go_help)):
            nav = button(text, callback)
            nav.setObjectName("nav")
            nav.setCheckable(True)
            row.addWidget(nav)
            self.nav_buttons.append(nav)
        row.addStretch()
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(240)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed)
        row.addWidget(self.profile_combo)
        row.addWidget(button("+", self.add_profile))
        self.armed = QCheckBox("Activado")
        self.armed.setChecked(True)
        self.armed.toggled.connect(self.armed_changed)
        row.addWidget(self.armed)
        outer.addWidget(header)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(14, 0, 14, 6)
        self.settings_button = RailButton("settings")
        self.settings_button.setCheckable(False)
        self.settings_button.setToolTip("Configuración")
        self.settings_button.setAccessibleName("Configuración")
        self.settings_button.clicked.connect(self.show_settings)
        footer.addWidget(self.settings_button)
        footer.addStretch()
        outer.addLayout(footer)
        self.build_home()
        self.build_detail()
        super().build_profiles()
        self.build_help()
        self.build_editor()
        self.select_nav(0)
        self.status("Selecciona tu periférico · F8 termina grabación · Ctrl+Alt+F12 detiene y restaura el control")

    def preferences(self):
        return QSettings(str(self.store.directory / "settings.ini"), QSettings.Format.IniFormat)

    def show_settings(self):
        from .preferences import startup_enabled, set_startup
        menu = QMenu(self)
        startup = menu.addAction("Iniciar con Windows")
        startup.setCheckable(True)
        try:
            startup.setChecked(startup_enabled())
        except OSError as error:
            self.error(str(error))
            return

        def toggle_startup(enabled):
            try:
                set_startup(enabled)
                self.status("Inicio con Windows " + ("activado" if enabled else "desactivado"))
            except OSError as error:
                self.error("No se pudo cambiar el inicio con Windows: " + str(error))
        startup.toggled.connect(toggle_startup)
        minimized = menu.addAction("Al iniciar con Windows, abrir en la bandeja")
        minimized.setCheckable(True)
        minimized.setChecked(self.preferences().value("startup_minimized", False, type=bool))
        minimized.toggled.connect(lambda value: self.preferences().setValue("startup_minimized", value))
        menu.addSeparator()
        pause = menu.addAction("Pausar asignaciones")
        pause.setCheckable(True)
        pause.setChecked(not self.armed.isChecked())
        pause.toggled.connect(lambda value: self.armed.setChecked(not value))
        menu.addAction("Detener macros y restaurar control", self.emergency_stop)
        menu.addSeparator()
        menu.addAction("Abrir carpeta de perfiles", self.open_data_folder)
        menu.addAction("Minimizar a la bandeja", self.to_tray)
        menu.exec(self.settings_button.mapToGlobal(self.settings_button.rect().topRight()))

    def build_home(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("↻  Detectar dispositivos", self.refresh_devices))
        layout.addLayout(row)
        layout.addSpacing(28)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards_widget = QWidget()
        self.cards = QGridLayout(self.cards_widget)
        self.cards.setContentsMargins(20, 25, 20, 25)
        self.cards.setSpacing(26)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll, 1)
        self.device_count = label("", "muted")
        layout.addWidget(self.device_count, 0, Qt.AlignmentFlag.AlignRight)
        self.stack.addWidget(page)

    def refresh_devices(self):
        try:
            self.devices = win.enumerate_devices()
        except OSError as error:
            self.status(str(error))
            return
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, device in enumerate(self.devices):
            card = HubCard(device)
            card.selected.connect(self.open_device)
            self.cards.addWidget(card, index // 3, index % 3)
        if not self.devices:
            self.cards.addWidget(label("Conecta un ratón o teclado y pulsa Detectar dispositivos.", "muted"), 0, 0)
        self.device_count.setText(f"{len(self.devices)} periféricos detectados")
        if self.device:
            current = next((d for d in self.devices if d.id == self.device.id), None)
            self.connection_label.setText("● CONECTADO" if current else "○ DESCONECTADO")
            if current:
                self.device = current
            else:
                self.stop_all()
                if self.g502:
                    self.g502.close()

    def build_detail(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 12, 24, 12)
        top = QHBoxLayout()
        top.addWidget(BackArrow(self.go_home))
        self.device_title = label("", "title")
        top.addWidget(self.device_title, 1)
        self.connection_label = label("", "muted")
        top.addWidget(self.connection_label)
        layout.addLayout(top)
        body = QHBoxLayout()
        rail = QVBoxLayout()
        self.rail_buttons = {}
        rail.setSpacing(6)
        for kind, index, tooltip in (("sensitivity", 3, "Sensibilidad"), ("assignments", 0, "Asignaciones"), ("lighting", 2, "Iluminación")):
            nav = RailButton(kind)
            nav.setToolTip(tooltip)
            nav.clicked.connect(lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
            nav.setChecked(index == 0)
            self.rail_buttons[index] = nav
            rail.addWidget(nav)
        rail.addStretch()
        body.addLayout(rail)
        sidebar = QFrame()
        self.assignment_sidebar = sidebar
        sidebar.setObjectName("assignmentPanel")
        sidebar.setFixedWidth(285)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(16, 22, 16, 18)
        left.addWidget(label("Asignaciones", "sectionTitle"))
        left.addSpacing(16)
        left.addWidget(label("MACROS    /    TECLAS", "eyebrow"))
        left.addWidget(label("Arrastra una macro a un objetivo para asignarla a este dispositivo.", "muted", True))
        self.search_macros = QLineEdit()
        self.search_macros.setPlaceholderText("Buscar una macro")
        self.search_macros.textChanged.connect(self.filter_library)
        left.addWidget(self.search_macros)
        left.addWidget(button("CREAR NUEVA MACRO", self.new_macro))
        self.assign_library = MacroLibrary()
        self.assign_library.setDragEnabled(True)
        self.assign_library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.assign_library.customContextMenuRequested.connect(self.library_context_menu)
        self.assign_library.itemDoubleClicked.connect(self.edit_library_macro)
        left.addWidget(self.assign_library, 1)
        self.binding_list = QListWidget()
        self.binding_list.setMaximumHeight(125)
        left.addWidget(self.binding_list)
        left.addWidget(button("QUITAR ASIGNACIÓN", self.remove_binding))
        self.binding_hint = label("", "muted", True)
        left.addWidget(self.binding_hint)
        self.direct_button = button("ACTIVAR BOTONES G", self.activate_g502, True)
        left.addWidget(self.direct_button)
        left.addWidget(label("G502: cierra G HUB y su agente antes de activar el control directo. Los cambios del ratón son temporales.", "muted", True))
        body.addWidget(sidebar)
        self.device_panels = QStackedWidget()
        assignments = QWidget()
        av = QVBoxLayout(assignments)
        self.canvas = AssignmentCanvas()
        self.canvas.target.connect(self.assign_target)
        self.hero_art = self.canvas  # Base class color update; canvas remains the source of targets.
        self.hero_art.color = "#00b7ed"
        av.addWidget(self.canvas, 1)
        views = QHBoxLayout()
        views.addStretch()
        views.addWidget(button("VISTA 1", lambda: self.change_view(False)))
        views.addWidget(button("VISTA 2", lambda: self.change_view(True)))
        views.addStretch()
        av.addLayout(views)
        self.device_panels.addWidget(assignments)
        lighting = QWidget()
        lv = QVBoxLayout(lighting)
        lv.addStretch()
        lv.addWidget(label("Iluminación del dispositivo", "title"))
        lv.addWidget(label("El control RGB físico todavía no está implementado. Esta pantalla no envía colores al ratón.", "muted", True))
        lv.addStretch()
        self.device_panels.addWidget(lighting)
        from .sensitivity import SensitivityPanel
        self.sensitivity_panel = SensitivityPanel(self)
        self.speed_slider = self.sensitivity_panel.speed_slider
        self.speed_value = self.sensitivity_panel.speed_value
        self.hardware_info = self.sensitivity_panel.hardware_info
        self.device_panels.addWidget(self.sensitivity_panel)
        body.addWidget(self.device_panels, 1)
        layout.addLayout(body, 1)
        self.device_type, self.device_meta = label(""), label("")
        self.stack.addWidget(page)

    def build_help(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(65, 40, 65, 40)
        layout.addWidget(label("Macros conectadas a un botón físico", "title"))
        layout.addWidget(label("SIN REPETICIÓN\nSe ejecuta una vez al pulsar. Soltar el activador no interrumpe esa ejecución.\n\n"
            "REPETIR DURANTE PULSACIÓN\nSe inicia al pulsar y se repite mientras mantienes el botón. Soltarlo interrumpe las esperas y libera las teclas de la macro.\n\n"
            "ALTERNANTE\nUna pulsación inicia el bucle. La siguiente pulsación del mismo activador lo detiene.\n\n"
            "SECUENCIA\nAl pulsar, Durante pulsación y Al soltar tienen acciones independientes. La parte central se repite mientras mantienes el botón.\n\n"
            "G502 HERO\nActiva BOTONES G con G HUB y su agente cerrados. Arrastra una macro al objetivo y pulsa físicamente ese botón para identificarlo. "
            "Al guardar se reserva ese control para LogiGian64 mientras el control directo esté activo. Se restauran el mapa y el modo al desconectarlo o salir.\n\n"
            "OTROS PERIFÉRICOS\nSe pueden asignar las teclas y botones que Windows expone. En el modo genérico se conserva su acción original; la supresión requiere un adaptador del dispositivo.\n\n"
            "PARADA\nCtrl+Alt+F12 detiene todas las macros, pausa las asignaciones y restaura el control directo. F8 termina una grabación. "
            "F9 se puede usar dentro de macros. Mantén LogiGian64 abierto o minimízalo a la bandeja.", "muted", True))
        layout.addStretch()
        layout.addWidget(button("Abrir carpeta de perfiles", self.open_data_folder), 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(button("Minimizar a la bandeja", self.to_tray), 0, Qt.AlignmentFlag.AlignLeft)
        self.stack.addWidget(page)

    def build_editor(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(35, 18, 35, 20)
        layout.addWidget(BackArrow(self.back_to_assignments), 0, Qt.AlignmentFlag.AlignLeft)
        self.macro_list = QListWidget()
        self.macro_list.currentRowChanged.connect(self.macro_selected)
        self.macro_list.hide()
        self.editor = QWidget()
        el = QVBoxLayout(self.editor)
        el.setContentsMargins(70, 0, 70, 0)
        header = QHBoxLayout()
        info = QVBoxLayout()
        self.macro_name = QLineEdit()
        self.macro_name.setStyleSheet("font-size:24px; font-weight:700; background:black; border:none")
        info.addWidget(self.macro_name)
        mode_row = QHBoxLayout()
        mode_row.addWidget(label("Tipos de macro"))
        self.mode_combo = QComboBox()
        self.mode_combo.hide()
        self.mode_buttons = {}
        for mode, icon in (("once", "→"), ("hold", "⟳"), ("toggle", "◉"), ("sequence", "▣"), ("latch", "⏸")):
            self.mode_combo.addItem(MODES[mode], mode)
            control = MacroModeButton(mode)
            control.setObjectName("mode")
            control.setCheckable(True)
            control.setToolTip(MODES[mode])
            control.setFixedSize(42, 34)
            control.clicked.connect(lambda checked=False, m=mode: self.mode_combo.setCurrentIndex(self.mode_combo.findData(m)))
            mode_row.addWidget(control)
            self.mode_buttons[mode] = control
        mode_row.addStretch()
        info.addLayout(mode_row)
        self.mode_description = label("", "muted", True)
        info.addWidget(self.mode_description)
        header.addLayout(info, 1)
        options = QVBoxLayout()
        std_row = QHBoxLayout()
        self.standard_delay = QCheckBox("USAR RETARDOS ESTÁNDAR")
        self.delay_ms = QSpinBox()
        self.delay_ms.setRange(0, 60000)
        self.delay_ms.setValue(50)
        self.delay_ms.setSuffix(" ms")
        self.delay_ms.setFixedWidth(100)
        self.standard_delay.setMinimumWidth(220)
        std_row.addWidget(self.standard_delay)
        std_row.addWidget(self.delay_ms)
        options.addLayout(std_row)
        self.show_releases = QCheckBox("MOSTRAR TECLA BAJADA / TECLA SUBIDA")
        self.show_releases.setChecked(True)
        self.show_releases.toggled.connect(self.render_timeline)
        options.addWidget(self.show_releases)
        options.addWidget(button("●  COLOR DE MACRO", self.choose_macro_color))
        self.record_mouse = QCheckBox("Incluir botones y rueda al grabar")
        self.record_mouse.setChecked(True)
        options.addWidget(self.record_mouse)
        self.standard_delay.toggled.connect(self.apply_standard_delay)
        self.delay_ms.valueChanged.connect(self.apply_standard_delay)
        header.addLayout(options)
        el.addLayout(header)
        self.phase_combo = QComboBox()
        for text, phase in (("AL PULSAR", "press"), ("DURANTE PULSACIÓN", "hold"), ("AL SOLTAR", "release")):
            self.phase_combo.addItem(text, phase)
        self.phase_combo.currentIndexChanged.connect(self.change_phase)
        el.addWidget(self.phase_combo, 0, Qt.AlignmentFlag.AlignLeft)
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setMinimumHeight(150)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.timeline_content = TimelineTrack()
        self.timeline_content.moved.connect(self.reorder_timeline)
        self.timeline_content.setStyleSheet("background:#000")
        self.timeline = FlowLayout(self.timeline_content)
        self.timeline.setContentsMargins(8, 16, 8, 16)
        self.timeline.setSpacing(12)
        self.timeline_scroll.setWidget(self.timeline_content)
        el.addWidget(self.timeline_scroll, 1)
        self.record_button = button("●  GRABAR PULSACIONES", self.toggle_record)
        self.record_button.setStyleSheet("background:#790028; padding:12px 20px")
        controls = QHBoxLayout()
        controls.addWidget(self.record_button)
        controls.addWidget(button("+  AÑADIR", self.action_menu))
        controls.addWidget(button("EDITAR TIEMPOS / PASOS", self.toggle_table))
        controls.addStretch()
        self.sequence_stats = label("", "muted")
        controls.addWidget(self.sequence_stats)
        el.addLayout(controls)
        self.record_label = label("Pulsa + para añadir acciones o comienza a grabar. F8 finaliza la grabación.", "muted", True)
        el.addWidget(self.record_label)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "ACCIÓN", "ENTRADA", "ESPERA · MS"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(220)
        self.table.hide()
        el.addWidget(self.table)
        edit = QHBoxLayout()
        edit.addWidget(button("− Eliminar paso", self.remove_step))
        edit.addWidget(button("↑", lambda: self.move_step(-1)))
        edit.addWidget(button("↓", lambda: self.move_step(1)))
        edit.addStretch()
        el.addLayout(edit)
        self.repeats = QSpinBox()
        self.repeats.setRange(1, 100)
        self.repeats.hide()
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(button("RESTABLECER", self.reset_macro))
        bottom.addWidget(button("PRUEBA ÚNICA EN 3 S", self.play_current))
        bottom.addWidget(button("DETENER", self.stop_all))
        bottom.addWidget(button("GUARDAR", self.save_macro, True))
        bottom.addStretch()
        el.addLayout(bottom)
        layout.addWidget(self.editor, 1)
        self.mode_combo.currentIndexChanged.connect(self.mode_changed)
        self.stack.addWidget(page)

    def open_device(self, device):
        super().open_device(device)
        self.canvas.configure(device)
        self.direct_button.setVisible((device.vid, device.pid) == ("046D", "C08B"))
        self.refresh_bindings()

    def change_view(self, side):
        self.canvas.side = side
        if self.device:
            self.canvas.configure(self.device, self.canvas.names)

    def refresh_macros(self, select_id=None):
        super().refresh_macros(select_id)
        self.refresh_bindings()

    def refresh_bindings(self):
        if not hasattr(self, "assign_library"):
            return
        self.assign_library.clear()
        self.binding_list.clear()
        names = {}
        for macro in self.store.active["macros"]:
            slots = [b.get("slot", "") for b in self.store.active["bindings"] if self.device and b["device_id"] == self.device.id and b["macro_id"] == macro["id"]]
            self.assign_library.addItem(macro["name"] + ("    " + ", ".join(filter(None, slots)) if slots else ""))
            item = self.assign_library.item(self.assign_library.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, macro["id"])
            item.setToolTip(MODES[macro.get("mode", "once")] + " · Doble clic para editar")
        if self.device:
            for binding in self.store.active["bindings"]:
                if binding["device_id"] != self.device.id:
                    continue
                macro = next(m for m in self.store.active["macros"] if m["id"] == binding["macro_id"])
                trigger = binding["trigger"]
                control = ("Control " + str(trigger["button"] + 1) if trigger["type"] == "gbutton" else
                           win.key_name(trigger["vk"]) if trigger["type"] == "key" else win.MOUSE_LABELS[trigger["button"]])
                slot = binding.get("slot") or control
                self.binding_list.addItem(slot + " → " + macro["name"])
                names[slot] = macro["name"]
            self.canvas.disabled = {c["slot"] for c in self.store.active.get("disabled_controls", [])
                                    if c["device_id"] == self.device.id}
            self.canvas.names = names
            self.canvas.overlay.update()
            self.binding_hint.setText("Pulsa un objetivo para asignar una macro." if not names else "Asignaciones guardadas en este perfil.")
        self.filter_library(self.search_macros.text())
        self.sync_g502()

    def filter_library(self, text):
        if not hasattr(self, "assign_library"):
            return
        for n in range(self.assign_library.count()):
            item = self.assign_library.item(n)
            item.setHidden(text.casefold() not in item.text().casefold())

    def library_context_menu(self, position):
        item = self.assign_library.itemAt(position)
        if not item:
            return
        self.assign_library.setCurrentItem(item)
        mid = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        edit = menu.addAction("Editar")
        rename = menu.addAction("Renombrar")
        delete = menu.addAction("Eliminar")
        action = menu.exec(self.assign_library.viewport().mapToGlobal(position))
        if action == edit:
            self.edit_library_macro(item)
        elif action == rename:
            self.rename_library_macro(item)
        elif action == delete:
            if self.leave_editor():
                self.refresh_macros(mid)
                self.delete_macro()

    def rename_library_macro(self, item):
        mid = item.data(Qt.ItemDataRole.UserRole)
        if not self.leave_editor():
            return
        macro = next((m for m in self.store.active["macros"] if m["id"] == mid), None)
        if not macro:
            return
        name, ok = QInputDialog.getText(self, "Renombrar macro", "Nombre", text=macro["name"])
        if ok and name.strip():
            old_name = macro["name"]
            macro["name"] = name.strip()[:100]
            if not self.persist():
                macro["name"] = old_name
            self.refresh_macros(mid)

    def edit_library_macro(self, item):
        mid = item.data(Qt.ItemDataRole.UserRole)
        if self.leave_editor():
            self.refresh_macros(mid)
            self.tabs.setCurrentIndex(1)

    def new_macro(self):
        if not self.leave_editor():
            return
        if len(self.store.active["macros"]) >= 200:
            return self.error("Un perfil admite hasta 200 macros.")
        name, ok = QInputDialog.getText(self, "Nueva macro", "Nombre de la macro", text="Macro " + str(len(self.store.active["macros"]) + 1))
        if not ok or not name.strip():
            return
        dialog = TypeDialog(self, name.strip())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        macro = validate_macro({"id": new_id(), "name": name.strip(), "mode": dialog.mode,
                                "events": [], "standard_delay": True, "standard_delay_ms": 50})
        self.store.active["macros"].append(macro)
        if self.persist():
            self.refresh_macros(macro["id"])
            self.tabs.setCurrentIndex(1)
            return macro['id']

    def load_macro(self, row):
        self._editor_loading = True
        super().load_macro(row)
        macro = self.current_macro()
        if macro:
            self.phase_drafts = copy.deepcopy(macro.get("sections", {"press": [], "hold": [], "release": []}))
            self.phase = "press"
            self.phase_combo.setCurrentIndex(0)
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(macro.get("mode", "once")))
            self.standard_delay.setChecked(macro.get("standard_delay", False))
            self.delay_ms.setValue(macro.get("standard_delay_ms", 50))
            self.macro_color = macro.get("color", "#9b0037")
            if macro.get("mode") == "sequence":
                self.draft = copy.deepcopy(self.phase_drafts["press"])
        self._editor_loading = False
        self.update_mode_controls()
        self.apply_standard_delay()
        self.render_events()

    def read_sections(self):
        self.phase_drafts[self.phase] = copy.deepcopy(self.read_draft())
        return copy.deepcopy(self.phase_drafts)

    def change_phase(self, index):
        if self._editor_loading or self.mode_combo.currentData() != "sequence":
            return
        if self.recording:
            self.finish_recording()
        self.read_sections()
        self.phase = self.phase_combo.itemData(index)
        self.draft = copy.deepcopy(self.phase_drafts[self.phase])
        self.render_events()

    def mode_changed(self, index):
        if self._editor_loading:
            return
        if self.recording:
            self.finish_recording()
        previous = getattr(self, "editing_mode", "once")
        mode = self.mode_combo.currentData()
        self.read_draft()
        if previous == "sequence" and mode != "sequence":
            self.read_sections()
            self.draft = sum((self.phase_drafts[p] for p in ("press", "hold", "release")), [])
        elif previous != "sequence" and mode == "sequence":
            self.phase_drafts = {"press": [], "hold": copy.deepcopy(self.draft), "release": []}
            self.phase = "hold"
            self._editor_loading = True
            self.phase_combo.setCurrentIndex(1)
            self._editor_loading = False
        self.update_mode_controls()
        self.render_events()

    def update_mode_controls(self):
        mode = self.mode_combo.currentData() or "once"
        self.editing_mode = mode
        for key, control in self.mode_buttons.items():
            control.setChecked(key == mode)
        self.phase_combo.setVisible(mode == "sequence")
        self.mode_description.setText({"once": "Se ejecuta una vez al pulsar el botón asignado.",
            "hold": "Se repite mientras mantienes pulsado el botón. Se detiene al soltar.",
            "toggle": "Una pulsación inicia el bucle. La siguiente pulsación lo detiene.",
            "sequence": "Configura Al pulsar, Durante pulsación y Al soltar por separado.",
            "latch": "Primera pulsación: mantiene las teclas y clics añadidos. Segunda pulsación: los suelta. Sin repeticiones ni temporizador; se ignoran las liberaciones grabadas."}[mode])
        self.standard_delay.setVisible(mode != "latch")
        self.delay_ms.setVisible(mode != "latch")

    def save_macro(self):
        if self.recording:
            self.finish_recording()
        if self.commit_draft():
            self.status("Macro guardada en el perfil «" + self.store.active["name"] + "»")
            self.tabs.setCurrentIndex(0)
            pending = getattr(self, '_pending_macro_target', None)
            if pending and self.device and pending[0] == self.device.id:
                from .macro_engine import MacroEngine
                macro = self.current_macro()
                if macro and MacroEngine.has_actions(macro):
                    self._pending_macro_target = None
                    QTimer.singleShot(0, lambda: self.assign_macro_target(pending[1], macro['id']))

    def apply_standard_delay(self, *args):
        if self._editor_loading:
            return
        if not self.standard_delay.isChecked() or self.mode_combo.currentData() == "latch":
            self.render_events()
            return
        self.read_draft()
        for events in [self.draft, *self.phase_drafts.values()]:
            for event in events:
                if event["type"] != "wait":
                    event["delay_ms"] = self.delay_ms.value()
        self.render_events()

    def capture_event(self, event):
        super().capture_event(event)
        if self.standard_delay.isChecked() and self.mode_combo.currentData() != "latch" and self.draft:
            self.draft[-1]["delay_ms"] = self.delay_ms.value()
            spin = self.table.cellWidget(len(self.draft) - 1, 3)
            if spin:
                spin.setValue(self.delay_ms.value())

    def commit_draft(self):
        macro = self.current_macro()
        if not macro:
            return True
        if self.recording:
            return False
        try:
            value = {**macro, "name": self.macro_name.text(), "mode": self.mode_combo.currentData() or "once",
                     "standard_delay": self.standard_delay.isChecked(), "standard_delay_ms": self.delay_ms.value(),
                     "color": self.macro_color, "events": copy.deepcopy(self.read_draft())}
            if value["mode"] == "sequence":
                value["sections"] = self.read_sections()
            else:
                value.pop("sections", None)
            clean = validate_macro(value)
            if clean == validate_macro(macro):
                return True
            old = copy.deepcopy(macro)
            macro.clear()
            macro.update(clean)
            if not self.persist():
                macro.clear()
                macro.update(old)
                return False
            self.refresh_bindings()
            return True
        except ValueError as error:
            self.error(error)
            return False

    def back_to_assignments(self):
        if self.leave_editor():
            self.tabs.setCurrentIndex(0)

    def set_control_state(self, slot, disabled):
        from .safety import PROTECTED_SLOTS
        if slot in PROTECTED_SLOTS:
            self.status("Clic izquierdo y derecho protegidos: no se pueden modificar ni desactivar.")
            return
        if not self.device:
            return
        bindings = self.store.active["bindings"]
        controls = self.store.active.setdefault("disabled_controls", [])
        existing = next((b for b in bindings if b["device_id"] == self.device.id and b.get("slot") == slot), None)
        control = next((c for c in controls if c["device_id"] == self.device.id and c["slot"] == slot), None)
        bit = (existing["trigger"]["button"] if existing and existing["trigger"]["type"] == "gbutton"
               else control["button"] if control else None)
        self.stop_all()
        bindings[:] = [b for b in bindings if not (b["device_id"] == self.device.id and
            (b.get("slot") == slot or (bit is not None and b["trigger"] == {"type": "gbutton", "button": bit})))]
        controls[:] = [c for c in controls if not (c["device_id"] == self.device.id and
            (c["slot"] == slot or (bit is not None and c["button"] == bit)))]
        if disabled:
            controls.append({"device_id": self.device.id, "slot": slot, "button": bit})
        self.persist()
        self.refresh_bindings()

    def assign_target(self, slot, macro_id=""):
        from .safety import PROTECTED_SLOTS
        if slot in PROTECTED_SLOTS:
            self.status("Clic izquierdo y derecho protegidos: no admiten macros ni desactivación.")
            return
        if not macro_id and self.device:
            self.canvas.selected = slot
            self.canvas.overlay.update()
            menu = QMenu(self)
            default = menu.addAction("Usar predeterminada")
            disable = menu.addAction("Desactivar")
            menu.addSeparator()
            assign = menu.addAction("Asignar macro…")
            action = menu.exec(QCursor.pos())
            if action == default:
                return self.set_control_state(slot, False)
            if action == disable:
                return self.set_control_state(slot, True)
            if action != assign:
                return
        self.assign_macro_target(slot, macro_id)

    def assign_macro_target(self, slot, macro_id=""):
        from .safety import PROTECTED_SLOTS
        if slot in PROTECTED_SLOTS:
            self.status("Clic izquierdo y derecho protegidos: no admiten macros.")
            return
        if not self.device or not self.leave_editor():
            return
        from .macro_engine import MacroEngine
        macros = [m for m in self.store.active["macros"] if MacroEngine.has_actions(m)]
        if not macros:
            self._pending_macro_target = (self.device.id, slot)
            self.status("Crea una macro con acciones y pulsa Guardar para continuar con " + slot + ".")
            if not self.new_macro():
                self._pending_macro_target = None
            return
        if (self.device.vid, self.device.pid) == ("046D", "C08B") and not (self.g502 and self.g502.ready):
            self._pending_binding = (self.device.id, slot, macro_id)
            if not (self.g502 and self.g502.thread and self.g502.thread.is_alive()):
                self.activate_g502()
            if not self.g502:
                self._pending_binding = None
            return
        self.stop_all()
        dialog = LearnBindingDialog(self, self.device, macros, slot, macro_id)
        self.learning = dialog
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self.learning = None
            self.physical_held.clear()
        if accepted and dialog.trigger:
            binding = dialog.binding()
            from .safety import protected_control
            if protected_control(binding):
                return self.error("Clic izquierdo y derecho protegidos. Elige otro botón físico.")
            assignments = self.store.active["bindings"]
            assignments[:] = [b for b in assignments if not (b["device_id"] == self.device.id and
                (b.get("slot") == slot or b["trigger"] == binding["trigger"]))]
            controls = self.store.active.setdefault("disabled_controls", [])
            controls[:] = [c for c in controls if not (c["device_id"] == self.device.id and
                (c["slot"] == slot or (binding["trigger"]["type"] == "gbutton" and c["button"] == binding["trigger"]["button"])))]
            assignments.append(binding)
            self.persist()
            self.refresh_bindings()

    def remove_binding(self):
        self.stop_all()
        super().remove_binding()
        self.refresh_bindings()

    def armed_changed(self, armed):
        super().armed_changed(armed)
        self.sync_g502()

    def sync_g502(self):
        if self.g502 and self.g502.ready:
            self.g502.update_buttons({b["trigger"]["button"] for b in self.store.active["bindings"]
                if self.armed.isChecked() and b["device_id"] == self.g502.device.id and
                b["trigger"]["type"] == "gbutton" and b["enabled"]} |
                {c["button"] for c in self.store.active.get("disabled_controls", [])
                 if self.armed.isChecked() and c["device_id"] == self.g502.device.id and type(c["button"]) is int})

    def render_event(self, row, event):
        if self.mode_combo.currentData() == "latch":
            event["delay_ms"] = 0
        elif self.standard_delay.isChecked() and event["type"] != "wait":
            event["delay_ms"] = self.delay_ms.value()
        super().render_event(row, event)
        if event["type"] != "wait":
            self.table.cellWidget(row, 3).setEnabled(not self.standard_delay.isChecked() and self.mode_combo.currentData() != "latch")
            if self.mode_combo.currentData() == "latch":
                self.table.cellWidget(row, 3).setSpecialValueText("Sin retardo")
        if not self.timeline_pending:
            self.timeline_pending = True
            QTimer.singleShot(0, self.render_timeline)

    def render_events(self):
        super().render_events()
        if hasattr(self, "timeline"):
            self.render_timeline()

    def render_timeline(self):
        self.timeline_pending = False
        if not hasattr(self, "timeline"):
            return
        while self.timeline.count():
            item = self.timeline.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        standard = self.standard_delay.isChecked() or self.mode_combo.currentData() == "latch"
        tokens = ([(row, "delay" if event["type"] == "wait" else "action", event)
                   for row, event in enumerate(self.draft)] if standard else timeline_tokens(self.draft))
        for index, (row, token_kind, event) in enumerate(tokens):
            kind = event["type"]
            if (not self.show_releases.isChecked() or self.mode_combo.currentData() == "latch") and kind in ("key", "mouse") and not event["down"]:
                continue
            if kind == "key":
                text = "BARRA ESPACIADORA" if event["vk"] == 32 else win.key_name(event["vk"], event.get("scan", 0), event.get("extended", False)).upper()
            elif kind == "mouse":
                text = win.MOUSE_LABELS[event["button"]].upper()
            elif kind == "wheel":
                text = f"RUEDA {event['delta']:+d}"
            elif kind == "text":
                text = event["text"][:25]
            else:
                text = Path(event.get("path", "")).name
            chip = TimelineBlock(index, row, text, self.macro_color,
                                 delay=event["delay_ms"] if token_kind == "delay" else None,
                                 down=event.get("down"), draggable=not self.recording)
            chip.selected.connect(self.select_step)
            chip.delay_changed.connect(self.edit_timeline_delay)
            self.timeline.addWidget(chip)
        plus = button("+", self.action_menu)
        plus.setFixedSize(48, 48)
        plus.setStyleSheet("background:#333; font-size:30px; font-weight:300; padding:0; border-radius:0")
        self.timeline.addWidget(plus)
        if not self.draft:
            self.timeline.addWidget(label("INICIAR AHORA", "muted"))

    def edit_timeline_delay(self, row, value):
        if self.recording:
            return
        self.read_draft()
        self.draft[row]["delay_ms"] = value
        self.render_events()

    def reorder_timeline(self, source, destination):
        if self.recording:
            return
        self.read_draft()
        if self.standard_delay.isChecked() or self.mode_combo.currentData() == "latch":
            event = self.draft.pop(source)
            self.draft.insert(destination - (destination > source), event)
        else:
            self.draft = reorder_tokens(self.draft, source, destination)
        self.render_events()

    def select_step(self, index):
        self.table.show()
        self.table.selectRow(index)
        self.table.scrollToItem(self.table.item(index, 0))

    def toggle_table(self):
        self.table.setVisible(not self.table.isVisible())

    def choose_macro_color(self):
        color = QColorDialog.getColor(QColor(self.macro_color), self, "Color de la macro")
        if color.isValid():
            self.macro_color = color.name()
            self.render_timeline()

    def reset_macro(self):
        if self.current_macro():
            if self.recording:
                self.finish_recording()
            index = next(i for i, m in enumerate(self.store.active["macros"]) if m["id"] == self.macro_id)
            self.load_macro(index)

    def toggle_record(self):
        if self.recording:
            return self.finish_recording()
        if not self.input_ready:
            return self.error("La captura de entrada de Windows no está disponible.")
        if not self.current_macro():
            return
        self.read_draft()
        self.stop_all()
        self.record_held = {}
        self.recording = True
        QApplication.instance().installEventFilter(self)
        self.record_start = self.last_record_time = time.monotonic()
        self.record_button.setText("■  FINALIZAR · F8")
        self.record_timer.start()
        self.record_tick()

    def finish_recording(self):
        QApplication.instance().removeEventFilter(self)
        super().finish_recording()

    def action_menu(self):
        if self.recording:
            return
        popup = QDialog(self, Qt.WindowType.Popup)
        popup.setStyleSheet("QDialog {background:#000; border:none} QPushButton {color:white; font-weight:700; text-align:left; padding:10px 12px; border:none; border-radius:4px} QPushButton:hover {border:1px solid white}")
        layout = QVBoxLayout(popup)
        layout.setSpacing(8)
        choice = []
        for title, color in (("●  Grabar pulsaciones", "#790028"), ("Texto y emojis", "#695000"),
                             ("Tecla / botón / rueda", "#804000"), ("Inicio de aplicación", "#656565"),
                             ("Sistema", "#333333"), ("Retardo", "#414154")):
            control = button(title.upper())
            control.setStyleSheet(f"background:{color}")
            control.clicked.connect(lambda checked=False, value=title: (choice.append(value), popup.accept()))
            layout.addWidget(control, 0, Qt.AlignmentFlag.AlignLeft)
        control = self.sender()
        popup.adjustSize()
        position = control.mapToGlobal(control.rect().bottomLeft()) if isinstance(control, QWidget) else self.mapToGlobal(self.rect().center())
        screen = self.screen().availableGeometry()
        position.setX(max(screen.left(), min(position.x(), screen.right() - popup.width())))
        position.setY(max(screen.top(), min(position.y(), screen.bottom() - popup.height())))
        popup.move(position)
        popup.exec()
        title = choice[0] if choice else ""
        if title.startswith("●"):
            return self.toggle_record()
        if title in ("Tecla / botón / rueda", "Retardo"):
            dialog = AddActionDialog(self)
            if title == "Retardo":
                dialog.kind.setCurrentIndex(2)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.append_actions(dialog.events())
        elif title == "Texto y emojis":
            text, ok = QInputDialog.getMultiLineText(self, "Texto y emojis", "Texto que escribirá la macro")
            if ok and text:
                self.append_actions([{"type": "text", "text": text, "delay_ms": 0}])
        elif title == "Inicio de aplicación":
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar aplicación", "", "Aplicación Windows (*.exe)")
            if path:
                self.append_actions([{"type": "launch", "path": path, "delay_ms": 0}])
        elif title == "Sistema":
            choices = {"Subir volumen": 175, "Bajar volumen": 174, "Silenciar": 173, "Reproducir / pausar": 179, "Pista siguiente": 176, "Pista anterior": 177}
            name, ok = QInputDialog.getItem(self, "Sistema", "Acción", list(choices), 0, False)
            if ok:
                self.append_actions([{"type": "key", "vk": choices[name], "scan": 0, "down": state, "delay_ms": 0} for state in (True, False)])

    def append_actions(self, events):
        if self.recording:
            self.finish_recording()
        self.read_draft()
        if len(self.draft) + len(events) > MAX_EVENTS:
            return self.error("La macro supera el límite de pasos.")
        self.draft.extend(events)
        self.render_events()
