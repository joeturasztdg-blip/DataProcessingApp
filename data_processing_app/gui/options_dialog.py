from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QRadioButton, QComboBox, QLineEdit,
    QLabel, QGroupBox, QDialog, QScrollArea, QCheckBox)

class OptionsDialog(QDialog):
    def __init__(self, schema, parent=None, title="Options"):
        super().__init__(parent)
        self.schema = schema
        self.controls = {}
        self.setWindowTitle(title)
        self.resize(500, 500)
        self._dynamic_multis = []
        self._controls_widgets = {}

        self.main_layout = QVBoxLayout(self)
        self._build_ui()
        self.main_layout.addStretch()
        self._add_dialog_buttons()
    # ---------------- UI Assembly ----------------
    def _build_ui(self):
        builders = {
            "radio": self._build_radio_group,
            "toggle_select": self._build_toggle_select,
            "radio_with_extras": self._build_radio_with_extras,
            "select": self._build_select,
            "multi_select": self._build_multi_select}
        for cfg in self.schema:
            builder = builders.get(cfg["type"])
            if not builder:
                raise ValueError(f"Unsupported schema type: {cfg['type']}")
            self.main_layout.addWidget(builder(cfg))
        self._refresh_dynamic_controls()


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
        layout = QHBoxLayout(box)
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
    
    def _build_select(self, cfg):
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        combo = QComboBox()
        for opt in cfg["options"]:
            label, value = (opt["label"], opt["value"]) if isinstance(opt, dict) else opt
            combo.addItem(label, value)

        default = cfg.get("default")
        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        layout.addWidget(combo)

        self._controls_widgets[cfg["key"]] = combo
        self.controls[cfg["key"]] = lambda: combo.currentData()

        combo.currentIndexChanged.connect(self._refresh_dynamic_controls)
        return box

    def _build_multi_select(self, cfg):
        box = QGroupBox(cfg["label"])
        outer = QVBoxLayout(box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(inner)

        checkboxes = []

        def set_options(options):
            nonlocal checkboxes
            currently_checked = {cb._value for cb in checkboxes if cb.isChecked()}

            while inner_layout.count():
                item = inner_layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

            checkboxes = []
            default = set(cfg.get("default", [])) | currently_checked

            for opt in options or []:
                label, value = (opt["label"], opt["value"]) if isinstance(opt, dict) else opt
                cb = QCheckBox(str(label))
                cb._value = value
                cb.setChecked(value in default)
                inner_layout.addWidget(cb)
                checkboxes.append(cb)

            inner_layout.addStretch()

        set_options(cfg.get("options", []))

        def read():
            return [cb._value for cb in checkboxes if cb.isChecked()]

        self.controls[cfg["key"]] = read

        depends_on = cfg.get("depends_on")
        options_provider = cfg.get("options_provider")
        if depends_on and callable(options_provider):
            self._dynamic_multis.append((depends_on, set_options, read, options_provider))

        return box

    def _refresh_dynamic_controls(self):
        for depends_on_key, set_options, _read, options_fn in getattr(self, "_dynamic_multis", []):
            dep_widget = self._controls_widgets.get(depends_on_key)
            if dep_widget is None:
                continue
            current_value = dep_widget.currentData()
            new_options = options_fn(current_value)
            set_options(new_options)

    def get_results(self):
        return {key: getter() for key, getter in self.controls.items()}
