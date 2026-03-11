from __future__ import annotations

import re
from typing import Any

import pandas as pd
from PySide6.QtWidgets import QDialog

from processing.repos.services_repo import ServicesRepository
from processing.repos.return_addresses_repo import ReturnAddressesRepository
from workspace.base import BaseWorkflow

from config.schemas import build_create_ecommerce_file_schema
from config.constants import (
    ECOMMERCE_HEADER_SYNONYMS,
    PAF_COUNTY_COL,
    PAF_POSTCODE_COL,
    PAF_TOWN_COL,
)

from gui.dialogs.paf_resolution_dialog import PAFResolutionDialog
from gui.dialogs.service_resolution_dialog import ServiceResolutionDialog
from gui.dialogs.options_dialog import OptionsDialog


def _collapse_postcode_series(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace("\t", "", regex=False)
    s = s.str.replace("\n", "", regex=False)
    s = s.str.replace("\r", "", regex=False)
    s = s.str.strip().str.upper()
    return s

def _collapse_text_series(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace("\t", " ", regex=False)
    s = s.str.replace("\n", " ", regex=False)
    s = s.str.replace("\r", " ", regex=False)
    s = s.str.strip()
    return s

def _is_blank_value(value) -> bool:
    if pd.isna(value):
        return True
    s = str(value).strip()
    return s == "" or s.lower() == "nan"

def _norm_header(text: str) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"[_\-.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _norm_compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm_header(text))

def _best_header_match(columns: list[str], aliases: list[str]) -> str | None:
    if not columns or not aliases:
        return None

    exact_map = {_norm_header(c): c for c in columns}
    compact_map = {_norm_compact(c): c for c in columns}

    alias_norms = [_norm_header(a) for a in aliases]
    alias_compacts = [_norm_compact(a) for a in aliases]

    for alias in alias_norms:
        if alias in exact_map:
            return exact_map[alias]

    for alias in alias_compacts:
        if alias in compact_map:
            return compact_map[alias]

    for alias in alias_norms:
        for col in columns:
            nc = _norm_header(col)
            if alias and (nc.startswith(alias) or alias in nc):
                return col

    for alias in alias_compacts:
        for col in columns:
            cc = _norm_compact(col)
            if alias and (cc.startswith(alias) or alias in cc):
                return col

    return None

def _detect_address_like_columns(columns: list[str]) -> list[str]:
    found: list[tuple[int, str]] = []

    for i, col in enumerate(columns):
        nh = _norm_header(col)
        nc = _norm_compact(col)

        is_address = False

        if re.search(r"\b(address|addr|add|line)\s*([1-9])\b", nh):
            is_address = True

        if re.search(r"(address|addr|add|line)([1-9])\b", nc):
            is_address = True

        if re.fullmatch(r"a[1-9]", nc):
            is_address = True

        if "address" in nh and re.search(r"\b[1-9]\b", nh):
            is_address = True

        if is_address:
            found.append((i, col))

    found.sort(key=lambda x: x[0])
    return [col for _, col in found]

def _detect_address_range(
    columns: list[str],
    *,
    town_col: str | None = None,
    county_col: str | None = None,
    postcode_col: str | None = None,
) -> tuple[str | None, str | None]:
    candidates: list[str] = []

    address_cols = _detect_address_like_columns(columns)
    candidates.extend(address_cols)

    for col in (town_col, county_col, postcode_col):
        if col and col in columns:
            candidates.append(col)

    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return None, None

    positions = [(columns.index(col), col) for col in candidates if col in columns]
    if not positions:
        return None, None

    positions.sort(key=lambda x: x[0])
    return positions[0][1], positions[-1][1]

def _detect_ecommerce_defaults(columns: list[str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}

    for target_key, aliases in ECOMMERCE_HEADER_SYNONYMS.items():
        match = _best_header_match(columns, aliases)
        if match:
            defaults[target_key] = match

    start, end = _detect_address_range(
        columns,
        town_col=defaults.get("town_column"),
        county_col=defaults.get("county_column"),
        postcode_col=defaults.get("postcode_column"),
    )
    if start:
        defaults["address_start"] = start
    if end:
        defaults["address_end"] = end

    return defaults

def _apply_schema_defaults(schema: list[dict], defaults: dict[str, Any]) -> None:
    def visit(cfg: dict) -> None:
        key = cfg.get("key")
        if key in defaults:
            cfg["default"] = defaults[key]

        if cfg.get("type") == "range_select":
            start_key = cfg.get("start_key")
            end_key = cfg.get("end_key")
            if start_key in defaults:
                cfg["default_start"] = defaults[start_key]
            if end_key in defaults:
                cfg["default_end"] = defaults[end_key]

        for child in cfg.get("children", []) or []:
            if isinstance(child, dict):
                visit(child)

        for child_key in ("control_a", "control_b"):
            child_cfg = cfg.get(child_key)
            if isinstance(child_cfg, dict):
                visit(child_cfg)

    for item in schema:
        visit(item)

def _build_preview_columns(
    *,
    all_columns: list[str],
    address_start: str | None,
    address_end: str | None,
    town_col: str | None,
    county_col: str | None,
    postcode_col: str,
) -> list[str]:
    address_columns: list[str] = []

    if (
        address_start
        and address_end
        and address_start != "__select__"
        and address_end != "__select__"
        and address_start in all_columns
        and address_end in all_columns
    ):
        start_idx = all_columns.index(address_start)
        end_idx = all_columns.index(address_end)

        if start_idx > end_idx:
            raise ValueError("Address start must come before Address end.")

        address_columns = all_columns[start_idx : end_idx + 1]

    special_cols = [c for c in [town_col, county_col, postcode_col] if c and c != "__select__"]
    base_address_columns = [c for c in address_columns if c not in special_cols]

    preview_columns = list(base_address_columns)

    if town_col and town_col != "__select__" and town_col not in preview_columns:
        preview_columns.append(town_col)

    if county_col and county_col != "__select__" and county_col not in preview_columns:
        preview_columns.append(county_col)

    if postcode_col and postcode_col != "__select__" and postcode_col not in preview_columns:
        preview_columns.append(postcode_col)

    return preview_columns

def _build_paf_name_map(
    *,
    preview_columns: list[str],
    town_col: str | None,
    county_col: str | None,
    postcode_col: str,
) -> dict[str, str]:
    name_map: dict[str, str] = {}

    address_idx = 1
    for col in preview_columns:
        if col == town_col:
            name_map[col] = PAF_TOWN_COL
        elif col == county_col:
            name_map[col] = PAF_COUNTY_COL
        elif col == postcode_col:
            name_map[col] = PAF_POSTCODE_COL
        else:
            name_map[col] = f"PAF Address {address_idx}"
            address_idx += 1

    return name_map

def _build_preview_specs(
    *,
    preview_columns: list[str],
    town_col: str | None,
    county_col: str | None,
    postcode_col: str,
) -> list[dict[str, str]]:
    paf_name_map = _build_paf_name_map(
        preview_columns=preview_columns,
        town_col=town_col,
        county_col=county_col,
        postcode_col=postcode_col,
    )

    specs: list[dict[str, str]] = []
    for src_col in preview_columns:
        paf_name = paf_name_map[src_col]
        specs.append(
            {
                "source": src_col,
                "paf": paf_name,
                "preview": f"{paf_name} (Preview)",
            }
        )
    return specs

def _rename_to_paf_columns(
    df: pd.DataFrame,
    *,
    preview_columns: list[str],
    town_col: str | None,
    county_col: str | None,
    postcode_col: str,
) -> pd.DataFrame:
    out = df.copy()
    rename_map = _build_paf_name_map(
        preview_columns=preview_columns,
        town_col=town_col,
        county_col=county_col,
        postcode_col=postcode_col,
    )
    out.rename(columns=rename_map, inplace=True)
    return out

def _normalise_weight_series(series: pd.Series) -> pd.Series:
    def convert(value):
        if pd.isna(value):
            return ""

        s = str(value).strip()
        if not s or s.lower() == "nan":
            return ""

        s_lower = s.lower()

        if s_lower.endswith("kg"):
            num = s[:-2].strip()
            try:
                grams = float(num) * 1000
            except ValueError:
                return s
            return str(int(grams)) if grams.is_integer() else str(grams)

        if s_lower.endswith("g"):
            num = s[:-1].strip()
            try:
                grams = float(num)
            except ValueError:
                return s
            return str(int(grams)) if grams.is_integer() else str(grams)

        try:
            n = float(s)
            return str(int(n)) if n.is_integer() else str(n)
        except ValueError:
            return s

    return series.map(convert)

def _apply_info_field(
    df: pd.DataFrame,
    *,
    mode: str | None,
    source_column: str | None,
    text_value: str | None,
    output_column: str,
) -> pd.DataFrame:
    out = df.copy()

    if mode == "a":
        if source_column and source_column in out.columns:
            if source_column != output_column:
                out.rename(columns={source_column: output_column}, inplace=True)
    elif mode == "b":
        out[output_column] = str(text_value or "").strip()

    if output_column == "Weight" and output_column in out.columns:
        out[output_column] = _normalise_weight_series(out[output_column])

    return out

def _validate_info_field(
    workflow: BaseWorkflow,
    *,
    df: pd.DataFrame,
    mode: str | None,
    source_column: str | None,
    text_value: str | None,
    field_label: str,
) -> bool:
    if mode == "a":
        if (
            not source_column
            or source_column == "__select__"
            or source_column not in df.columns
        ):
            workflow.warn("Create E-Commerce File", f"Please select a {field_label.lower()} column.")
            return False

    elif mode == "b":
        if not str(text_value or "").strip():
            workflow.warn("Create E-Commerce File", f"Please enter a {field_label.lower()} value.")
            return False

    return True

def _populate_missing_town_from_county_or_address(
    df: pd.DataFrame,
    *,
    town_col: str,
    county_col: str | None,
    postcode_col: str,
    preview_columns: list[str],
) -> pd.DataFrame:
    out = df.copy()

    if town_col not in out.columns:
        return out

    county_exists = bool(
        county_col
        and county_col != "__select__"
        and county_col in out.columns
    )

    address_fallback_cols = [
        c for c in preview_columns
        if c in out.columns and c not in {town_col, county_col, postcode_col}
    ]

    for row_index in out.index:
        current_town = out.at[row_index, town_col]
        if not _is_blank_value(current_town):
            continue

        if county_exists:
            county_value = out.at[row_index, county_col]
            if not _is_blank_value(county_value):
                out.at[row_index, town_col] = county_value
                out.at[row_index, county_col] = ""
                continue

        for src_col in reversed(address_fallback_cols):
            src_value = out.at[row_index, src_col]
            if _is_blank_value(src_value):
                continue

            out.at[row_index, town_col] = src_value
            out.at[row_index, src_col] = ""
            break

    return out

def _multiply_weight_by_quantity(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "Weight" not in out.columns or "Quantity" not in out.columns:
        return out

    def to_number(value):
        if pd.isna(value):
            return None
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    multiplied = []
    for _, row in out.iterrows():
        weight = to_number(row.get("Weight"))
        qty = to_number(row.get("Quantity"))

        if weight is None or qty is None:
            multiplied.append(row.get("Weight", ""))
            continue

        result = weight * qty
        multiplied.append(str(int(result)) if float(result).is_integer() else str(result))

    out["Weight"] = multiplied
    return out

def _apply_recipient_name(
    df: pd.DataFrame,
    *,
    name_mode: str | None,
    name_column: str | None,
    name_text: str | None,
    surname_mode: str | None,
    surname_column: str | None,
    surname_text: str | None,
) -> pd.DataFrame:
    out = df.copy()

    def resolve_series(
        *,
        mode: str | None,
        source_column: str | None,
        text_value: str | None,
    ) -> pd.Series:
        if mode == "a" and source_column and source_column in out.columns:
            return out[source_column].fillna("").astype(str).str.strip()

        if mode == "b":
            value = str(text_value or "").strip()
            return pd.Series([value] * len(out), index=out.index, dtype="object")

        return pd.Series([""] * len(out), index=out.index, dtype="object")

    first = resolve_series(
        mode=name_mode,
        source_column=name_column,
        text_value=name_text,
    )

    last = resolve_series(
        mode=surname_mode,
        source_column=surname_column,
        text_value=surname_text,
    )

    recipient = first.where(last.eq(""), first + " " + last)
    recipient = recipient.fillna("").astype(str).str.strip()

    out["Recipient Name"] = recipient

    drop_cols: list[str] = []

    if name_mode == "a" and name_column in out.columns:
        drop_cols.append(name_column)

    if surname_mode == "a" and surname_column in out.columns:
        drop_cols.append(surname_column)

    if drop_cols:
        out.drop(columns=list(dict.fromkeys(drop_cols)), inplace=True)

    return out

def _use_old_service_code(
    df: pd.DataFrame,
    *,
    services_repo: ServicesRepository,
    service_column: str = "Service",
) -> pd.DataFrame:
    out = df.copy()

    if service_column not in out.columns:
        return out

    raw_values = out[service_column].fillna("").astype(str)
    keys = raw_values.map(lambda v: v.strip().upper())
    lookup = services_repo.get_old_codes_by_new_codes(keys.tolist())

    if not lookup:
        return out

    out[service_column] = [
        lookup.get(key, original)
        for original, key in zip(raw_values.tolist(), keys.tolist())
    ]
    return out

def _to_float_or_none(value) -> float | None:
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

def _normalise_service_code(value) -> str:
    return str(value or "").strip().upper()

def _service_rule_maps(
    services_repo: ServicesRepository,
) -> tuple[dict[str, dict], dict[str, dict]]:
    rows = services_repo.list_all(limit=100000)

    by_new: dict[str, dict] = {}
    by_old: dict[str, dict] = {}

    for row in rows:
        new_code = _normalise_service_code(row.get("new_code"))
        old_code = _normalise_service_code(row.get("old_code"))

        if new_code:
            by_new[new_code] = row
        if old_code:
            by_old[old_code] = row

    return by_new, by_old

def _service_rule_cache(
    services_repo: ServicesRepository,
) -> dict[str, Any]:
    by_new, by_old = _service_rule_maps(services_repo)
    all_rules = list(by_new.values())

    return {
        "by_new": by_new,
        "by_old": by_old,
        "all_rules": all_rules,
    }

def _find_service_rule(
    service_value: str,
    by_new: dict[str, dict],
    by_old: dict[str, dict],
) -> dict | None:
    key = _normalise_service_code(service_value)
    if not key:
        return None
    return by_new.get(key) or by_old.get(key)

def _service_fits_rule(
    *,
    length_value,
    width_value,
    height_value,
    weight_value,
    rule: dict,
) -> bool:
    length = _to_float_or_none(length_value)
    width = _to_float_or_none(width_value)
    height = _to_float_or_none(height_value)
    weight = _to_float_or_none(weight_value)

    min_length = _to_float_or_none(rule.get("min_length_mm"))
    min_width = _to_float_or_none(rule.get("min_width_mm"))
    min_height = _to_float_or_none(rule.get("min_height_mm"))

    max_length = _to_float_or_none(rule.get("max_length_mm"))
    max_width = _to_float_or_none(rule.get("max_width_mm"))
    max_height = _to_float_or_none(rule.get("max_height_mm"))
    max_weight = _to_float_or_none(rule.get("max_weight_g"))

    dimension_pairs = [
        (length, min_length, max_length),
        (width, min_width, max_width),
        (height, min_height, max_height),
    ]

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

def _service_display_code(rule: dict) -> str:
    old_code = _normalise_service_code(rule.get("old_code"))
    new_code = _normalise_service_code(rule.get("new_code"))
    return old_code or new_code

def _service_reject_reason(
    *,
    service_value,
    length_value,
    width_value,
    height_value,
    weight_value,
    by_new: dict[str, dict],
    by_old: dict[str, dict],
) -> str | None:
    rule = _find_service_rule(service_value, by_new, by_old)
    if rule is None:
        return "Invalid Service"

    if not _service_fits_rule(
        length_value=length_value,
        width_value=width_value,
        height_value=height_value,
        weight_value=weight_value,
        rule=rule,
    ):
        max_weight = _to_float_or_none(rule.get("max_weight_g"))
        weight = _to_float_or_none(weight_value)
        if weight is not None and max_weight is not None and weight > max_weight:
            return "Too Heavy For Selected Service"
        return "Outside Selected Service Dimensions"

    return None

def _valid_services_for_rows(
    rows: list[dict[str, Any]],
    *,
    all_rules: list[dict],
) -> list[str]:
    valid_codes: list[str] = []
    seen: set[str] = set()

    for rule in all_rules:
        code = _service_display_code(rule)
        if not code or code in seen:
            continue

        for row in rows:
            if _service_fits_rule(
                length_value=row.get("Length"),
                width_value=row.get("Width"),
                height_value=row.get("Height"),
                weight_value=row.get("Weight"),
                rule=rule,
            ):
                seen.add(code)
                valid_codes.append(code)
                break

    valid_codes.sort()
    return valid_codes

def _concat_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    usable = [f.copy() for f in frames if f is not None and not f.empty]
    if not usable:
        return pd.DataFrame()
    return pd.concat(usable, ignore_index=True, sort=False)

def _apply_max_service_dimensions(
    df: pd.DataFrame,
    *,
    services_repo: ServicesRepository,
    service_column: str = "Service",
) -> pd.DataFrame:
    out = df.copy()

    if service_column not in out.columns:
        return out

    by_new, by_old = _service_rule_maps(services_repo)

    def _scalar_text(row, col: str) -> str:
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

    def _rule_or_existing(rule_value, existing_value) -> str:
        if pd.isna(rule_value):
            return existing_value
        text = str(rule_value).strip()
        return text if text else existing_value

    lengths: list[str] = []
    widths: list[str] = []
    heights: list[str] = []

    for _, row in out.iterrows():
        service_value = _scalar_text(row, service_column)
        rule = _find_service_rule(service_value, by_new, by_old)

        existing_length = _scalar_text(row, "Length")
        existing_width = _scalar_text(row, "Width")
        existing_height = _scalar_text(row, "Height")

        if rule is None:
            lengths.append(existing_length)
            widths.append(existing_width)
            heights.append(existing_height)
            continue

        lengths.append(_rule_or_existing(rule.get("max_length_mm"), existing_length))
        widths.append(_rule_or_existing(rule.get("max_width_mm"), existing_width))
        heights.append(_rule_or_existing(rule.get("max_height_mm"), existing_height))

    out["Length"] = lengths
    out["Width"] = widths
    out["Height"] = heights
    return out

def _return_address_output_map(row: dict[str, Any]) -> dict[str, str]:
    return {
        "Return Contact Name": "" if pd.isna(row.get("contact_name")) else str(row.get("contact_name", "")).strip(),
        "Return Address 1": "" if pd.isna(row.get("address1")) else str(row.get("address1", "")).strip(),
        "Return Address 2": "" if pd.isna(row.get("address2")) else str(row.get("address2", "")).strip(),
        "Return Address 3": "" if pd.isna(row.get("address3")) else str(row.get("address3", "")).strip(),
        "Return Town": "" if pd.isna(row.get("Town")) else str(row.get("Town", "")).strip(),
        "Return Postcode": "" if pd.isna(row.get("postcode")) else str(row.get("postcode", "")).strip(),
    }
    
def _apply_return_address(
    df: pd.DataFrame,
    *,
    selected_return_address: str | None,
    return_addresses_repo: ReturnAddressesRepository,
) -> pd.DataFrame:
    selected = str(selected_return_address or "").strip()
    if not selected or selected == "__select__":
        return df

    matches = return_addresses_repo.search(selected, limit=100000)
    chosen = next(
        (
            row for row in matches
            if str(row.get("contact_name", "")).strip() == selected
        ),
        None,
    )
    if chosen is None:
        return df

    out = df.copy()
    values = _return_address_output_map(chosen)

    for col_name, value in values.items():
        out[col_name] = value

    return out

def _build_return_address_options(repo: ReturnAddressesRepository) -> list[tuple[str, str]]:
    rows = repo.list_all(limit=100000)

    names: list[str] = []
    seen: set[str] = set()

    for row in rows:
        name = str(row.get("contact_name", "") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)

    names.sort(key=lambda x: x.lower())
    return [("— Select —", "__select__")] + [(name, name) for name in names]

def _sorted_paf_address_columns(columns: list[str]) -> list[str]:
    def sort_key(col: str) -> tuple[int, str]:
        text = str(col)
        prefix = "PAF Address "
        if text.startswith(prefix):
            suffix = text[len(prefix):].strip()
            try:
                return (0, int(suffix))
            except ValueError:
                return (0, 999999)
        return (1, text.lower())

    return sorted(
        [str(c) for c in columns if str(c).startswith("PAF Address ")],
        key=sort_key,
    )

def _order_ecommerce_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()
    cols = [str(c) for c in out.columns]

    ordered: list[str] = []

    def add(col: str):
        if col in out.columns and col not in ordered:
            ordered.append(col)

    leading_fixed = [
        "Client Item Reference",
        "Recipient Name",
        "Company",
    ]

    service_block = [
        "Service",
        "Weight",
        "Length",
        "Width",
        "Height",
        "Country Code",
        "Quantity",
        "Product Description",
        "Retail Value",
    ]

    return_address_block = [
        "Return Contact Name",
        "Return Address 1",
        "Return Address 2",
        "Return Address 3",
        "Return Town",
        "Return Postcode",
    ]

    for col in leading_fixed:
        add(col)

    for col in _sorted_paf_address_columns(cols):
        add(col)

    add(PAF_TOWN_COL)
    add(PAF_COUNTY_COL)
    add(PAF_POSTCODE_COL)

    reserved = set(ordered) | set(service_block) | set(return_address_block)

    middle = [c for c in out.columns if c not in reserved]
    ordered.extend(middle)

    for col in service_block:
        add(col)

    for col in return_address_block:
        add(col)

    for col in out.columns:
        if col not in ordered:
            ordered.append(col)

    return out.loc[:, ordered]

class CreateEcommerceFile(BaseWorkflow):
    RECIPIENT_FIELD_SPECS = [
        {"prefix": "name", "label": "Name", "required": True},
        {"prefix": "surname", "label": "Surname", "required": False},
    ]

    INFO_FIELD_SPECS = [
        {"prefix": "company", "label": "Company", "output": "Company", "required": False},
        {"prefix": "reference", "label": "Reference", "output": "Client Item Reference", "required": True},
        {"prefix": "service", "label": "Service", "output": "Service", "required": True},
        {"prefix": "weight", "label": "Weight", "output": "Weight", "required": True},
        {"prefix": "length", "label": "Length", "output": "Length", "required": True},
        {"prefix": "width", "label": "Width", "output": "Width", "required": True},
        {"prefix": "height", "label": "Height", "output": "Height", "required": True},
        {"prefix": "country_code", "label": "Country Code", "output": "Country Code", "required": False},
        {"prefix": "quantity", "label": "Quantity", "output": "Quantity", "required": False},
        {"prefix": "product_description", "label": "Product Description", "output": "Product Description", "required": False},
        {"prefix": "retail_value", "label": "Retail Value", "output": "Retail Value", "required": False},
    ]

    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        def on_loaded(df: pd.DataFrame, has_header: bool):
            if df is None or df.empty:
                self.warn("Create E-Commerce File", "File contains no data.")
                return

            opts = self._prompt_for_options(df)
            if opts is None:
                return

            if not self._validate_core_options(df, opts):
                return

            fields = self._collect_fields(opts)
            multiply_weight_by_quantity = bool(opts.get("multiply_weight_by_quantity", False))
            change_service_code = bool(opts.get("change_service_code", True))
            use_max_service_dimensions = bool(opts.get("use_max_service_dimensions", False))
            selected_return_address = opts.get("return_address")

            if not self._validate_selected_fields(
                df,
                fields=fields,
                use_max_service_dimensions=use_max_service_dimensions,
            ):
                return

            postcode_col = str(opts["postcode_column"])
            town_col = str(opts["town_column"])
            county_col = opts.get("county_column")
            address_start = opts.get("address_start")
            address_end = opts.get("address_end")
            out_delim = (opts.get("delimiter") or ",").strip() or ","

            try:
                preview_columns = _build_preview_columns(
                    all_columns=list(df.columns),
                    address_start=address_start,
                    address_end=address_end,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
            except ValueError as e:
                self.warn("Create E-Commerce File", str(e))
                return

            preview_specs = _build_preview_specs(
                preview_columns=preview_columns,
                town_col=town_col,
                county_col=county_col,
                postcode_col=postcode_col,
            )

            prepared_df = _populate_missing_town_from_county_or_address(
                df,
                town_col=town_col,
                county_col=county_col,
                postcode_col=postcode_col,
                preview_columns=preview_columns,
            )

            resolution_state = self._collect_paf_resolution_state(
                prepared_df,
                postcode_col=postcode_col,
                town_col=town_col,
                preview_specs=preview_specs,
            )

            resolution_result = self._run_paf_resolution_dialog_if_needed(
                resolution_state=resolution_state,
                postcode_col=postcode_col,
                town_col=town_col,
            )
            if resolution_result is None:
                return

            def job_build():
                return self._build_pre_service_frames(
                    prepared_df=prepared_df,
                    postcode_col=postcode_col,
                    fields=fields,
                    multiply_weight_by_quantity=multiply_weight_by_quantity,
                    change_service_code=change_service_code,
                    use_max_service_dimensions=use_max_service_dimensions,
                    selected_return_address=selected_return_address,
                    resolution_state=resolution_state,
                    resolution_result=resolution_result,
                )

            def on_done(build_result):
                if build_result is None:
                    return

                working_df, paf_reject_df = build_result

                working_df = self._run_service_resolution_loop(
                    working_df,
                    use_max_service_dimensions=use_max_service_dimensions,
                )
                if working_df is None:
                    return

                working_df, service_reject_df = self._split_valid_and_service_rejects(working_df)

                valid_df = _rename_to_paf_columns(
                    working_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                valid_df = _order_ecommerce_output_columns(valid_df)

                paf_reject_df = self._rename_reject_frame_to_paf(
                    paf_reject_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                paf_reject_df = _order_ecommerce_output_columns(paf_reject_df)

                service_reject_df = self._rename_reject_frame_to_paf(
                    service_reject_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )
                service_reject_df = _order_ecommerce_output_columns(service_reject_df)

                reject_df = _concat_frames([paf_reject_df, service_reject_df])
                if reject_df is not None and not reject_df.empty:
                    reject_df = _order_ecommerce_output_columns(reject_df)

                edited = self.preview_dialog(valid_df, title="Preview (E-Commerce File)")
                if edited is None:
                    return

                edited = self.drop_empty_rows_cols(edited)

                outfile = self.ask_save_csv_default_from_infile(
                    infile,
                    title="Save E-Commerce output file",
                    suffix=" (ecommerce).csv",
                    filter="CSV Files (*.csv);;All Files (*)",
                )
                if not outfile:
                    return

                self.save_csv_then(
                    edited,
                    outfile,
                    title="Create E-Commerce File",
                    delimiter=out_delim,
                    has_header=has_header,
                    success_msg="E-Commerce file created successfully.",
                    sanitize=True,
                )

                if reject_df is not None and not reject_df.empty:
                    reject_path = outfile.replace(".csv", "_Rejects.csv")
                    reject_df.to_csv(reject_path, index=False)

            self.busy(
                "Create E-Commerce File",
                "Building E-Commerce file…",
                job_build,
                on_done=on_done,
                on_err=lambda e: self.fail("Create E-Commerce File", e),
                cancelable=True,
            )

        self.load_df_then(
            infile,
            title="Create E-Commerce File",
            header_mode="none",
            on_loaded=on_loaded,
        )

    def _prompt_for_options(self, df: pd.DataFrame) -> dict[str, Any] | None:
        col_options = [("— Select —", "__select__")]
        col_options += [(str(c), str(c)) for c in df.columns]

        return_addresses_repo = ReturnAddressesRepository()
        return_address_options = _build_return_address_options(return_addresses_repo)

        preview_rows = df.head(10).fillna("").to_dict("records")
        schema = build_create_ecommerce_file_schema(
            column_options=col_options,
            preview_rows=preview_rows,
            return_address_options=return_address_options,
        )

        detected_defaults = _detect_ecommerce_defaults(list(df.columns))
        _apply_schema_defaults(schema, detected_defaults)

        dlg = OptionsDialog(schema,parent=self.mw,title="Create E-Commerce File",
                            initial_size=(1400, 900),
                            minimum_size=(1320, 900),
                            minimum_content_width=1200)

        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_results()

    def _validate_core_options(self, df: pd.DataFrame, opts: dict[str, Any]) -> bool:
        postcode_col = opts.get("postcode_column")
        town_col = opts.get("town_column")
        county_col = opts.get("county_column")

        if not postcode_col or postcode_col == "__select__" or postcode_col not in df.columns:
            self.warn("Create E-Commerce File", "Please select a postcode column.")
            return False

        if not town_col or town_col == "__select__" or town_col not in df.columns:
            self.warn("Create E-Commerce File", "Please select a town column.")
            return False

        if county_col and county_col != "__select__" and county_col not in df.columns:
            self.warn("Create E-Commerce File", "Selected county column was not found.")
            return False

        return True

    def _read_switch_field(self, opts: dict[str, Any], prefix: str) -> dict[str, Any]:
        return {
            "mode": opts.get(f"{prefix}_mode"),
            "column": opts.get(f"{prefix}_column"),
            "text": opts.get(f"{prefix}_text"),
        }

    def _collect_fields(self, opts: dict[str, Any]) -> dict[str, dict[str, Any]]:
        fields: dict[str, dict[str, Any]] = {}

        for spec in self.RECIPIENT_FIELD_SPECS:
            field = self._read_switch_field(opts, spec["prefix"])
            field["label"] = spec["label"]
            field["required"] = spec["required"]
            fields[spec["prefix"]] = field

        for spec in self.INFO_FIELD_SPECS:
            field = self._read_switch_field(opts, spec["prefix"])
            field["label"] = spec["label"]
            field["required"] = spec["required"]
            field["output"] = spec["output"]
            fields[spec["prefix"]] = field

        return fields

    def _validate_selected_fields(
        self,
        df: pd.DataFrame,
        *,
        fields: dict[str, dict[str, Any]],
        use_max_service_dimensions: bool = False,
    ) -> bool:
        for spec in self.RECIPIENT_FIELD_SPECS:
            field = fields[spec["prefix"]]
            if field["required"]:
                if not _validate_info_field(
                    self,
                    df=df,
                    mode=field.get("mode"),
                    source_column=field.get("column"),
                    text_value=field.get("text"),
                    field_label=field["label"],
                ):
                    return False

        for spec in self.INFO_FIELD_SPECS:
            field = fields[spec["prefix"]]

            if use_max_service_dimensions and field.get("output") in {"Length", "Width", "Height"}:
                continue

            if field["required"]:
                if not _validate_info_field(
                    self,
                    df=df,
                    mode=field.get("mode"),
                    source_column=field.get("column"),
                    text_value=field.get("text"),
                    field_label=field["label"],
                ):
                    return False

        return True
    
    def _collect_paf_resolution_state(
        self,
        prepared_df: pd.DataFrame,
        *,
        postcode_col: str,
        town_col: str,
        preview_specs: list[dict[str, str]],
    ) -> dict[str, Any]:
        collapsed_postcodes = _collapse_postcode_series(prepared_df[postcode_col])
        unique_vals = {v for v in collapsed_postcodes.tolist() if v}

        repo = self.mw.s.postcodes_repo
        existing = repo.existing_postcode_set(unique_vals)
        matched_mask = collapsed_postcodes.isin(existing)

        town_series = _collapse_text_series(prepared_df[town_col])
        town_missing_mask = town_series.eq("") | town_series.str.lower().eq("nan")

        resolution_mask = (~matched_mask) | town_missing_mask
        resolution_df = prepared_df.loc[resolution_mask].copy()
        resolution_postcodes = collapsed_postcodes[resolution_mask].tolist()
        resolution_indices = list(prepared_df[resolution_mask].index)

        issue_labels: list[str] = []
        for row_index in resolution_indices:
            reasons = []
            if not bool(matched_mask.loc[row_index]):
                reasons.append("Postcode not found")
            if bool(town_missing_mask.loc[row_index]):
                reasons.append("Town missing")
            issue_labels.append(", ".join(reasons) if reasons else "Review")

        row_previews: list[dict[str, str]] = []
        if preview_specs:
            for _, row in resolution_df.iterrows():
                preview: dict[str, str] = {}
                for spec in preview_specs:
                    value = row.get(spec["source"], "")
                    preview[spec["preview"]] = "" if pd.isna(value) else str(value)
                row_previews.append(preview)

        return {
            "resolution_indices": resolution_indices,
            "resolution_postcodes": resolution_postcodes,
            "issue_labels": issue_labels,
            "row_previews": row_previews,
            "preview_specs": preview_specs,
        }

    def _run_paf_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
        postcode_col: str,
        town_col: str,
    ) -> dict[str, Any] | None:
        if not resolution_state["resolution_postcodes"]:
            return {
                "corrected": {},
                "added": {},
                "removed": set(),
                "row_updates": {},
            }

        dialog = PAFResolutionDialog(
            current_postcodes=resolution_state["resolution_postcodes"],
            issue_labels=resolution_state["issue_labels"],
            row_previews=resolution_state["row_previews"],
            preview_specs=resolution_state["preview_specs"],
            postcode_column=postcode_col,
            town_column=town_col,
            normalizer=lambda x: _collapse_postcode_series(pd.Series([x]))[0],
            parent=self.mw,
        )

        if not dialog.exec():
            return None

        result = dialog.result()
        return {
            "corrected": result["corrected"],
            "added": result["added"],
            "removed": result["removed"],
            "row_updates": result.get("row_updates", {}),
        }

    def _apply_all_info_fields(
        self,
        frame: pd.DataFrame,
        *,
        fields: dict[str, dict[str, Any]],
        multiply_weight_by_quantity: bool,
        change_service_code: bool,
    ) -> pd.DataFrame:
        out = frame.copy()

        out = _apply_recipient_name(
            out,
            name_mode=fields["name"].get("mode"),
            name_column=fields["name"].get("column"),
            name_text=fields["name"].get("text"),
            surname_mode=fields["surname"].get("mode"),
            surname_column=fields["surname"].get("column"),
            surname_text=fields["surname"].get("text"),
        )

        for spec in self.INFO_FIELD_SPECS:
            field = fields[spec["prefix"]]
            out = _apply_info_field(
                out,
                mode=field.get("mode"),
                source_column=field.get("column"),
                text_value=field.get("text"),
                output_column=spec["output"],
            )

        if change_service_code:
            services_repo = ServicesRepository()
            out = _use_old_service_code(
                out,
                services_repo=services_repo,
                service_column="Service",
            )

        if multiply_weight_by_quantity:
            out = _multiply_weight_by_quantity(out)

        return out

    def _build_pre_service_frames(
        self,
        *,
        prepared_df: pd.DataFrame,
        postcode_col: str,
        fields: dict[str, dict[str, Any]],
        multiply_weight_by_quantity: bool,
        change_service_code: bool,
        use_max_service_dimensions: bool,
        selected_return_address: str | None,
        resolution_state: dict[str, Any],
        resolution_result: dict[str, Any],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        repo = self.mw.s.postcodes_repo
        working_df = prepared_df.copy()
        paf_reject_rows = []

        resolution_indices = resolution_state["resolution_indices"]
        corrected = resolution_result["corrected"]
        added = resolution_result["added"]
        removed = resolution_result["removed"]
        row_updates = resolution_result["row_updates"]

        for i, row_index in enumerate(resolution_indices):
            if row_index not in working_df.index:
                continue

            if i in removed:
                paf_reject_rows.append(working_df.loc[row_index].copy())
                working_df.drop(index=row_index, inplace=True)
                continue

            updates = row_updates.get(i, {})
            for col, value in updates.items():
                if col in working_df.columns:
                    working_df.loc[row_index, col] = value

            if i in corrected:
                working_df.loc[row_index, postcode_col] = corrected[i]
                continue

            if i in added:
                working_df.loc[row_index, postcode_col] = added[i]
                repo.insert_postcode(added[i])
                continue

            paf_reject_rows.append(working_df.loc[row_index].copy())
            working_df.drop(index=row_index, inplace=True)

        working_df.reset_index(drop=True, inplace=True)

        working_df = self._apply_all_info_fields(
            working_df,
            fields=fields,
            multiply_weight_by_quantity=multiply_weight_by_quantity,
            change_service_code=change_service_code,
        )

        working_df = _apply_return_address(
            working_df,
            selected_return_address=selected_return_address,
            return_addresses_repo=ReturnAddressesRepository(),
        )

        if use_max_service_dimensions:
            working_df = _apply_max_service_dimensions(
                working_df,
                services_repo=ServicesRepository(),
                service_column="Service",
            )

        paf_reject_df = pd.DataFrame(paf_reject_rows)
        if not paf_reject_df.empty:
            paf_reject_df.reset_index(drop=True, inplace=True)
            paf_reject_df = self._apply_all_info_fields(
                paf_reject_df,
                fields=fields,
                multiply_weight_by_quantity=multiply_weight_by_quantity,
                change_service_code=change_service_code,
            )

            paf_reject_df = _apply_return_address(
                paf_reject_df,
                selected_return_address=selected_return_address,
                return_addresses_repo=ReturnAddressesRepository(),
            )

            if use_max_service_dimensions:
                paf_reject_df = _apply_max_service_dimensions(
                    paf_reject_df,
                    services_repo=ServicesRepository(),
                    service_column="Service",
                )

        return working_df, paf_reject_df
    
    def _collect_service_resolution_state(
        self,
        df: pd.DataFrame,
        *,
        rule_cache: dict[str, Any],
    ) -> dict[str, Any]:
        by_new = rule_cache["by_new"]
        by_old = rule_cache["by_old"]

        resolution_indices: list[int] = []
        rows: list[dict[str, str]] = []

        required_cols = ["Length", "Width", "Height", "Weight", "Service"]
        for col in required_cols:
            if col not in df.columns:
                return {
                    "resolution_indices": [],
                    "rows": [],
                    "valid_services": [],
                }

        for idx, row in df.iterrows():
            reject_reason = _service_reject_reason(
                service_value=row.get("Service"),
                length_value=row.get("Length"),
                width_value=row.get("Width"),
                height_value=row.get("Height"),
                weight_value=row.get("Weight"),
                by_new=by_new,
                by_old=by_old,
            )

            if not reject_reason:
                continue

            resolution_indices.append(int(idx))
            rows.append(
                {
                    "Length": "" if pd.isna(row.get("Length")) else str(row.get("Length")),
                    "Width": "" if pd.isna(row.get("Width")) else str(row.get("Width")),
                    "Height": "" if pd.isna(row.get("Height")) else str(row.get("Height")),
                    "Weight": "" if pd.isna(row.get("Weight")) else str(row.get("Weight")),
                    "Service": "" if pd.isna(row.get("Service")) else str(row.get("Service")),
                    "Reject Reason": reject_reason,
                }
            )

        valid_services = _valid_services_for_rows(
            rows,
            all_rules=rule_cache["all_rules"],
        )

        return {
            "resolution_indices": resolution_indices,
            "rows": rows,
            "valid_services": valid_services,
        }

    def _run_service_resolution_dialog_if_needed(
        self,
        *,
        resolution_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not resolution_state["rows"]:
            return {
                "rows": [],
                "original_rows": [],
                "mass_update": {},
            }

        dlg = ServiceResolutionDialog(
            resolution_state["rows"],
            valid_services=resolution_state["valid_services"],
            parent=self.mw,
        )
        if not dlg.exec():
            return None

        return {
            "rows": dlg.result_rows(),
            "original_rows": [dict(r or {}) for r in resolution_state["rows"]],
            "mass_update": dlg.mass_update_values(),
        }

    def _apply_service_resolution_result(
        self,
        df: pd.DataFrame,
        *,
        resolution_indices: list[int],
        result: dict[str, Any],
        use_max_service_dimensions: bool = False,
    ) -> pd.DataFrame:
        out = df.copy()
        edited_rows = list(result.get("rows", []) or [])
        original_rows = list(result.get("original_rows", []) or [])
        mass_update = dict(result.get("mass_update") or {})

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

                out.loc[idx, col] = value_to_write

        if use_max_service_dimensions:
            out = _apply_max_service_dimensions(
                out,
                services_repo=ServicesRepository(),
                service_column="Service",
            )

        return out

    def _run_service_resolution_loop(
        self,
        df: pd.DataFrame,
        *,
        use_max_service_dimensions: bool = False,
    ) -> pd.DataFrame | None:
        services_repo = ServicesRepository()
        rule_cache = _service_rule_cache(services_repo)

        working_df = df.copy()

        if use_max_service_dimensions:
            working_df = _apply_max_service_dimensions(
                working_df,
                services_repo=services_repo,
                service_column="Service",
            )

        while True:
            resolution_state = self._collect_service_resolution_state(
                working_df,
                rule_cache=rule_cache,
            )

            if not resolution_state["rows"]:
                return working_df

            if not resolution_state["valid_services"]:
                self.warn(
                    "Resolve Services",
                    "No valid services are available for the current rejected rows.",
                )
                return None

            result = self._run_service_resolution_dialog_if_needed(
                resolution_state=resolution_state,
            )
            if result is None:
                return None

            working_df = self._apply_service_resolution_result(
                working_df,
                resolution_indices=resolution_state["resolution_indices"],
                result=result,
                use_max_service_dimensions=use_max_service_dimensions,
            )

    def _split_valid_and_service_rejects(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        services_repo = ServicesRepository()
        by_new, by_old = _service_rule_maps(services_repo)

        valid_indices: list[int] = []
        reject_rows: list[dict[str, Any]] = []

        for idx, row in df.iterrows():
            reject_reason = _service_reject_reason(
                service_value=row.get("Service"),
                length_value=row.get("Length"),
                width_value=row.get("Width"),
                height_value=row.get("Height"),
                weight_value=row.get("Weight"),
                by_new=by_new,
                by_old=by_old,
            )

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

    def _rename_reject_frame_to_paf(
        self,
        df: pd.DataFrame,
        *,
        preview_columns: list[str],
        town_col: str | None,
        county_col: str | None,
        postcode_col: str,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        return _rename_to_paf_columns(
            df,
            preview_columns=preview_columns,
            town_col=town_col,
            county_col=county_col,
            postcode_col=postcode_col,
        )