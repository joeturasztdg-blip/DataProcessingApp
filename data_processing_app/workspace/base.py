from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PySide6.QtWidgets import QDialog, QMessageBox

from gui.dialogs.options_dialog import OptionsDialog
from gui.dialogs.preview_dialog import PreviewDialog

DoneHandler = Callable[[Any], None]
ErrHandler = Callable[[str], None]

@dataclass
class BaseWorkflow:
    mw: Any
    # ---------------- Messaging ----------------
    def info(self, msg: str, colour: str = "green") -> None:
        self.mw.s.logger.log(msg, colour)

    def warn(self, title: str, msg: str) -> None:
        QMessageBox.warning(self.mw, title, msg)

    def fail(self, title: str, err_text: str) -> None:
        self.mw.show_error(title, (err_text or "").strip() or "Unknown error")

    def fail_exception(self, title: str, exc: Exception) -> None:
        self.fail(title, str(exc))
    # ---------------- Busy job wrappers ----------------
    def busy(
        self,
        title: str,
        message: str,
        fn: Callable[[], Any],
        *,
        on_done: Optional[DoneHandler] = None,
        on_err: Optional[ErrHandler] = None,
        cancelable: bool = False):
        return self.mw._run_busy(title,message,fn,on_done=on_done,on_err=on_err or (lambda e: self.fail(title, e)),cancelable=cancelable)
    # ---------------- helpers ----------------
    def options_dialog(self, schema, *, title: str) -> Optional[dict]:
        dlg = OptionsDialog(schema, parent=self.mw, title=title)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_results()

    def preview_dialog(self, df, *, title: str = "Preview"):
        dlg = PreviewDialog(df, self.mw, title=title)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.get_dataframe()
    
    def sanitize_df_for_export(self, df):
        return df.map(lambda x: str(x).replace("\n", " ").strip())
    
    def drop_empty_rows_cols(self, df):
        import pandas as pd
        if df is None or df.empty:
            return df
        tmp = df.astype(object).where(pd.notnull(df), "")
        non_empty = tmp.astype(str).apply(lambda s: s.str.strip().ne(""))

        out = df.loc[non_empty.any(axis=1), non_empty.any(axis=0)].copy()
        out.reset_index(drop=True, inplace=True)
        return out
    
    def ask_save_csv_default_from_infile(self,infile: str,*,title: str,suffix: str = ".csv",filter: str = "CSV Files (*.csv);;All Files (*)") -> Optional[str]:
        import os
        base = os.path.splitext(os.path.basename(infile))[0]
        default_name = f"{base}{suffix}"
        return self.mw.ask_save_csv(title, filter, defaultName=default_name)
    # ---------------- Common workflow phases ----------------
    def load_df_then(self,infile: str,*,title: str,header_mode: str = "none",make_writable: bool = False,on_loaded: Callable[[Any, bool], None]):
        if make_writable:
            try:
                self.mw.make_file_writable(infile)
            except Exception:
                pass

        def job_load(_progress, cancel):
            return self.mw.s.loader.load_file(infile,header_cleaning_mode=header_mode,cancel_event=cancel,)

        def handle_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return
                on_loaded(df, bool(has_header))
            except Exception as e:
                self.fail_exception(f"{title} failed", e)
        return self.busy(title,"Loading file…",job_load,on_done=handle_loaded,cancelable=True,)

    def save_csv_then(self,df,outfile: str,*,title: str,delimiter: str,has_header: bool,success_msg: str = "File created successfully.",sanitize: bool = True):
        if sanitize:
            df = self.sanitize_df_for_export(df)

        def job_save():
            enc_label = self.mw._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
            return enc_label

        def done(enc_label):
            suffix = f' (Encoding: {enc_label})' if enc_label else ""
            self.info(f"{success_msg}{suffix}", "green")

        return self.busy(title,"Saving file…",job_save,on_done=done,on_err=lambda e: QMessageBox.critical(self.mw, "Save Error", e),)

    def run_busy(self,title: str,message: str,fn: Callable[[], Any],*,success_msg: Optional[str] = None,on_done: Optional[DoneHandler] = None,
                 on_err: Optional[ErrHandler] = None,cancelable: bool = False):
        if on_done is None and success_msg is not None:
            on_done = lambda _res: self.info(success_msg, "green")
        return self.busy(title, message, fn, on_done=on_done, on_err=on_err, cancelable=cancelable)