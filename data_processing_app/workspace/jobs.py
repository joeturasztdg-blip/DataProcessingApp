from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread, Qt, QSignalBlocker
from PySide6.QtWidgets import QProgressDialog

from config.constants import BUSY_THREAD_SHUTDOWN_MS

CANCELLED_MSG = "__CANCELLED__"

def start_busy_job(
    parent,
    *,
    title: str,
    message: str,
    fn: Callable[..., Any],
    cancelable: bool = False,
    progress_total: Optional[int] = None,
) -> BusyJob:
    return BusyJob(
        parent,
        title=title,
        message=message,
        fn=fn,
        cancelable=cancelable,
        progress_total=progress_total,
    ).start()

class BusyWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self,fn: Callable[..., Any],total: Optional[int] = None,cancel_event: Optional[threading.Event] = None):
        super().__init__()
        self._fn = fn
        self._total = total or 0
        self._cancel = cancel_event or threading.Event()

    def _progress_cb(self, current: int, total: Optional[int] = None, message: str = ""):
        if self._cancel.is_set():
            raise RuntimeError(CANCELLED_MSG)

        t = int(total) if total is not None else int(self._total)
        self.progress.emit(int(current), int(t), str(message or ""))

    @Slot()
    def run(self):
        try:
            sig = inspect.signature(self._fn)
            n_params = len(sig.parameters)

            if n_params >= 2:
                res = self._fn(self._progress_cb, self._cancel)
            elif n_params == 1:
                res = self._fn(self._progress_cb)
            else:
                res = self._fn()
            self.finished.emit(res)

        except Exception as e:
            msg = str(e).strip() or "Unknown error"
            if msg == CANCELLED_MSG:
                self.error.emit(CANCELLED_MSG)
            else:
                self.error.emit(msg)

class BusyJob(QObject):
    finished = Signal(object)
    error = Signal(str)
    cancel_requested = Signal()

    def __init__(self,parent,*,title: str,message: str,fn: Callable[..., Any],cancelable: bool = False,progress_total: Optional[int] = None,):
        super().__init__(parent)

        self._title = title
        self._message = message
        self._cancelable = cancelable
        self._progress_total = int(progress_total) if progress_total is not None else None

        self.dialog = QProgressDialog(parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setLabelText(message)
        self.dialog.setMinimumDuration(0)
        self.dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._cancel_event = threading.Event()

        if cancelable:
            self.dialog.setCancelButtonText("Cancel")
        else:
            self.dialog.setCancelButton(None)

        if self._progress_total is not None and self._progress_total > 0:
            self.dialog.setRange(0, self._progress_total)
            self.dialog.setValue(0)
        else:
            self.dialog.setRange(0, 0)

        self.thread = QThread(self)
        self.worker = BusyWorker(fn, total=self._progress_total, cancel_event=self._cancel_event)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)

        if cancelable:
            self.dialog.canceled.connect(self._on_cancel)

    def start(self):
        self.dialog.show()
        self.thread.start()
        return self

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, message: str):
        if total and self.dialog.maximum() != total:
            self.dialog.setRange(0, total)

        if message:
            self.dialog.setLabelText(message)

        if self.dialog.maximum() > 0:
            self.dialog.setValue(max(0, min(current, self.dialog.maximum())))

    @Slot(object)
    def _on_finished(self, res: Any):
        try:
            if self.dialog.maximum() > 0:
                self.dialog.setValue(self.dialog.maximum())
            # Block signals so close() doesn't emit canceled()
            blocker = QSignalBlocker(self.dialog)
            self.dialog.close()
            del blocker
        except Exception:
            pass
        self.finished.emit(res)
        self._cleanup()

    @Slot(str)
    def _on_error(self, err_text: str):
        try:
            blocker = QSignalBlocker(self.dialog)
            self.dialog.close()
            del blocker
        except Exception:
            pass
        self.error.emit(err_text)
        self._cleanup()

    @Slot()
    def _on_cancel(self):
        if self._cancel_event.is_set():
            return

        self._cancel_event.set()
        self.cancel_requested.emit()

        try:
            self.dialog.setLabelText("Cancelling")
            self.dialog.setCancelButton(None)
            self.dialog.setWindowTitle(self._title)
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()
        except Exception:
            pass

    def _cleanup(self):
        try:
            self.thread.quit()
            self.thread.wait(BUSY_THREAD_SHUTDOWN_MS)
        except Exception:
            pass
        try:
            self.worker.deleteLater()
            self.thread.deleteLater()
            self.deleteLater()
        except Exception:
            pass


@dataclass
class JobRunner:
    parent: Any
    _jobs: list = field(default_factory=list)

    def run(
        self,
        title: str,
        message: str,
        fn: Callable[..., Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_err: Optional[Callable[[str], None]] = None,
        cancelable: bool = False,
        progress_total: Optional[int] = None,
    ):
        job = start_busy_job(
            self.parent,
            title=title,
            message=message,
            fn=fn,
            cancelable=cancelable,
            progress_total=progress_total,
        )
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
