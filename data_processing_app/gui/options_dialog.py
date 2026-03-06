from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QRadioButton, QComboBox,
    QLineEdit, QLabel, QGroupBox, QDialog, QScrollArea, QCheckBox,
    QToolButton, QFrame, QStyle, QStackedLayout, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView
)

class OptionsDialog(QDialog):
    def __init__(self, schema: list[dict], parent=None, title: str = "Options"):
        super().__init__(parent)
        self.schema = schema
        self.controls: Dict[str, Callable[[], Any]] = {}

        self.setWindowTitle(title)
        self.setMinimumSize(400,400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._dynamic_multis: list[
            tuple[str, Callable[[list], None], Callable[[], list], Callable[[Any], list]]
        ] = []
        self._controls_widgets: Dict[str, QWidget] = {}
        self._number_widgets: Dict[str, Any] = {}
        self._item_split_total: int | None = None
        self._syncing_item_split: bool = False

        # ---- pager state (for showing 2 "file" multi-selects at a time) ----
        self._pagers: dict[str, dict] = {}
        self._active_pager_group: str | None = None
        
        self._multi_rows: dict[str, dict[object, QCheckBox]] = {}   # key -> value -> checkbox
        self._mutex_groups: dict[str, list[str]] = {}              # group -> list of multi_select keys
        
        self._required_keys: set[str] = set()
        self._ok_button: QPushButton | None = None

        self.main_layout = QVBoxLayout(self)
        self._build_ui()
        self.main_layout.addStretch()
        self._add_dialog_buttons()

    # ---------------- UI assembly ----------------
    def _builders(self):
        return {
            "radio": self._build_radio,
            "radio_with_extras": self._build_radio_with_extras,
            "select": self._build_select,
            "text": self._build_text,
            "compact_select": self._build_compact_select,
            "compact_select_row": self._build_compact_select_row,
            "toggle_select": self._build_toggle_select,
            "switch_with_extras": self._build_switch_with_extras,
            "multi_select": self._build_multi_select,
            "number": self._build_number,
            "range_select": self._build_range_select,
            "table_preview": self._build_table_preview,
            "section": self._build_section,
        }
    
    def _build_ui(self) -> None:
        builders = self._builders()

        inserted_pager_groups: set[str] = set()
        active_group: str | None = None

        for cfg in self.schema:
            group = cfg.get("page_group")
            group = str(group) if group else None

            # If we are leaving a paged block, insert pager row *now* (between files and next section)
            if active_group and (group != active_group):
                if active_group not in inserted_pager_groups:
                    self._ensure_pager_group(active_group)
                    self.main_layout.addLayout(self._build_pager_row(active_group))
                    inserted_pager_groups.add(active_group)
                active_group = None

            # Track entering/continuing a paged block
            if group:
                active_group = group

            t = cfg.get("type")
            builder = builders.get(t)
            if not builder:
                raise ValueError(f"Unsupported schema type: {t!r}")
            self.main_layout.addWidget(builder(cfg))

        # If schema ends while still inside a paged block, insert pager at end of that block
        if active_group and active_group not in inserted_pager_groups:
            self._ensure_pager_group(active_group)
            self.main_layout.addLayout(self._build_pager_row(active_group))
            inserted_pager_groups.add(active_group)

        self._refresh_dynamic_controls()
        self._refresh_required_state()
    
    def _add_dialog_buttons(self) -> None:
        btns = QHBoxLayout()
        btns.addStretch()

        btn_cancel = QPushButton("Cancel")
        self._ok_button = QPushButton("Continue")
        self._ok_button.setDefault(True)

        btn_cancel.clicked.connect(self.reject)
        self._ok_button.clicked.connect(self.accept)

        btns.addWidget(btn_cancel)
        btns.addWidget(self._ok_button)
        self.main_layout.addLayout(btns)

        self._refresh_required_state()

    # ----------------Helpers----------------
    @staticmethod
    def _iter_options(options: Optional[Iterable]) -> Iterable[Tuple[str, Any]]:
        for opt in options or []:
            if isinstance(opt, dict):
                yield str(opt.get("label", "")), opt.get("value")
            elif isinstance(opt, (list, tuple)) and len(opt) == 2:
                label, value = opt
                yield str(label), value
            else:
                yield str(opt), opt

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    @staticmethod
    def _get_checked_value(radios: list[QRadioButton], default=None):
        return next((r._value for r in radios if r.isChecked()), default)

    def _make_combo(self, *, options, default=None, enabled: bool = True, visible: bool = True) -> QComboBox:
        combo = QComboBox()
        for label, value in self._iter_options(options):
            combo.addItem(label, value)

        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        combo.setEnabled(bool(enabled))
        combo.setVisible(bool(visible))
        return combo

    def _make_radio(self, label: str, value: Any, checked: bool = False) -> QRadioButton:
        rb = QRadioButton(label)
        rb._value = value
        rb.setChecked(bool(checked))
        return rb

    def _make_radio_group(
        self,
        *,
        parent_layout,
        options,
        default=None,
        orientation: str = "horizontal",
    ) -> tuple[list[QRadioButton], Callable[[], Any]]:
        if orientation == "vertical":
            radios: list[QRadioButton] = []
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                parent_layout.addWidget(rb)
                radios.append(rb)
        else:
            row = QHBoxLayout()
            parent_layout.addLayout(row)
            radios = []
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                row.addWidget(rb)
                radios.append(rb)
            row.addStretch()

        get_value = lambda: self._get_checked_value(radios, default=default)
        return radios, get_value

    def _auto_resize_to_contents(self) -> None:
        self.main_layout.activate()
        hint = self.sizeHint()
        screen = self.screen()
        if screen is None:
            self.adjustSize()
            return
        avail = screen.availableGeometry()
        w = min(hint.width(), max(300, avail.width() - 40))
        h = min(hint.height(), max(200, avail.height() - 80))
        self.resize(w, h)

    def _is_cfg_visible(self, cfg: dict) -> bool:
        rule = cfg.get("visible_if")
        if not rule:
            return True

        dep_key = rule.get("key")
        op = (rule.get("op") or "==").strip()
        rhs = rule.get("value")

        dep_getter = self.controls.get(dep_key)
        dep_val = dep_getter() if callable(dep_getter) else None

        try:
            if op == "==":
                return dep_val == rhs
            if op == "!=":
                return dep_val != rhs
            if op == "<=":
                return dep_val <= rhs
            if op == "<":
                return dep_val < rhs
            if op == ">=":
                return dep_val >= rhs
            if op == ">":
                return dep_val > rhs
        except Exception:
            return True

        return True

    def _update_mutex_group(self, group: str) -> None:
        keys = self._mutex_groups.get(group) or []
        if not keys:
            return

        owner: dict[Any, str] = {}
        selected_by_key: dict[str, set[Any]] = {}

        # Determine which control owns each selected value
        for k in keys:
            getter = self.controls.get(k)
            selected = set(getter() if callable(getter) else [])
            selected_by_key[k] = selected
            for v in selected:
                owner.setdefault(v, k)

        # Apply: show checkbox for available items; show X (in same left slot) for blocked items
        for k in keys:
            rows = self._multi_rows.get(k) or {}
            mine = selected_by_key.get(k, set())

            for v, (cb, x, stack) in rows.items():
                if v in mine:
                    cb.setEnabled(True)
                    stack.setCurrentWidget(cb)
                    continue

                o = owner.get(v)
                if o is not None and o != k:
                    cb.setChecked(False)
                    cb.setEnabled(False)
                    stack.setCurrentWidget(x)
                else:
                    cb.setEnabled(True)
                    stack.setCurrentWidget(cb)
    
    def _register_required_key(self, key: str) -> None:
        if key:
            self._required_keys.add(str(key))

    def _is_missing_required_value(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() in ("", "__select__")
        return False

    def _refresh_required_state(self) -> None:
        if self._ok_button is None:
            return

        for key in self._required_keys:
            getter = self.controls.get(key)
            if not callable(getter):
                continue
            if self._is_missing_required_value(getter()):
                self._ok_button.setEnabled(False)
                return

        self._ok_button.setEnabled(True)
    # ---------------- Builders ----------------
    def _build_text(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            layout.addWidget(QLabel(label_text))

        edit = QLineEdit()
        edit.setText(str(cfg.get("default", "")))

        placeholder = cfg.get("placeholder")
        if placeholder is not None:
            edit.setPlaceholderText(str(placeholder))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(edit)
        row.addStretch()

        layout.addLayout(row)

        key = cfg["key"]
        self.controls[key] = lambda: edit.text().strip()
        self._controls_widgets[key] = container

        if cfg.get("required"):
            self._register_required_key(key)

        edit.textChanged.connect(self._refresh_required_state)
        edit.textChanged.connect(self._refresh_dynamic_controls)

        return container
    
    def _build_extras_controller(
        self,
        *,
        base_layout,
        extras_cfg: dict,
        is_enabled_fn: Callable[[], bool],
        get_value_fn: Callable[[], Any],
        layout_override: Optional[dict] = None,
    ) -> tuple[Callable[[], None], Callable[[dict], None]]:
        extra_widgets: dict[Any, list[tuple[str, QWidget]]] = {}

        for opt_value, extras in (extras_cfg or {}).items():
            widgets: list[tuple[str, QWidget]] = []
            target_layout = layout_override.get(opt_value, base_layout) if layout_override else base_layout

            for extra in extras if isinstance(extras, list) else [extras]:
                etype = extra.get("type")
                if etype == "text":
                    row = QHBoxLayout()
                    row.addWidget(QLabel(extra.get("label", "")))

                    edit = QLineEdit()
                    edit.setText(str(extra.get("default", "")))
                    edit.setEnabled(False)

                    placeholder = extra.get("placeholder")
                    if placeholder is not None:
                        edit.setPlaceholderText(str(placeholder))

                    row.addWidget(edit)
                    target_layout.addLayout(row)
                    widgets.append((extra["key"], edit))

                elif etype == "select":
                    row = QHBoxLayout()
                    row.addWidget(QLabel(extra.get("label", "")))

                    combo = self._make_combo(
                        options=extra.get("options") or [],
                        default=extra.get("default"),
                        enabled=False,
                        visible=True,
                    )
                    row.addWidget(combo)
                    target_layout.addLayout(row)
                    widgets.append((extra["key"], combo))

                else:
                    raise ValueError(f"Unsupported extra type: {etype!r}")

            extra_widgets[opt_value] = widgets

        def update_state() -> None:
            enabled = bool(is_enabled_fn())
            current = get_value_fn()
            for opt, widgets in extra_widgets.items():
                active = False
                if enabled:
                    active = (opt == "__enabled__") or (opt == current)
                for _, w in widgets:
                    w.setEnabled(active)

        def read_extras(result: dict) -> None:
            current = get_value_fn()
            widgets_to_read: list[tuple[str, QWidget]] = []
            widgets_to_read += extra_widgets.get(current, [])
            widgets_to_read += extra_widgets.get("__enabled__", [])

            for key, widget in widgets_to_read:
                if isinstance(widget, QLineEdit):
                    result[key] = widget.text().strip()
                elif isinstance(widget, QComboBox):
                    result[key] = widget.currentData()

        return update_state, read_extras

    def _build_radio(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        radios, get_selected = self._make_radio_group(
            parent_layout=layout,
            options=cfg.get("options", []),
            default=cfg.get("default"),
            orientation="horizontal",
        )

        self._controls_widgets[cfg["key"]] = box
        self.controls[cfg["key"]] = get_selected

        for rb in radios:
            rb.toggled.connect(self._refresh_dynamic_controls)

        return box

    def _build_radio_with_extras(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        options = cfg.get("options", []) or []
        default = cfg.get("default")
        orientation = (cfg.get("orientation") or "vertical").lower()

        radios: list[QRadioButton] = []

        if orientation == "horizontal":
            row = QHBoxLayout()
            layout.addLayout(row)
            for opt in options:
                if not isinstance(opt, dict):
                    raise ValueError("radio_with_extras expects dict options with label/value/extras")
                rb = self._make_radio(
                    str(opt.get("label", "")),
                    opt.get("value"),
                    checked=(opt.get("value") == default),
                )
                row.addWidget(rb)
                radios.append(rb)
            row.addStretch()
        else:
            for opt in options:
                if not isinstance(opt, dict):
                    raise ValueError("radio_with_extras expects dict options with label/value/extras")
                rb = self._make_radio(
                    str(opt.get("label", "")),
                    opt.get("value"),
                    checked=(opt.get("value") == default),
                )
                layout.addWidget(rb)
                radios.append(rb)

        get_selected = lambda: self._get_checked_value(radios, default=default)

        # ---- shared extras support ----
        shared_extras = cfg.get("shared_extras")
        disable_value = cfg.get("disable_value", "none")

        if shared_extras:
            spacer = QWidget()
            extras_layout = QVBoxLayout(spacer)
            extras_layout.setContentsMargins(25, 0, 0, 0)
            layout.addWidget(spacer)

            extras_cfg = {"__enabled__": shared_extras}

            update_extras, read_extras = self._build_extras_controller(
                base_layout=extras_layout,
                extras_cfg=extras_cfg,
                is_enabled_fn=lambda: get_selected() != disable_value,
                get_value_fn=get_selected,
                layout_override=None,
            )

            for rb in radios:
                rb.toggled.connect(update_extras)
                rb.toggled.connect(self._refresh_dynamic_controls)
            update_extras()

            def read():
                result = {"value": get_selected()}
                read_extras(result)
                return result

            self.controls[cfg["key"]] = read
            return box

        # ---- per-option extras (existing behavior) ----
        extras_layout_map: dict[Any, QVBoxLayout] = {}

        for opt in options:
            if not isinstance(opt, dict):
                continue
            val = opt.get("value")
            if opt.get("extras"):
                spacer = QWidget()
                spacer_layout = QVBoxLayout(spacer)
                spacer_layout.setContentsMargins(25, 0, 0, 0)
                layout.addWidget(spacer)
                extras_layout_map[val] = spacer_layout

        extras_cfg = {
            opt.get("value"): opt.get("extras")
            for opt in options
            if isinstance(opt, dict) and opt.get("extras")
        }

        update_extras, read_extras = self._build_extras_controller(
            base_layout=layout,
            extras_cfg=extras_cfg,
            is_enabled_fn=lambda: True,
            get_value_fn=get_selected,
            layout_override=extras_layout_map,
        )

        for rb in radios:
            rb.toggled.connect(update_extras)
            rb.toggled.connect(self._refresh_dynamic_controls)
        update_extras()

        def read():
            result = {"value": get_selected()}
            read_extras(result)
            return result

        self.controls[cfg["key"]] = read
        return box

    def _build_switch_with_extras(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        key = str(cfg["key"])
        default_mode = "b" if str(cfg.get("default", "a")).lower() == "b" else "a"

        state_name_a = str(cfg.get("state_name_a", "Option A"))
        state_name_b = str(cfg.get("state_name_b", "Option B"))

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        toggle = QCheckBox()
        toggle.setChecked(default_mode == "b")
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet("""
            QCheckBox {
                spacing: 0px;
            }

            QCheckBox::indicator {
                width: 46px;
                height: 24px;
                border-radius: 12px;
                background-color: #4b5563;
                border: 1px solid #1f2937;
            }

            QCheckBox::indicator:checked {
                background-color: #22c55e;
                border: 1px solid #166534;
            }
        """)
        top_row.addWidget(toggle)

        state_text_label = QLabel()
        top_row.addWidget(state_text_label)
        top_row.addStretch()

        layout.addLayout(top_row)

        stack_host = QWidget()
        stack = QStackedLayout(stack_host)
        stack.setContentsMargins(0, 0, 0, 0)

        control_a_cfg = dict(cfg.get("control_a") or {})
        control_b_cfg = dict(cfg.get("control_b") or {})

        if not control_a_cfg or not control_b_cfg:
            raise ValueError("switch_with_extras requires both 'control_a' and 'control_b'")

        builders = self._builders()

        type_a = control_a_cfg.get("type")
        type_b = control_b_cfg.get("type")

        builder_a = builders.get(type_a)
        builder_b = builders.get(type_b)

        if not builder_a:
            raise ValueError(f"Unsupported switch_with_extras control_a type: {type_a!r}")
        if not builder_b:
            raise ValueError(f"Unsupported switch_with_extras control_b type: {type_b!r}")

        widget_a = builder_a(control_a_cfg)
        widget_b = builder_b(control_b_cfg)

        stack.addWidget(widget_a)
        stack.addWidget(widget_b)

        layout.addWidget(stack_host)

        def current_mode():
            return "b" if toggle.isChecked() else "a"

        def apply_state():
            mode = current_mode()

            if mode == "b":
                stack.setCurrentIndex(1)
                state_text_label.setText(state_name_b)
            else:
                stack.setCurrentIndex(0)
                state_text_label.setText(state_name_a)

            self._refresh_dynamic_controls()
            self._refresh_required_state()

        self.controls[key] = current_mode
        self._controls_widgets[key] = container

        toggle.toggled.connect(apply_state)

        apply_state()
        return container

    def _build_select(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        combo = self._make_combo(
            options=cfg.get("options", []),
            default=cfg.get("default"),
            enabled=True,
            visible=True)
        layout.addWidget(combo)

        self._controls_widgets[cfg["key"]] = box
        self.controls[cfg["key"]] = lambda: combo.currentData()

        combo.currentIndexChanged.connect(self._refresh_dynamic_controls)
        return box

    def _build_compact_select(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(cfg.get("label", "Select"))
        layout.addWidget(label)

        combo = QComboBox()
        for text, value in self._iter_options(cfg.get("options", [])):
            combo.addItem(str(text), value)

        default = cfg.get("default")
        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(combo)
        row.addStretch()
        layout.addLayout(row)

        self.controls[cfg["key"]] = combo.currentData
        if cfg.get("required"):
            self._register_required_key(cfg["key"])

        combo.currentIndexChanged.connect(self._refresh_required_state)

        return container

    def _build_range_select(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        options = cfg.get("options", [])

        start_key = cfg.get("start_key", f'{cfg["key"]}_start')
        end_key = cfg.get("end_key", f'{cfg["key"]}_end')

        start_combo = QComboBox()
        end_combo = QComboBox()

        for text, value in self._iter_options(options):
            start_combo.addItem(str(text), value)
            end_combo.addItem(str(text), value)

        start_default = cfg.get("default_start")
        if start_default is not None:
            idx = start_combo.findData(start_default)
            if idx >= 0:
                start_combo.setCurrentIndex(idx)

        end_default = cfg.get("default_end")
        if end_default is not None:
            idx = end_combo.findData(end_default)
            if idx >= 0:
                end_combo.setCurrentIndex(idx)

        start_col = QVBoxLayout()
        start_col.setContentsMargins(0, 0, 0, 0)
        start_col.setSpacing(2)
        start_col.addWidget(QLabel(cfg.get("start_label", "Address start")))
        start_col.addWidget(start_combo)

        end_col = QVBoxLayout()
        end_col.setContentsMargins(0, 0, 0, 0)
        end_col.setSpacing(2)
        end_col.addWidget(QLabel(cfg.get("end_label", "Address end")))
        end_col.addWidget(end_combo)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addLayout(start_col)
        row.addWidget(QLabel("-"))
        row.addLayout(end_col)
        row.addStretch()

        layout.addLayout(row)

        self.controls[start_key] = start_combo.currentData
        self.controls[end_key] = end_combo.currentData
        
        for key in cfg.get("required_keys", []):
            self._register_required_key(key)

        start_combo.currentIndexChanged.connect(self._refresh_required_state)
        end_combo.currentIndexChanged.connect(self._refresh_required_state)

        return container

    def _build_toggle_select(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        default_state = (cfg.get("default") or "off").strip().lower()
        rb_off = self._make_radio(cfg["toggle"]["off"], "off", checked=(default_state == "off"))
        rb_on = self._make_radio(cfg["toggle"]["on"], "on", checked=(default_state == "on"))

        layout.addWidget(rb_off)

        row = QHBoxLayout()
        row.addWidget(rb_on)

        options = cfg.get("options") or []
        combo = self._make_combo(options=options, default=None, enabled=False, visible=bool(options))
        if combo.isVisible():
            row.addWidget(combo)
        layout.addLayout(row)

        update_extras, read_extras = self._build_extras_controller(
            base_layout=layout,
            extras_cfg=cfg.get("extra", {}) or {},
            is_enabled_fn=rb_on.isChecked,
            get_value_fn=combo.currentData,
        )

        def update_state():
            combo.setEnabled(rb_on.isChecked() and combo.isVisible())
            update_extras()
            self._refresh_dynamic_controls()

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

    def _build_multi_select(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 22, 12, 12)  # L, T, R, B
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.viewport().setStyleSheet("border: none;")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)

        key = cfg["key"]
        mutex_group = cfg.get("mutex_group")

        # value -> (checkbox, x_label, stack_layout)
        rows: dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]] = {}
        self._multi_rows[key] = rows

        def read_selected() -> list:
            return [v for v, (cb, _x, _stack) in rows.items() if cb.isChecked()]

        def _notify_mutex_changed():
            if mutex_group:
                self._update_mutex_group(mutex_group)

        def set_options(options: list[tuple[str, Any]]):
            prev_selected = set(read_selected())

            while inner_layout.count():
                item = inner_layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

            rows.clear()

            # indicator size from current style (stable across DPI/themes)
            probe = QCheckBox()
            iw = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, None, probe)
            ih = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight, None, probe)

            row_h = ih

            for label, value in options:
                row = QWidget()
                row_l = QHBoxLayout(row)
                row_l.setContentsMargins(0, 0, 0, 0)
                row_l.setSpacing(8)

                cb = QCheckBox()
                cb.setChecked(value in prev_selected)
                cb.setFixedSize(iw, ih)

                x = QLabel("X")
                x.setAlignment(Qt.AlignmentFlag.AlignCenter)
                x.setFixedSize(iw, ih)
                x.setFrameShape(QFrame.Shape.Box)
                x.setLineWidth(1)

                indicator = QWidget()
                stack = QStackedLayout(indicator)
                stack.setContentsMargins(0, 0, 0, 0)
                stack.addWidget(cb)
                stack.addWidget(x)
                stack.setCurrentWidget(cb)

                txt = QLabel(str(label))
                txt.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

                row_l.addWidget(indicator, 0, Qt.AlignmentFlag.AlignVCenter)
                row_l.addWidget(txt, 1, Qt.AlignmentFlag.AlignVCenter)

                cb.stateChanged.connect(_notify_mutex_changed)

                rows[value] = (cb, x, stack)
                inner_layout.addWidget(row)

                row_h = max(row_h, txt.sizeHint().height(), ih)
                row.setFixedHeight(row_h)

            inner_layout.addStretch(1)

            # show exactly 2 rows; scroll in exactly 2-row jumps
            if rows:
                viewport_h = (row_h * 2) + inner_layout.spacing()
                scroll.setFixedHeight(viewport_h + 6)

                sb = scroll.verticalScrollBar()
                step = max(1, row_h * 2)
                sb.setSingleStep(step)
                sb.setPageStep(step)

            inner_layout.activate()
            inner.adjustSize()
            scroll.updateGeometry()
            box.updateGeometry()

            _notify_mutex_changed()

        set_options(cfg.get("options", []) or [])

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self.controls[key] = read_selected
        self._controls_widgets[key] = box

        depends_on = cfg.get("depends_on")
        options_provider = cfg.get("options_provider")
        if depends_on and callable(options_provider):
            self._dynamic_multis.append((depends_on, set_options, read_selected, options_provider))

        if mutex_group:
            self._mutex_groups.setdefault(mutex_group, []).append(key)

        return box

    def _sync_item_split_numbers(self, changed_key: str):
        if self._syncing_item_split:
            return
        if self._item_split_total is None:
            return

        spin1 = self._number_widgets.get("items_file1")
        spin2 = self._number_widgets.get("items_file2")
        if spin1 is None or spin2 is None:
            return

        total = int(self._item_split_total)

        def clamp(v: int) -> int:
            if v < 0:
                return 0
            if v > total:
                return total
            return v

        try:
            self._syncing_item_split = True

            if changed_key == "items_file2":
                v2 = clamp(int(spin2.value()))
                v1 = total - v2
                v1 = clamp(v1)

                v2 = total - v1
                v2 = clamp(v2)

            else:
                v1 = clamp(int(spin1.value()))
                v2 = total - v1
                v2 = clamp(v2)

                v1 = total - v2
                v1 = clamp(v1)

            if spin1.value() != v1:
                spin1.blockSignals(True)
                spin1.setValue(int(v1))
                spin1.blockSignals(False)

            if spin2.value() != v2:
                spin2.blockSignals(True)
                spin2.setValue(int(v2))
                spin2.blockSignals(False)

        finally:
            self._syncing_item_split = False
    
    def _build_number(self, cfg: dict) -> QGroupBox:
        from PySide6.QtWidgets import QSpinBox

        box = QGroupBox(cfg.get("label", ""))
        layout = QVBoxLayout(box)

        spin = QSpinBox()
        spin.setMinimum(int(cfg.get("min", 0)))
        spin.setMaximum(int(cfg.get("max", 10_000_000)))
        spin.setValue(int(cfg.get("default", 0)))

        layout.addWidget(spin)

        key = cfg["key"]
        self._controls_widgets[key] = box
        self._number_widgets[key] = spin
        self.controls[key] = spin.value

        if key == "items_file1":
            try:
                self._item_split_total = int(cfg.get("default", 0))
            except Exception:
                self._item_split_total = None

        spin.valueChanged.connect(self._refresh_dynamic_controls)

        if key in ("items_file1", "items_file2"):
            spin.valueChanged.connect(lambda _v, k=key: self._sync_item_split_numbers(k))
            if key == "items_file1":
                self._sync_item_split_numbers("items_file1")

        return box
    
    def _build_table_preview(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg.get("label", "Preview"))
        layout = QVBoxLayout(box)

        rows = cfg.get("rows", []) or []

        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAlternatingRowColors(True)

        if rows:
            columns = list(rows[0].keys())

            table.setColumnCount(len(columns))
            table.setRowCount(len(rows))
            table.setHorizontalHeaderLabels([str(c) for c in columns])

            for r, row in enumerate(rows):
                for c, col in enumerate(columns):
                    value = row.get(col, "")
                    item = QTableWidgetItem("" if value is None else str(value))
                    table.setItem(r, c, item)

            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
            table.verticalHeader().setVisible(False)
        else:
            table.setColumnCount(0)
            table.setRowCount(0)

        visible_rows = min(max(len(rows), 1), 10)
        row_height = table.verticalHeader().defaultSectionSize() if table.rowCount() else 30
        header_height = table.horizontalHeader().height()
        frame_height = 8
        table.setMinimumHeight((visible_rows * row_height) + header_height + frame_height)
        table.setMaximumHeight((visible_rows * row_height) + header_height + frame_height + 4)

        layout.addWidget(table)

        return box
    
    def _build_section(self, cfg: dict) -> QGroupBox:
        box = QGroupBox(cfg.get("label", "Section"))
        layout = QVBoxLayout(box)

        builders = self._builders()

        for child in cfg.get("children", []):
            t = child.get("type")
            builder = builders.get(t)
            if not builder:
                raise ValueError(f"Unsupported section child type: {t!r}")
            layout.addWidget(builder(child))

        return box
    
    def _build_compact_select_row(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for child in cfg.get("children", []):
            child_widget = self._build_compact_select(child)
            layout.addWidget(child_widget)

        layout.addStretch()
        return container
    # ---------------- Pager ----------------
    def _ensure_pager_group(self, group: str) -> None:
        if group in self._pagers:
            return

        items = [cfg for cfg in self.schema if str(cfg.get("page_group", "")) == group and cfg.get("key")]

        def _sort_key(c: dict) -> int:
            k = str(c.get("key", ""))
            digits = "".join(ch for ch in k if ch.isdigit())
            return int(digits) if digits else 999

        items = sorted(items, key=_sort_key)

        self._pagers[group] = {
            "items": items,
            "page": 0,
            "page_size": 2,
            "lbl": None,
            "btn_up": None,
            "btn_down": None}

        if self._active_pager_group is None:
            self._active_pager_group = group

    def _build_pager_row(self, group: str) -> QHBoxLayout:
        st = self._pagers[group]

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("Navigate files:")
        btn_up = QToolButton()
        btn_up.setText("▲")
        btn_down = QToolButton()
        btn_down.setText("▼")
        lbl_status = QLabel("")

        nav_row.addWidget(lbl_title)
        nav_row.addWidget(btn_up)
        nav_row.addWidget(btn_down)
        nav_row.addWidget(lbl_status)
        nav_row.addStretch()

        st["lbl"] = lbl_status
        st["btn_up"] = btn_up
        st["btn_down"] = btn_down

        btn_up.clicked.connect(lambda _=False, g=group: self._pager_move(g, -1))
        btn_down.clicked.connect(lambda _=False, g=group: self._pager_move(g, +1))

        return nav_row

    def _pager_move(self, group: str, delta: int) -> None:
        st = self._pagers.get(group)
        if not st:
            return
        st["page"] = max(0, int(st["page"]) + int(delta))
        self._refresh_pagers()

    def _pager_eligible_keys(self, items: list[dict]) -> list[str]:
        keys: list[str] = []
        for cfg in items:
            k = cfg.get("key")
            if not k:
                continue
            if self._is_cfg_visible(cfg):
                keys.append(str(k))
        return keys

    def _refresh_pagers(self) -> None:
        for group, st in self._pagers.items():
            items: list[dict] = st["items"]
            eligible = self._pager_eligible_keys(items)
            page_size = int(st["page_size"])
            page = int(st["page"])

            lbl = st.get("lbl")
            btn_up = st.get("btn_up")
            btn_down = st.get("btn_down")

            if not eligible:
                if lbl:
                    lbl.setText("No file selectors")
                if btn_up:
                    btn_up.setEnabled(False)
                if btn_down:
                    btn_down.setEnabled(False)
                for cfg in items:
                    w = self._controls_widgets.get(cfg.get("key"))
                    if w:
                        w.setVisible(False)
                continue

            max_page = (len(eligible) - 1) // page_size
            if page > max_page:
                page = max_page
                st["page"] = page

            start = page * page_size
            window = eligible[start : start + page_size]
            window_set = set(window)

            for cfg in items:
                k = str(cfg.get("key", ""))
                w = self._controls_widgets.get(k)
                if not w:
                    continue
                w.setVisible(self._is_cfg_visible(cfg) and (k in window_set))

            start_n = start + 1
            end_n = min(start + page_size, len(eligible))

            if lbl:
                lbl.setText(f"Showing {start_n}-{end_n} of {len(eligible)}")
            if btn_up:
                btn_up.setEnabled(page > 0)
            if btn_down:
                btn_down.setEnabled(page < max_page)
    # ---------------- Dynamic refresh + results ----------------
    def _refresh_dynamic_controls(self) -> None:
        for depends_on_key, set_options, _read, options_fn in self._dynamic_multis:
            getter = self.controls.get(depends_on_key)
            if not callable(getter):
                continue
            current_value = getter()
            new_options = options_fn(current_value)
            set_options(new_options)

        for cfg in self.schema:
            key = cfg.get("key")
            if not key:
                continue

            if cfg.get("page_group"):
                continue

            target = self._controls_widgets.get(key)
            if not target:
                continue

            target.setVisible(bool(self._is_cfg_visible(cfg)))

        self._refresh_pagers()
        self._auto_resize_to_contents()

    def keyPressEvent(self, event: QKeyEvent):
        if self._active_pager_group and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._pager_move(self._active_pager_group, -1 if event.key() == Qt.Key.Key_Up else 1)
            return
        super().keyPressEvent(event)

    def get_results(self) -> dict:
        return {key: getter() for key, getter in self.controls.items()}