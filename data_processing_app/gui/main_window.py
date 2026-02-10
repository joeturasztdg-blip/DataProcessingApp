import os
import tempfile
import shutil
import stat

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QMessageBox, QLineEdit,
    QLabel, QFileDialog, QInputDialog, QGroupBox, QTextEdit, QDialog,
)
from PySide6.QtCore import Qt, Signal

from config.constants import APP_TITLE
from config.schemas import (
    CHANGE_DELIM_SCHEMA, CREATE_FILE_SCHEMA, SPLIT_ZONES_SCHEMA,
    UPDATE_OUT_FILE_SCHEMA, CREATE_ZIP_SCHEMA, PRINT_PDF_SCHEMA
)
from config.seeds import seed_dict, split_seed_dict

from utils.logging_adapter import LoggerAdapter
from processing.cleansing import DataCleaner
from processing.headers import HeaderDetector
from processing.loading import FileLoader
from processing.transforms import DomainTransforms
from processing.packaging import ZipEncryptor

from gui.dialogs import OptionsDialog, PreviewDialog
from gui.progress import run_busy
from gui.password_broker import PasswordBroker
from utils.pdf_utils import BatchPdfPrintDialog


class MainWindow(QWidget):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel("<h2>Data processing application.</h2>")
        header.setAlignment(Qt.AlignCenter)
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        group = QGroupBox("Processing Actions")
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)

        self.btn_change_delim = QPushButton("Change CSV Delimiter")
        self.btn_create_file = QPushButton("Create file")
        self.btn_split_zones = QPushButton("Split mail into zones")
        self.btn_update_out_file = QPushButton("Update .OUT file")
        self.btn_create_zip = QPushButton("Create ZIP")
        self.btn_generate_random_password = QPushButton("Generate Random Password")
        self.btn_print_pdf = QPushButton("Print PDF")

        for btn in (
            self.btn_change_delim, self.btn_create_file, self.btn_split_zones,
            self.btn_update_out_file, self.btn_create_zip,
            self.btn_generate_random_password, self.btn_print_pdf
        ):
            btn.setMinimumHeight(40)
            group_layout.addWidget(btn)

        layout.addWidget(group)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.log_signal.connect(self.log.append)
        self.logger = LoggerAdapter(lambda msg, _c=None: self.log_signal.emit(msg))
        self.password_broker = PasswordBroker(self)
        self._jobs = []

        # ---------------- Modular Processing Stack ----------------
        self.cleaner = DataCleaner(self.logger)
        self.headers = HeaderDetector(self.logger)
        self.transforms = DomainTransforms()
        self.packager = ZipEncryptor()
        self.loader = FileLoader(
            header_detector=self.headers,
            cleaner=self.cleaner,
            logger=self.logger,
            password_callback=self.password_broker.get_password)

        self.btn_change_delim.clicked.connect(self.handle_change_delim)
        self.btn_create_file.clicked.connect(self.handle_create_file)
        self.btn_split_zones.clicked.connect(self.handle_split_zones)
        self.btn_update_out_file.clicked.connect(self.handle_update_out_file)
        self.btn_create_zip.clicked.connect(self.handle_create_zip)
        self.btn_generate_random_password.clicked.connect(self.handle_generate_random_password)
        self.btn_print_pdf.clicked.connect(self.handle_batch_print_pdfs)

        self.last_input_dir = os.getcwd()
    # ---------------- UI helpers ----------------
    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)
        self.logger.log(f"[ERROR] {title}: {text}", "red")

    def _get_start_dir(self, path=None):
        if path and os.path.exists(path):
            return path
        return self.last_input_dir or os.getcwd()

    def update_last_input_dir(self, selected_path):
        if not selected_path:
            return
        if isinstance(selected_path, (list, tuple)):
            selected_path = selected_path[0]
        if os.path.isfile(selected_path):
            self.last_input_dir = os.path.dirname(selected_path)
        elif os.path.isdir(selected_path):
            self.last_input_dir = selected_path

    def ask_open_file(self, title="Open file", filter="All Files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, title, self._get_start_dir(), filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def ask_open_files(self, title="Open files", filter="All Files (*)"):
        paths, _ = QFileDialog.getOpenFileNames(self, title, self._get_start_dir(), filter)
        if paths:
            self.update_last_input_dir(paths)
        return paths or None

    def ask_save_csv(self, title="Save file", filter="CSV Files (*.csv);;All Files (*)", defaultName=None):
        start_dir = self._get_start_dir()
        start_path = os.path.join(start_dir, defaultName) if defaultName else start_dir
        path, _ = QFileDialog.getSaveFileName(self, title, start_path, filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def make_file_writable(self, path: str):
        if os.path.exists(path):
            attrs = os.stat(path).st_mode
            if not (attrs & stat.S_IWRITE):
                os.chmod(path, attrs | stat.S_IWRITE)

    def _save_csv(self, df, filename, has_header=True, delimiter=","):
        df.to_csv(filename, index=False, header=has_header, sep=delimiter)
        
    def _run_busy(self, title: str, message: str, fn, on_done=None, on_err=None):
        job = run_busy(self, title=title, message=message, fn=fn)
        self._jobs.append(job)
        def forget(*_):
            if job in self._jobs:
                self._jobs.remove(job)
        job.finished.connect(forget)
        job.error.connect(forget)
        if on_done:
            job.finished.connect(on_done)
        if on_err:
            job.error.connect(on_err)
        return job
    # ---------------- Change Delim ----------------
    def handle_change_delim(self):
        infile = self.ask_open_file("Choose CSV/TXT file to load","CSV/TXT Files (*.csv *.txt);;All Files (*)")
        if not infile:
            return
        self.make_file_writable(infile)
        
        def job_load():
            return self.loader.load_file(infile)

        def on_err(err_text):
            self.show_error("Change delimiter failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                dlg = OptionsDialog(CHANGE_DELIM_SCHEMA, parent=self, title="Change CSV Delimiter")
                if dlg.exec() != QDialog.Accepted:
                    return
                out_delim = dlg.get_results().get("delimiter")
                if not out_delim:
                    return

                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.ask_save_csv("Save CSV as", "CSV Files (*.csv);;All Files (*)", defaultName=default_name)
                if not outfile:
                    return

                def job_save():
                    self._save_csv(df, outfile, has_header=has_header, delimiter=out_delim)
                    return True

                self._run_busy("Change CSV Delimiter", "Saving file…", job_save,
                    on_done=lambda _: self.logger.log("File created successfully.", "green"),
                    on_err=lambda e: QMessageBox.critical(self, "Save Error", e),)

            except Exception as e:
                self.show_error("Change delimiter failed", str(e))

        self._run_busy("Change CSV Delimiter", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)
    # ---------------- Create File ----------------
    def handle_create_file(self):
        infile = self.ask_open_file("Choose File", "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)")
        if not infile:
            return

        dlg = OptionsDialog(CREATE_FILE_SCHEMA, parent=self, title="Create File Options")
        if dlg.exec() != QDialog.Accepted:
            return
        opts = dlg.get_results()
        header_mode = opts.get("header_cleaning", "none")
        if not hasattr(self, "_jobs"):
            self._jobs = []

        def job_load():
            return self.loader.load_file(infile, header_cleaning_mode=header_mode)

        def on_error(err_text):
            QMessageBox.critical(self, "Error", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return
                # -------------------- MMI --------------------
                mmi_opts = opts.get("mmi", {})
                if mmi_opts.get("enabled"):
                    mmi_type = mmi_opts.get("value")
                    try:
                        if mmi_type == "Scotts":
                            cell_name = mmi_opts.get("cell_name", "")
                            if not cell_name:
                                QMessageBox.warning(self, "Missing cell name", "Scotts MMI requires a cell name.")
                                return
                            df = self.transforms.append_mmi(df, "Scotts", cell_name=cell_name)
                        else:
                            df = self.transforms.append_mmi(df, mmi_type)
                    except Exception as e:
                        QMessageBox.critical(self, "MMI Error", str(e))
                        return
                # -------------------- Seeds --------------------
                seed_opts = opts.get("seeds", {})
                if seed_opts.get("enabled"):
                    seed_key = seed_opts.get("value")
                    try:
                        seed_rows = seed_dict[seed_key][1]
                        df = self.transforms.append_seeds(df, seed_rows)
                    except Exception as e:
                        QMessageBox.critical(self, "Seed Error", str(e))
                        return

                preview = PreviewDialog(df, self)
                if preview.exec() != QDialog.Accepted:
                    return
                df = preview.get_dataframe()
                df = df.map(lambda x: str(x).replace("\n", " ").strip())

                delimiter = opts.get("delimiter", ",")
                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.ask_save_csv("Save output file","CSV Files (*.csv);;All Files (*)",defaultName=default_name)
                if not outfile:
                    return

                def job_save():
                    self._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
                    return True

                save_job = run_busy(self, title="Create File", message="Saving file…", fn=job_save)
                self._jobs.append(save_job)

                def forget_save(*_):
                    if save_job in self._jobs:
                        self._jobs.remove(save_job)

                save_job.finished.connect(forget_save)
                save_job.error.connect(forget_save)

                save_job.finished.connect(lambda _: self.logger.log("File created successfully.", "green"))
                save_job.error.connect(lambda err: QMessageBox.critical(self, "Save Error", err))

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        job = run_busy(self, title="Create File", message="Loading file…", fn=job_load)
        self._jobs.append(job)

        def forget(*_):
            if job in self._jobs:
                self._jobs.remove(job)

        job.finished.connect(forget)
        job.error.connect(forget)

        job.finished.connect(on_loaded)
        job.error.connect(on_error)
    # ---------------- File Split ----------------
    def handle_split_zones(self):
        infile = self.ask_open_file("Choose mail CSV/TXT or Excel to split","CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)")
        if not infile:
            return
        self.make_file_writable(infile)

        def job_load():
            return self.loader.load_file(infile)

        def on_err(err_text):
            self.show_error("Split mail failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                zonal, national = self.transforms.split_by_zone(df)
                zonal = self.transforms.remove_cols(zonal)
                national = self.transforms.remove_cols(national)

                has_headerZ = has_headerN = has_header

                dlg = OptionsDialog(SPLIT_ZONES_SCHEMA, parent=self, title="Split Zones Options")
                if dlg.exec() != QDialog.Accepted:
                    return
                opts = dlg.get_results()

                seed_opts = opts.get("seeds", {})
                seeds = None
                if seed_opts.get("enabled"):
                    seed_key = seed_opts.get("value")
                    seeds = split_seed_dict.get(seed_key, (None, None))[1]

                if seeds:
                    if isinstance(seeds, dict):
                        if seeds.get("DamartZ"):
                            zonal = self.transforms.append_seeds(zonal, seeds["DamartZ"])
                        if seeds.get("DamartN"):
                            national = self.transforms.append_seeds(national, seeds["DamartN"])
                    else:
                        zonal = self.transforms.append_seeds(zonal, seeds)
                        national = self.transforms.append_seeds(national, seeds)

                npreview = PreviewDialog(national, self, title="National Preview")
                if npreview.exec() != QDialog.Accepted:
                    return
                national = npreview.get_dataframe()

                zpreview = PreviewDialog(zonal, self, title="Zonal Preview")
                if zpreview.exec() != QDialog.Accepted:
                    return
                zonal = zpreview.get_dataframe()

                out_delim = opts.get("delimiter", ",")
                if not out_delim:
                    return

                raw_base = os.path.splitext(os.path.basename(infile))[0]
                base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base
                default_nat = f"{base} P1.csv"
                default_zon = f"{base} P2.csv"

                nat_out = self.ask_save_csv("Save National CSV (P1)","CSV Files (*.csv);;All Files (*)",defaultName=default_nat)
                if not nat_out:
                    return
                zon_out = self.ask_save_csv("Save Zonal CSV (P2)","CSV Files (*.csv);;All Files (*)",defaultName=default_zon)
                if not zon_out:
                    return
                national = national.map(lambda x: str(x).replace("\n", " ").strip())
                zonal = zonal.map(lambda x: str(x).replace("\n", " ").strip())

                def job_save():
                    self._save_csv(national, nat_out, has_header=has_headerN, delimiter=out_delim)
                    self._save_csv(zonal, zon_out, has_header=has_headerZ, delimiter=out_delim)
                    return True

                self._run_busy("Split Zones","Saving files…",job_save,
                    on_done=lambda _: self.logger.log("Files created successfully.", "green"),
                    on_err=lambda e: self.show_error("Split mail failed", e),)

            except Exception as e:
                self.show_error("Split mail failed", str(e))

        self._run_busy("Split Zones", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)
    # ---------------- Update OutFile ----------------
    def handle_update_out_file(self):
        infile = self.ask_open_file("Choose CSV/TXT to update", "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)")
        if not infile:
            return

        self.make_file_writable(infile)

        def job_load():
            return self.loader.load_file(infile)

        def on_err(err_text):
            self.show_error("Update OUT file failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                dlg = OptionsDialog(UPDATE_OUT_FILE_SCHEMA, parent=self, title="Update Out File")
                if dlg.exec() != QDialog.Accepted:
                    return
                opts = dlg.get_results()

                ucid_opts = opts.get("ucid_updates", {})
                ucid_mode = ucid_opts.get("value", "none")

                ucid_map = {}
                if ucid_mode == "1":
                    if ucid_opts.get("ucid1"):
                        ucid_map["UCID1"] = ucid_opts["ucid1"]
                        ucid_map["UCID2"] = ucid_opts["ucid1"]
                elif ucid_mode == "2":
                    if ucid_opts.get("ucid1"):
                        ucid_map["UCID1"] = ucid_opts["ucid1"]
                    if ucid_opts.get("ucid2"):
                        ucid_map["UCID2"] = ucid_opts["ucid2"]

                if ucid_map:
                    df = self.transforms.update_UCID(df, ucid_map)

                padding_choice = opts.get("barcode_padding", "none")
                if padding_choice != "none":
                    df = self.transforms.apply_barcode_padding(df, padding_choice)

                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.ask_save_csv("Save OUT file CSV","CSV Files (*.csv);;All Files (*)",defaultName=default_name)
                if not outfile:
                    return

                delimiter = opts.get("delimiter", ",")

                def job_save():
                    self._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
                    return True

                self._run_busy("Update OUT File","Saving file…",job_save,
                    on_done=lambda _: self.logger.log("OUT file updated successfully.", "green"),
                    on_err=lambda e: QMessageBox.critical(self, "Save Error", e),)

            except Exception as e:
                self.show_error("Update OUT file failed", str(e))

        self._run_busy("Update OUT File", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)
    # ---------------- Create Zip ----------------
    def handle_create_zip(self):
        files = self.ask_open_files("Choose files to ZIP","All Files (*.*);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx)")
        if not files:
            return

        dlg = OptionsDialog(CREATE_ZIP_SCHEMA, parent=self, title="ZIP Password")
        if dlg.exec() != QDialog.Accepted:
            return
        opts = dlg.get_results()
        pw_opts = opts["password_mode"]

        if pw_opts["value"] == "random":
            password = self.packager.generate_password()
        else:
            password = pw_opts.get("password", "").strip()
            if not password:
                QMessageBox.warning(self, "Missing password", "Please enter a password.")
                return

        first_file = os.path.basename(files[0])
        base = ".".join(first_file.split(".")[:-2]) or first_file.split(".")[0]
        default_zip_name = f"{base} DATA.zip"

        zipfile = self.ask_save_csv("Save encrypted ZIP as", "ZIP Files (*.zip);;All Files (*)", defaultName=default_zip_name)
        if not zipfile:
            return

        def job_zip():
            pw_txt_path = os.path.join(os.path.dirname(zipfile), "password.txt")
            pw_warning = None
            try:
                with open(pw_txt_path, "w", encoding="utf-8") as f:
                    f.write(password)
            except Exception as e:
                pw_warning = f"Could not save password to {pw_txt_path}:\n{e}"

            temp_dir = tempfile.mkdtemp(prefix="mail_pipeline_zip_")
            try:
                for fpath in files:
                    shutil.copy2(fpath, os.path.join(temp_dir, os.path.basename(fpath)))
                self.packager.create_zip(temp_dir, zipfile, password)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            return {"password": password, "pw_warning": pw_warning}

        def on_zipped(res):
            if res.get("pw_warning"):
                QMessageBox.warning(self, "Warning", res["pw_warning"])
            self.logger.log(f"Zip file saved successfully. Password: {res['password']}", "green")

        def on_zip_err(err_text):
            self.show_error("Create ZIP failed", err_text)

        self._run_busy("Create ZIP", "Creating ZIP…", job_zip, on_done=on_zipped, on_err=on_zip_err)
    # ---------------- Generate Password ----------------
    def handle_generate_random_password(self):
        password = self.packager.generate_password()
        self.logger.log(f"Generated random password: {password}", "green")
    # ---------------- Print PDFs ----------------
    def handle_batch_print_pdfs(self):
        pdfs = self.ask_open_files("Select PDFs for batch print", "PDF Files (*.pdf)")
        if not pdfs:
            return

        dlg_opts = OptionsDialog(PRINT_PDF_SCHEMA, parent=self,title="Print Options")
        if dlg_opts.exec() != QDialog.Accepted:
            return

        print_opts = dlg_opts.get_results()
        dlg = BatchPdfPrintDialog(pdfs, print_opts, self)
        dlg.exec()