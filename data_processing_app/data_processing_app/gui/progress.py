# gui/progress.py
from __future__ import annotations

import traceback
from typing import Callable, Any

from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
from PySide6.QtWidgets import QProgressDialog


class BusyWorker(QObject):
    finished = Signal(object)   # result
    error = Signal(str)         # traceback

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self):
        try:
            res = self._fn()
            self.finished.emit(res)
        except Exception:
            self.error.emit(traceback.format_exc())


class BusyJob(QObject):
    """
    Owns thread/worker/dialog and guarantees the dialog closes BEFORE external slots run.
    """
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, parent, title: str, message: str, fn: Callable[[], Any], cancelable: bool = False):
        super().__init__(parent)

        self.dialog = QProgressDialog(message, "Cancel" if cancelable else None, 0, 0, parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setMinimumDuration(150)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        if not cancelable:
            self.dialog.setCancelButton(None)

        self.thread = QThread(self)
        self.worker = BusyWorker(fn)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        # IMPORTANT: close dialog first, then emit finished/error on next event loop tick
        self.worker.finished.connect(self._handle_finished)
        self.worker.error.connect(self._handle_error)

        if cancelable:
            # UI cancel closes dialog and stops thread loop (does not stop computation)
            self.dialog.canceled.connect(self._cleanup_deferred)

    def start(self):
        self.dialog.show()
        self.thread.start()
        return self

    @Slot(object)
    def _handle_finished(self, res):
        try:
            self.dialog.close()
        except Exception:
            pass

        # Emit finished AFTER dialog closes (next tick)
        QTimer.singleShot(0, lambda: self.finished.emit(res))
        self._cleanup_deferred()

    @Slot(str)
    def _handle_error(self, err):
        try:
            self.dialog.close()
        except Exception:
            pass

        QTimer.singleShot(0, lambda: self.error.emit(err))
        self._cleanup_deferred()

    def _cleanup_deferred(self):
        QTimer.singleShot(0, self._cleanup)

    def _cleanup(self):
        if self.thread.isRunning():
            self.thread.quit()

        self.worker.deleteLater()
        self.thread.deleteLater()
        self.deleteLater()


def run_busy(parent, title: str, message: str, fn: Callable[[], Any], cancelable: bool = False) -> BusyJob:
    """
    Returns a BusyJob. Keep a reference (e.g., store on self._jobs).
    """
    return BusyJob(parent, title, message, fn, cancelable=cancelable).start()
