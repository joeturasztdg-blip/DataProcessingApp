from __future__ import annotations

import pandas as pd

from PySide6.QtWidgets import QDialog

from workspace.base import BaseWorkflow
from config.schemas import build_create_ecommerce_file_schema
from gui.paf_resolution_dialog import PAFResolutionDialog
from gui.options_dialog import OptionsDialog


PAF_POSTCODE_COL = "PAF Postcode"
PAF_TOWN_COL = "PAF Town"
PAF_COUNTY_COL = "PAF County"
CLIENT_ITEM_REFERENCE_COL = "Client Item Reference"


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

        address_columns = all_columns[start_idx:end_idx + 1]

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


def _apply_client_item_reference(
    df: pd.DataFrame,
    *,
    reference_mode: str | None,
    reference_column: str | None,
    reference_text: str | None,
) -> pd.DataFrame:
    out = df.copy()

    if reference_mode == "a":
        if reference_column and reference_column in out.columns:
            if reference_column != CLIENT_ITEM_REFERENCE_COL:
                out.rename(columns={reference_column: CLIENT_ITEM_REFERENCE_COL}, inplace=True)
    elif reference_mode == "b":
        out[CLIENT_ITEM_REFERENCE_COL] = str(reference_text or "").strip()

    return out


class CreateEcommerceFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)"
        )
        if not infile:
            return

        def on_loaded(df: pd.DataFrame, has_header: bool):
            if df is None or df.empty:
                self.warn("Create E-Commerce File", "File contains no data.")
                return

            col_options = [("— Select —", "__select__")]
            col_options += [(str(c), str(c)) for c in df.columns]

            preview_rows = df.head(10).fillna("").to_dict("records")
            schema = build_create_ecommerce_file_schema(
                column_options=col_options,
                preview_rows=preview_rows
            )

            dlg = OptionsDialog(schema, parent=self.mw, title="Create E-Commerce File")
            dlg.setMinimumSize(1000, 750)

            if dlg.exec() != QDialog.Accepted:
                return

            opts = dlg.get_results()

            postcode_col = opts.get("postcode_column")
            town_col = opts.get("town_column")
            county_col = opts.get("county_column")
            address_start = opts.get("address_start")
            address_end = opts.get("address_end")
            reference_mode = opts.get("reference_mode")
            reference_column = opts.get("reference_column")
            reference_text = opts.get("reference_text")

            if not postcode_col or postcode_col == "__select__" or postcode_col not in df.columns:
                self.warn("Create E-Commerce File", "Please select a postcode column.")
                return

            if not town_col or town_col == "__select__" or town_col not in df.columns:
                self.warn("Create E-Commerce File", "Please select a town column.")
                return

            if county_col and county_col != "__select__" and county_col not in df.columns:
                self.warn("Create E-Commerce File", "Selected county column was not found.")
                return

            if reference_mode == "a":
                if (
                    not reference_column
                    or reference_column == "__select__"
                    or reference_column not in df.columns
                ):
                    self.warn("Create E-Commerce File", "Please select a reference column.")
                    return
            elif reference_mode == "b":
                if not str(reference_text or "").strip():
                    self.warn("Create E-Commerce File", "Please enter a reference value.")
                    return

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

            collapsed_postcodes = _collapse_postcode_series(df[postcode_col])
            unique_vals = {v for v in collapsed_postcodes.tolist() if v}

            repo = self.mw.s.postcodes_repo
            existing = repo.existing_postcode_set(unique_vals)

            matched_mask = collapsed_postcodes.isin(existing)

            town_series = _collapse_text_series(df[town_col])
            town_missing_mask = town_series.eq("") | town_series.str.lower().eq("nan")

            resolution_mask = (~matched_mask) | town_missing_mask

            resolution_df = df.loc[resolution_mask].copy()
            resolution_postcodes = collapsed_postcodes[resolution_mask].tolist()

            issue_labels: list[str] = []
            resolution_indices = list(df[resolution_mask].index)
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
                    preview = {}
                    for spec in preview_specs:
                        value = row.get(spec["source"], "")
                        preview[spec["preview"]] = "" if pd.isna(value) else str(value)
                    row_previews.append(preview)

            corrected = {}
            added = {}
            removed = set()
            row_updates = {}

            if resolution_postcodes:
                dialog = PAFResolutionDialog(
                    current_postcodes=resolution_postcodes,
                    issue_labels=issue_labels,
                    row_previews=row_previews,
                    preview_specs=preview_specs,
                    postcode_column=postcode_col,
                    town_column=town_col,
                    normalizer=lambda x: _collapse_postcode_series(pd.Series([x]))[0],
                    parent=self.mw
                )

                if not dialog.exec():
                    return

                result = dialog.result()
                corrected = result["corrected"]
                added = result["added"]
                removed = result["removed"]
                row_updates = result.get("row_updates", {})

            def job_build():
                working_df = df.copy()
                reject_rows = []

                for i, row_index in enumerate(resolution_indices):
                    if i in removed:
                        reject_rows.append(working_df.loc[row_index].copy())
                        working_df.drop(index=row_index, inplace=True)
                        continue

                    if i in corrected:
                        postcode = corrected[i]

                        for col, value in row_updates.get(i, {}).items():
                            if col in working_df.columns:
                                working_df.loc[row_index, col] = value

                        working_df.loc[row_index, postcode_col] = postcode
                        continue

                    if i in added:
                        postcode = added[i]

                        for col, value in row_updates.get(i, {}).items():
                            if col in working_df.columns:
                                working_df.loc[row_index, col] = value

                        repo.insert_postcode(postcode)
                        working_df.loc[row_index, postcode_col] = postcode
                        continue

                    reject_rows.append(working_df.loc[row_index].copy())
                    working_df.drop(index=row_index, inplace=True)

                working_df.reset_index(drop=True, inplace=True)

                working_df = _apply_client_item_reference(
                    working_df,
                    reference_mode=reference_mode,
                    reference_column=reference_column,
                    reference_text=reference_text,
                )

                working_df = _rename_to_paf_columns(
                    working_df,
                    preview_columns=preview_columns,
                    town_col=town_col,
                    county_col=county_col,
                    postcode_col=postcode_col,
                )

                reject_df = pd.DataFrame(reject_rows)
                if not reject_df.empty:
                    reject_df = _apply_client_item_reference(
                        reject_df,
                        reference_mode=reference_mode,
                        reference_column=reference_column,
                        reference_text=reference_text,
                    )

                    reject_df = _rename_to_paf_columns(
                        reject_df,
                        preview_columns=preview_columns,
                        town_col=town_col,
                        county_col=county_col,
                        postcode_col=postcode_col,
                    )

                return working_df, reject_df

            def on_done(result):
                if result is None:
                    return

                valid_df, reject_df = result

                edited = self.preview_dialog(valid_df, title="Preview (E-Commerce File)")
                if edited is None:
                    return

                edited = self.drop_empty_rows_cols(edited)

                outfile = self.ask_save_csv_default_from_infile(
                    infile,
                    title="Save E-Commerce output file",
                    suffix=" (ecommerce).csv",
                    filter="CSV Files (*.csv);;All Files (*)"
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
                    sanitize=True
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
                cancelable=True
            )

        self.load_df_then(
            infile,
            title="Create E-Commerce File",
            header_mode="none",
            on_loaded=on_loaded
        )