"""One cancellable operation; all widgets stay on the GUI thread."""

import logging
from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QThread, Signal

from ai_subtitle_studio.domain.errors import OperationCancelled, StudioError


class OperationWorker(QThread):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, task: Callable, parent=None, *, with_progress: bool = False):
        super().__init__(parent)
        self.task = task
        self.with_progress = with_progress
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            result = (
                self.task(self.cancel_event, self.progress.emit)
                if self.with_progress
                else self.task(self.cancel_event)
            )
            self.succeeded.emit(result)
        except OperationCancelled:
            self.cancelled.emit()
        except (StudioError, OSError) as exc:
            # OSError strings can contain paths, but not subtitle dialogue.
            self.failed.emit(str(exc))
        except Exception:
            # Never dump unknown payloads/dialogue into logs or GUI.
            logging.getLogger(__name__).error("Nieoczekiwany błąd operacji plikowej")
            self.failed.emit("Nieoczekiwany błąd. Sprawdź plik i uruchom diagnostykę doctor.")
