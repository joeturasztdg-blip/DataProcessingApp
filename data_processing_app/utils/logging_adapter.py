from utils.formatting import color

class LoggerAdapter:
    def __init__(self, sink=None):
        self._sink = sink or (lambda m, c=None: None)

    def log(self, msg, colour=None):
        try:
            if colour:
                self._sink(color(msg, colour), None)
            else:
                self._sink(msg, None)
        except TypeError:
            self._sink(msg, colour)
