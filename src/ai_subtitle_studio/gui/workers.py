"""One cancellable operation; all widgets stay on the GUI thread."""

import logging
from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QThread, Signal

from ai_subtitle_studio.domain.errors import OperationCancelled, StudioError


class OperationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, task: Callable[[Event], object], parent=None):
        super().__init__(parent)
        self.task = task
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            self.succeeded.emit(self.task(self.cancel_event))
        except OperationCancelled:
            self.cancelled.emit()
        except (StudioError, OSError) as exc:
            # OSError strings can contain paths, but not subtitle dialogue.
            self.failed.emit(str(exc))
        except Exception:
            # Never dump unknown payloads/dialogue into logs or GUI.
            logging.getLogger(__name__).error("Nieoczekiwany błąd operacji plikowej")
            self.failed.emit("Nieoczekiwany błąd. Sprawdź plik i uruchom diagnostykę doctor.")
