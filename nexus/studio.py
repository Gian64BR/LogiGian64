from __future__ import annotations

import copy
from pathlib import Path
import time

from PySide6.QtCore import Qt, QTimer, QSettings, QEvent, QSize
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget,
    QScrollArea, QComboBox, QCheckBox, QLineEdit, QSpinBox, QTableWidget, QAbstractItemView,
    QHeaderView, QListWidget, QInputDialog, QDialog, QMessageBox, QColorDialog, QSlider,
    QFileDialog, QMenu, QPushButton, QApplication, QListWidgetItem, QSizePolicy, QLayout, QListView)

from .app import MainWindow, panel
from .core import MODES, MAX_EVENTS, new_id, validate_macro, DEFAULT_MACRO_COLOR, macro_label_color, macro_badge_color
from .widgets import label, button
from .studio_widgets import HubCard, MacroLibrary, MacroSearch, AssignmentPanel, AssignmentCanvas, TypeDialog, LearnBindingDialog, RailButton, BackArrow, MacroModeButton
from .timeline import TimelineBlock, TimelineTrack, FlowLayout, timeline_tokens, reorder_tokens, editor_events
from .dialogs import AddActionDialog, DelayDialog
from . import windows as win
from .studio_widgets import ConnectionLabel, ProfileCard


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
            self.window.assignment_sidebar.setVisible(index not in (2, 3))
        for key, control in getattr(self.window, "rail_buttons", {}).items():
            control.setChecked(key == (0 if index == 1 else index))


class StudioWindow(MainWindow):
    def __init__(self, store=None):
        self.phase = "press"
        self.phase_drafts = {phase: [] for phase in ("press", "hold", "release")}
        self._editor_loading = False
        self.macro_color = DEFAULT_MACRO_COLOR
        self.macro_color_custom = False
        self.timeline_pending = False
        super().__init__(store)
        from . import __version__
        self.setWindowTitle(f"LogiGian64 {__version__} — Macros y asignaciones")
        self.setMinimumSize(1000, 580)
        available = self.screen().availableGeometry()
        self.resize(min(1300, available.width()), min(900, available.height()))

    def eventFilter(self, watched, event):
        if not self.recording and event.type() == QEvent.Type.FocusIn and isinstance(watched, QWidget):
            for row in range(self.table.rowCount()):
                spin = self.table.cellWidget(row, 3)
                if spin and (watched is spin or spin.isAncestorOf(watched)):
                    self.table.selectRow(row)
                    break
        if not self.recording and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            if watched is self.table or self.table.isAncestorOf(watched):
                self.remove_step()
                return True
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
        self.timeline_timer = QTimer(self)
        self.timeline_timer.setSingleShot(True)
        self.timeline_timer.timeout.connect(self.render_timeline)
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
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
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
        self.build_profiles()
        self.build_help()
        self.build_editor()
        self.select_nav(0)
        self.status("Selecciona tu periférico · F8 termina grabación · Ctrl+Alt+F12 detiene y restaura el control")

    def build_profiles(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.addWidget(label('TU BIBLIOTECA LOCAL', 'eyebrow'))
        layout.addWidget(label('Perfiles', 'title'))
        layout.addWidget(label('Selecciona un perfil. Haz doble clic para activarlo.', 'muted'))
        self.profile_list = QListWidget()
        self.profile_list.setObjectName('profileList')
        self.profile_list.setViewMode(QListView.ViewMode.IconMode)
        self.profile_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.profile_list.setMovement(QListView.Movement.Static)
        self.profile_list.setWrapping(True)
        self.profile_list.setGridSize(QSize(312, 218))
        self.profile_list.setSpacing(8)
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profile_list.currentRowChanged.connect(self.update_profile_cards)
        self.profile_list.itemDoubleClicked.connect(lambda: self.activate_profile())
        layout.addWidget(self.profile_list, 1)
        actions = QHBoxLayout()
        for text, callback, primary in [('+ Nuevo', self.add_profile, True), ('Activar', self.activate_profile, False),
                ('Duplicar', self.duplicate_profile, False), ('Importar JSON', self.import_profile, False),
                ('Exportar JSON', self.export_profile, False)]:
            actions.addWidget(button(text, callback, primary))
        actions.addStretch()
        layout.addLayout(actions)
        self.stack.addWidget(page)

    def refresh_profiles(self):
        super().refresh_profiles()
        for row, profile in enumerate(self.store.profiles):
            item = self.profile_list.item(row)
            item.setText('')
            item.setData(Qt.ItemDataRole.UserRole, profile['id'])
            item.setSizeHint(QSize(296, 202))
            card = ProfileCard(profile, profile['id'] == self.store.active_id)
            card.selected.connect(lambda r=row: self.profile_list.setCurrentRow(r))
            card.activated.connect(lambda r=row: self.profile_card_action(r, self.activate_profile))
            card.rename.connect(lambda r=row: self.profile_card_action(r, self.rename_profile))
            card.remove.connect(lambda r=row: self.profile_card_action(r, self.delete_profile))
            self.profile_list.setItemWidget(item, card)
        self.update_profile_cards()

    def update_profile_cards(self, *_):
        for row in range(self.profile_list.count()):
            card = self.profile_list.itemWidget(self.profile_list.item(row))
            if card:
                card.set_selected(row == self.profile_list.currentRow())

    def profile_card_action(self, row, callback):
        self.profile_list.setCurrentRow(row)
        callback()

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
        minimized = menu.addAction("Inicio con Windows: solo en la bandeja")
        minimized.setEnabled(False)
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
                renamed = (self.device.name, self.device.button_count) != (current.name, current.button_count)
                self.device = current
                self.device_title.setText(current.name)
                if renamed:
                    self.canvas.configure(current, self.canvas.names)
            else:
                self.stop_all()
        self.schedule_auto_g502()

    def build_detail(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 12, 24, 12)
        top = QHBoxLayout()
        top.addWidget(BackArrow(self.go_home))
        self.device_title = label("", "title")
        top.addWidget(self.device_title, 1)
        self.connection_label = ConnectionLabel()
        top.addWidget(self.connection_label)
        top.addWidget(button('Identificar modelo', self.identify_device_model))
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
        sidebar = AssignmentPanel()
        sidebar.setObjectName("assignmentPanel")
        self.assignment_content = sidebar
        self.assignment_sidebar = QScrollArea()
        self.assignment_sidebar.setObjectName("assignmentScroll")
        self.assignment_sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.assignment_sidebar.setWidgetResizable(True)
        self.assignment_sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assignment_sidebar.setFixedWidth(300)
        self.assignment_sidebar.setWidget(sidebar)
        left = QVBoxLayout(sidebar)
        left.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        left.setContentsMargins(16, 22, 16, 18)
        left.setSpacing(8)
        left.addWidget(label("Asignaciones", "sectionTitle"))
        left.addSpacing(12)
        left.addWidget(label('MACROS', 'macroSection'), 0, Qt.AlignmentFlag.AlignLeft)
        left.addSpacing(6)
        left.addWidget(label('Arrastra un macro a un objetivo para asignarlo a este dispositivo.', 'macroInstructions', True))
        self.search_macros = MacroSearch()
        self.search_macros.setPlaceholderText("Buscar una macro")
        self.search_macros.textChanged.connect(self.filter_library)
        left.addWidget(self.search_macros)
        left.addWidget(button("CREAR NUEVA MACRO", self.new_macro))
        self.assign_library = MacroLibrary()
        self.assign_library.setObjectName('macroLibrary')
        self.assign_library.setMinimumHeight(132)
        self.assign_library.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.assign_library.setDragEnabled(True)
        self.assign_library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.assign_library.customContextMenuRequested.connect(self.library_context_menu)
        self.assign_library.itemDoubleClicked.connect(self.edit_library_macro)
        left.addWidget(self.assign_library, 1)
        left.addSpacing(6)
        self.binding_list = QListWidget()
        self.binding_list.setObjectName('assignedButtons')
        self.binding_list.setMinimumHeight(104)
        self.binding_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.binding_list.setMaximumHeight(156)
        self.binding_list.currentRowChanged.connect(self.binding_row_selected)
        left.addWidget(self.binding_list, 1)
        self.keyboard_macro_button = button('DESACTIVAR MACRO', self.toggle_selected_keyboard_macro)
        self.keyboard_macro_button.hide()
        self.keyboard_macro_button.setEnabled(False)
        left.addWidget(self.keyboard_macro_button)
        self.remove_binding_button = button("QUITAR ASIGNACIÓN", self.remove_binding)
        left.addWidget(self.remove_binding_button)
        self.binding_hint = label("", "muted", True)
        self.binding_hint.hide()
        self.direct_button = button("ACTIVAR BOTONES G", self.activate_g502, True)
        left.addWidget(self.direct_button)
        self.device_notice = label("", "muted", True)
        self.device_notice.hide()
        body.addWidget(self.assignment_sidebar)
        self.device_panels = QStackedWidget()
        self.device_panels.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        assignments = QWidget()
        av = QVBoxLayout(assignments)
        self.canvas = AssignmentCanvas()
        self.canvas.setMinimumSize(440, 280)
        self.canvas.target.connect(self.assign_target)
        self.canvas.target_context.connect(self.assign_target)
        self.canvas.selection_changed.connect(self.keyboard_target_selected)
        self.hero_art = self.canvas  # Base class color update; canvas remains the source of targets.
        self.hero_art.color = "#00b7ed"
        av.addWidget(self.canvas, 1)
        views = QHBoxLayout()
        views.addStretch()
        self.front_view_button = button("VISTA 1", lambda: self.change_view(False))
        self.side_view_button = button("VISTA 2", lambda: self.change_view(True))
        views.addWidget(self.front_view_button)
        views.addWidget(self.side_view_button)
        views.addStretch()
        av.addLayout(views)
        self.device_panels.addWidget(assignments)
        from .lighting import LightingPanel
        self.lighting_panel = LightingPanel(self)
        self.device_panels.addWidget(self.lighting_panel)
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
        for mode in ('once', 'hold', 'toggle', 'sequence', 'latch'):
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
        color_row = QHBoxLayout()
        color_row.addWidget(button('COLOR DE MACRO', self.choose_macro_color), 1)
        self.reset_color_button = button('RESTABLECER COLOR', self.reset_macro_color)
        self.reset_color_button.setToolTip('Restablecer el rojo del editor y los nombres blancos predeterminados.')
        color_row.addWidget(self.reset_color_button)
        options.addLayout(color_row)
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
        self.phase_combo.hide()  # Internal phase routing; all three are visible below.
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
        self.single_timeline_content = self.timeline_content
        self.single_timeline = self.timeline
        self.timeline_wrapper = QWidget()
        wrapper = QVBoxLayout(self.timeline_wrapper)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(self.single_timeline_content)
        self.sequence_container = QWidget()
        sections = QVBoxLayout(self.sequence_container)
        sections.setContentsMargins(0, 0, 0, 0)
        sections.setSpacing(18)
        self.phase_tracks, self.phase_layouts, self.phase_headers, self.phase_plus = {}, {}, {}, {}
        for title, phase in (('AL PULSAR', 'press'), ('AL MANTENER', 'hold'), ('AL SOLTAR', 'release')):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)
            heading = button(title, lambda checked=False, p=phase: self.select_phase(p))
            heading.setCheckable(True)
            heading.setFixedSize(176, 34)
            heading.setObjectName('mode')
            section_layout.addWidget(heading, 0, Qt.AlignmentFlag.AlignLeft)
            track = TimelineTrack()
            track.setMinimumHeight(90)
            track.moved.connect(lambda source, destination, p=phase: self.reorder_phase(p, source, destination))
            flow = FlowLayout(track)
            self.phase_tracks[phase], self.phase_layouts[phase], self.phase_headers[phase] = track, flow, heading
            section_layout.addWidget(track)
            sections.addWidget(section)
        wrapper.addWidget(self.sequence_container)
        self.sequence_container.hide()
        self.timeline_scroll.setWidget(self.timeline_wrapper)
        el.addWidget(self.timeline_scroll, 1)
        self.record_button = button("●  GRABAR PULSACIONES", self.toggle_record)
        self.record_button.setStyleSheet("background:#790028; padding:12px 20px")
        controls = QHBoxLayout()
        controls.addWidget(self.record_button)
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
        self.table.installEventFilter(self)
        self.table.viewport().installEventFilter(self)
        self.table.itemSelectionChanged.connect(self.highlight_steps)
        self.table.cellDoubleClicked.connect(self.edit_table_text)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_text_menu)
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
        self.apply_steps_button = button('APLICAR', self.apply_steps)
        bottom.addWidget(self.apply_steps_button)
        bottom.addWidget(button("GUARDAR", self.save_macro, True))
        bottom.addStretch()
        el.addLayout(bottom)
        layout.addWidget(self.editor, 1)
        self.mode_combo.currentIndexChanged.connect(self.mode_changed)
        self.stack.addWidget(page)

    def open_device(self, device):
        super().open_device(device)
        self.lighting_panel.load_device(device)
        self.canvas.configure(device)
        self.direct_button.setVisible((device.vid, device.pid) == ("046D", "C08B"))
        has_views = device.kind == 'mouse' and (device.vid, device.pid) in [('046D', 'C08B'), ('30FA', '0400')]
        self.front_view_button.setVisible(has_views)
        self.side_view_button.setVisible(has_views)
        self.keyboard_macro_button.setVisible(device.kind == 'keyboard')
        self.device_notice.setText('Solo F1–F12 pueden activar macros. Las demás teclas no se reasignan. La función original de Windows también permanece activa.' if device.kind == 'keyboard' else
            'G502: cierra G HUB y su agente antes de activar el control directo. Los cambios del ratón son temporales.' if (device.vid, device.pid) == ('046D', 'C08B') else
            (f'Windows informa {device.button_count} botones. ' if device.button_count else 'Windows no informa la cantidad de botones. ') +
            'Clic izquierdo y derecho protegidos. Las macros conservan la acción original del botón.')
        self.refresh_bindings()

    def identify_device_model(self):
        if not self.device:
            return
        from PySide6.QtWidgets import QFormLayout, QDialogButtonBox
        from .device_identity import save_identity
        dialog = QDialog(self)
        dialog.setWindowTitle('Identificar periférico')
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(f'USB {self.device.vid}:{self.device.pid}', 'eyebrow'))
        layout.addWidget(label('Indica el fabricante y modelo de este periférico. Se guardan solo para esta unidad; no cambia sus funciones.', 'muted', True))
        form = QFormLayout()
        maker = QLineEdit(self.device.manufacturer)
        model_name = self.device.name
        if maker.text() and model_name.casefold().startswith(maker.text().casefold() + ' '):
            model_name = model_name[len(maker.text()) + 1:]
        model = QLineEdit(model_name)
        maker.setMaxLength(80)
        model.setMaxLength(100)
        form.addRow('Fabricante', maker)
        form.addRow('Modelo', model)
        layout.addLayout(form)
        remember = QCheckBox('Recordar el modelo en otros puertos de este equipo')
        remember.setChecked(True)
        remember.setToolTip('Se reutiliza solo si hay una única unidad coincidente y ningún modelo ambiguo.')
        layout.addWidget(remember)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        def save():
            try:
                save_identity(self.device, maker.text(), model.text(), remember_ports=remember.isChecked())
            except (OSError, ValueError) as error:
                self.error(str(error))
                return
            dialog.accept()
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.device_title.setText(self.device.name)
            self.refresh_devices()
            self.status('Modelo identificado: ' + self.device.name)

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
        self.binding_list.blockSignals(True)
        self.binding_list.clear()
        names = {}
        name_colors = {}
        for macro in self.store.active["macros"]:
            slots = [b.get("slot", "") for b in self.store.active["bindings"] if self.device and b["device_id"] == self.device.id and b["macro_id"] == macro["id"]]
            self.assign_library.addItem(macro["name"] + ("    " + ", ".join(filter(None, slots)) if slots else ""))
            item = self.assign_library.item(self.assign_library.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, macro["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, macro['name'])
            item.setData(Qt.ItemDataRole.UserRole + 2, ', '.join(filter(None, slots)))
            item.setData(Qt.ItemDataRole.UserRole + 3, macro_badge_color(macro))
            item.setForeground(QColor(macro_label_color(macro)))
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
                paused = self.device.kind == 'keyboard' and not binding.get('enabled', True)
                self.binding_list.addItem(slot + " → " + macro["name"] + (' · DESACTIVADA' if paused else ''))
                self.binding_list.item(self.binding_list.count() - 1).setData(Qt.ItemDataRole.UserRole, slot)
                self.binding_list.item(self.binding_list.count() - 1).setForeground(QColor(macro_label_color(macro)))
                names[slot] = macro["name"]
                name_colors[slot] = macro_label_color(macro)
            self.canvas.disabled = {c["slot"] for c in self.store.active.get("disabled_controls", [])
                                    if c["device_id"] == self.device.id}
            self.canvas.names = names
            self.canvas.name_colors = name_colors
            self.canvas.paused = {b.get('slot') for b in self.store.active['bindings']
                                  if b['device_id'] == self.device.id and not b.get('enabled', True)}
            self.canvas.overlay.update()
            self.binding_hint.setText("Pulsa un objetivo para asignar una macro." if not names else "Asignaciones guardadas en este perfil.")
        self.filter_library(self.search_macros.text())
        self.binding_list.blockSignals(False)
        self.update_keyboard_macro_action()
        self.sync_g502()

    def keyboard_macro_binding(self, slot):
        from .keyboard_support import FUNCTION_KEYS
        if not self.device or self.device.kind != 'keyboard' or slot not in FUNCTION_KEYS:
            return None
        return next((b for b in self.store.active['bindings'] if b['device_id'] == self.device.id
                     and b['trigger'].get('type') == 'key' and b['trigger'].get('vk') == FUNCTION_KEYS[slot]), None)

    def keyboard_target_selected(self, slot):
        if self.device and self.device.kind == 'keyboard':
            self.canvas.selected = slot
            self.canvas.overlay.update()
            self.update_keyboard_macro_action()

    def binding_row_selected(self, row):
        item = self.binding_list.item(row)
        if item:
            self.keyboard_target_selected(item.data(Qt.ItemDataRole.UserRole))

    def update_keyboard_macro_action(self):
        if not hasattr(self, 'keyboard_macro_button'):
            return
        binding = self.keyboard_macro_binding(self.canvas.selected)
        self.keyboard_macro_button.setEnabled(binding is not None)
        self.keyboard_macro_button.setText('ACTIVAR MACRO' if binding and not binding.get('enabled', True) else 'DESACTIVAR MACRO')
        if binding:
            state = 'activa' if binding.get('enabled', True) else 'desactivada'
            self.binding_hint.setText(f'{self.canvas.selected}: macro {state}. La tecla conserva su función original.')

    def set_keyboard_macro_enabled(self, slot, enabled):
        from .keyboard_support import FUNCTION_KEYS
        binding = self.keyboard_macro_binding(slot)
        if not binding:
            self.status('Selecciona una F1–F12 que tenga una macro asignada.')
            return
        previous = binding.get('enabled', True)
        if not enabled:
            self.player.stop_owner((self.device.id, 'key', FUNCTION_KEYS[slot], None))
        binding['enabled'] = bool(enabled)
        if not self.persist():
            binding['enabled'] = previous
        self.refresh_bindings()
        self.status(f'{slot}: macro ' + ('activada' if binding['enabled'] else 'desactivada') + '. La tecla mantiene su función original.')

    def toggle_selected_keyboard_macro(self):
        binding = self.keyboard_macro_binding(self.canvas.selected)
        if binding:
            self.set_keyboard_macro_enabled(self.canvas.selected, not binding.get('enabled', True))

    def keyboard_target_menu(self, slot):
        self.keyboard_target_selected(slot)
        binding = self.keyboard_macro_binding(slot)
        menu = QMenu(self)
        assign = menu.addAction('Asignar macro…')
        toggle = menu.addAction('Activar macro' if binding and not binding.get('enabled', True) else 'Desactivar macro')
        toggle.setEnabled(binding is not None)
        menu.addSeparator()
        remove = menu.addAction('Quitar asignación')
        remove.setEnabled(binding is not None)
        action = menu.exec(QCursor.pos())
        if action == toggle and binding:
            self.set_keyboard_macro_enabled(slot, not binding.get('enabled', True))
        elif action == remove and binding:
            self.set_control_state(slot, False)
        elif action == assign:
            self.assign_macro_target(slot)

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
        names = {m['name'].strip().casefold() for m in self.store.active['macros']}
        number = 1
        while f'macro {number}' in names or str(number) in names:
            number += 1
        name = f'Macro {number}'
        dialog = TypeDialog(self, name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        macro = validate_macro({"id": new_id(), "name": dialog.macro_name, "mode": dialog.mode,
                                "events": [], "color": DEFAULT_MACRO_COLOR, 'custom_color': False, "standard_delay": True, "standard_delay_ms": 50})
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
            self.macro_color = macro.get("color", DEFAULT_MACRO_COLOR)
            self.macro_color_custom = macro.get('custom_color', self.macro_color.lower() != DEFAULT_MACRO_COLOR)
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

    def select_phase(self, phase):
        if self.recording:
            self.finish_recording()
        if phase != self.phase:
            self.phase_combo.setCurrentIndex(self.phase_combo.findData(phase))
        else:
            self.phase_headers[phase].setChecked(True)

    def phase_action_menu(self, phase):
        if self.recording:
            return
        self.select_phase(phase)
        self.action_menu()

    def select_phase_step(self, phase, row):
        if phase is not None:
            self.select_phase(phase)
        self.select_step(row)

    def delete_phase_step(self, phase, row):
        if phase is not None:
            self.select_phase(phase)
        self.delete_timeline_step(row)

    def edit_phase_delay(self, phase, row, value):
        if phase is not None:
            self.select_phase(phase)
        self.edit_timeline_delay(row, value)

    def reorder_phase(self, phase, source, destination):
        self.select_phase(phase)
        self.reorder_timeline(source, destination)

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
        self.phase_combo.hide()
        self.sequence_container.setVisible(mode == 'sequence')
        self.single_timeline_content.setVisible(mode != 'sequence')
        self.mode_description.setText({"once": "Se ejecuta una vez al pulsar el botón asignado.",
            "hold": "Se repite mientras mantienes pulsado el botón. Se detiene al soltar.",
            "toggle": "Una pulsación inicia el bucle. La siguiente pulsación lo detiene.",
            "sequence": "Configura Al pulsar, Al mantener y Al soltar. Cada fase tiene su propio botón +.",
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
        self.read_draft()
        standard = self.delay_ms.value() if self.standard_delay.isChecked() and self.mode_combo.currentData() != 'latch' else None
        self.draft = editor_events(self.draft, standard, trim_leading=True)
        self.phase_drafts = {phase: editor_events(events, standard, trim_leading=True) for phase, events in self.phase_drafts.items()}
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
                     "color": self.macro_color, 'custom_color': self.macro_color_custom, "events": copy.deepcopy(self.read_draft())}
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
        from .keyboard_support import FUNCTION_KEYS
        if self.device and self.device.kind == 'keyboard' and (slot not in FUNCTION_KEYS or disabled):
            self.status('En el teclado solo se asignan macros a F1–F12; las teclas no se desactivan.')
            return
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
        from .keyboard_support import FUNCTION_KEYS
        if self.device and self.device.kind == 'keyboard' and slot not in FUNCTION_KEYS:
            self.status('Solo F1–F12 admiten asignación de macros.')
            return
        if self.device and self.device.kind == 'keyboard' and not macro_id:
            return self.keyboard_target_menu(slot)
        from .safety import PROTECTED_SLOTS
        if slot in PROTECTED_SLOTS:
            self.status("Clic izquierdo y derecho protegidos: no admiten macros ni desactivación.")
            return
        if not macro_id and self.device:
            self.canvas.selected = slot
            self.canvas.overlay.update()
            menu = QMenu(self)
            default = menu.addAction("Usar predeterminada")
            disable = menu.addAction("Desactivar") if self.device.kind != 'keyboard' else None
            menu.addSeparator()
            assign = menu.addAction("Asignar macro…")
            action = menu.exec(QCursor.pos())
            if action == default:
                return self.set_control_state(slot, False)
            if disable is not None and action == disable:
                return self.set_control_state(slot, True)
            if action != assign:
                return
        self.assign_macro_target(slot, macro_id)

    def assign_macro_target(self, slot, macro_id=""):
        if self.device and self.device.kind == 'mouse' and self.device.button_count is not None and (self.device.vid, self.device.pid) != ('046D', 'C08B'):
            minimum = {'Principal': 1, 'Secundario': 2, 'Central': 3, 'Lateral 4': 4, 'Lateral 5': 5}.get(slot)
            if minimum is None or minimum > self.device.button_count:
                self.status('Ese botón no está disponible en este ratón.')
                return
        from .keyboard_support import FUNCTION_KEYS
        if self.device and self.device.kind == 'keyboard' and slot not in FUNCTION_KEYS:
            self.status('Solo F1–F12 admiten asignación de macros.')
            return
        if self.device and self.device.kind == 'keyboard':
            self.keyboard_target_selected(slot)
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
            if self.device.kind == 'keyboard' and binding['trigger'] != {'type': 'key', 'vk': FUNCTION_KEYS[slot], 'mods': []}:
                return self.error('La asignación debe corresponder a la tecla de función seleccionada.')
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
        super().render_event(row, event)
        spin = self.table.cellWidget(row, 3)
        if event['type'] == 'text':
            spin.setValue(event.get('char_delay_ms', 0))
            spin.setToolTip('Retardo entre letras; la primera se escribe inmediatamente.')
        if event['type'] == 'wait':
            self.table.item(row, 1).setText('Retardo')
        spin.setEnabled(not self.standard_delay.isChecked() and self.mode_combo.currentData() != 'latch')
        spin.installEventFilter(self)
        spin.lineEdit().installEventFilter(self)
        spin.lineEdit().selectionChanged.connect(lambda r=row: self.table.selectRow(r))
        if not self.timeline_pending:
            self.timeline_pending = True
            self.timeline_timer.start(0)

    def render_events(self):
        if not self.recording and not self._editor_loading and self.mode_combo.currentData() != 'latch':
            self.draft = editor_events(self.draft, self.delay_ms.value() if self.standard_delay.isChecked() else None)
        super().render_events()
        if hasattr(self, "timeline"):
            self.render_timeline()

    def read_draft(self):
        for row, event in enumerate(self.draft):
            spin = self.table.cellWidget(row, 3)
            if spin:
                event['char_delay_ms' if event['type'] == 'text' else 'delay_ms'] = spin.value()
        return self.draft

    def apply_steps(self):
        if self.recording:
            return
        self.read_draft()
        self.render_events()

    def edit_table_text(self, row, column=0):
        if self.recording or not 0 <= row < len(self.draft) or self.draft[row]['type'] != 'text':
            return
        text, accepted = QInputDialog.getMultiLineText(self, 'Editar texto', 'Texto de la acción', self.draft[row]['text'])
        if accepted and text:
            if len(text) > 5000 or '\x00' in text:
                return self.error('El texto debe contener entre 1 y 5000 caracteres, sin caracteres nulos.')
            self.read_draft()
            self.draft[row]['text'] = text
            self.render_events()
            self.table.selectRow(row)

    def table_text_menu(self, position):
        item = self.table.itemAt(position)
        if item is None or self.recording or self.draft[item.row()]['type'] != 'text':
            return
        self.table.selectRow(item.row())
        menu = QMenu(self)
        edit = menu.addAction('Editar')
        if menu.exec(self.table.viewport().mapToGlobal(position)) == edit:
            self.edit_table_text(item.row())

    def update_stats(self, *_):
        total = 0
        for row, event in enumerate(self.draft):
            spin = self.table.cellWidget(row, 3)
            if spin:
                total += spin.value() * (max(0, len(event['text'])-1) if event['type'] == 'text' else 1)
        self.sequence_stats.setText(f'{len(self.draft)} pasos · {total / 1000:.2f} s')

    def highlight_steps(self):
        rows = {index.row() for index in self.table.selectedIndexes()}
        if not hasattr(self, 'timeline'):
            return
        for i in range(self.timeline.count()):
            chip = self.timeline.itemAt(i).widget()
            if isinstance(chip, TimelineBlock):
                chip.is_selected = chip.row in rows
                chip.update()

    def delete_timeline_step(self, row):
        if self.recording:
            return
        self.table.selectRow(row)
        self.remove_step()

    def remove_step(self):
        if self.recording:
            return
        self.read_draft()
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            del self.draft[row]
        if any(event['type'] != 'wait' for event in self.draft):
            while self.draft and self.draft[0]['type'] == 'wait':
                self.draft.pop(0)
            while self.draft and self.draft[-1]['type'] == 'wait':
                self.draft.pop()
        self.render_events()

    def render_timeline(self):
        self.timeline_timer.stop()
        self.timeline_pending = False
        if not hasattr(self, "timeline"):
            return
        sequence = self.mode_combo.currentData() == 'sequence'
        self.sequence_container.setVisible(sequence)
        self.single_timeline_content.setVisible(not sequence)
        if sequence:
            self.timeline, self.timeline_content = self.phase_layouts[self.phase], self.phase_tracks[self.phase]
            for phase in ('press', 'hold', 'release'):
                self.phase_headers[phase].setChecked(phase == self.phase)
                self.render_track(self.phase_layouts[phase], self.draft if phase == self.phase else self.phase_drafts[phase], phase)
        else:
            self.timeline, self.timeline_content = self.single_timeline, self.single_timeline_content
            self.render_track(self.timeline, self.draft)
        self.highlight_steps()

    def render_track(self, timeline, events, phase=None):
        while timeline.count():
            item = timeline.takeAt(timeline.count() - 1)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        standard = self.standard_delay.isChecked() or self.mode_combo.currentData() == "latch"
        tokens = ([(row, "delay" if event["type"] == "wait" else "action", event)
                   for row, event in enumerate(events)] if standard else timeline_tokens(events))
        for index, (row, token_kind, event) in enumerate(tokens):
            kind = event["type"]
            if standard and kind == 'wait':
                continue
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
            chip.selected.connect(lambda row, p=phase: self.select_phase_step(p, row))
            chip.delete_requested.connect(lambda row, p=phase: self.delete_phase_step(p, row))
            chip.delay_changed.connect(lambda row, value, p=phase: self.edit_phase_delay(p, row, value))
            timeline.addWidget(chip)
        plus = button('+', self.action_menu if phase is None else lambda checked=False, p=phase: self.phase_action_menu(p))
        plus.setFixedSize(48, 48)
        plus.setStyleSheet("background:#333; font-size:30px; font-weight:300; padding:0; border-radius:0")
        timeline.addWidget(plus)
        if phase is not None:
            self.phase_plus[phase] = plus
        if not events:
            timeline.addWidget(label("INICIAR AHORA", "muted"))

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
            actions = [event for event in self.draft if event['type'] != 'wait']
            start = sum(e['type'] != 'wait' for e in self.draft[:source])
            end = sum(e['type'] != 'wait' for e in self.draft[:destination])
            event = actions.pop(start)
            actions.insert(end - (end > start), event)
            self.draft = actions
        else:
            if self.draft[source]['type'] == 'wait':
                destination = max(1, min(destination, len(self.draft)-1))
            self.draft = reorder_tokens(self.draft, source, destination)
            while self.draft and self.draft[0]['type'] == 'wait':
                self.draft.pop(0)
            while self.draft and self.draft[-1]['type'] == 'wait':
                self.draft.pop()
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
            self.macro_color_custom = True
            self.render_timeline()

    def reset_macro_color(self):
        self.macro_color = DEFAULT_MACRO_COLOR
        self.macro_color_custom = False
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
        if self.mode_combo.currentData() == 'sequence':
            control = self.phase_plus.get(self.phase, control)
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
            dialog = DelayDialog(self) if title == 'Retardo' else AddActionDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.append_actions(dialog.events())
        elif title == "Texto y emojis":
            text, ok = QInputDialog.getMultiLineText(self, "Texto y emojis", "Texto que escribirá la macro")
            if ok and text:
                self.append_actions([{"type": "text", "text": text, "delay_ms": 0, 'char_delay_ms': 0}])
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
        if events and all(event['type'] == 'wait' for event in events):
            if sum(event['type'] != 'wait' for event in self.draft) < 2:
                return self.error('Añade primero dos acciones para colocar el retardo entre ellas.')
            position = max(1, min(self.table.currentRow()+1, len(self.draft)-1))
            self.draft[position:position] = events
        else:
            self.draft.extend(events)
        self.render_events()
