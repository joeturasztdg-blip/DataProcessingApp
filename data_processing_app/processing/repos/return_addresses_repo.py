from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from processing.database import resolve_config_db, connect_sqlite


class ReturnAddressesRepository:
    def __init__(self, *, db_filename: str = "return_addresses.db", db_path: Optional[str] = None):
        self.db_path = db_path or resolve_config_db(db_filename)
        self.table_name = "return_addresses"

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, row_factory=True)

    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT
                    ID,
                    contact_name,
                    address1,
                    address2,
                    address3,
                    Town,
                    postcode
                FROM {self.table_name}
                ORDER BY ID ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT
                    ID,
                    contact_name,
                    address1,
                    address2,
                    address3,
                    Town,
                    postcode
                FROM {self.table_name}
                WHERE
                    contact_name LIKE ?
                    OR address1 LIKE ?
                    OR address2 LIKE ?
                    OR address3 LIKE ?
                    OR Town LIKE ?
                    OR postcode LIKE ?
                ORDER BY ID ASC
                LIMIT ?
                """,
                (pat, pat, pat, pat, pat, pat, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def next_id(self) -> int:
        with self._connect() as con:
            row = con.execute(
                f"SELECT COALESCE(MAX(ID), 0) + 1 AS nxt FROM {self.table_name}"
            ).fetchone()
        return int(row["nxt"]) if row and row["nxt"] is not None else 1

    def insert_row(
        self,
        *,
        id_: int,
        contact_name: str,
        address1: str,
        address2: str = "",
        address3: str = "",
        town: str,
        postcode: str,
    ) -> None:
        with self._connect() as con:
            con.execute(
                f"""
                INSERT INTO {self.table_name}
                (
                    ID,
                    contact_name,
                    address1,
                    address2,
                    address3,
                    Town,
                    postcode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(id_),
                    str(contact_name),
                    str(address1),
                    str(address2) if address2 is not None else "",
                    str(address3) if address3 is not None else "",
                    str(town),
                    str(postcode),
                ),
            )
            con.commit()