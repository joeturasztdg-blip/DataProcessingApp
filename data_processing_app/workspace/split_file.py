from __future__ import annotations

import os

from config.schemas import build_split_file_schema
from config.constants import SPLIT_MAX_UNIQUE
from workspace.base import BaseWorkflow


class SplitFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose file to split",
            "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        def on_loaded(df, has_header: bool):
            try:
                total_rows = len(df)
                if total_rows == 0:
                    self.fail("Split File", "File contains no rows.")
                    return

                if df.columns is None or len(df.columns) == 0:
                    self.fail("Split File", "No columns found in file.")
                    return

                # ==================================================
                # Helpers
                # ==================================================
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
                    self.fail(
                        "Split File",
                        f"No suitable columns found to split on (must have {SPLIT_MAX_UNIQUE} or fewer unique values).",
                    )
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

                def apply_mmi_all(dfs: list):
                    mmi_opts = opts.get("mmi", {}) or {}
                    if not mmi_opts.get("enabled"):
                        return dfs

                    mmi_type = mmi_opts.get("value")
                    if not mmi_type:
                        return dfs

                    out = []
                    for d in dfs:
                        try:
                            if mmi_type == "Scotts":
                                cell_name = (mmi_opts.get("cell_name") or "").strip()
                                if not cell_name:
                                    self.warn("Missing cell name", "Scotts MMI requires a cell name.")
                                    return None
                                out.append(self.mw.s.transforms.append_mmi(d, "Scotts", cell_name=cell_name))
                            else:
                                out.append(self.mw.s.transforms.append_mmi(d, mmi_type))
                        except Exception as e:
                            self.fail("MMI Error", str(e))
                            return None
                    return out

                def apply_seeds_mode(dfs: list, *, base_df_cols: int):
                    seed_mode_opts = opts.get("seeds_mode", {}) or {}
                    seed_mode = seed_mode_opts.get("value", "none")  # none | file1 | all
                    if seed_mode == "none":
                        return dfs

                    try:
                        rows_to_add = []

                        std_id = seed_mode_opts.get("standard_seed")
                        if std_id:
                            rows_to_add += self.mw.s.seeds_repo.get_seed_rows(std_id)

                        bes_id = seed_mode_opts.get("bespoke_seed")
                        if bes_id and bes_id != "__none__":
                            rows_to_add += self.mw.s.seeds_repo.get_seed_rows(bes_id)

                        if not rows_to_add:
                            return dfs

                        if base_df_cols == 5:
                            self.mw.s.logger.log("Append seeds: dropping DPS column", "yellow")
                        elif base_df_cols == 4:
                            self.mw.s.logger.log("Append seeds: dropping Address 2 and DPS columns", "yellow")

                        if seed_mode == "file1":
                            dfs[0] = self.mw.s.transforms.append_seeds(dfs[0], rows_to_add)
                            return dfs

                        if seed_mode == "all":
                            return [self.mw.s.transforms.append_seeds(d, rows_to_add) for d in dfs]

                        return dfs

                    except Exception as e:
                        msg = str(e).strip() or "Append seeds failed"
                        self.mw.s.logger.log(msg, "red")
                        return None

                # ==================================================
                # Build schema
                # ==================================================
                standard_options = self.mw.s.seeds_repo.list_seed_options("Standard")
                bespoke_options = self.mw.s.seeds_repo.list_seed_options("Bespoke")

                schema = build_split_file_schema(
                    standard_options=standard_options,
                    bespoke_options=bespoke_options,
                )

                for item in schema:
                    if item.get("key") == "items_file1":
                        item["default"] = total_rows
                        item["min"] = 0
                        item["max"] = total_rows
                    elif item.get("key") == "items_file2":
                        item["default"] = 0
                        item["min"] = 0
                        item["max"] = total_rows

                for item in schema:
                    if item.get("key") == "split_column":
                        item["options"] = col_options
                        item["default"] = "__select__"

                for item in schema:
                    if (
                        item.get("type") == "multi_select"
                        and str(item.get("key", "")).startswith("file")
                        and str(item.get("key", "")).endswith("_values")
                    ):
                        item["depends_on"] = "split_column"
                        item["options_provider"] = values_provider
                        item["options"] = []
                        item["mutex_group"] = "split_files"

                # ==================================================
                # Show dialog
                # ==================================================
                opts = self.options_dialog(schema, title="Split File Options")
                if not opts:
                    return

                split_mode = opts.get("split_mode", "column")

                # ==================================================
                # Split by number of items
                # ==================================================
                if split_mode == "items":
                    n1 = int(opts.get("items_file1", 0))
                    n2 = int(opts.get("items_file2", 0))

                    if n1 < 0 or n2 < 0 or (n1 + n2) != total_rows:
                        self.fail("Split File", f"File 1 + File 2 must equal {total_rows} rows.")
                        return

                    df1 = df.iloc[:n1].copy()
                    df2 = df.iloc[n1:n1 + n2].copy()

                    out_dfs = [df1, df2]

                    out_dfs = apply_mmi_all(out_dfs)
                    if out_dfs is None:
                        return

                    out_dfs = apply_seeds_mode(out_dfs, base_df_cols=len(df.columns))
                    if out_dfs is None:
                        return

                    df1 = self.preview_dialog(out_dfs[0], title="File 1 Preview")
                    if df1 is None:
                        return
                    df1 = self.drop_empty_rows_cols(df1)

                    df2 = self.preview_dialog(out_dfs[1], title="File 2 Preview")
                    if df2 is None:
                        return
                    df2 = self.drop_empty_rows_cols(df2)

                    out_delim = opts.get("delimiter", ",")
                    if not out_delim:
                        return

                    raw_base = os.path.splitext(os.path.basename(infile))[0]
                    base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base

                    p1 = self.mw.ask_save_csv(
                        "Save File 1",
                        "CSV Files (*.csv);;All Files (*)",
                        defaultName=f"{base} File 1.csv",
                    )
                    if not p1:
                        return

                    p2 = self.mw.ask_save_csv(
                        "Save File 2",
                        "CSV Files (*.csv);;All Files (*)",
                        defaultName=f"{base} File 2.csv",
                    )
                    if not p2:
                        return

                    def job_save():
                        enc1 = self.mw._save_csv(
                            self.sanitize_df_for_export(df1),
                            p1,
                            has_header=has_header,
                            delimiter=out_delim,
                        )
                        enc2 = self.mw._save_csv(
                            self.sanitize_df_for_export(df2),
                            p2,
                            has_header=has_header,
                            delimiter=out_delim,
                        )
                        return {"File 1": enc1, "File 2": enc2}

                    self.busy(
                        "Split File",
                        "Saving files…",
                        job_save,
                        on_done=lambda encs: self.info(
                            "Files created successfully. "
                            f"(Encoding: File 1={encs.get('File 1')}, File 2={encs.get('File 2')})",
                            "green",
                        ),
                        on_err=lambda e: self.fail("Split File failed", e),
                    )
                    return

                # ==================================================
                # Split by column
                # ==================================================
                split_col = opts.get("split_column")
                if not split_col or split_col == "__select__":
                    self.warn("Missing column", "Please select a column to split by.")
                    return

                split_count = int(opts.get("split_count") or 2)
                split_count = max(2, min(split_count, 5))

                file_sets: list[set[str]] = []
                for i in range(1, split_count + 1):
                    file_sets.append(set(opts.get(f"file{i}_values") or []))

                if not any(file_sets):
                    self.warn("Missing groups", "Select at least one value for at least one file.")
                    return

                seen: dict[str, int] = {}
                for i, s in enumerate(file_sets, start=1):
                    for v in s:
                        if v in seen:
                            self.warn(
                                "Overlapping values",
                                f"Some values are selected for both File {seen[v]} and File {i}. "
                                "Please select each value only once.",
                            )
                            return
                        seen[v] = i

                series = df[split_col].astype(str).map(lambda x: x.strip())

                out_dfs = []
                for s in file_sets:
                    mask = series.isin(s)
                    out_dfs.append(df[mask].copy())

                out_dfs = apply_mmi_all(out_dfs)
                if out_dfs is None:
                    return

                out_dfs = apply_seeds_mode(out_dfs, base_df_cols=len(df.columns))
                if out_dfs is None:
                    return

                for i in range(split_count):
                    edited = self.preview_dialog(out_dfs[i], title=f"File {i+1} Preview")
                    if edited is None:
                        return
                    out_dfs[i] = self.drop_empty_rows_cols(edited)

                out_delim = opts.get("delimiter", ",")
                if not out_delim:
                    return

                raw_base = os.path.splitext(os.path.basename(infile))[0]
                base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base

                out_paths = []
                for i in range(1, split_count + 1):
                    p = self.mw.ask_save_csv(
                        f"Save File {i}",
                        "CSV Files (*.csv);;All Files (*)",
                        defaultName=f"{base} File {i}.csv",
                    )
                    if not p:
                        return
                    out_paths.append(p)

                out_dfs = [self.sanitize_df_for_export(d) for d in out_dfs]

                def job_save():
                    for d, p in zip(out_dfs, out_paths):
                        self.mw._save_csv(d, p, has_header=has_header, delimiter=out_delim)
                    return True

                self.busy(
                    "Split File",
                    "Saving files…",
                    job_save,
                    on_done=lambda _: self.info("Files created successfully.", "green"),
                    on_err=lambda e: self.fail("Split File failed", e),
                )

            except Exception as e:
                self.fail_exception("Split File", e)

        self.load_df_then(
            infile,
            title="Split File",
            header_mode="none",
            on_loaded=on_loaded,
        )