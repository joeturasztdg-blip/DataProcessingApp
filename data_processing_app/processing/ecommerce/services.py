from __future__ import annotations

from typing import Any

import pandas as pd

from config.constants import MAX_SERVICE_DIMENSIONS, DEFAULT_WINDSOR_DETAILS
from processing.repos.services_repo import ServicesRepository

class EcommerceServices:
    def to_float_or_none(self, value) -> float | None:
        if isinstance(value, pd.Series):
            non_blank = []
            for item in value.tolist():
                if pd.isna(item):
                    continue
                s = str(item).strip()
                if not s or s.lower() == "nan":
                    continue
                non_blank.append(item)

            if not non_blank:
                return None

            value = non_blank[-1]

        if pd.isna(value):
            return None

        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None

        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    def normalise_service_code(self, value) -> str:
        return str(value or "").strip().upper()

    def service_rule_maps(self,services_repo: ServicesRepository) -> tuple[dict[str, dict], dict[str, dict]]:
        rows = services_repo.list_all(limit=100000)

        by_new: dict[str, dict] = {}
        by_old: dict[str, dict] = {}

        for row in rows:
            new_code = self.normalise_service_code(row.get("new_code"))
            old_code = self.normalise_service_code(row.get("old_code"))

            if new_code:
                by_new[new_code] = row
            if old_code:
                by_old[old_code] = row

        return by_new, by_old

    def service_rule_cache(self,services_repo: ServicesRepository) -> dict[str, Any]:
        by_new, by_old = self.service_rule_maps(services_repo)
        all_rules = list(by_new.values())

        return {"by_new": by_new,"by_old": by_old,"all_rules": all_rules,}

    def find_service_rule(self,service_value: str,by_new: dict[str, dict],by_old: dict[str, dict]) -> dict | None:
        key = self.normalise_service_code(service_value)
        if not key:
            return None
        return by_new.get(key) or by_old.get(key)

    def canonical_service_code_from_rule(self,rule: dict | None,fallback: str = "") -> str:
        if not rule:
            return self.normalise_service_code(fallback)

        replacement_code = self.normalise_service_code(rule.get("replacement_code"))
        if replacement_code:
            return replacement_code

        new_code = self.normalise_service_code(rule.get("new_code"))
        if new_code:
            return new_code

        old_code = self.normalise_service_code(rule.get("old_code"))
        if old_code:
            return old_code

        return self.normalise_service_code(fallback)

    def canonicalise_service_value(self,service_value,*,by_new: dict[str, dict],by_old: dict[str, dict]) -> str:
        original = "" if pd.isna(service_value) else str(service_value).strip()
        rule = self.find_service_rule(original, by_new, by_old)
        return self.canonical_service_code_from_rule(rule, fallback=original)

    def service_fits_rule(self,*,length_value,width_value,height_value,weight_value,rule: dict) -> bool:
        length = self.to_float_or_none(length_value)
        width = self.to_float_or_none(width_value)
        height = self.to_float_or_none(height_value)
        weight = self.to_float_or_none(weight_value)

        min_length = self.to_float_or_none(rule.get("min_length_mm"))
        min_width = self.to_float_or_none(rule.get("min_width_mm"))
        min_height = self.to_float_or_none(rule.get("min_height_mm"))

        max_length = self.to_float_or_none(rule.get("max_length_mm"))
        max_width = self.to_float_or_none(rule.get("max_width_mm"))
        max_height = self.to_float_or_none(rule.get("max_height_mm"))
        max_weight = self.to_float_or_none(rule.get("max_weight_g"))

        dimension_pairs = [(length, min_length, max_length),(width, min_width, max_width),(height, min_height, max_height)]

        for value, min_v, max_v in dimension_pairs:
            if value is None:
                continue
            if min_v is not None and value < min_v:
                return False
            if max_v is not None and value > max_v:
                return False

        if weight is not None and max_weight is not None and weight > max_weight:
            return False

        return True

    def service_display_code(self, rule: dict) -> str:
        return self.canonical_service_code_from_rule(rule)

    def service_reject_reason(self,*,service_value,length_value,width_value,height_value,weight_value,by_new: dict[str, dict],by_old: dict[str, dict]) -> str | None:
        rule = self.find_service_rule(service_value, by_new, by_old)
        if rule is None:
            return "Invalid Service"

        if not self.service_fits_rule(length_value=length_value,width_value=width_value,height_value=height_value,weight_value=weight_value,rule=rule,):
            max_weight = self.to_float_or_none(rule.get("max_weight_g"))
            weight = self.to_float_or_none(weight_value)
            if weight is not None and max_weight is not None and weight > max_weight:
                return "Too Heavy For Selected Service"
            return "Outside Selected Service Dimensions"

        return None

    def valid_services_for_rows(self,rows: list[dict[str, Any]],*,all_rules: list[dict],) -> list[str]:
        valid_codes: list[str] = []
        seen: set[str] = set()

        for rule in all_rules:
            code = self.service_display_code(rule)
            if not code or code in seen:
                continue

            for row in rows:
                if self.service_fits_rule(length_value=row.get("Length"),width_value=row.get("Width"),height_value=row.get("Height"),weight_value=row.get("Weight"),rule=rule,):
                    seen.add(code)
                    valid_codes.append(code)
                    break

        valid_codes.sort()
        return valid_codes

    def apply_max_service_dimensions(self,df: pd.DataFrame,*,services_repo: ServicesRepository,service_column: str = "Service",) -> pd.DataFrame:
        out = df.copy()

        if service_column not in out.columns:
            return out

        by_new, by_old = self.service_rule_maps(services_repo)

        def scalar_text(row, col: str) -> str:
            value = row.get(col, "")
            if isinstance(value, pd.Series):
                values = []
                for item in value.tolist():
                    if pd.isna(item):
                        continue
                    s = str(item).strip()
                    if not s or s.lower() == "nan":
                        continue
                    values.append(s)
                return values[-1] if values else ""
            return "" if pd.isna(value) else str(value).strip()

        def fallback_dimension(column_name: str, existing_value: str) -> str:
            fallback = str(MAX_SERVICE_DIMENSIONS.get(column_name, "") or "").strip()
            return fallback or existing_value

        def rule_or_fallback(rule_value, column_name: str, existing_value: str) -> str:
            if pd.isna(rule_value):
                return fallback_dimension(column_name, existing_value)

            text = str(rule_value).strip()
            if text:
                return text

            return fallback_dimension(column_name, existing_value)

        lengths: list[str] = []
        widths: list[str] = []
        heights: list[str] = []

        for _, row in out.iterrows():
            service_value = scalar_text(row, service_column)
            rule = self.find_service_rule(service_value, by_new, by_old)

            existing_length = scalar_text(row, "Length")
            existing_width = scalar_text(row, "Width")
            existing_height = scalar_text(row, "Height")

            if rule is None:
                lengths.append(existing_length)
                widths.append(existing_width)
                heights.append(existing_height)
                continue

            lengths.append(rule_or_fallback(rule.get("max_length_mm"), "Length", existing_length))
            widths.append(rule_or_fallback(rule.get("max_width_mm"), "Width", existing_width))
            heights.append(rule_or_fallback(rule.get("max_height_mm"), "Height", existing_height))

        out["Length"] = lengths
        out["Width"] = widths
        out["Height"] = heights
        return out

    def use_replacement_service_code(self,df: pd.DataFrame,*,services_repo: ServicesRepository,service_column: str = "Service",) -> pd.DataFrame:
        out = df.copy()

        if service_column not in out.columns:
            return out
        by_new, by_old = self.service_rule_maps(services_repo)
        out[service_column] = out[service_column].map(lambda value: self.canonicalise_service_value(value,by_new=by_new,by_old=by_old))
        return out

    def collect_service_resolution_state(self,df: pd.DataFrame,*,rule_cache: dict[str, Any],) -> dict[str, Any]:
        by_new = rule_cache["by_new"]
        by_old = rule_cache["by_old"]

        resolution_indices: list[int] = []
        rows: list[dict[str, str]] = []

        required_cols = ["Length", "Width", "Height", "Weight", "Service"]
        for col in required_cols:
            if col not in df.columns:
                return {"resolution_indices": [],"rows": [],"valid_services": [],}

        for idx, row in df.iterrows():
            reject_reason = self.service_reject_reason(service_value=row.get("Service"),length_value=row.get("Length"),width_value=row.get("Width"),
                                                       height_value=row.get("Height"),weight_value=row.get("Weight"),by_new=by_new,by_old=by_old)
            if not reject_reason:
                continue

            resolution_indices.append(int(idx))
            rows.append(
                {"Length": "" if pd.isna(row.get("Length")) else str(row.get("Length")),
                 "Width": "" if pd.isna(row.get("Width")) else str(row.get("Width")),
                 "Height": "" if pd.isna(row.get("Height")) else str(row.get("Height")),
                 "Weight": "" if pd.isna(row.get("Weight")) else str(row.get("Weight")),
                 "Service": "" if pd.isna(row.get("Service")) else str(row.get("Service")),
                 "Reject Reason": reject_reason})

        valid_services = self.valid_services_for_rows(rows,all_rules=rule_cache["all_rules"])

        return {"resolution_indices": resolution_indices,"rows": rows,"valid_services": valid_services,}

    def apply_service_resolution_result(self,df: pd.DataFrame,*,resolution_indices: list[int],result: dict[str, Any],
                                        use_max_service_dimensions: bool = False,services_repo: ServicesRepository,) -> pd.DataFrame:
        out = df.copy()
        edited_rows = list(result.get("rows", []) or [])
        original_rows = list(result.get("original_rows", []) or [])
        mass_update = dict(result.get("mass_update") or {})

        by_new, by_old = self.service_rule_maps(services_repo)

        if use_max_service_dimensions:
            bulk_fields = ("Weight", "Service")
        else:
            bulk_fields = ("Length", "Width", "Height", "Weight", "Service")

        for pos, idx in enumerate(resolution_indices):
            if idx not in out.index:
                continue

            edited = edited_rows[pos] if pos < len(edited_rows) else {}
            original = original_rows[pos] if pos < len(original_rows) else {}

            for col in bulk_fields:
                if col not in out.columns:
                    continue

                current_value = out.loc[idx, col]

                bulk_value = mass_update.get(col, "")
                bulk_value = "" if pd.isna(bulk_value) else str(bulk_value).strip()

                original_value = original.get(col, "")
                original_value = "" if pd.isna(original_value) else str(original_value).strip()

                edited_value = edited.get(col, "")
                edited_value = "" if pd.isna(edited_value) else str(edited_value).strip()

                value_to_write = current_value

                if bulk_value:
                    value_to_write = bulk_value

                if edited_value != original_value:
                    value_to_write = edited_value

                if col == "Service":
                    value_to_write = self.canonicalise_service_value(value_to_write,by_new=by_new,by_old=by_old)

                out.loc[idx, col] = value_to_write

        if use_max_service_dimensions:
            out = self.apply_max_service_dimensions(out,services_repo=services_repo,service_column="Service",)

        return out

    def split_valid_and_service_rejects(self,df: pd.DataFrame,*,services_repo: ServicesRepository) -> tuple[pd.DataFrame, pd.DataFrame]:
        by_new, by_old = self.service_rule_maps(services_repo)

        valid_indices: list[int] = []
        reject_rows: list[dict[str, Any]] = []

        for idx, row in df.iterrows():
            reject_reason = self.service_reject_reason(service_value=row.get("Service"),length_value=row.get("Length"),
                                                       width_value=row.get("Width"),height_value=row.get("Height"),weight_value=row.get("Weight"),
                                                       by_new=by_new,by_old=by_old)
            if reject_reason:
                reject_row = row.to_dict()
                reject_row["Reject Reason"] = reject_reason
                reject_rows.append(reject_row)
            else:
                valid_indices.append(idx)

        valid_df = df.loc[valid_indices].copy()
        valid_df.reset_index(drop=True, inplace=True)

        reject_df = pd.DataFrame(reject_rows)
        if not reject_df.empty:
            reject_df.reset_index(drop=True, inplace=True)

        return valid_df, reject_df

    def apply_default_windsor_details(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        for col, value in DEFAULT_WINDSOR_DETAILS.items():
            out[col] = value

        return out