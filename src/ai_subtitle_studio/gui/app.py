import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ai_subtitle_studio.gui.main_window import MainWindow


def run(*, smoke_test: bool = False) -> int:
    app = QApplication(sys.argv[:1])
    app.setApplicationName("AI Subtitle Studio")
    app.setOrganizationName("AI Subtitle Studio")
    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(250, window.close)
    return app.exec()
