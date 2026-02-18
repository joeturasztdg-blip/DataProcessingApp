# workspace/create_zip.py
from __future__ import annotations

import os
import shutil
import tempfile

from config.schemas import CREATE_ZIP_SCHEMA
from workspace.base import BaseWorkflow


class CreateZip(BaseWorkflow):
    def run(self, checked: bool = False):
        files = self.mw.ask_open_files(
            "Choose files to ZIP",
            "All Files (*.*);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx)",
        )
        if not files:
            return

        opts = self.options_dialog(CREATE_ZIP_SCHEMA, title="ZIP Password")
        if not opts:
            return

        pw_opts = opts.get("password_mode") or {}
        mode = pw_opts.get("value", "random")

        if mode == "random":
            password = self.mw.s.packager.generate_password()
        else:
            password = (pw_opts.get("password") or "").strip()
            if not password:
                self.warn("Missing password", "Please enter a password.")
                return

        first_file = os.path.basename(files[0])
        base = ".".join(first_file.split(".")[:-2]) or first_file.split(".")[0]
        default_zip_name = f"{base} DATA.zip"

        zipfile = self.mw.ask_save_csv(
            "Save encrypted ZIP as",
            "ZIP Files (*.zip);;All Files (*)",
            defaultName=default_zip_name,
        )
        if not zipfile:
            return

        def job_zip():
            temp_dir = tempfile.mkdtemp(prefix="mail_pipeline_zip_")
            try:
                for fpath in files:
                    shutil.copy2(fpath, os.path.join(temp_dir, os.path.basename(fpath)))

                # Create ZIP first
                self.mw.s.packager.create_zip(temp_dir, zipfile, password)

                # Then save password.txt alongside the zip
                pw_txt_path = os.path.join(os.path.dirname(zipfile), "password.txt")
                pw_warning = None
                try:
                    with open(pw_txt_path, "w", encoding="utf-8") as f:
                        f.write(password)
                except Exception as e:
                    pw_warning = f"Could not save password to {pw_txt_path}:\n{e}"

                return {"password": password, "pw_warning": pw_warning}

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        def on_zipped(res: dict):
            if res.get("pw_warning"):
                self.warn("Warning", res["pw_warning"])
            self.info(f"Zip file saved successfully. Password: {res['password']}", "green")

        # Use BaseWorkflow's generic busy runner
        self.run_busy(
            "Create ZIP",
            "Creating ZIP…",
            job_zip,
            on_done=on_zipped,
            on_err=lambda e: self.fail("Create ZIP failed", e),
        )
