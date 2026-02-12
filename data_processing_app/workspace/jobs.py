from __future__ import annotations

from dataclasses import dataclass, field
import traceback
from typing import Callable, Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
from PySide6.QtWidgets import QProgressDialog

class BusyWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

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

        self.worker.finished.connect(self._handle_finished)
        self.worker.error.connect(self._handle_error)

        if cancelable:
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
    return BusyJob(parent, title, message, fn, cancelable=cancelable).start()

@dataclass
class JobRunner:
    parent: Any
    _jobs: list = field(default_factory=list)

    def run(
        self,
        title: str,
        message: str,
        fn: Callable[[], Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_err: Optional[Callable[[str], None]] = None,
        cancelable: bool = False,
    ):
        job = run_busy(self.parent, title=title, message=message, fn=fn, cancelable=cancelable)
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
