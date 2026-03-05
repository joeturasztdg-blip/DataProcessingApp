from __future__ import annotations

import os
import sys
import sqlite3
from typing import Optional

def resolve_config_db(rel_name: str) -> str:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        p = os.path.join(bundle, "config", rel_name)
        if os.path.exists(p):
            return p
    return os.path.join(os.getcwd(), "config", rel_name)


def connect_sqlite(db_path: str, *, row_factory: bool = True) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    if row_factory:
        con.row_factory = sqlite3.Row
    return con