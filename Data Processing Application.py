import os
import sys
import tempfile
import pandas as pd
import re
import csv
import shutil
import subprocess, platform, math
import secrets
import string
from pandas.api.types import is_object_dtype
import stat
import pickle
import io
import msoffcrypto
from collections import Counter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QListWidget,
    QLabel, QFileDialog, QInputDialog, QGroupBox, QTextEdit, QDialog, QAbstractItemView, QTableView, QMenu)
from PySide6.QtCore import Qt, QAbstractTableModel, QMimeData, QModelIndex
from PySide6.QtGui import QKeyEvent, QDrag, QCursor, QPainter, QColor
import fitz

csv.field_size_limit(sys.maxsize)
# ---------------------------------------------------------------------------------------
# Constants and seed data
# ---------------------------------------------------------------------------------------
seed_dict = {
    "1": ("Advertising", [
        ["Royal Mail Wholesale UCID1", "PO Box 72662", "", "", "London", "E1W 9LD", "1A"],
        ["Client Services UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
        ["Royal Mail Wholesale UCID2", "PO Box 72662", "", "", "London", "E1W 9LD", "1A"],
        ["Client Services UCID2", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
    ]),

    "2": ("Digital Stamp", [
        ["SM Digital Stamp Sample UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
        ["RM Digital Stamp Sample UCID1", "RM Digital Stamp Team", "PO BOX 73733", "LONDON", "", "EC1P 1JX"],
        ["SM Digital Stamp Sample UCID2", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
        ["RM Digital Stamp Sample UCID2", "RM Digital Stamp Team", "PO BOX 73733", "LONDON", "", "EC1P 1JX"],
    ]),

    "3": ("Partially Addressing", [
        ["Royal Mail Wholesale UCID1", "PO Box 72662", "", "London", "E1W 9LD", "1A"],
        ["Royal Mail Partially Addressed UCID1", "PO Box 75218", "", "London", "E1W 9PZ", "1A"],
        ["Client Services UCID1", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
        ["Royal Mail Wholesale UCID2", "PO Box 72662", "", "London", "E1W 9LD", "1A"],
        ["Client Services UCID2", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
        ["Royal Mail Partially Addressed UCID2", "PO Box 75218", "", "London", "E1W 9PZ", "1A"]
    ]),

    "4": ("Damart", [
        ["", "", "Royal Mail Wholesale UCID K8Z000", "PO Box 72662", "", "London", "E1W 9LD"],
        ["", "", "Client Services UCID K8Z000", "The Delivery Group", "Unit 2 Catalina Approach", "Warrington", "WA5 3UY"],
    ]),

    "5": ("Print Data Solutions", [
        ["","","","","James Chan", "33A Conisboro Avenue", "", "Reading", "RG4 7JE"],
        ["","","","","Karan Gupta", "1 Hob Mews", "35 Tadema Road", "London", "SW10 0PZ"],
        ["","","","","Royal Mail Wholesale UCID", "PO Box 72662", "", "London", "E1W 9LD"],
        ["","","","","Client Services UCID", "The Delivery Group", "Unit 2 Catalina Approach", "Warrington", "WA5 3UY"],
        ["","","","","Royal Mail Wholesale UCID", "PO Box 72662", "", "London", "E1W 9LD"],
        ["","","","","Client Services UCID", "The Delivery Group", "Unit 2 Catalina Approach", "Warrington", "WA5 3UY"],
    ]),
    
    "6": ("GeoffNeal", [
        ["", "", "Kings House", "174 Hammersmith Rd", "London", "W6 7JP"],
        ["", "", "5 South View Road", "Loughton", "Essex", "IG10 3LG"],
        ["", "", "Kings House", "174 Hammersmith Rd", "London", "W6 7JP"],
        ["", "Knells Farm Cottage",	"Queen Street", "Paddock Wood", "Kent", "TN12 6NP"],
        ["", "", "Brook House", "54a Cowley Mill Road", "Uxbridge", "UB8 2FX"],
        ["", "Royal Mail Wholesale UCID1", "PO Box 72662", "", "London", "E1W 9LD", "1A"],
        ["", "Royal Mail Partially Addressed UCID1", "PO Box 75218", "", "London", "E1W 9PZ", "1A"],
        ["", "Client Services UCID1", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
        ["", "Royal Mail Wholesale UCID2", "PO Box 72662", "", "London", "E1W 9LD", "1A"],
        ["", "Royal Mail Partially Addressed UCID2", "PO Box 75218", "", "London", "E1W 9PZ", "1A"],
        ["", "Client Services UCID2", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"]
    ]),
    
    "7": ("Signal / Guide Dogs", [
        ["Royal Mail Wholesale UCID1", "PO Box 72662", "", "", "London", "E1W 9LD", "", "", "", "", "Y", "1A"],
        ["Client Services UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "", "", "", "", "Y", "1B"],
        ["Royal Mail Wholesale UCID2", "PO Box 72662", "", "", "London", "E1W 9LD", "", "", "", "", "Y", "1A"],
        ["Client Services UCID2", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "", "", "", "", "Y", "1B"],
    ]),
}

split_seed_dict = {
    "1": ("Advertising", [
        ["Royal Mail Wholesale UCID1", "PO Box 72662", "", "", "London", "E1W 9LD", "1A"],
        ["Client Services UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY", "1B"],
    ]),
    "2": ("Digital Stamp", [
        ["SM Digital Stamp Sample UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
        ["RM Digital Stamp Sample UCID1", "RM Digital Stamp Team", "PO BOX 73733", "LONDON", "", "EC1P 1JX"],
    ]),
    "3": ("Partially Addressing", [
        ["Royal Mail Wholesale UCID1", "PO Box 75218", "", "", "London", "E1W 9PZ"],
        ["PA Team UCID1", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
    ]),
    "4": ("Damart", {
        "DamartN": [
            ["", "", "Royal Mail Wholesale UCID K8Z000", "PO Box 72662", "", "", "London", "E1W 9LD"],
            ["", "", "Client Services UCID K8Z000", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
        ],
        "DamartZ": [
            ["", "", "Royal Mail Wholesale UCID IZK000", "PO Box 72662", "", "", "London", "E1W 9LD"],
            ["", "", "Client Services UCID IZK000", "The Delivery Group", "Unit 2 Catalina Approach", "Omega South", "Warrington", "WA5 3UY"],
        ],
    })}

APP_TITLE = "Data processing application."

SYSTEM_PRINTERS = [
    r"\\TDG-FP01\DPWarLabel01",
    r"\\TDG-FP01\DPWarLabel02",
    r"\\TDG-FP01\DPWarLabel03",
    r"\\TDG-FP01\DPWarLabel04",
    r"\\TDG-FP01\DPWarLabel05",
    r"\\TDG-FP01\DPWarLabel06",
]

def color(text, c):
    if c == "red":
        return f'<span style="color:#cc0000;"><b>{text}</b></span>'
    if c == "yellow":
        return f'<span style="color:#c9a100;"><b>{text}</b></span>'
    if c == "green":
        return f'<span style="color:#0a8900;"><b>{text}</b></span>'
    return text

# ---------------------------------------------------------------------------------------
# Processing class
# ---------------------------------------------------------------------------------------
class Processor:
    CONTROL_CHARS = ''.join(map(chr, range(0, 32)))
    CONTROL_REGEX = re.compile(f"[{re.escape(CONTROL_CHARS)}]")

    def __init__(self, logger=None):
        self.logger = logger or (lambda m, c=None: None)
        self.cleansing_stats = Counter()
        self.last_header_result = None
        self.dropped_header_announced = False

    def log(self, msg, colour=None):
        try:
            if colour:
                self.logger(color(msg, colour), None)
            else:
                self.logger(msg, None)
        except TypeError:
            self.logger(msg, colour)

    # -------------------- cleansing --------------------
    def normalise_row(self, row):
        return ["" if c is None else str(c).strip() for c in row]

    def is_empty(self, cell):
        return cell == ""

    def cleanse_cell_string(self, x):
        if not isinstance(x, str):
            return x
        removed_count = 0
        s = x
        matches = re.findall(r"_x0{3}[0-9A-Fa-f]{1}_", s)
        if matches:
            removed_count += sum(len(m) for m in matches)
            s = re.sub(r"_x0{3}[0-9A-Fa-f]{1}_", " ", s)
        control_matches = self.CONTROL_REGEX.findall(s)
        removed_count += len(control_matches)
        s = self.CONTROL_REGEX.sub(" ", s)
        removed_nbsp = s.count("\xa0")
        removed_count += removed_nbsp
        if removed_nbsp:
            s = s.replace("\xa0", " ")
        if removed_count > 0:
            self.cleansing_stats['removed_chars'] += removed_count
            self.cleansing_stats['modified_cells'] += 1
        return s

    def cleanse_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        self.cleansing_stats.clear()
        df = df.astype(object).where(pd.notnull(df), "")
        df = df.map(self.cleanse_cell_string)
        df = df.replace("", pd.NA)
        before_rows, before_cols = df.shape
        df = df.dropna(how="all")
        
        cols_to_drop = []

        for i, col in enumerate(df.columns):
            col_data = df.iloc[:, i]

            # ALWAYS reduce to a single boolean
            col_data_empty = bool(col_data.isna().all())

            header = str(col).strip()

            is_placeholder = not header or re.fullmatch(r"Column\d+", header)

            if col_data_empty and is_placeholder:
                cols_to_drop.append(col)

        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        
        after_rows, after_cols = df.shape
        df = df.fillna("")
        removed = self.cleansing_stats.get("removed_chars", 0)
        modified = self.cleansing_stats.get("modified_cells", 0)
        if removed > 0:
            self.log(f"Removed {removed} hidden characters from {modified} cells.", "yellow")
        dropped_rows = before_rows - after_rows
        dropped_cols = before_cols - after_cols
        if dropped_rows > 0:
            self.log(f"Dropped {dropped_rows} empty rows", "yellow")
        if dropped_cols > 0:
            self.log(f"Dropped {dropped_cols} empty columns.", "yellow")
        return df
    
    def clean_header_names(self, df: pd.DataFrame, has_header: bool) -> pd.DataFrame:
        if not has_header:
            return df
        original = list(df.columns)
        cleaned = [
            c.replace("_", " ").strip() if isinstance(c, str) else c
            for c in original]
        if original != cleaned:
            self.log("[HEADER] Replaced underscores with spaces in column names.", "yellow")
            df.columns = cleaned
        return df

    def pad_rows(self, rows):
        if not rows:
            return rows, 0
        max_cols = 0
        for r in rows:
            if len(r) > max_cols:
                max_cols = len(r)
        if max_cols == 0:
            return rows, 0
        padded = []
        for r in rows:
            if len(r) == max_cols:
                padded.append(r)
            else:
                new = r + [""] * (max_cols - len(r))
                padded.append(new)
        return padded, max_cols

    def append_seeds(self, df: pd.DataFrame, seeds):
        if not seeds:
            return df
        ncols = len(df.columns)
        padded_seeds = [s + [""] * max(0, ncols - len(s)) for s in seeds]
        seed_df = pd.DataFrame(padded_seeds, columns=list(df.columns)[:ncols])
        return pd.concat([df, seed_df], ignore_index=True)

    def append_mmi(self, df: pd.DataFrame, mmi_choice, cell_name=None, new_col_name="MMI"):
        if mmi_choice == "MaMS Leeds":
            col_a = df.columns[0]
            col_c = df.columns[2] if len(df.columns) > 2 else df.columns[0]
            df[new_col_name] = ("Y|" + df[col_a].astype(str).str.strip() + "|" + df[col_c].astype(str).str.strip())
        elif mmi_choice == "Scotts":
            if not cell_name:
                raise ValueError("Cell name is required for Scotts MMI")
            col_a = df.columns[0]
            df[new_col_name] = ("Y|" + df[col_a].astype(str).str.strip() + "|" + cell_name.strip())
        elif mmi_choice == "ProHub DMS":
            col_a = df.columns[0]
            col_b = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            col_g = df.columns[6] if len(df.columns) > 6 else df.columns[0]
            df[new_col_name] = (df[col_g].astype(str).str.strip().str[:-12] + "00" + df[col_a].astype(str).str.strip() + df[col_b].astype(str).str.strip().str[1:])
        return df

    def remove_cols(self, df: pd.DataFrame):
        base_cols = ["BagNo", "ItemNo", "SscZone", "Carrier", "Depot", "BagBreak", "BarcodeData"]
        remove = [c for c in base_cols if c in df.columns]
        return df.drop(columns=remove, errors="ignore")

    def find_7zip(self):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            exe_path = os.path.join(bundle_dir, "7z")
            if os.path.isfile(exe_path):
                return exe_path
            exe_path_exe = os.path.join(bundle_dir, "7z.exe")
            if os.path.isfile(exe_path_exe):
                return exe_path_exe
        candidates = ["7z", "7za", "7zr",
            r"C:\\Program Files\\7-Zip\\7z.exe",
            r"C:\\Program Files (x86)\\7-Zip\\7z.exe",
            "/usr/local/bin/7z",
            "/opt/homebrew/bin/7z",
            "/usr/bin/7z"]
        for c in candidates:
            path = shutil.which(c) or (c if os.path.isfile(c) else None)
            if path:
                return path
        return None

    def create_encrypted_zip(self, folder, zip_filename, password):
        seven = self.find_7zip()
        if seven is None:
            raise FileNotFoundError("7-Zip not found on PATH.")
        folder_contents = os.path.join(folder, "*")
        cmd = [seven, "a", "-tzip", zip_filename, folder_contents, f"-p{password}", "-mem=ZipCrypto"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip failed: {result.stderr}")
        return True

    def get_row_sig(self, row):
        signature = []
        for cell in row:
            text = str(cell).strip()
            has_alpha = any(c.isalpha() for c in text)
            has_digit = any(c.isdigit() for c in text)
            cell_len = len(text)
            signature.append((has_alpha, has_digit, cell_len))
        return signature

    def score_row_similarity(self, sig_a, sig_b):
        score = 0
        for (a_alpha, a_digit, _), (b_alpha, b_digit, _) in zip(sig_a, sig_b):
            if a_alpha == b_alpha:
                score += 1
            if a_digit == b_digit:
                score += 1
        return score

    def row_digit_count(self, row):
        return sum(any(c.isdigit() for c in str(cell)) for cell in row)

    def row_avg_word_length(self, row):
        total = 0
        count = 0
        for cell in row:
            s = str(cell).strip()
            if not s:
                continue
            l = len(s)
            total += l
            count += 1
        return (total / count) if count else 0.0

    def uses_similarity_rule(self, r1, r2, r3):
        sig1 = self.get_row_sig(r1)
        sig2 = self.get_row_sig(r2)
        sig3 = self.get_row_sig(r3)
        sim12 = self.score_row_similarity(sig1, sig2)
        sim23 = self.score_row_similarity(sig2, sig3)
        return sim12 < sim23 * 0.75

    def uses_digit_density_rule(self, r1, r2, r3):
        d1 = self.row_digit_count(r1)
        d2 = self.row_digit_count(r2)
        d3 = self.row_digit_count(r3)
        return d1 < min(d2, d3) / 2

    def uses_word_length_rule(self, r1, r2, r3):
        l1 = self.row_avg_word_length(r1)
        l2 = self.row_avg_word_length(r2)
        l3 = self.row_avg_word_length(r3)
        return l1 > max(l2, l3) * 1.3

    def header_contains_keywords(self, row):
        HEADER_KEYWORDS = {
            "name", "address", "postcode", "post code", "zip", "email",
            "city", "town", "county", "country",
            "a1", "a2", "a3", "a4", "a5", "a6",
            "seed", "pid", "contact_id", "marketing_campaign", "brand_cd", "dps"
        }

        tokens = {
            str(c).strip().lower()
            for c in row
            if str(c).strip()
        }

        return bool(tokens & HEADER_KEYWORDS)


    def detect_delimiter(self, filename):
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(8192)
        candidates = [",", ";", "\t", "|"]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="".join(candidates))
            return dialect.delimiter
        except Exception:
            pass
        counts = {d: sample.count(d) for d in candidates}
        best = max(counts, key=counts.get)
        if counts[best] < 2:
            return ","
        return best

    def split_raw_lines(self, filename, delimiter):
        split_lines = []
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                split_lines.append(row)
        return split_lines

    def is_csv(self, name):
        return name.lower().endswith((".csv", ".txt"))

    def is_excel(self, name):
        return name.lower().endswith((".xls", ".xlsx"))

    def process_loaded_rows(self, lines):
        if len(lines) < 4:
            raise ValueError("Invalid file.")
        row1, row2, row3 = lines[0], lines[1], lines[2]
        result = self.detect_header(row1, row2, row3)
        self.last_header_result = result
        has_header, col_names, data_rows = self.apply_header_result(result, lines)
        padded_rows, max_cols = self.pad_rows(data_rows)
        if len(col_names) < max_cols:
            col_names += [f"Column{len(col_names) + i + 1}" for i in range(max_cols - len(col_names))]
        df = pd.DataFrame(padded_rows, columns=col_names).astype(object)
        df = self.cleanse_dataframe(df)
        return df, has_header

    def load_csv(self, filename):
        delimiter = self.detect_delimiter(filename)
        raw_lines = self.split_raw_lines(filename, delimiter)
        return self.process_loaded_rows(raw_lines)

    def load_excel(self, filename):
        # FIRST: try normal Excel load
        try:
            raw_df = pd.read_excel(filename, header=None, dtype=str).fillna("")
            raw_lines = raw_df.values.tolist()
            return self.process_loaded_rows(raw_lines)

        except Exception as e:
            # SECOND: check if file is actually encrypted
            try:
                with open(filename, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    if not office_file.is_encrypted():
                        # ❌ Not encrypted → real error, re-raise
                        raise

            except Exception:
                # Not an encrypted file → bubble original error
                raise

            # THIRD: encrypted file path
            self.log("Encrypted file - password required", "yellow")

            password, ok = QInputDialog.getText(
                None,
                "Password required",
                "This Excel file is password protected.\nEnter password:"
            )
            if not ok or not password:
                raise ValueError("Password entry cancelled.")

            try:
                decrypted = io.BytesIO()
                with open(filename, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted)

                decrypted.seek(0)
                raw_df = pd.read_excel(decrypted, header=None, dtype=str).fillna("")
                raw_lines = raw_df.values.tolist()
                return self.process_loaded_rows(raw_lines)

            except Exception as e2:
                raise ValueError(
                    "Could not open Excel file — incorrect password or unsupported encryption."
                ) from e2


    def load_file(self, filename):
        if self.is_csv(filename):
            return self.load_csv(filename)
        elif self.is_excel(filename):
            return self.load_excel(filename)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

    def save_csv(self, df, filename, has_header=True, delimiter=","):
        df.to_csv(filename, index=False, header=has_header, sep=delimiter)
        
    def trailing_empty_run(self, row):
        cnt = 0
        for c in reversed(row):
            if str(c).strip() == "":
                cnt += 1
            else:
                break
        return cnt

    def is_duplicate_header(self, r1, r2):
        return [c.strip().lower() for c in r1] == [c.strip().lower() for c in r2]

    def detect_partial_header(self, r1, r3):
        score = 0
        if sum(1 for c in r3 if str(c).strip()) > 0 and sum(1 for c in r1 if str(c).strip()) <= max(1, int(sum(1 for c in r3 if str(c).strip()) * 0.6)):
            score += 1
        if self.trailing_empty_run(r1) > self.trailing_empty_run(r3):
            score += 1
        prefix = 0
        for c in r1:
            if str(c).strip():
                prefix += 1
            else:
                break
        if prefix > 0 and sum(1 for c in r1 if str(c).strip()) - prefix <= max(1, int(prefix * 0.2)):
            score += 1
        return score >= 2

    def detect_real_header(self, r1, r2, r3):
        if self.header_contains_keywords(r1):
            return True
        if self.uses_similarity_rule(r1, r2, r3):
            return True
        if self.uses_digit_density_rule(r1, r2, r3):
            return True
        if self.uses_word_length_rule(r1, r2, r3):
            return True
        return False

    def detect_header(self, row1, row2, row3):
        r1 = self.normalise_row(row1)
        r2 = self.normalise_row(row2)
        r3 = self.normalise_row(row3)
        if self.is_duplicate_header(r1, r2):
            return "duplicate"
        if self.detect_partial_header(r1, r3):
            return "partial"
        if self.detect_real_header(r1, r2, r3):
            return "real"
        return "none"

    def drop_useless_header(self, df, has_header):
        if not has_header:
            return df, False
        placeholder = re.compile(r"^Column\d+$")
        if all(placeholder.match(str(c)) for c in df.columns):
            if not self.dropped_header_announced:
                self.dropped_header_announced = True
            df = df.iloc[1:].reset_index(drop=True)
            return df, False
        return df, True

    def analyze_and_log_header(self, df, has_header):
        raw_result = self.last_header_result
        placeholder = re.compile(r"^Column\d+$", re.IGNORECASE)
        col_names = [str(c).strip() for c in df.columns]
        first_row = [str(v).strip() for v in df.iloc[0].tolist()] if len(df) else []
        if raw_result == "duplicate":
            if has_header and first_row and [c.lower() for c in col_names] == [v.lower() for v in first_row]:
                self.log("[HEADER] Detected duplicate header, dropping row 2.", "yellow")
                df = df.iloc[1:].reset_index(drop=True)
            else:
                self.log("[HEADER] Detected duplicate header, dropping row 2.", "yellow")
            while len(df) > 0 and [c.lower() for c in col_names] == [v.lower() for v in df.iloc[0].astype(str)]:
                df = df.iloc[1:].reset_index(drop=True)
                self.log("[HEADER] Dropped additional duplicate header row.","yellow")
        placeholder_flags = [bool(placeholder.match(c)) for c in col_names]
        if any(placeholder_flags) and not all(placeholder_flags):
            self.log("[HEADER] Detected partial header.", "yellow")
            return df, has_header
        if has_header:
            if all(placeholder.match(c) for c in col_names):
                df2, new_has = self.drop_useless_header(df, has_header)
                self.log("[HEADER] Placeholder header dropped.", "yellow")
                return df2, new_has
            if raw_result == "real":
                self.log("[HEADER] Real header confirmed.", "green")
            elif raw_result == "partial":
                self.log("[HEADER] Partial header applied.", "yellow")
            elif raw_result == "duplicate":
                pass
            else:
                self.log("[HEADER] !!UNKNOWN HEADER!!", "red")
            return df, has_header
        self.log("[HEADER] No header detected.", "yellow")
        return df, has_header

    def apply_header_result(self, result, split_lines):
        row1 = split_lines[0]
        if result == "real":
            col_names = [str(c).strip() for c in row1]
            return True, col_names, split_lines[1:]
        elif result == "duplicate":
            col_names = [str(c).strip() for c in row1]
            return True, col_names, split_lines[2:]
        elif result == "partial":
            data_rows = split_lines[1:]
            padded_data, max_cols = self.pad_rows(data_rows)
            col_names = [str(c).strip() for c in row1]
            if len(col_names) < max_cols:
                col_names += [f"Column{len(col_names)+i+1}" for i in range(max_cols - len(col_names))]
            return True, col_names, padded_data
        else:
            padded, max_cols = self.pad_rows(split_lines)
            col_names = [f"Column{i+1}" for i in range(max_cols)]
            return False, col_names, padded
        
    @staticmethod
    def update_ucid(df: pd.DataFrame, ucidMap: dict) -> pd.DataFrame:
        pattern = re.compile(r"\b(UCID1|UCID2)\b")
        def replacer(match):
            key = match.group(1)
            return f"UCID {ucidMap[key]}"
        for col in df.columns:
            col_data = df[col]
            if not isinstance(col_data, pd.Series):
                continue
            if is_object_dtype(col_data):
                df[col] = col_data.astype(str).map(lambda v: pattern.sub(replacer, v))
        return df

    @staticmethod
    def split_by_zone(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "SscZone" not in df.columns:
            raise ValueError("No 'SscZone' column — validate data.")
        ssc = df["SscZone"].astype(str).str.replace("\u00A0", " ", regex=False).str.strip()
        zone_letter = ssc.str.extract(r'([A-Za-z])\s*$', expand=False).str.upper()
        missing = zone_letter.isna()
        if missing.any():
            fallback = ssc[missing].str.rstrip().str[-1:].str.upper()
            fallback = fallback.where(fallback.str.match(r'^[A-Z]$'), other=pd.NA)
            zone_letter.loc[missing] = fallback
        is_zonal = zone_letter.isin(["A", "B"])
        zonal = df[is_zonal.fillna(False)]
        national = df[~is_zonal.fillna(False)]
        return zonal.copy(), national.copy()
# ---------------------------------------------------------------------------------------
# Drag & Drop GUI code
# ---------------------------------------------------------------------------------------
class DragDropTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        
        self.preview_indexes = []

    def startDrag(self, supportedActions):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mouse_index = self.indexAt(self.mapFromGlobal(QCursor.pos()))
        if mouse_index in indexes:
            drag = QDrag(self)
            mime = self.model().mimeData(indexes)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def dragMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            self.clear_preview()
            return
        model = self.model()
        selected = self.selectedIndexes()
        if not selected:
            self.clear_preview()
            return
        rows = sorted(set(i.row() for i in selected))
        cols = sorted(set(i.column() for i in selected))
        top_left_row = index.row()
        top_left_col = index.column()
        self.preview_indexes = [
            model.index(top_left_row + r_i, top_left_col + c_i)
            for r_i, r in enumerate(rows)
            for c_i, c in enumerate(cols)
            if (top_left_row + r_i < model.rowCount() and top_left_col + c_i < model.columnCount())]
        self.viewport().update()
        event.accept()

    def clear_preview(self):
        if self.preview_indexes:
            self.preview_indexes = []
            self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.preview_indexes:
            return
        painter = QPainter(self.viewport())
        painter.setBrush(QColor(0, 120, 215, 50))
        painter.setPen(QColor(0, 120, 215))
        for idx in self.preview_indexes:
            rect = self.visualRect(idx)
            painter.drawRect(rect)

    def dragLeaveEvent(self, event):
        self.clear_preview()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            event.ignore()
            return
        model = self.model()
        if not model:
            event.ignore()
            return
        if event.mimeData().hasFormat(model.MIME_TYPE):
            if model.dropMimeData(event.mimeData(), Qt.DropAction.MoveAction, index.row(), index.column(), index):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
        self.clear_preview()
# ---------------------------------------------------------------------------------------
# Pandas model for preview
# ---------------------------------------------------------------------------------------
class DragDropPandasModel(QAbstractTableModel):
    MIME_TYPE = "application/x-pandas-cell-block"

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df.copy()
        self.undo_stack = []
        self.redo_stack = []

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return str(self.df.iat[index.row(), index.column()])
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            self.push_undo_state()
            self.df.iat[index.row(), index.column()] = value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return (
            Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsDragEnabled |
            Qt.ItemFlag.ItemIsDropEnabled |
            Qt.ItemFlag.ItemIsEditable)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self.df.columns[section])
        return str(section + 1)
    
    def rename_column(self, col: int, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            return
        current = str(self.df.columns[col])
        if current == new_name:
            return
        self.push_undo_state()
        self.df.columns = [
            new_name if i == col else c
            for i, c in enumerate(self.df.columns)]
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, col, col)
    
    def insert_row_above(self, row: int):
        self.push_undo_state()
        self.beginInsertRows(QModelIndex(), row, row)
        empty = pd.DataFrame([[""] * self.columnCount()], columns=self.df.columns)
        top = self.df.iloc[:row]
        bottom = self.df.iloc[row:]
        self.df = pd.concat([top, empty, bottom], ignore_index=True)
        self.endInsertRows()
        
    def insert_row_below(self, row: int):
        self.insert_row_above(row + 1)
            
    def delete_row(self, row: int):
        if self.rowCount() <= 1:
            return
        self.push_undo_state()
        self.beginRemoveRows(QModelIndex(), row, row)
        self.df = self.df.drop(self.df.index[row]).reset_index(drop=True)
        self.endRemoveRows()

    def insert_column_left(self, col: int):
        self.push_undo_state()
        self.beginInsertColumns(QModelIndex(), col, col)
        name = f"Column{self.columnCount() + 1}"
        self.df.insert(col, name, "")
        self.endInsertColumns()

    def insert_column_right(self, col: int):
        self.insert_column_left(col + 1)

    def delete_column(self, col: int):
        if self.columnCount() <= 1:
            return
        self.push_undo_state()
        self.beginRemoveColumns(QModelIndex(), col, col)
        self.df.drop(self.df.columns[col], axis=1, inplace=True)
        self.endRemoveColumns()

    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, indexes):
        mime = QMimeData()
        if not indexes:
            return mime
        rows = sorted(set(idx.row() for idx in indexes))
        cols = sorted(set(idx.column() for idx in indexes))
        block = self.df.iloc[rows, cols]
        encoded = pickle.dumps((rows, cols, block))
        mime.setData(self.MIME_TYPE, encoded)
        return mime

    def dropMimeData(self, mime, action, dest_row, dest_col, parent):
        if action != Qt.DropAction.MoveAction or not mime.hasFormat(self.MIME_TYPE):
            return False
        try:
            rows, cols, block = pickle.loads(bytes(mime.data(self.MIME_TYPE)))  # FIX: unpack all values
        except Exception:
            return False
        if parent is not None and parent.isValid():
            dest_row = parent.row()
            dest_col = parent.column()
        if dest_row is None or dest_col is None or dest_row < 0 or dest_col < 0:
            return False
        self.beginResetModel()
        try:
            src_rows = list(rows)
            src_cols = list(cols)
            move_pairs = []
            orig = self.df.copy()
            for r_i, sr in enumerate(src_rows):
                for c_i, sc in enumerate(src_cols):
                    dr = dest_row + r_i
                    dc = dest_col + c_i
                    if 0 <= dr < self.rowCount() and 0 <= dc < self.columnCount():
                        move_pairs.append(((sr, sc), (dr, dc)))
            if not move_pairs:
                return False
            self.push_undo_state()
            for (sr, sc), (dr, dc) in move_pairs:
                self.df.iat[dr, dc] = orig.iat[sr, sc]
            dest_set = set(dst for (_, dst) in move_pairs)
            src_set = set(src for (src, _) in move_pairs)
            for (sr, sc) in src_set:
                if (sr, sc) not in dest_set:
                    self.df.iat[sr, sc] = ""
            return True
        finally:
            self.endResetModel()

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def get_dataframe(self):
        return self.df.copy()
    
    def mousePressEvent(self, event):
        self._context_index = self.indexAt(event.pos())
        self._context_pos = event.pos()
        super().mousePressEvent(event)

    def push_undo_state(self):
        self.undo_stack.append(self.df.copy())
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.df.copy())
            self.df = self.undo_stack.pop()
            self.layoutChanged.emit()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.df.copy())
            self.df = self.redo_stack.pop()
            self.layoutChanged.emit()

    def copy_selection(self, indexes):
        if not indexes:
            return
        rows = sorted(set(i.row() for i in indexes))
        cols = sorted(set(i.column() for i in indexes))
        lines = []
        for r in rows:
            values = []
            for c in cols:
                val = str(self.df.iat[r, c]).replace("\n", " ").strip()
                values.append(val)
            lines.append("\t".join(values))
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)

    def paste_at(self, start_index):
        if not start_index.isValid():
            return
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        self.push_undo_state()
        rows = [r for r in text.split("\n") if r.strip() != ""]
        for r_i, row in enumerate(rows):
            cols = row.split("\t")
            for c_i, val in enumerate(cols):
                tr = start_index.row() + r_i
                tc = start_index.column() + c_i
                if tr < len(self.df) and tc < len(self.df.columns):
                    self.df.iat[tr, tc] = val
        self.layoutChanged.emit()

    def clear_selection(self, indexes):
        if not indexes:
            return
        self.push_undo_state()
        for idx in indexes:
            if idx.isValid():
                self.df.iat[idx.row(), idx.column()] = ""
        self.layoutChanged.emit()
# ---------------------------------------------------------------------------------------
# Preview Dialog
# ---------------------------------------------------------------------------------------
class PreviewDialog(QDialog):
    def __init__(self, dataframe, parent=None, title="Preview"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1500, 750)
        self.model = DragDropPandasModel(dataframe)
        layout = QVBoxLayout(self)
        self.table_view = DragDropTableView()
        self.table_view.setModel(self.model)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table_view)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        self.table_view.verticalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    def get_dataframe(self):
        return self.model.get_dataframe()

    def keyPressEvent(self, event: QKeyEvent):
        model = self.table_view.model()
        sel = self.table_view.selectedIndexes()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and event.key() == Qt.Key.Key_C:
            model.copy_selection(sel)
            return
        if ctrl and event.key() == Qt.Key.Key_V:
            start_index = sel[0] if sel else model.index(0, 0)
            model.paste_at(start_index)
            return
        if ctrl and event.key() == Qt.Key.Key_Z:
            model.undo()
            return
        if (ctrl and event.key() == Qt.Key.Key_Y) or (
            ctrl and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Z):
            model.redo()
            return
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if sel:
                model.clear_selection(sel)
            return
        super().keyPressEvent(event)

    def show_header_context_menu(self, pos):
        model = self.table_view.model()
        menu = QMenu(self)
        sender = self.sender()
        # ---------- COLUMN HEADER ----------
        if sender == self.table_view.horizontalHeader():
            col = sender.logicalIndexAt(pos)
            if col < 0:
                return
            menu.addAction(
                "Insert Column Left",
                lambda: model.insert_column_left(col))
            menu.addAction(
                "Insert Column Right",
                lambda: model.insert_column_right(col))
            menu.addSeparator()
            menu.addAction(
                "Rename Column",
                lambda: self.rename_column_dialog(col))
            menu.addSeparator()
            menu.addAction(
                "Delete Column",
                lambda: model.delete_column(col))
            menu.exec(sender.mapToGlobal(pos))
            return
        # ---------- ROW HEADER ----------
        if sender == self.table_view.verticalHeader():
            row = sender.logicalIndexAt(pos)
            if row < 0:
                return
            menu.addAction(
                "Insert Row Above",
                lambda: model.insert_row_above(row))
            menu.addAction(
                "Insert Row Below",
                lambda: model.insert_row_below(row))
            menu.addSeparator()
            menu.addAction(
                "Delete Row",
                lambda: model.delete_row(row))
            menu.exec(sender.mapToGlobal(pos))
            return

    def rename_column_dialog(self, col: int):
        model = self.table_view.model()
        current = str(model.df.columns[col])
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Column",
            "Column name:",
            text=current)
        if not ok or not new_name.strip():
            return
        model.rename_column(col, new_name)
        
    def show_context_menu(self, pos):
        view = self.table_view
        model = view.model()
        indexes = view.selectedIndexes()
        menu = QMenu(self)
        menu.addAction("Copy", lambda: model.copy_selection(indexes))
        menu.addAction(
            "Paste",
            lambda: model.paste_at(indexes[0] if indexes else model.index(0, 0)))
        menu.addSeparator()
        menu.addAction("Undo", model.undo)
        menu.addAction("Redo", model.redo)
        menu.addSeparator()
        menu.addAction(
            "Clear",
            lambda: model.clear_selection(indexes))
        menu.exec(view.viewport().mapToGlobal(pos))
# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------
def append_label_page_to_pdf(input_pdf):
    base = os.path.splitext(os.path.basename(input_pdf))[0]
    label_text = base.split("-", 1)[0]
    src = fitz.open(input_pdf)
    fd, temp_out = tempfile.mkstemp(suffix="_withlabel.pdf")
    os.close(fd)
    out = fitz.open()
    out.insert_pdf(src)

    LABEL_WIDTH  = 288   # 4"
    LABEL_HEIGHT = 432   # 6"
    page = out.new_page(width=LABEL_WIDTH, height=LABEL_HEIGHT)
    rect = fitz.Rect(0, 0, LABEL_WIDTH, LABEL_HEIGHT)

    page.insert_textbox(
        rect,
        label_text,
        fontsize=24,
        fontname="helv",
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_CENTER,
        rotate=90)

    out.save(temp_out)
    out.close()
    src.close()
    return temp_out

def print_to_specific_printer(pdf_path, printer_name):
    system = platform.system()

    if system == "Windows":
        possible = [
            os.path.join(os.getcwd(), "SumatraPDF.exe"),
            os.path.join(os.path.dirname(sys.argv[0]), "SumatraPDF.exe"),
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",]
        sumatra = next((p for p in possible if os.path.exists(p)), None)
        if not sumatra:
            QMessageBox.critical(None, "Error", 
                "SumatraPDF.exe not found.\nPlace it next to the application.")
            return
        cmd = [sumatra,
            "-print-to", printer_name,
            "-print-settings", "noscale",
            "-silent",
            pdf_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return
    subprocess.run(["lp", "-d", printer_name, pdf_path])

class BatchPdfPrintDialog(QDialog):
    def __init__(self, pdf_list, parent=None):
        super().__init__(parent)

        self.pdf_list = pdf_list
        self.batch_index = 0
        self.batch_size = len(SYSTEM_PRINTERS)  # ← dynamic batch size

        self.setWindowTitle("Print Files")
        self.resize(300, 250)

        self.layout = QVBoxLayout(self)

        self.lbl_header = QLabel("Files Loaded:")
        self.layout.addWidget(self.lbl_header)

        self.file_list_widget = QListWidget()
        self.layout.addWidget(self.file_list_widget)

        total_batches = math.ceil(len(pdf_list) / self.batch_size)
        self.lbl_status = QLabel(f"Batch 1 / {total_batches}")
        self.layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_skip = QPushButton("Skip")
        self.btn_next = QPushButton("Print && Next")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_next)
        self.layout.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_skip.clicked.connect(self.handle_skip)
        self.btn_next.clicked.connect(self.handle_print_next)

        self.refresh_file_list()
        self.update_button_label()

    def refresh_file_list(self):
        self.file_list_widget.clear()
        batch = self.pdf_list[self.batch_index:self.batch_index + self.batch_size]
        for f in batch:
            self.file_list_widget.addItem(os.path.basename(f))

    def update_button_label(self):
        remaining = len(self.pdf_list) - self.batch_index
        if remaining <= self.batch_size:
            self.btn_next.setText("Print && Finish")
        else:
            self.btn_next.setText("Print && Next")

    def handle_print_next(self):
        batch_files = self.pdf_list[
            self.batch_index : self.batch_index + self.batch_size
        ]

        for i, pdf in enumerate(batch_files):
            if i >= len(SYSTEM_PRINTERS):
                break
            labeled_pdf = append_label_page_to_pdf(pdf)
            print_to_specific_printer(labeled_pdf, SYSTEM_PRINTERS[i])

        self.batch_index += self.batch_size

        if self.batch_index >= len(self.pdf_list):
            self.lbl_status.setText("Finished")
            self.accept()
            return

        self.refresh_file_list()
        total_batches = math.ceil(len(self.pdf_list) / self.batch_size)
        current_batch = math.ceil(self.batch_index / self.batch_size) + 1
        self.lbl_status.setText(f"Batch {current_batch} / {total_batches}")
        self.update_button_label()

    def handle_skip(self):
        self.batch_index += self.batch_size

        if self.batch_index >= len(self.pdf_list):
            self.accept()
            return

        self.refresh_file_list()
        total_batches = math.ceil(len(self.pdf_list) / self.batch_size)
        current_batch = math.ceil(self.batch_index / self.batch_size) + 1
        self.lbl_status.setText(f"Batch {current_batch} / {total_batches}")
        self.update_button_label()
# ---------------------------------------------------------------------------------------
# Main Window: GUI only, delegates processing to Processor instance
# ---------------------------------------------------------------------------------------
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
        self.btn_create_seeds = QPushButton("Create file with optional seeds")
        self.btn_split_zones = QPushButton("Split mail into zones")
        self.btn_update_ucid = QPushButton("Update UCID")
        self.btn_create_zip = QPushButton("Create encrypted ZIP")
        self.btn_print_pdf = QPushButton("Print PDF")

        for btn in (self.btn_change_delim, self.btn_create_seeds, self.btn_split_zones, self.btn_update_ucid, self.btn_create_zip, self.btn_print_pdf):
            btn.setMinimumHeight(40)
            group_layout.addWidget(btn)
        layout.addWidget(group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.processor = Processor(logger=self._log_to_widget)
        self.btn_change_delim.clicked.connect(self.handle_change_delim)
        self.btn_create_seeds.clicked.connect(self.handle_create_seeds)
        self.btn_split_zones.clicked.connect(self.handle_split_zones)
        self.btn_update_ucid.clicked.connect(self.handle_update_ucid)
        self.btn_create_zip.clicked.connect(self.handle_create_zip)
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

    def ask_save_csv(self, title="Save file", filter="CSV Files (*.csv);;All Files (*)", defaultName=None):
        start_dir = self._get_start_dir()
        start_path = os.path.join(start_dir, defaultName) if defaultName else start_dir

        path, _ = QFileDialog.getSaveFileName(self, title, start_path, filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def clean_filename(self, infile: str) -> str:
        base = os.path.basename(infile)
        name, ext = os.path.splitext(base)
        name = re.sub(r"[^\w\s&]", "", name)   # remove punctuation
        name = name.replace("_", " ")         # turn underscores into spaces
        name = re.sub(r"\s+", " ", name)      # Collapse multiple spaces
        name = name.strip()                   # Trim
        return f"{name}.csv"

    def make_file_writable(self, path: str):
        if os.path.exists(path):
            attrs = os.stat(path).st_mode
            if not (attrs & stat.S_IWRITE):
                os.chmod(path, attrs | stat.S_IWRITE)

    def ask_folder(self, title="Select folder"):
        path = QFileDialog.getExistingDirectory(self, title, self._get_start_dir())
        if path:
            self.update_last_input_dir(path)
        return path or None

    def ask_text(self, title, label, default=""):
        text, ok = QInputDialog.getText(self, title, label, text=default)
        return text if ok else None

    def ask_choice(self, title, label, options):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setComboBoxItems(options)
        ok = dialog.exec()
        return dialog.textValue() if ok else None

    def ask_password_option(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Password option")
        layout = QVBoxLayout(dlg)
        btn_random = QPushButton("Generate random password")
        btn_enter  = QPushButton("Enter a password")
        layout.addWidget(btn_random)
        layout.addWidget(btn_enter)
        btn_random.clicked.connect(lambda: dlg.done(1))
        btn_enter.clicked.connect(lambda: dlg.done(2))
        result = dlg.exec()
        if result == 1:
            return "random"
        if result == 2:
            return "enter"
        return None

    def ask_ucid_count(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("How many UCIDs?")
        layout = QHBoxLayout(dlg)
        btn_random = QPushButton("1")
        btn_enter  = QPushButton("2")
        layout.addWidget(btn_random)
        layout.addWidget(btn_enter)
        btn_random.clicked.connect(lambda: dlg.done(1))
        btn_enter.clicked.connect(lambda: dlg.done(2))
        result = dlg.exec()
        if result == 1:
            return "1"
        if result == 2:
            return "2"
        return None

    def choose_delimiter(self):
        delim_map = {"Comma": ",", "Semicolon": ";", "Tab": "\t", "Pipe": "|"}
        choice = self.ask_choice("Choose delimiter", "Select output delimiter:", list(delim_map.keys()))
        if choice is None:
            return None
        return delim_map[choice]
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

            self.processor.log(f"[LOAD] Loading file: {infile}", "green")
            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

            out_delim = self.choose_delimiter()
            if out_delim is None:
                return

            base = os.path.splitext(os.path.basename(infile))[0]
            default_name = f"{base}.csv"

            outfile = self.ask_save_csv(
                "Save re-delimited CSV as",
                "CSV Files (*.csv);;All Files (*)",
                defaultName=default_name
            )
            if not outfile:
                return

            self.processor.save_csv(
                df,
                outfile,
                has_header=has_header,
                delimiter=out_delim
            )

            self.processor.log("File created successfully.", "green")

        except Exception as e:
            self.show_error("Change delimiter failed", str(e))

    #--------------------------------------------------------Create File--------------------------------------------------------
    def handle_create_seeds(self):
        try:
            infile = self.ask_open_file(
                "Choose CSV/TXT or Excel file to load",
                "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)"
            )
            if not infile:
                return

            self.make_file_writable(infile)

            self.processor.log(f"[LOAD] Loading file: {infile}", "green")
            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

            # Add MMI column
            add_mmi_q = QMessageBox.question(
                self,
                "Add MMI?",
                "Would you like to add an MMI column?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Cancel)
            if add_mmi_q == QMessageBox.Cancel:
                return
            elif add_mmi_q == QMessageBox.Yes:
                mmi_choice = self.ask_choice(
                    "Choose MMI",
                    "Select information:",
                    ["MaMS Leeds", "Scotts", "ProHub DMS"]
                )
                if not mmi_choice:
                    return
                if mmi_choice == "MaMS Leeds":
                    df = self.processor.append_mmi(df, mmi_choice)
                elif mmi_choice == "Scotts":
                    cell_name, ok = QInputDialog.getText(
                        self, "MMI", "Enter the cell name:")
                    if not ok or not cell_name.strip():
                        self.processor.log("MMI cancelled.", "yellow")
                        return
                    df = self.processor.append_mmi(df, mmi_choice, cell_name=cell_name)
                elif mmi_choice == "ProHub DMS":
                    df = self.processor.append_mmi(df, mmi_choice)

            # Add seeds
            add_seeds_q = QMessageBox.question(
                self,
                "Add seeds?",
                "Would you like to add seed rows to this file?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel)
            seeds = None
            if add_seeds_q == QMessageBox.Cancel:
                return
            elif add_seeds_q == QMessageBox.Yes:
                keys = [f"{k}: {seed_dict[k][0]}" for k in seed_dict]
                sel = self.ask_choice("Select seeds", "Choose seed service:", keys)
                if not sel:
                    return
                sel_key = sel.split(":", 1)[0].strip()
                seeds = seed_dict.get(sel_key, (None, None))[1]

            if seeds:
                df = self.processor.append_seeds(df, seeds)

            # Preview
            preview = PreviewDialog(df, self)
            if preview.exec() != QDialog.Accepted:
                return
            df = preview.get_dataframe()

            out_delim = self.choose_delimiter()
            if out_delim is None:
                return

            base = os.path.splitext(os.path.basename(infile))[0]
            default_filename = self.clean_filename(f"{base}.csv")

            outfile = self.ask_save_csv(
                "Save CSV as",
                "CSV Files (*.csv);;All Files (*)",
                defaultName=default_filename
            )
            if not outfile:
                return

            df = df.map(lambda x: str(x).replace("\n", " ").strip())
            self.processor.save_csv(df, outfile, has_header=has_header, delimiter=out_delim)

            self.processor.log("File created successfully.", "green")

        except Exception as e:
            self.show_error("Create seeds failed", str(e))

    #--------------------------------------------------------Zonal Split--------------------------------------------------------
    def handle_split_zones(self):
        try:
            infile = self.ask_open_file(
                "Choose mail CSV/TXT or Excel to split",
                "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)"
            )
            if not infile:
                return

            self.make_file_writable(infile)

            self.processor.log(f"[LOAD] Loading file: {infile}", "green")
            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

            zonal, national = self.processor.split_by_zone(df)
            zonal = self.processor.remove_cols(zonal)
            national = self.processor.remove_cols(national)

            zonal, has_headerZ = self.processor.drop_useless_header(zonal, has_header)
            national, has_headerN = self.processor.drop_useless_header(national, has_header)

            add_seeds_q = QMessageBox.question(
                self,
                "Add seeds?",
                "Add seed rows to both outputs?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel)
            seeds = None
            if add_seeds_q == QMessageBox.Cancel:
                return
            elif add_seeds_q == QMessageBox.Yes:
                keys = [f"{k}: {split_seed_dict[k][0]}" for k in split_seed_dict]
                sel = self.ask_choice("Select seeds", "Choose seed service:", keys)
                if not sel:
                    return
                sel_key = sel.split(":", 1)[0].strip()
                seeds = split_seed_dict.get(sel_key, (None, None))[1]

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

            out_delim = self.choose_delimiter()
            if out_delim is None:
                return

            raw_base = os.path.splitext(os.path.basename(infile))[0]
            base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base

            default_nat = self.clean_filename(f"{base} P1.csv")
            default_zon = self.clean_filename(f"{base} P2.csv")

            nat_out = self.ask_save_csv(
                "Save National CSV (P1)",
                "CSV Files (*.csv);;All Files (*)",
                defaultName=default_nat
            )
            if not nat_out:
                return

            zon_out = self.ask_save_csv(
                "Save Zonal CSV (P2)",
                "CSV Files (*.csv);;All Files (*)",
                defaultName=default_zon
            )
            if not zon_out:
                return

            national = national.map(lambda x: str(x).replace("\n", " ").strip())
            zonal = zonal.map(lambda x: str(x).replace("\n", " ").strip())

            self.processor.save_csv(national, nat_out, has_header=has_headerN, delimiter=out_delim)
            self.processor.save_csv(zonal, zon_out, has_header=has_headerZ, delimiter=out_delim)

            self.processor.log("Files created successfully.", "green")

        except Exception as e:
            self.show_error("Split mail failed", str(e))

    #--------------------------------------------------------Update UCID--------------------------------------------------------
    def handle_update_ucid(self):
        try:
            infile = self.ask_open_file(
                "Choose CSV/TXT or Excel to update UCID",
                "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)"
            )
            if not infile:
                return

            self.make_file_writable(infile)

            self.processor.log(f"[LOAD] Loading file: {infile}", "green")
            df, has_header = self.processor.load_file(infile)
            df, has_header = self.processor.analyze_and_log_header(df, has_header)
            df = self.processor.clean_header_names(df, has_header)

            opt = self.ask_ucid_count()
            if opt is None:
                return

            if opt == "1":
                ucid1 = self.ask_text("UCID replacement", "Enter UCID:", "")
                if ucid1 is None:
                    return
                ucid2 = ucid1
            else:
                ucid1 = self.ask_text("UCID replacement", "Enter first UCID:", "")
                if ucid1 is None:
                    return
                ucid2 = self.ask_text("UCID replacement", "Enter second UCID:", "")
                if ucid2 is None:
                    return

            ucid_map = {
                "UCID1": ucid1.strip(),
                "UCID2": ucid2.strip()
            }

            df = self.processor.update_ucid(df, ucid_map)

            base = os.path.splitext(os.path.basename(infile))[0]
            default_name = f"{base}.csv"

            outfile = self.ask_save_csv(
                "Save UCID-updated CSV",
                "CSV Files (*.csv);;All Files (*)",
                defaultName=default_name
            )
            if not outfile:
                return

            out_delim = self.choose_delimiter()
            if out_delim is None:
                return

            self.processor.save_csv(df, outfile, has_header=has_header, delimiter=out_delim)

            self.processor.log("UCID updated successfully.", "green")

        except Exception as e:
            self.show_error("Update UCID failed", str(e))

    #--------------------------------------------------------Create ZIP--------------------------------------------------------
    def handle_create_zip(self):
        try:
            files = self.ask_open_files(
                "Choose files to encrypt",
                "All Files (*.*);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx)"
            )
            if not files:
                return

            first_file = os.path.basename(files[0])
            base = '.'.join(first_file.split('.')[:-2]) or first_file.split('.')[0]
            default_zip_name = f"{base} DATA.zip"

            zipfile = self.ask_save_csv(
                "Save encrypted ZIP as",
                "ZIP Files (*.zip);;All Files (*)",
                defaultName=default_zip_name
            )
            if not zipfile:
                return

            choice = self.ask_password_option()
            if choice is None:
                return

            SAFE_CHARS = string.ascii_letters + string.digits + "-_@#$^!=+"

            if choice == "random":
                password = ''.join(secrets.choice(SAFE_CHARS) for _ in range(16))
            else:
                password = self.ask_text("Enter password", "Enter ZIP password:", "")
                if password is None:
                    return

            pw_txt_path = os.path.join(os.path.dirname(zipfile), "password.txt")
            try:
                with open(pw_txt_path, "w", encoding="utf-8") as f:
                    f.write(password)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Could not save password to {pw_txt_path}:\n{e}"
                )

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

            self.processor.log(
                "Zip file saved successfully. Password saved in text file.",
                "green"
            )

        except FileNotFoundError as e:
            self.show_error("7-Zip not found", str(e))
        except Exception as e:
            self.show_error("Create ZIP failed", str(e))

    #--------------------------------------------------------Print Files--------------------------------------------------------
    def handle_batch_print_pdfs(self):
        pdfs = self.ask_open_files(
            "Select PDFs for batch print",
            "PDF Files (*.pdf)"
        )
        if not pdfs:
            return

        dlg = BatchPdfPrintDialog(pdfs, self)
        dlg.exec()
# ---------------------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------------------
def main():
    try:
        app = QApplication(sys.argv)
        w = MainWindow()
        w.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
