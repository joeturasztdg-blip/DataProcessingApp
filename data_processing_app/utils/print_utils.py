from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Optional


def _find_sumatra() -> Optional[str]:
    possible: list[str] = []
    # ---- PyInstaller onefile bundle dir ----
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        possible.append(os.path.join(bundle, "SumatraPDF.exe"))
    # ---- Normal locations ----
    possible.extend([
        os.path.join(os.getcwd(), "SumatraPDF.exe"),
        os.path.join(os.path.dirname(sys.argv[0]), "SumatraPDF.exe"),
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",])
    return next((p for p in possible if os.path.exists(p)), None)


def print_to_specific_printer(pdf_path: str, printer_name: str) -> None:
    system = platform.system()

    if system == "Windows":
        sumatra = _find_sumatra()
        if not sumatra:
            raise FileNotFoundError(
                "SumatraPDF.exe not found.\n"
                "Place it next to the application (or install it in Program Files)."
            )

        cmd = [
            sumatra,
            "-print-to", printer_name,
            "-print-settings", "noscale",
            "-silent",
            pdf_path,
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()
            raise RuntimeError(msg or f"Printing failed (exit code {res.returncode}).")
        return

    res = subprocess.run(["lp", "-d", printer_name, pdf_path], capture_output=True, text=True)
    if res.returncode != 0:
        msg = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(msg or f"Printing failed (exit code {res.returncode}).")