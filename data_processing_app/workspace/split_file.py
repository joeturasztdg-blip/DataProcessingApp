from __future__ import annotations

import os

from config.schemas import SPLIT_FILE_SCHEMA
from config.seeds import seed_dict
from config.constants import SPLIT_MAX_UNIQUE
from workspace.base import BaseWorkflow


class SplitFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file("Choose file to split",
            "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)",)
        if not infile:
            return

        def on_loaded(df, has_header: bool):
            try:
                if df.columns is None or len(df.columns) == 0:
                    self.fail("Split File", "No columns found in file.")
                    return

                def unique_count_up_to(series, limit: int):
                    seen = set()
                    has_non_blank = False
                    for v in series.astype(str):
                        s = v.strip()
                        if s:
                            has_non_blank = True
                            seen.add(s)
                            if len(seen) > limit:
                                return len(seen), has_non_blank
                    return len(seen), has_non_blank

                eligible = []
                for c in df.columns:
                    try:
                        n, has_non_blank = unique_count_up_to(df[c], SPLIT_MAX_UNIQUE)
                    except Exception:
                        continue
                    if has_non_blank and n <= SPLIT_MAX_UNIQUE:
                        eligible.append((str(c), n))

                if not eligible:
                    self.fail("Split File",
                        f"No suitable columns found to split on (must have {SPLIT_MAX_UNIQUE} or fewer unique values).")
                    return

                col_options = [("Select a column", "__select__")]
                for col_name, n in sorted(eligible, key=lambda t: (t[0].casefold(), t[1])):
                    col_options.append((f"{col_name} ({n})", col_name))

                def values_provider(col_name: str):
                    if not col_name or col_name == "__select__" or col_name not in df.columns:
                        return []
                    s = df[col_name].astype(str).map(lambda x: x.strip())
                    uniq = sorted(set(s.tolist()), key=lambda t: t.casefold())
                    return [("(blank)" if v == "" else v, v) for v in uniq]

                schema = [dict(x) for x in SPLIT_FILE_SCHEMA]

                schema[0]["options"] = col_options
                schema[0]["default"] = "__select__"

                schema[1]["depends_on"] = "split_column"
                schema[1]["options_provider"] = values_provider
                schema[1]["options"] = []

                schema[2]["depends_on"] = "split_column"
                schema[2]["options_provider"] = values_provider
                schema[2]["options"] = []

                opts = self.options_dialog(schema, title="Split File Options")
                if not opts:
                    return

                split_col = opts.get("split_column")
                if not split_col or split_col == "__select__":
                    self.warn("Missing column", "Please select a column to split by.")
                    return

                file1_vals = set(opts.get("file1_values") or [])
                file2_vals = set(opts.get("file2_values") or [])

                if not file1_vals and not file2_vals:
                    self.warn("Missing groups", "Select at least one value for File 1 or File 2.")
                    return

                overlap = file1_vals & file2_vals
                if overlap:
                    self.warn("Overlapping values",
                        "Some values are selected for both File 1 and File 2. "
                        "Please select each value only once.",)
                    return

                series = df[split_col].astype(str).map(lambda x: x.strip())
                mask1 = series.isin(file1_vals)
                mask2 = series.isin(file2_vals)

                file1_df = df[mask1].copy()
                file2_df = df[mask2].copy()

                seed_opts = opts.get("seeds", {}) or {}
                if seed_opts.get("enabled"):
                    seed_key = seed_opts.get("value")
                    seeds = seed_dict.get(seed_key, (None, None))[1]
                    if seeds:
                        file1_df = self.mw.s.transforms.append_seeds(file1_df, seeds)

                edited1 = self.preview_dialog(file1_df, title="File 1 Preview")
                if edited1 is None:
                    return
                file1_df = edited1

                edited2 = self.preview_dialog(file2_df, title="File 2 Preview")
                if edited2 is None:
                    return
                file2_df = edited2

                out_delim = opts.get("delimiter", ",")
                if not out_delim:
                    return

                raw_base = os.path.splitext(os.path.basename(infile))[0]
                base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base

                out1 = self.mw.ask_save_csv(
                    "Save File 1 (File 1)",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=f"{base} File 1.csv")
                if not out1:
                    return

                out2 = self.mw.ask_save_csv(
                    "Save File 2 (File 2)",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=f"{base} File 2.csv")
                if not out2:
                    return

                file1_df = self.sanitize_df_for_export(file1_df)
                file2_df = self.sanitize_df_for_export(file2_df)

                def job_save():
                    self.mw._save_csv(file1_df, out1, has_header=has_header, delimiter=out_delim)
                    self.mw._save_csv(file2_df, out2, has_header=has_header, delimiter=out_delim)
                    return True

                self.busy(
                    "Split File",
                    "Saving files…",
                    job_save,
                    on_done=lambda _: self.info("Files created successfully.", "green"),
                    on_err=lambda e: self.fail("Split file failed", e))

            except Exception as e:
                self.fail_exception("Split file failed", e)

        self.load_df_then(
            infile,
            title="Split File",
            make_writable=True,
            on_loaded=on_loaded)