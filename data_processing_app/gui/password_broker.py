# gui/password_broker.py
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, Qt, QMutex, QWaitCondition
from PySide6.QtWidgets import QInputDialog, QLineEdit


class PasswordBroker(QObject):
    """
    Thread-safe password requester.

    Worker thread calls get_password(prompt) -> str|None
    UI thread shows dialog and returns the password (or None if cancelled).
    """
    request = Signal(str)  # prompt text

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._response = None
        self._pending = False

        # Ensure the slot runs on the UI thread even if emitted from a worker
        self.request.connect(self._on_request, Qt.ConnectionType.QueuedConnection)

    def get_password(self, prompt: str) -> str | None:
        """
        Safe to call from any thread. Blocks the caller thread until user responds.
        """
        self._mutex.lock()
        try:
            # Mark pending and clear previous response
            self._pending = True
            self._response = None
            self.request.emit(prompt)

            # Wait until UI thread sets response
            while self._pending:
                self._wait.wait(self._mutex)

            return self._response
        finally:
            self._mutex.unlock()

    @Slot(str)
    def _on_request(self, prompt: str):
        # Runs on UI thread
        pw, ok = QInputDialog.getText(
            None,
            "Password required",
            prompt,
            QLineEdit.EchoMode.Password
        )
        response = pw if ok else None

        # Wake the waiting worker thread
        self._mutex.lock()
        try:
            self._response = response
            self._pending = False
            self._wait.wakeAll()
        finally:
            self._mutex.unlock()
