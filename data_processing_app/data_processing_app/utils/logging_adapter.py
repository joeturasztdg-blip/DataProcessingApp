# utils/logging_adapter.py
from __future__ import annotations
from utils.formatting import color

class LoggerAdapter:
    """
    logger sink signature: sink(message: str, colour: str|None)
    Can be a normal function OR a Qt Signal.emit function.
    """
    def __init__(self, sink=None):
        self._sink = sink or (lambda m, c=None: None)

    def log(self, msg, colour=None):
        try:
            if colour:
                # format as HTML for QTextEdit
                self._sink(color(msg, colour), None)
            else:
                self._sink(msg, None)
        except TypeError:
            # fallback for legacy sinks expecting (msg, colour)
            self._sink(msg, colour)
