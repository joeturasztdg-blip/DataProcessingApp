import os
import tempfile
import shutil
import stat

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QMessageBox, QLineEdit,
    QLabel, QFileDialog, QInputDialog, QGroupBox, QTextEdit, QDialog,)
from PySide6.QtCore import Qt

from config.constants import APP_TITLE
from config.schemas import CHANGE_DELIM_SCHEMA, CREATE_FILE_SCHEMA, SPLIT_ZONES_SCHEMA, UPDATE_OUT_FILE_SCHEMA, CREATE_ZIP_SCHEMA, PRINT_PDF_SCHEMA
from config.seeds import seed_dict, split_seed_dict
from processing.processor import Processor
from gui.dialogs import OptionsDialog, PreviewDialog
from utils.pdf_utils import BatchPdfPrintDialog

class MainWindow(QWidget):
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

        for btn in (self.btn_change_delim, self.btn_create_file, self.btn_split_zones, self.btn_update_out_file,
                    self.btn_create_zip, self.btn_generate_random_password, self.btn_print_pdf):
            btn.setMinimumHeight(40)
            group_layout.addWidget(btn)
        layout.addWidget(group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.processor = Processor(logger=self._log_to_widget, password_callback=self.ask_excel_password)
        self.btn_change_delim.clicked.connect(self.handle_change_delim)
        self.btn_create_file.clicked.connect(self.handle_create_file)
        self.btn_split_zones.clicked.connect(self.handle_split_zones)
        self.btn_update_out_file.clicked.connect(self.handle_update_out_file)
        self.btn_create_zip.clicked.connect(self.handle_create_zip)
        self.btn_generate_random_password.clicked.connect(self.handle_generate_random_password)
        self.btn_print_pdf.clicked.connect(self.handle_batch_print_pdfs)
        
        self.last_input_dir = os.getcwd()
        
    def _log_to_widget(self, msg, _colour=None):
        self.log.append(msg)

    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)
        self.processor.log(f"[ERROR] {title}: {text}", "red")
        
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
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            self._get_start_dir(),
            filter
        )
        if path:
            self.update_last_input_dir(path)
        return path or None

    def ask_open_files(self, title="Open files", filter="All Files (*)"):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            title,
            self._get_start_dir(),
            filter
        )
        if paths:
            self.update_last_input_dir(paths)
        return paths or None


    def ask_excel_password(self, prompt: str) -> str | None:
        password, ok = QInputDialog.getText(
            self,
            "Password required",
            prompt,
            QLineEdit.EchoMode.Password
        )
        return password if ok else None


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
    
    def _unwrap_df(self, result, logs):
        if isinstance(result, tuple):
            return result[0]
        return result
    #--------------------------------------------------------Change Delimiter--------------------------------------------------------
    def handle_change_delim(self):
        try:
            infile = self.ask_open_file(
                "Choose CSV/TXT file to load",
                "CSV/TXT Files (*.csv *.txt);;All Files (*)"
            )
            if not infile:
                return

            self.make_file_writable(infile)

            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

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
            self.processor.save_csv(df, outfile, has_header=has_header, delimiter=out_delim)
            self.processor.log("File created successfully.", "green")

        except Exception as e:
            self.show_error("Change delimiter failed", str(e))
    #--------------------------------------------------------Create File--------------------------------------------------------
    def handle_create_file(self):
        logs = []
        infile = self.ask_open_file("Choose File",
                "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)")
        if not infile:
            return
        try:
            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        dlg = OptionsDialog(CREATE_FILE_SCHEMA, parent=self, title="Create File Options")
        if dlg.exec() != QDialog.Accepted:
            return
        opts = dlg.get_results()
        #--------------------MMI--------------------
        mmi_opts = opts.get("mmi", {})
        if mmi_opts.get("enabled"):
            mmi_type = mmi_opts.get("value")
            try:
                if mmi_type == "Scotts":
                    cell_name = mmi_opts.get("cell_name", "")
                    if not cell_name:
                        QMessageBox.warning(self, "Missing cell name", "Scotts MMI requires a cell name.")
                        return
                    df = self._unwrap_df(self.processor.append_mmi(df, "Scotts", cell_name=cell_name), logs)
                else:
                    df = self._unwrap_df(self.processor.append_mmi(df, mmi_type), logs)
            except Exception as e:
                QMessageBox.critical(self, "MMI Error", str(e))
                return
        #--------------------Seeds--------------------
        seed_opts = opts.get("seeds", {})
        if seed_opts.get("enabled"):
            seed_key = seed_opts.get("value")
            try:
                seed_columns = seed_dict[seed_key][1]
                df = self._unwrap_df(self.processor.append_seeds(df, seed_columns), logs)
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
        outfile = self.ask_save_csv("Save output file", "CSV Files (*.csv);;All Files (*)", defaultName=default_name)

        if not outfile:
            return
        try:
            self.processor.save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
            self.processor.log("File created successfully.", "green")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
    #--------------------------------------------------------Zonal Split--------------------------------------------------------
    def handle_split_zones(self):
        try:
            infile = self.ask_open_file("Choose mail CSV/TXT or Excel to split",
                "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)")
            if not infile:
                return
            self.make_file_writable(infile)

            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

            zonal, national = self.processor.split_by_zone(df)
            zonal = self.processor.remove_cols(zonal)
            national = self.processor.remove_cols(national)

            zonal, has_headerZ = self.processor.drop_useless_header(zonal, has_header)
            national, has_headerN = self.processor.drop_useless_header(national, has_header)

            dlg = OptionsDialog(SPLIT_ZONES_SCHEMA, parent=self, title="Split Zones Options")
            if dlg.exec() != QDialog.Accepted:
                return
            opts = dlg.get_results()
            #--------------------Seeds--------------------
            seed_opts = opts.get("seeds", {})
            seeds = None

            if seed_opts.get("enabled"):
                seed_key = seed_opts.get("value")
                seeds = split_seed_dict.get(seed_key, (None, None))[1]

            if seeds:
                if isinstance(seeds, dict):
                    if seeds.get("DamartZ"):
                        zonal = self.processor.append_seeds(zonal, seeds["DamartZ"])
                    if seeds.get("DamartN"):
                        national = self.processor.append_seeds(national, seeds["DamartN"])
                else:
                    zonal = self.processor.append_seeds(zonal, seeds)
                    national = self.processor.append_seeds(national, seeds)

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
            default_nat = (f"{base} P1.csv")
            default_zon = (f"{base} P2.csv")
            nat_out = self.ask_save_csv("Save National CSV (P1)", "CSV Files (*.csv);;All Files (*)", defaultName=default_nat)
            if not nat_out:
                return
            zon_out = self.ask_save_csv("Save Zonal CSV (P2)", "CSV Files (*.csv);;All Files (*)", defaultName=default_zon)
            if not zon_out:
                return
            national = national.map(lambda x: str(x).replace("\n", " ").strip())
            zonal = zonal.map(lambda x: str(x).replace("\n", " ").strip())
            self.processor.save_csv(national, nat_out, has_header=has_headerN, delimiter=out_delim)
            self.processor.save_csv(zonal, zon_out, has_header=has_headerZ, delimiter=out_delim)

            self.processor.log("Files created successfully.", "green")
        except Exception as e:
            self.show_error("Split mail failed", str(e))
    #--------------------------------------------------------Update Out File--------------------------------------------------------
    def handle_update_out_file(self):
        try:
            infile = self.ask_open_file("Choose CSV/TXT to update",
                "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)")
            if not infile:
                return
            self.make_file_writable(infile)
            df, has_header = self.processor.load_file(infile)

            dlg = OptionsDialog(UPDATE_OUT_FILE_SCHEMA, parent=self, title="Update Out File")
            if dlg.exec() != QDialog.Accepted:
                return
            opts = dlg.get_results()
            #--------------------Update UCIDs--------------------
            ucid_opts = opts.get("ucid_updates", {})
            ucid_mode = ucid_opts.get("value", "none")

            ucidMap = {}

            if ucid_mode == "1":
                if ucid_opts.get("ucid1"):
                    ucidMap["UCID1"] = ucid_opts["ucid1"]
                    ucidMap["UCID2"] = ucid_opts["ucid1"]

            elif ucid_mode == "2":
                if ucid_opts.get("ucid1"):
                    ucidMap["UCID1"] = ucid_opts["ucid1"]
                if ucid_opts.get("ucid2"):
                    ucidMap["UCID2"] = ucid_opts["ucid2"]

            if ucidMap:
                df = Processor.update_UCID(df, ucidMap)
            #--------------------Barcode Padding--------------------
            barcode_opts = opts.get("barcode_padding", {})
            padding_choice = opts.get("barcode_padding", "none")
            if padding_choice != "none":
                df = Processor.apply_barcode_padding(df, padding_choice)

            base = os.path.splitext(os.path.basename(infile))[0]
            default_name = f"{base}.csv"
            outfile = self.ask_save_csv("Save OUT file CSV", "CSV Files (*.csv);;All Files (*)", defaultName=default_name)
            if not outfile:
                return
            
            delimiter = opts.get("delimiter", ",")
            self.processor.save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
            self.processor.log("OUT file updated successfully.", "green")
        except Exception as e:
            self.show_error("Update OUT file failed", str(e))
    #--------------------------------------------------------Create ZIP--------------------------------------------------------
    def handle_create_zip(self):
        try:
            files = self.ask_open_files("Choose files to ZIP",
                "All Files (*.*);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx)")
            if not files:
                return
            
            dlg = OptionsDialog(CREATE_ZIP_SCHEMA, parent=self, title="ZIP Password")
            if dlg.exec() != QDialog.Accepted:
                return
            opts = dlg.get_results()
            pw_opts = opts["password_mode"]            
            if pw_opts["value"] == "random":
                password = self.processor.generate_random_password()
            else:
                password = pw_opts.get("password", "").strip()
                if not password:
                    QMessageBox.warning(self, "Missing password", "Please enter a password.")
                    return
                
            first_file = os.path.basename(files[0])
            base = '.'.join(first_file.split('.')[:-2]) or first_file.split('.')[0]
            default_zip_name = f"{base} DATA.zip"
            zipfile = self.ask_save_csv("Save encrypted ZIP as", "ZIP Files (*.zip);;All Files (*)", defaultName=default_zip_name)
            if not zipfile:
                return
            
            pw_txt_path = os.path.join(os.path.dirname(zipfile), "password.txt")
            try:
                with open(pw_txt_path, "w", encoding="utf-8") as f:
                    f.write(password)
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Could not save password to {pw_txt_path}:\n{e}")

            temp_dir = tempfile.mkdtemp(prefix="mail_pipeline_zip_")
            try:
                for fpath in files:
                    try:
                        shutil.copy2(fpath, os.path.join(temp_dir, os.path.basename(fpath)))
                    except Exception as e:
                        self.processor.log(f"[WARN] Could not copy '{fpath}' -> {e}", "red")
                self.processor.create_encrypted_zip(temp_dir, zipfile, password)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.processor.log(f"Zip file saved successfully. Password: {password}", "green")
        except FileNotFoundError as e:
            self.show_error("7-Zip not found", str(e))
        except Exception as e:
            self.show_error("Create ZIP failed", str(e))
    #--------------------------------------------------------Generate Password--------------------------------------------------------
    def handle_generate_random_password(self):
        password = self.processor.generate_random_password()
        self.processor.log(f"Generated random password: {password}", "green")
    #--------------------------------------------------------Print Files--------------------------------------------------------
    def handle_batch_print_pdfs(self):
        pdfs = self.ask_open_files("Select PDFs for batch print", "PDF Files (*.pdf)")
        if not pdfs:
            return

        dlg_opts = OptionsDialog(
            PRINT_PDF_SCHEMA,
            parent=self,
            title="Print Options"
        )

        if dlg_opts.exec() != QDialog.Accepted:
            return

        print_opts = dlg_opts.get_results()

        dlg = BatchPdfPrintDialog(pdfs, print_opts, self)
        dlg.exec()

