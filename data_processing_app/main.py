import sys
import csv

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


csv.field_size_limit(sys.maxsize)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
