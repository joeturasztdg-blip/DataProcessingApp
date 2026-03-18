from PySide6.QtWidgets import QComboBox, QLineEdit

class StateRules:
    def __init__(self, ctx, rules, mutex, set_bound_widget_enabled):
        self.ctx = ctx
        self.rules = rules
        self.mutex = mutex
        self._set_bound_widget_enabled = set_bound_widget_enabled
        self._last_use_max_service_dimensions = None
        self._last_use_windsor_agreement_defaults = None

    def apply_state(self) -> None:
        use_max = bool(self.ctx.get("use_max_service_dimensions"))
        just_checked_max = use_max and (self._last_use_max_service_dimensions is not True)

        if just_checked_max:
            for prefix in ("length", "width", "height"):
                self._reset_switch_binding_to_initial(prefix)
            self.mutex.refresh_selects()

        for prefix in ("length", "width", "height"):
            self._set_bound_widget_enabled(f"{prefix}_mode", not use_max)
            self._set_bound_widget_enabled(f"{prefix}_column", not use_max)
            self._set_bound_widget_enabled(f"{prefix}_text", not use_max)

        self._last_use_max_service_dimensions = use_max

        use_windsor = bool(self.ctx.get("use_windsor_agreement_defaults"))
        just_checked_windsor = (
            use_windsor and (self._last_use_windsor_agreement_defaults is not True)
        )

        if just_checked_windsor:
            for prefix in ("country_code", "product_description", "quantity", "retail_value"):
                self._reset_switch_binding_to_initial(prefix)
            self.mutex.refresh_selects()

        for prefix in ("country_code", "product_description", "quantity", "retail_value"):
            self._set_bound_widget_enabled(f"{prefix}_mode", not use_windsor)
            self._set_bound_widget_enabled(f"{prefix}_column", not use_windsor)
            self._set_bound_widget_enabled(f"{prefix}_text", not use_windsor)

        self._last_use_windsor_agreement_defaults = use_windsor

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

            current_options = [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]
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
            required_now = self.rules.cfg_is_currently_required(parent_cfg)
            suffix = "*" if required_now else ""

            if base_field_name:
                if initial_mode == "b":
                    label.setText(f"Enter {base_field_name}{suffix}")
                else:
                    label.setText(f"Select {base_field_name}{suffix}")