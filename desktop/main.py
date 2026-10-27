import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

APP_STYLESHEET = """
QWidget { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; }
QToolTip { background: #1e293b; color: #ffffff; border: none; padding: 4px 8px; }
QComboBox { color: #000000; }
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #000000;
    selection-background-color: #dbeafe;
    selection-color: #000000;
}
QDialog, QMessageBox, QInputDialog { background: #ffffff; }
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel { color: #000000; }
QDialog QLineEdit, QInputDialog QLineEdit { color: #000000; background: #ffffff; border: 1px solid #94a3b8; border-radius: 4px; padding: 4px; }
QDialog QPushButton, QMessageBox QPushButton {
    color: #000000; background: #f1f5f9; border: 1px solid #cbd5e1;
    border-radius: 5px; padding: 6px 16px; min-width: 64px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover { background: #e2e8f0; }
"""

ICON_PATH = Path(__file__).resolve().parent / "pe_ams_icon.ico"


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
