from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Tuple

from gui.toggle_switch import ToggleSwitch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,
    QRadioButton,QComboBox,QLineEdit,QLabel,QGroupBox,QDialog,QScrollArea,QCheckBox,QToolButton,QFrame,
    QStyle,QStackedLayout,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QSpinBox)

@dataclass
class ControlBinding:
    key: str
    widget: QWidget
    get_value: Callable[[], Any]
    cfg: dict = field(default_factory=dict)
    required: bool = False

@dataclass
class DynamicMultiBinding:
    depends_on: str
    set_options: Callable[[list[tuple[str, Any]]], None]
    read_selected: Callable[[], list]
    options_provider: Callable[[Any], list]

@dataclass
class PagerState:
    group: str
    items: list[dict]
    page: int = 0
    page_size: int = 2
    label: QLabel | None = None
    btn_up: QToolButton | None = None
    btn_down: QToolButton | None = None

class DialogContext:
    def __init__(self):
        self.bindings: dict[str, ControlBinding] = {}
        self.dynamic_multis: list[DynamicMultiBinding] = []
        self.multi_rows: dict[str, dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]]] = {}
        self.mutex_groups: dict[str, list[str]] = {}
        self.number_widgets: dict[str, QSpinBox] = {}
        self.required_keys: set[str] = set()

    def register(self, binding: ControlBinding) -> None:
        if binding.key:
            self.bindings[binding.key] = binding
            if binding.required:
                self.required_keys.add(binding.key)

    def get(self, key: str) -> Any:
        binding = self.bindings.get(str(key))
        if not binding:
            return None
        return binding.get_value()

    def widget_for(self, key: str) -> QWidget | None:
        binding = self.bindings.get(str(key))
        return binding.widget if binding else None
    
    def binding(self, key: str):
        return self.bindings.get(key)

class ExtrasBinding:
    def __init__(
        self,
        widgets_by_option: dict[Any, list[tuple[str, QWidget]]],
        enabled_when: Callable[[], bool],
        selected_value: Callable[[], Any],
    ):
        self.widgets_by_option = widgets_by_option
        self.enabled_when = enabled_when
        self.selected_value = selected_value

    def refresh(self) -> None:
        enabled = bool(self.enabled_when())
        current = self.selected_value()

        for option, widgets in self.widgets_by_option.items():
            active = enabled and (option == "__enabled__" or option == current)
            for _, widget in widgets:
                widget.setEnabled(active)

    def read_into(self, result: dict) -> None:
        current = self.selected_value()
        widgets = list(self.widgets_by_option.get(current, []))
        widgets += self.widgets_by_option.get("__enabled__", [])

        for key, widget in widgets:
            if isinstance(widget, QLineEdit):
                result[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentData()

class PagerManager:
    def __init__(self, dialog: "OptionsDialog"):
        self.dialog = dialog
        self.states: dict[str, PagerState] = {}
        self.active_group: str | None = None

    def register_schema(self, schema: list[dict]) -> None:
        groups: dict[str, list[dict]] = {}

        for cfg in schema:
            group = cfg.get("page_group")
            if not group or not cfg.get("key"):
                continue
            group = str(group)
            groups.setdefault(group, []).append(cfg)

        def sort_key(c: dict) -> int:
            key = str(c.get("key", ""))
            digits = "".join(ch for ch in key if ch.isdigit())
            return int(digits) if digits else 999

        for group, items in groups.items():
            self.states[group] = PagerState(
                group=group,
                items=sorted(items, key=sort_key),
            )

        if self.states and self.active_group is None:
            self.active_group = next(iter(self.states.keys()))

    def build_nav_row(self, group: str) -> QHBoxLayout:
        state = self.states[group]

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

        state.label = lbl_status
        state.btn_up = btn_up
        state.btn_down = btn_down

        btn_up.clicked.connect(lambda _=False, g=group: self.move(g, -1))
        btn_down.clicked.connect(lambda _=False, g=group: self.move(g, +1))

        return nav_row

    def move(self, group: str, delta: int) -> None:
        state = self.states.get(group)
        if not state:
            return
        state.page = max(0, state.page + int(delta))
        self.refresh()

    def eligible_keys(self, items: list[dict]) -> list[str]:
        keys: list[str] = []
        for cfg in items:
            key = cfg.get("key")
            if not key:
                continue

            visible_if = cfg.get("visible_if")
            if visible_if and not self.dialog._rule_matches(visible_if):
                continue

            keys.append(str(key))

        return keys

    def refresh(self) -> None:
        for group, state in self.states.items():
            eligible = self.eligible_keys(state.items)
            page_size = int(state.page_size)
            page = int(state.page)

            if not eligible:
                if state.label:
                    state.label.setText("No file selectors")
                if state.btn_up:
                    state.btn_up.setEnabled(False)
                if state.btn_down:
                    state.btn_down.setEnabled(False)

                for cfg in state.items:
                    widget = self.dialog.ctx.widget_for(cfg.get("key"))
                    if widget:
                        widget.setVisible(False)
                continue

            max_page = (len(eligible) - 1) // page_size
            if page > max_page:
                page = max_page
                state.page = page

            start = page * page_size
            window = eligible[start : start + page_size]
            window_set = set(window)

            for cfg in state.items:
                key = str(cfg.get("key", ""))
                widget = self.dialog.ctx.widget_for(key)
                if widget is None:
                    continue
                visible_if = cfg.get("visible_if")
                is_visible = True if not visible_if else bool(self.dialog._rule_matches(visible_if))
                widget.setVisible(is_visible and key in window_set)

            start_n = start + 1
            end_n = min(start + page_size, len(eligible))

            if state.label:
                state.label.setText(f"Showing {start_n}-{end_n} of {len(eligible)}")
            if state.btn_up:
                state.btn_up.setEnabled(page > 0)
            if state.btn_down:
                state.btn_down.setEnabled(page < max_page)

class BuilderFactory:
    def __init__(self, dialog: "OptionsDialog"):
        self.dialog = dialog
        self._builders: dict[str, Callable[[dict], QWidget]] = {
            "radio": dialog._build_radio,
            "radio_with_extras": dialog._build_radio_with_extras,
            "select": dialog._build_select,
            "text": dialog._build_text,
            "compact_select": dialog._build_compact_select,
            "compact_select_row": dialog._build_compact_select_row,
            "toggle_select": dialog._build_toggle_select,
            "switch_with_extras": dialog._build_switch_with_extras,
            "multi_select": dialog._build_multi_select,
            "number": dialog._build_number,
            "range_select": dialog._build_range_select,
            "table_preview": dialog._build_table_preview,
            "section": dialog._build_section,
            "checkbox": dialog._build_checkbox}

    def build(self, cfg: dict) -> QWidget:
        kind = cfg.get("type")
        builder = self._builders.get(kind)
        if not builder:
            raise ValueError(f"Unsupported schema type: {kind!r}")
        return builder(cfg)

class OptionsDialog(QDialog):
    def __init__(self,schema: list[dict],parent=None,title: str = "Options",*,
                 initial_size: tuple[int, int] = (600, 720),
                 minimum_size: tuple[int, int] = (500, 650),
                 minimum_content_width: int = 500):
        super().__init__(parent)

        self.schema = schema
        self.ctx = DialogContext()
        self.factory = BuilderFactory(self)
        self.pagers = PagerManager(self)

        self._ok_button: QPushButton | None = None
        self._item_split_total: int | None = None
        self._syncing_item_split: bool = False
        self._last_use_max_service_dimensions: bool | None = None

        self.setWindowTitle(title)
        self.resize(*initial_size)
        self.setMinimumSize(*minimum_size)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)

        self.scroll.setWidget(self.body)
        self.main_layout.addWidget(self.scroll, 1)

        self._build_ui()

        self.body_layout.addStretch(1)
        self._add_dialog_buttons()

        self.adjustSize()
        self.setMinimumWidth(max(self.minimumWidth(), minimum_content_width))
    # ---------------- Common helpers ----------------
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
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _get_checked_value(radios: list[QRadioButton], default=None):
        return next((r._value for r in radios if r.isChecked()), default)

    def _make_combo(
        self,
        *,
        options,
        default=None,
        enabled: bool = True,
        visible: bool = True,
    ) -> QComboBox:
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
        radios: list[QRadioButton] = []

        if orientation == "vertical":
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                parent_layout.addWidget(rb)
                radios.append(rb)
        else:
            row = QHBoxLayout()
            parent_layout.addLayout(row)
            for label, value in self._iter_options(options):
                rb = self._make_radio(label, value, checked=(value == default))
                row.addWidget(rb)
                radios.append(rb)
            row.addStretch()

        return radios, (lambda: self._get_checked_value(radios, default=default))

    def _auto_resize_to_contents(self) -> None:
        self.main_layout.activate()
        hint = self.sizeHint()
        screen = self.screen()

        if screen is None:
            self.adjustSize()
            return

        avail = screen.availableGeometry()
        width = min(hint.width(), max(300, avail.width() - 40))
        height = min(hint.height(), max(200, avail.height() - 80))
        self.resize(width, height)

    def _rule_matches(self, rule: dict) -> bool:
        if not rule:
            return True

        dep_key = rule.get("key")
        op = (rule.get("op") or "==").strip()
        rhs = rule.get("value")
        lhs = self.ctx.get(dep_key)

        try:
            if op == "==":
                return lhs == rhs
            if op == "!=":
                return lhs != rhs
            if op == "<=":
                return lhs <= rhs
            if op == "<":
                return lhs < rhs
            if op == ">=":
                return lhs >= rhs
            if op == ">":
                return lhs > rhs
        except Exception:
            return False

        return False

    def _is_missing_required_value(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() in ("", "__select__")
        return False

    def _required_keys_for_switch_with_extras(self, cfg: dict) -> list[str]:
        required_if = cfg.get("required_if")
        mode_map = cfg.get("required_mode_map") or {}

        if not mode_map:
            return []

        if required_if and not self._rule_matches(required_if):
            return []

        mode_key = str(cfg.get("key", "")).strip()
        if not mode_key:
            return []

        mode_binding = self.ctx.binding(mode_key)
        if mode_binding is None:
            return []

        mode = mode_binding.get_value()
        keys = mode_map.get(mode, [])
        return [str(k) for k in keys if k]

    def _collect_switch_required_keys(self, cfg: dict, out: set[str]) -> None:
        cfg_type = str(cfg.get("type", ""))

        if cfg_type == "section":
            for child in cfg.get("children", []):
                self._collect_switch_required_keys(child, out)
            return

        if cfg_type == "compact_select_row":
            for child in cfg.get("children", []):
                self._collect_switch_required_keys(child, out)
            return

        if cfg_type == "switch_with_extras":
            control_a = cfg.get("control_a") or {}
            control_b = cfg.get("control_b") or {}

            key_a = str(control_a.get("key", "")).strip()
            key_b = str(control_b.get("key", "")).strip()

            out.discard(key_a)
            out.discard(key_b)

            for key in self._required_keys_for_switch_with_extras(cfg):
                out.add(key)

            return

    def _refresh_required_state(self) -> None:
        if self._ok_button is None:
            return

        required_keys = set(self.ctx.required_keys)

        for cfg in self.schema:
            self._collect_switch_required_keys(cfg, required_keys)

        if bool(self.ctx.get("use_max_service_dimensions")):
            for prefix in ("length", "width", "height"):
                required_keys.discard(f"{prefix}_column")
                required_keys.discard(f"{prefix}_text")

        for key in required_keys:
            if self._is_missing_required_value(self.ctx.get(key)):
                self._ok_button.setEnabled(False)
                return

        self._ok_button.setEnabled(True)

    def _connect_standard_refresh(self, signal) -> None:
        signal.connect(self.refresh_all)

    def _cfg_is_currently_required(self, cfg: dict) -> bool:
        if bool(cfg.get("always_required", False)):
            return True

        required_if = cfg.get("required_if")
        if required_if:
            return self._rule_matches(required_if)

        return False
    
    def _set_bound_widget_enabled(self, key: str, enabled: bool) -> None:
        binding = self.ctx.binding(str(key))
        if binding is None or binding.widget is None:
            return
        binding.widget.setEnabled(bool(enabled))

    def _apply_use_max_service_dimensions_state(self) -> None:
        checked = bool(self.ctx.get("use_max_service_dimensions"))

        for prefix in ("length", "width", "height"):
            self._set_bound_widget_enabled(f"{prefix}_mode", not checked)
            self._set_bound_widget_enabled(f"{prefix}_column", not checked)
            self._set_bound_widget_enabled(f"{prefix}_text", not checked)
    
    def _set_bound_widget_enabled(self, key: str, enabled: bool) -> None:
        binding = self.ctx.binding(str(key))
        if binding is None or binding.widget is None:
            return
        binding.widget.setEnabled(bool(enabled))

    def _reset_switch_binding_to_initial(self, prefix: str) -> None:
        mode_binding = self.ctx.binding(f"{prefix}_mode")
        if mode_binding is None:
            return

        container = mode_binding.widget
        if container is None:
            return

        toggle = getattr(container, "_switch_toggle", None)
        stack = getattr(container, "_switch_stack", None)
        widget_a = getattr(container, "_switch_widget_a", None)
        widget_b = getattr(container, "_switch_widget_b", None)
        label = getattr(container, "_switch_label", None)

        initial_mode = getattr(container, "_initial_mode", "a")
        initial_column_value = getattr(container, "_initial_column_value", "__select__")
        initial_text_value = getattr(container, "_initial_text_value", "")

        if toggle is not None:
            toggle.blockSignals(True)
            toggle.setChecked(initial_mode == "b")
            toggle.blockSignals(False)

        if stack is not None:
            stack.setCurrentIndex(1 if initial_mode == "b" else 0)

        combo = widget_a.findChild(QComboBox) if widget_a is not None else None
        text_edit = widget_b.findChild(QLineEdit) if widget_b is not None else None

        if combo is not None:
            combo.blockSignals(True)

            current_options = []
            for i in range(combo.count()):
                current_options.append((combo.itemText(i), combo.itemData(i)))

            if not any(value == initial_column_value for _, value in current_options):
                insert_at = 1 if current_options and current_options[0][1] == "__select__" else 0
                combo.insertItem(insert_at, str(initial_column_value), initial_column_value)

            idx = combo.findData(initial_column_value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                select_idx = combo.findData("__select__")
                if select_idx >= 0:
                    combo.setCurrentIndex(select_idx)
                elif combo.count() > 0:
                    combo.setCurrentIndex(0)

            combo.blockSignals(False)

        if text_edit is not None:
            text_edit.blockSignals(True)
            text_edit.setText("" if initial_text_value is None else str(initial_text_value))
            text_edit.blockSignals(False)

        parent_cfg = getattr(container, "_switch_parent_cfg", {}) or {}
        if label is not None:
            base_field_name = str(parent_cfg.get("field_name", "")).strip()
            required_now = self._cfg_is_currently_required(parent_cfg)
            suffix = "*" if required_now else ""

            if base_field_name:
                if initial_mode == "b":
                    label.setText(f"Enter {base_field_name}{suffix}")
                else:
                    label.setText(f"Select {base_field_name}{suffix}")

    def _apply_use_max_service_dimensions_state(self) -> None:
        checked = bool(self.ctx.get("use_max_service_dimensions"))
        just_checked = checked and (self._last_use_max_service_dimensions is not True)

        if just_checked:
            for prefix in ("length", "width", "height"):
                self._reset_switch_binding_to_initial(prefix)
            self._refresh_mutex_selects()

        for prefix in ("length", "width", "height"):
            self._set_bound_widget_enabled(f"{prefix}_mode", not checked)
            self._set_bound_widget_enabled(f"{prefix}_column", not checked)
            self._set_bound_widget_enabled(f"{prefix}_text", not checked)

        self._last_use_max_service_dimensions = checked
    # ---------------- UI assembly ----------------

    def _build_ui(self) -> None:
        self.pagers.register_schema(self.schema)

        inserted_pager_groups: set[str] = set()
        active_group: str | None = None

        for cfg in self.schema:
            group = cfg.get("page_group")
            group = str(group) if group else None

            if active_group and (group != active_group):
                if active_group not in inserted_pager_groups:
                    self.body_layout.addLayout(self.pagers.build_nav_row(active_group))
                    inserted_pager_groups.add(active_group)
                active_group = None

            if group:
                active_group = group

            widget = self.factory.build(cfg)
            self.body_layout.addWidget(widget)

        if active_group and active_group not in inserted_pager_groups:
            self.body_layout.addLayout(self.pagers.build_nav_row(active_group))

        self.refresh_all()
    
    def _add_dialog_buttons(self) -> None:
        row = QHBoxLayout()
        row.addStretch()

        btn_cancel = QPushButton("Cancel")
        self._ok_button = QPushButton("Continue")
        self._ok_button.setDefault(True)

        btn_cancel.clicked.connect(self.reject)
        self._ok_button.clicked.connect(self.accept)

        row.addWidget(btn_cancel)
        row.addWidget(self._ok_button)
        self.main_layout.addLayout(row)

        self._refresh_required_state()

    def _register_binding(
        self,
        key: str,
        widget: QWidget,
        get_value: Callable[[], Any],
        cfg: dict,
    ) -> None:
        if not key:
            return
        binding = ControlBinding(
            key=str(key),
            widget=widget,
            get_value=get_value,
            cfg=cfg,
            required=bool(cfg.get("required")),
        )
        self.ctx.register(binding)

    # ---------------- Shared extras helper ----------------

    def _build_extras_controller(
        self,
        *,
        base_layout,
        extras_cfg: dict,
        is_enabled_fn: Callable[[], bool],
        get_value_fn: Callable[[], Any],
        layout_override: Optional[dict] = None,
    ) -> ExtrasBinding:
        widgets_by_option: dict[Any, list[tuple[str, QWidget]]] = {}

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
                    edit.textChanged.connect(self.refresh_all)

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
                    combo.currentIndexChanged.connect(self.refresh_all)

                else:
                    raise ValueError(f"Unsupported extra type: {etype!r}")

            widgets_by_option[opt_value] = widgets

        return ExtrasBinding(
            widgets_by_option=widgets_by_option,
            enabled_when=is_enabled_fn,
            selected_value=get_value_fn,
        )

    # ---------------- Builders ----------------

    def _build_text(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            layout.addWidget(QLabel(label_text))

        edit = QLineEdit()
        edit.setText(str(cfg.get("default", "")))
        edit.setFixedHeight(24)
        edit.setFixedWidth(220)

        placeholder = cfg.get("placeholder")
        if placeholder is not None:
            edit.setPlaceholderText(str(placeholder))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(edit)
        row.addStretch()
        layout.addLayout(row)

        key = cfg["key"]
        self._register_binding(key, container, lambda: edit.text().strip(), cfg)

        edit.textChanged.connect(self.refresh_all)
        return container

    def _build_radio(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        radios, get_selected = self._make_radio_group(
            parent_layout=layout,
            options=cfg.get("options", []),
            default=cfg.get("default"),
            orientation="horizontal",
        )

        self._register_binding(cfg["key"], box, get_selected, cfg)

        for rb in radios:
            rb.toggled.connect(self.refresh_all)

        return box

    def _build_radio_with_extras(self, cfg: dict) -> QWidget:
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

        shared_extras = cfg.get("shared_extras")
        disable_value = cfg.get("disable_value", "none")

        if shared_extras:
            spacer = QWidget()
            extras_layout = QVBoxLayout(spacer)
            extras_layout.setContentsMargins(25, 0, 0, 0)
            layout.addWidget(spacer)

            extras = self._build_extras_controller(
                base_layout=extras_layout,
                extras_cfg={"__enabled__": shared_extras},
                is_enabled_fn=lambda: get_selected() != disable_value,
                get_value_fn=get_selected,
                layout_override=None,
            )

            def refresh_extras():
                extras.refresh()
                self.refresh_all()

            for rb in radios:
                rb.toggled.connect(refresh_extras)

            extras.refresh()

            def read():
                result = {"value": get_selected()}
                extras.read_into(result)
                return result

            self._register_binding(cfg["key"], box, read, cfg)
            return box

        extras_layout_map: dict[Any, QVBoxLayout] = {}
        for opt in options:
            if not isinstance(opt, dict):
                continue
            value = opt.get("value")
            if opt.get("extras"):
                spacer = QWidget()
                spacer_layout = QVBoxLayout(spacer)
                spacer_layout.setContentsMargins(25, 0, 0, 0)
                layout.addWidget(spacer)
                extras_layout_map[value] = spacer_layout

        extras_cfg = {
            opt.get("value"): opt.get("extras")
            for opt in options
            if isinstance(opt, dict) and opt.get("extras")
        }

        extras = self._build_extras_controller(
            base_layout=layout,
            extras_cfg=extras_cfg,
            is_enabled_fn=lambda: True,
            get_value_fn=get_selected,
            layout_override=extras_layout_map,
        )

        def refresh_extras():
            extras.refresh()
            self.refresh_all()

        for rb in radios:
            rb.toggled.connect(refresh_extras)

        extras.refresh()

        def read():
            result = {"value": get_selected()}
            extras.read_into(result)
            return result

        self._register_binding(cfg["key"], box, read, cfg)
        return box

    def _build_switch_with_extras(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        key = str(cfg["key"])
        default_mode = "b" if str(cfg.get("default", "a")).lower() == "b" else "a"

        toggle = ToggleSwitch()
        toggle.setChecked(default_mode == "b")
        layout.addWidget(toggle)

        state_text_label = QLabel()
        layout.addWidget(state_text_label)

        stack_host = QWidget()
        stack = QStackedLayout(stack_host)
        stack.setContentsMargins(0, 0, 0, 0)

        control_a_cfg = dict(cfg.get("control_a") or {})
        control_b_cfg = dict(cfg.get("control_b") or {})
        if not control_a_cfg or not control_b_cfg:
            raise ValueError("switch_with_extras requires both 'control_a' and 'control_b'")

        widget_a = self.factory.build(control_a_cfg)
        widget_b = self.factory.build(control_b_cfg)

        stack.addWidget(widget_a)
        stack.addWidget(widget_b)

        layout.addWidget(stack_host)
        layout.addStretch()

        base_field_name = str(cfg.get("field_name", "")).strip()
        fallback_a = str(cfg.get("state_name_a", "Option A"))
        fallback_b = str(cfg.get("state_name_b", "Option B"))

        def current_mode():
            return "b" if toggle.isChecked() else "a"

        def current_label_text() -> str:
            required_now = self._cfg_is_currently_required(cfg)
            suffix = "*" if required_now else ""

            if base_field_name:
                if current_mode() == "b":
                    return f"Enter {base_field_name}{suffix}"
                return f"Select {base_field_name}{suffix}"

            if current_mode() == "b":
                return fallback_b + suffix
            return fallback_a + suffix

        def apply_state():
            mode = current_mode()

            if mode == "b":
                stack.setCurrentIndex(1)
            else:
                stack.setCurrentIndex(0)

            state_text_label.setText(current_label_text())
            self.refresh_all()

        # Capture actual initial built state, including autodetected combo selection
        combo_a = widget_a.findChild(QComboBox)
        text_b = widget_b.findChild(QLineEdit)

        container._switch_toggle = toggle
        container._switch_label = state_text_label
        container._switch_stack = stack
        container._switch_widget_a = widget_a
        container._switch_widget_b = widget_b
        container._switch_parent_cfg = dict(cfg)

        container._initial_mode = default_mode
        container._initial_column_value = combo_a.currentData() if combo_a is not None else control_a_cfg.get("default")
        container._initial_text_value = text_b.text() if text_b is not None else (
            "" if control_b_cfg.get("default") is None else str(control_b_cfg.get("default"))
        )

        self._register_binding(key, container, current_mode, cfg)

        mode_cfg = {
            "required": bool(cfg.get("required")),
            "_switch_parent_cfg": dict(cfg),
        }
        self._register_binding(f"{key}_mode", container, current_mode, mode_cfg)

        toggle.toggled.connect(apply_state)

        apply_state()
        return container

    def _build_select(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)

        combo = self._make_combo(
            options=cfg.get("options", []),
            default=cfg.get("default"),
            enabled=True,
            visible=True,
        )
        layout.addWidget(combo)

        self._register_binding(cfg["key"], box, lambda: combo.currentData(), cfg)
        combo.currentIndexChanged.connect(self.refresh_all)
        return box

    def _build_compact_select(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_text = str(cfg.get("label", "")).strip()
        if label_text:
            layout.addWidget(QLabel(label_text))

        combo = QComboBox()
        combo.setFixedHeight(24)

        for text, value in self._iter_options(cfg.get("options", [])):
            combo.addItem(str(text), value)

        default = cfg.get("default")
        if default is not None:
            idx = combo.findData(default)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(combo)
        row.addStretch()
        layout.addLayout(row)

        self._register_binding(cfg["key"], container, combo.currentData, cfg)
        combo.currentIndexChanged.connect(self.refresh_all)
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

        self._register_binding(start_key, container, start_combo.currentData, {"required": start_key in cfg.get("required_keys", [])})
        self._register_binding(end_key, container, end_combo.currentData, {"required": end_key in cfg.get("required_keys", [])})

        start_combo.currentIndexChanged.connect(self.refresh_all)
        end_combo.currentIndexChanged.connect(self.refresh_all)

        return container

    def _build_toggle_select(self, cfg: dict) -> QWidget:
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

        extras = self._build_extras_controller(
            base_layout=layout,
            extras_cfg=cfg.get("extra", {}) or {},
            is_enabled_fn=rb_on.isChecked,
            get_value_fn=combo.currentData,
        )

        def update_state():
            combo.setEnabled(rb_on.isChecked() and combo.isVisible())
            extras.refresh()
            self.refresh_all()

        rb_on.toggled.connect(update_state)
        combo.currentIndexChanged.connect(update_state)
        update_state()

        def read():
            if not rb_on.isChecked():
                return {"enabled": False}
            result = {"enabled": True, "value": combo.currentData()}
            extras.read_into(result)
            return result

        self._register_binding(cfg["key"], box, read, cfg)
        return box

    def _build_multi_select(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg["label"])
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 22, 12, 12)
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
        rows: dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]] = {}
        self.ctx.multi_rows[key] = rows

        def read_selected() -> list:
            return [value for value, (cb, _x, _stack) in rows.items() if cb.isChecked()]

        def notify_mutex_changed():
            if mutex_group:
                self._refresh_mutex_group(mutex_group)
            self._refresh_required_state()

        def set_options(options: list[tuple[str, Any]]):
            prev_selected = set(read_selected())

            while inner_layout.count():
                item = inner_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            rows.clear()

            probe = QCheckBox()
            iw = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, None, probe)
            ih = probe.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight, None, probe)
            row_h = ih

            for label, value in options:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

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

                row_layout.addWidget(indicator, 0, Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(txt, 1, Qt.AlignmentFlag.AlignVCenter)

                cb.stateChanged.connect(notify_mutex_changed)

                rows[value] = (cb, x, stack)
                inner_layout.addWidget(row)

                row_h = max(row_h, txt.sizeHint().height(), ih)
                row.setFixedHeight(row_h)

            inner_layout.addStretch(1)

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

            if mutex_group:
                self._refresh_mutex_group(mutex_group)

        set_options(cfg.get("options", []) or [])

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._register_binding(key, box, read_selected, cfg)

        depends_on = cfg.get("depends_on")
        options_provider = cfg.get("options_provider")
        if depends_on and callable(options_provider):
            self.ctx.dynamic_multis.append(
                DynamicMultiBinding(
                    depends_on=depends_on,
                    set_options=set_options,
                    read_selected=read_selected,
                    options_provider=options_provider,
                )
            )

        if mutex_group:
            self.ctx.mutex_groups.setdefault(mutex_group, []).append(key)

        return box

    def _build_number(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", ""))
        layout = QVBoxLayout(box)

        spin = QSpinBox()
        spin.setMinimum(int(cfg.get("min", 0)))
        spin.setMaximum(int(cfg.get("max", 10_000_000)))
        spin.setValue(int(cfg.get("default", 0)))
        layout.addWidget(spin)

        key = cfg["key"]
        self.ctx.number_widgets[key] = spin
        self._register_binding(key, box, spin.value, cfg)

        if key == "items_file1":
            try:
                self._item_split_total = int(cfg.get("default", 0))
            except Exception:
                self._item_split_total = None

        spin.valueChanged.connect(self.refresh_all)

        if key in ("items_file1", "items_file2"):
            spin.valueChanged.connect(lambda _v, k=key: self._sync_item_split_numbers(k))
            if key == "items_file1":
                self._sync_item_split_numbers("items_file1")

        return box

    def _build_table_preview(self, cfg: dict) -> QWidget:
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

    def _build_section(self, cfg: dict) -> QWidget:
        box = QGroupBox(cfg.get("label", "Section"))
        layout = QVBoxLayout(box)

        for child in cfg.get("children", []):
            layout.addWidget(self.factory.build(child))

        return box

    def _build_compact_select_row(self, cfg: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for child in cfg.get("children", []):
            child_widget = self.factory.build(child)
            layout.addWidget(child_widget, 1)

        return container

    def _build_checkbox(self, cfg: dict) -> QWidget:
        cb = QCheckBox(str(cfg.get("label", "")))
        cb.setChecked(bool(cfg.get("default", False)))

        key = str(cfg["key"])
        self._register_binding(key, cb, cb.isChecked, cfg)

        def on_toggled(_checked: bool):
            self.refresh_all()

        cb.toggled.connect(on_toggled)
        return cb
    # ---------------- Dynamic / mutex / pager refresh ----------------

    def _refresh_dynamic_multis(self) -> None:
        for binding in self.ctx.dynamic_multis:
            current_value = self.ctx.get(binding.depends_on)
            new_options = binding.options_provider(current_value)
            binding.set_options(new_options)

    def _refresh_visibility(self) -> None:
        for cfg in self.schema:
            key = cfg.get("key")
            if not key:
                continue

            if cfg.get("page_group"):
                continue

            widget = self.ctx.widget_for(key)
            if widget is not None:
                visible_if = cfg.get("visible_if")
                widget.setVisible(True if not visible_if else bool(self._rule_matches(visible_if)))

    def _binding_is_mutex_active(self, binding: ControlBinding) -> bool:
        cfg = binding.cfg or {}

        parent_mode_key = cfg.get("parent_mode_key")
        active_mode_value = cfg.get("active_mode_value")

        if not parent_mode_key:
            return True

        return self.ctx.get(parent_mode_key) == active_mode_value
    
    def _refresh_mutex_group(self, group: str) -> None:
        keys = [str(k) for k in self.ctx.mutex_groups.get(str(group), [])]
        if not keys:
            return

        group_rows: dict[str, dict[Any, tuple[QCheckBox, QLabel, QStackedLayout]]] = {}
        selected_by_key: dict[str, set[Any]] = {}

        for key in keys:
            rows = self.ctx.multi_rows.get(key) or {}
            group_rows[key] = rows
            selected_by_key[key] = {
                value for value, (cb, _x, _stack) in rows.items()
                if cb.isChecked()
            }

        for key in keys:
            rows = group_rows.get(key, {})
            selected_elsewhere: set[Any] = set()

            for other_key, selected_values in selected_by_key.items():
                if other_key == key:
                    continue
                selected_elsewhere.update(selected_values)

            for value, (cb, x_lbl, stack) in rows.items():
                is_selected_here = cb.isChecked()
                blocked_elsewhere = value in selected_elsewhere

                # A value is blocked only if selected in another selector.
                should_enable = is_selected_here or not blocked_elsewhere
                cb.setEnabled(should_enable)

                # Show X only for values blocked by another selector and not selected here.
                if blocked_elsewhere and not is_selected_here:
                    stack.setCurrentWidget(x_lbl)
                else:
                    stack.setCurrentWidget(cb)

    def _refresh_mutex_selects(self) -> None:
        groups: dict[str, list[ControlBinding]] = {}

        for binding in self.ctx.bindings.values():
            cfg = binding.cfg or {}
            group = cfg.get("mutex_group")
            if group:
                groups.setdefault(str(group), []).append(binding)

        for _, bindings in groups.items():
            selected_values: dict[str, object] = {}

            for binding in bindings:
                if not self._binding_is_mutex_active(binding):
                    continue

                value = binding.get_value()
                if value not in (None, "", "__select__"):
                    selected_values[str(binding.key)] = value

            for binding in bindings:
                cfg = binding.cfg or {}
                options = cfg.get("options") or []
                current_value = binding.get_value()

                widget = binding.widget
                combo = widget if isinstance(widget, QComboBox) else widget.findChild(QComboBox)
                if combo is None:
                    continue

                blocked = {
                    v for k, v in selected_values.items()
                    if k != str(binding.key)
                }

                filtered = []
                for label, value in self._iter_options(options):
                    if value == "__select__" or value == current_value or value not in blocked:
                        filtered.append((label, value))

                if current_value in blocked:
                    current_value = "__select__"

                combo.blockSignals(True)
                combo.clear()

                for label, value in filtered:
                    combo.addItem(label, value)

                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    idx = combo.findData("__select__")
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                combo.blockSignals(False)
            
    def _refresh_switch_labels(self, cfg: dict) -> None:
        cfg_type = str(cfg.get("type", ""))

        if cfg_type == "section":
            for child in cfg.get("children", []):
                self._refresh_switch_labels(child)
            return

        if cfg_type == "compact_select_row":
            for child in cfg.get("children", []):
                self._refresh_switch_labels(child)
            return

        if cfg_type != "switch_with_extras":
            return

        binding = self.ctx.binding(str(cfg.get("key", "")))
        if binding is None:
            return

        widget = binding.widget
        if widget is None:
            return

        label = widget.findChild(QLabel)
        if label is None:
            return

        mode = binding.get_value()
        base_field_name = str(cfg.get("field_name", "")).strip()
        required_now = self._cfg_is_currently_required(cfg)
        suffix = "*" if required_now else ""

        if base_field_name:
            if mode == "b":
                label.setText(f"Enter {base_field_name}{suffix}")
            else:
                label.setText(f"Select {base_field_name}{suffix}")

    def refresh_all(self) -> None:
        self._refresh_dynamic_multis()
        self._refresh_visibility()
        self._apply_use_max_service_dimensions_state()
        self._refresh_mutex_selects()

        for group in self.ctx.mutex_groups:
            self._refresh_mutex_group(group)

        for cfg in self.schema:
            self._refresh_switch_labels(cfg)

        if self.pagers is not None:
            self.pagers.refresh()

        self._refresh_required_state()
    # ---------------- Item split sync ----------------
    def _sync_item_split_numbers(self, changed_key: str):
        if self._syncing_item_split:
            return
        if self._item_split_total is None:
            return

        spin1 = self.ctx.number_widgets.get("items_file1")
        spin2 = self.ctx.number_widgets.get("items_file2")
        if spin1 is None or spin2 is None:
            return

        total = int(self._item_split_total)

        def clamp(value: int) -> int:
            if value < 0:
                return 0
            if value > total:
                return total
            return value

        try:
            self._syncing_item_split = True

            if changed_key == "items_file2":
                v2 = clamp(int(spin2.value()))
                v1 = clamp(total - v2)
                v2 = clamp(total - v1)
            else:
                v1 = clamp(int(spin1.value()))
                v2 = clamp(total - v1)
                v1 = clamp(total - v2)

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
    # ---------------- Keyboard / results ----------------

    def keyPressEvent(self, event: QKeyEvent):
        if self.pagers.active_group and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.pagers.move(
                self.pagers.active_group,
                -1 if event.key() == Qt.Key.Key_Up else 1,
            )
            return
        super().keyPressEvent(event)

    def get_results(self) -> dict:
        return {key: binding.get_value() for key, binding in self.ctx.bindings.items()}