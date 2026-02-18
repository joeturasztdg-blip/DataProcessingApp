APP_TITLE = "Data processing application."

DELIMITER_OPTIONS = [("Comma (,)", ","),
                     ("Semicolon (;)", ";"),
                     ("Tab", "\t"),
                     ("Pipe (|)", "|")]

SPLIT_MAX_UNIQUE = 20
# =========================
# PRINTING CONSTANTS
# =========================
PDF_LABEL_WIDTH_PT = 288
PDF_LABEL_HEIGHT_PT = 432
PDF_LABEL_FONT = "helv"
PDF_LABEL_FONT_SIZE = 24
PDF_LABEL_ROTATE = 90

SYSTEM_PRINTERS = [
    r"\\TDG-FP01\DPWarLabel01",
    r"\\TDG-FP01\DPWarLabel02",
    r"\\TDG-FP01\DPWarLabel03",
    r"\\TDG-FP01\DPWarLabel04",
    r"\\TDG-FP01\DPWarLabel05",
    r"\\TDG-FP01\DPWarLabel06",
]
# =========================
# GUI / TABLE CONSTANTS
# =========================
# Drag/drop table ergonomics
TABLE_EDGE_GRAB_PX = 4
TABLE_SCROLL_MARGIN_PX = 24
TABLE_SCROLL_INTERVAL_MS = 120
# Preview dialog default size
PREVIEW_WIDTH = 1500
PREVIEW_HEIGHT = 750
# Main window sizing
MAIN_WINDOW_MIN_WIDTH = 760
MAIN_WINDOW_MIN_HEIGHT = 560
# =========================
# WORKFLOW GUARDRAILS
# =========================
# Split-file heuristics
SPLIT_MAX_UNIQUE = 20
# CSV sniffing
CSV_SNIFF_BYTES = 8192
# Busy job defaults
BUSY_THREAD_SHUTDOWN_MS = 2000