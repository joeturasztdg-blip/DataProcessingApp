from __future__ import annotations

import pandas as pd
from workspace.base import BaseWorkflow
from config.schemas import build_create_ecommerce_file_schema


POSTCODE_MATCH_COL = "Postcode Match"


def _collapse_postcode_series(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace("\t", "", regex=False)
    s = s.str.replace("\n", "", regex=False)
    s = s.str.replace("\r", "", regex=False)
    s = s.str.strip().str.upper()
    return s


class CreateEcommerceFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)")
        if not infile:
            return

        def on_loaded(df: pd.DataFrame, has_header: bool):
            if df is None or df.empty:
                self.warn("Create E-Commerce File", "File contains no data.")
                return

            col_options: list[tuple[str, str]] = [("— Select —", "__select__")]
            for c in df.columns:
                col_options.append((str(c), str(c)))

            schema = build_create_ecommerce_file_schema(column_options=col_options)
            opts = self.options_dialog(schema, title="Create E-Commerce File")
            if not opts:
                return

            postcode_col = opts.get("postcode_column")
            if not postcode_col or postcode_col == "__select__" or postcode_col not in df.columns:
                self.warn("Create E-Commerce File", "Please select a postcode column.")
                return

            out_delim = (opts.get("delimiter") or ",").strip() or ","

            def job_build():
                collapsed = _collapse_postcode_series(df[postcode_col])

                unique_vals = set(v for v in collapsed.tolist() if v)
                existing = self.mw.s.postcodes_repo.existing_postcode_set(unique_vals)

                out = df.copy()
                out[POSTCODE_MATCH_COL] = collapsed.map(lambda v: "Match" if (v in existing) else "No Match")
                return out

            def on_done(out_df: pd.DataFrame):
                edited = self.preview_dialog(out_df, title="Preview (E-Commerce File)")
                if edited is None:
                    return

                edited = self.drop_empty_rows_cols(edited)

                outfile = self.ask_save_csv_default_from_infile(
                    infile,
                    title="Save E-Commerce output file",
                    suffix=" (ecommerce).csv",
                    filter="CSV Files (*.csv);;All Files (*)")
                if not outfile:
                    return

                self.save_csv_then(
                    edited,
                    outfile,
                    title="Create E-Commerce File",
                    delimiter=out_delim,
                    has_header=has_header,
                    success_msg="E-Commerce file created successfully.",
                    sanitize=True)

            self.busy(
                "Create E-Commerce File",
                "Building E-Commerce file…",
                job_build,
                on_done=on_done,
                on_err=lambda e: self.fail("Create E-Commerce File", e),
                cancelable=True)

        self.load_df_then(
            infile,
            title="Create E-Commerce File",
            header_mode="none",
            on_loaded=on_loaded)