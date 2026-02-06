
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QRadioButton, QComboBox, QLineEdit,
    QLabel, QInputDialog, QGroupBox, QDialog, QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from gui.models import DragDropPandasModel
from gui.table import DragDropTableView


class PreviewDialog(QDialog):
    def __init__(self, dataframe, parent=None, title="Preview"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1500, 750)
        self.model = DragDropPandasModel(dataframe)
        layout = QVBoxLayout(self)
        self.table_view = DragDropTableView()
        self.table_view.setModel(self.model)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table_view)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        self.table_view.verticalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    def get_dataframe(self):
        return self.model.get_dataframe()

    def keyPressEvent(self, event: QKeyEvent):
        model = self.table_view.model()
        sel = self.table_view.selectedIndexes()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and event.key() == Qt.Key.Key_C:
            model.copy_selection(sel)
            return
        if ctrl and event.key() == Qt.Key.Key_V:
            start_index = sel[0] if sel else model.index(0, 0)
            model.paste_at(start_index)
            return
        if ctrl and event.key() == Qt.Key.Key_Z:
            model.undo()
            return
        if (ctrl and event.key() == Qt.Key.Key_Y) or (
            ctrl and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Z):
            model.redo()
            return
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if sel:
                model.clear_selection(sel)
            return
        super().keyPressEvent(event)

    def show_header_context_menu(self, pos):
        model = self.table_view.model()
        menu = QMenu(self)
        sender = self.sender()
        # ---------- COLUMN HEADER ----------
        if sender == self.table_view.horizontalHeader():
            col = sender.logicalIndexAt(pos)
            if col < 0:
                return
            menu.addAction(
                "Insert Column Left",
                lambda: model.insert_column_left(col))
            menu.addAction(
                "Insert Column Right",
                lambda: model.insert_column_right(col))
            menu.addSeparator()
            menu.addAction(
                "Rename Column",
                lambda: self.rename_column_dialog(col))
            menu.addSeparator()
            menu.addAction(
                "Delete Column",
                lambda: model.delete_column(col))
            menu.exec(sender.mapToGlobal(pos))
            return
        # ---------- ROW HEADER ----------
        if sender == self.table_view.verticalHeader():
            row = sender.logicalIndexAt(pos)
            if row < 0:
                return
            menu.addAction(
                "Insert Row Above",
                lambda: model.insert_row_above(row))
            menu.addAction(
                "Insert Row Below",
                lambda: model.insert_row_below(row))
            menu.addSeparator()
            menu.addAction(
                "Delete Row",
                lambda: model.delete_row(row))
            menu.exec(sender.mapToGlobal(pos))
            return

    def rename_column_dialog(self, col: int):
        model = self.table_view.model()
        current = str(model.df.columns[col])
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Column",
            "Column name:",
            text=current)
        if not ok or not new_name.strip():
            return
        model.rename_column(col, new_name)
        
    def show_context_menu(self, pos):
        view = self.table_view
        model = view.model()
        indexes = view.selectedIndexes()
        menu = QMenu(self)
        menu.addAction("Copy", lambda: model.copy_selection(indexes))
        menu.addAction(
            "Paste",
            lambda: model.paste_at(indexes[0] if indexes else model.index(0, 0)))
        menu.addSeparator()
        menu.addAction("Undo", model.undo)
        menu.addAction("Redo", model.redo)
        menu.addSeparator()
        menu.addAction(
            "Clear",
            lambda: model.clear_selection(indexes))
        menu.exec(view.viewport().mapToGlobal(pos))

class OptionsDialog(QDialog):
    def __init__(self, schema, parent=None, title="Options"):
        super().__init__(parent)
        self.schema = schema
        self.controls = {}
        self.setWindowTitle(title)
        self.resize(500, 500)

        self.main_layout = QVBoxLayout(self)
        self._build_ui()
        self.main_layout.addStretch()
        self._add_dialog_buttons()
    # ---------------- UI Assembly ----------------
    def _build_ui(self):
        builders = {
            "radio": self._build_radio_group,
            "toggle_select": self._build_toggle_select,
            "radio_with_extras": self._build_radio_with_extras}
        for cfg in self.schema:
            builder = builders.get(cfg["type"])
            if not builder:
                raise ValueError(f"Unsupported schema type: {cfg['type']}")
            self.main_layout.addWidget(builder(cfg))

    def _add_dialog_buttons(self):
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_ok = QPushButton("Continue")
        btn_ok.setDefault(True)
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        self.main_layout.addLayout(btns)
    # ---------------- Helpers ----------------
    def _get_checked_value(self, radios, default=None):
        return next((r._value for r in radios if r.isChecked()), default)

    def _create_radio(self, label, value, checked=False):
        rb = QRadioButton(label)
        rb._value = value
        rb.setChecked(checked)
        return rb

    def _build_radio_buttons(self, layout, options, default=None):
        radios = []
        for opt in options:
            label, value = (opt["label"], opt["value"]) if isinstance(opt, dict) else opt
            rb = self._create_radio(label, value, value == default)
            layout.addWidget(rb)
            radios.append(rb)
        return radios
    # ---------------- Extras Controller ----------------
    def _build_extras_controller(self, layout, extras_cfg, is_enabled_fn, get_value_fn, layout_override=None):
        extra_widgets = {}

        for opt_value, extras in extras_cfg.items():
            widgets = []
            target_layout = layout_override.get(opt_value, layout) if layout_override else layout
            for extra in extras if isinstance(extras, list) else [extras]:
                if extra["type"] == "text":
                    row = QHBoxLayout()
                    lbl = QLabel(extra["label"])
                    edit = QLineEdit()
                    edit.setEnabled(False)
                    row.addWidget(lbl)
                    row.addWidget(edit)
                    target_layout.addLayout(row)
                    widgets.append((extra["key"], edit))
            extra_widgets[opt_value] = widgets

        def update_state():
            enabled = is_enabled_fn()
            current = get_value_fn()
            for opt, widgets in extra_widgets.items():
                for _, w in widgets:
                    w.setEnabled(enabled and opt == current)

        def read_extras(result):
            for key, widget in extra_widgets.get(get_value_fn(), []):
                result[key] = widget.text().strip()
                
        return update_state, read_extras
    # ---------------- Builders ----------------
    def _build_radio_group(self, cfg):
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        radios = self._build_radio_buttons(layout, cfg["options"], cfg.get("default"))
        self.controls[cfg["key"]] = lambda: self._get_checked_value(radios)
        return box

    def _build_toggle_select(self, cfg):
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        rb_off = self._create_radio(cfg["toggle"]["off"], "off")
        rb_on = self._create_radio(cfg["toggle"]["on"], "on")
        rb_off.setChecked(cfg.get("default", "off") == "off")
        rb_on.setChecked(cfg.get("default", "off") == "on")
        layout.addWidget(rb_off)
        row = QHBoxLayout()
        row.addWidget(rb_on)

        combo = QComboBox()
        for opt in cfg["options"]:
            label, value = (opt["label"], opt["value"]) if isinstance(opt, dict) else (opt, opt)
            combo.addItem(label, value)
        row.addWidget(combo)
        layout.addLayout(row)

        update_extras, read_extras = self._build_extras_controller(
            layout,
            cfg.get("extra", {}),
            is_enabled_fn=rb_on.isChecked,
            get_value_fn=combo.currentData)

        def update_state():
            combo.setEnabled(rb_on.isChecked())
            update_extras()

        rb_on.toggled.connect(update_state)
        combo.currentIndexChanged.connect(update_state)
        update_state()

        def read():
            if not rb_on.isChecked():
                return {"enabled": False}
            result = {"enabled": True, "value": combo.currentData()}
            read_extras(result)
            return result

        self.controls[cfg["key"]] = read
        return box

    def _build_radio_with_extras(self, cfg):
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        radios = []
        extras_layout_map = {}
        for opt in cfg["options"]:
            rb = self._create_radio(opt["label"], opt["value"])
            layout.addWidget(rb)
            radios.append(rb)
            if opt.get("extras"):
                spacer = QWidget()
                spacer_layout = QVBoxLayout(spacer)
                spacer_layout.setContentsMargins(25, 0, 0, 0)
                layout.addWidget(spacer)
                extras_layout_map[opt["value"]] = spacer_layout
        default = cfg.get("default")
        for rb in radios:
            rb.setChecked(rb._value == default)
        get_selected = lambda: self._get_checked_value(radios)
        extras_cfg = {
            opt["value"]: opt["extras"]
            for opt in cfg["options"]
            if opt.get("extras")}

        update_extras, read_extras = self._build_extras_controller(
            layout,
            extras_cfg,
            is_enabled_fn=lambda: True,
            get_value_fn=get_selected,
            layout_override=extras_layout_map)

        for rb in radios:
            rb.toggled.connect(update_extras)
        update_extras()

        def read():
            result = {"value": get_selected()}
            read_extras(result)
            return result

        self.controls[cfg["key"]] = read
        return box
    
    def get_results(self):
        return {key: getter() for key, getter in self.controls.items()}
