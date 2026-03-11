from __future__ import annotations

from workspace.base import BaseWorkflow
from gui.dialogs.databases_dialog import QueryDatabasesDialog


class QueryDatabases(BaseWorkflow):
    def run(self, checked: bool = False):
        dlg = QueryDatabasesDialog(self.mw)
        dlg.exec()