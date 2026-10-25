"""Working media/subtitle import and copy export; AI modes are explicitly planned."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_subtitle_studio.config import LANGUAGES, SUBTITLE_EXTENSIONS, VIDEO_EXTENSIONS
from ai_subtitle_studio.domain.models import JobConfig, MediaInfo
from ai_subtitle_studio.gui.workers import OperationWorker
from ai_subtitle_studio.media.extract import extract_audio
from ai_subtitle_studio.media.probe import probe_media
from ai_subtitle_studio.subtitles.io import SubtitleDocument, export_subtitles, load_subtitles


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Subtitle Studio — media i napisy")
        self.resize(980, 720)
        self.setAcceptDrops(True)
        self.video_path: Path | None = None
        self.media_info: MediaInfo | None = None
        self.document: SubtitleDocument | None = None
        self.worker: OperationWorker | None = None
        self._success: Callable[[object], None] | None = None
        self._cancelable = False
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        intro = QLabel("Faza 1 · lokalne pliki · bez pobierania modeli. Upuść wideo lub SRT/ASS.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        files = QHBoxLayout()
        self.video_button = QPushButton("Otwórz wideo…")
        self.video_button.clicked.connect(self.choose_video)
        self.subtitles_button = QPushButton("Otwórz napisy…")
        self.subtitles_button.clicked.connect(self.choose_subtitles)
        files.addWidget(self.video_button)
        files.addWidget(self.subtitles_button)
        layout.addLayout(files)
        form = QFormLayout()
        self.video_field = QLineEdit()
        self.video_field.setReadOnly(True)
        form.addRow("Wideo:", self.video_field)
        self.metadata = QLabel("Brak wideo")
        self.metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.metadata.setWordWrap(True)
        form.addRow("Metadane:", self.metadata)
        self.audio_combo = QComboBox()
        self.audio_combo.setAccessibleName("Ścieżka audio")
        self.audio_combo.currentIndexChanged.connect(self._update_controls)
        form.addRow("Ścieżka audio:", self.audio_combo)
        self.language_combo = QComboBox()
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        form.addRow("Język źródłowy:", self.language_combo)
        self.encoding_combo = QComboBox()
        for label, encoding in (
            ("UTF-8 / BOM (automatycznie)", None),
            ("UTF-16", "utf-16"),
            ("Windows CP1250", "cp1250"),
        ):
            self.encoding_combo.addItem(label, encoding)
        form.addRow("Kodowanie przy imporcie:", self.encoding_combo)
        self.subtitle_field = QLineEdit()
        self.subtitle_field.setReadOnly(True)
        form.addRow("Napisy:", self.subtitle_field)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.extract_button = QPushButton("Zapisz wybraną ścieżkę jako WAV…")
        self.extract_button.clicked.connect(self.choose_extract)
        self.export_button = QPushButton("Zapisz kopię napisów…")
        self.export_button.clicked.connect(self.choose_export)
        actions.addWidget(self.extract_button)
        actions.addWidget(self.export_button)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Początek [ms]", "Koniec [ms]", "Tekst"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAccessibleName("Podgląd zaimportowanych napisów; bez edycji")
        layout.addWidget(self.table)
        planned = QHBoxLayout()
        self.planned_buttons = []
        for title in ("Synchronizuj", "Transkrybuj", "Transkrybuj i tłumacz", "Tłumacz napisy"):
            button = QPushButton(f"{title} — Planowane")
            button.setEnabled(False)
            button.setToolTip("Funkcja kolejnych faz; nie jest zaimplementowana.")
            planned.addWidget(button)
            self.planned_buttons.append(button)
        layout.addLayout(planned)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.clicked.connect(self.cancel_operation)
        layout.addWidget(self.cancel_button)
        self.status = QLabel("Gotowe. Oryginalne pliki nigdy nie są nadpisywane.")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Status operacji")
        layout.addWidget(self.status)
        self._update_controls()

    def _update_controls(self, *_):
        busy = self.worker is not None
        for widget in (
            self.video_button,
            self.subtitles_button,
            self.audio_combo,
            self.language_combo,
            self.encoding_combo,
        ):
            widget.setEnabled(not busy)
        self.extract_button.setEnabled(
            not busy and self.video_path is not None and self.audio_combo.currentData() is not None
        )
        self.export_button.setEnabled(not busy and self.document is not None)
        self.cancel_button.setEnabled(busy and self._cancelable)
        self.progress.setVisible(busy)

    def _start(self, task, success, message: str, *, cancelable: bool = False) -> None:
        if self.worker is not None:
            return
        self._success = success
        self._cancelable = cancelable
        self.worker = OperationWorker(task, self)
        self.worker.succeeded.connect(self._succeeded)
        self.worker.failed.connect(lambda text: self.status.setText(f"Błąd: {text}"))
        self.worker.cancelled.connect(lambda: self.status.setText("Operacja anulowana."))
        self.worker.finished.connect(self._finished)
        self.status.setText(message)
        self._update_controls()
        self.worker.start()

    def _succeeded(self, result):
        if self._success:
            self._success(result)

    def _finished(self):
        worker, self.worker = self.worker, None
        self._success = None
        if worker:
            worker.deleteLater()
        self._update_controls()

    def cancel_operation(self):
        if self.worker and self._cancelable:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Anulowanie…")

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz wideo", "", "Wideo (*.mkv *.mp4 *.mov *.avi)"
        )
        if path:
            self.load_video(Path(path))

    def load_video(self, path: Path):
        def loaded(info: MediaInfo):
            self.video_path = path.resolve()
            self.media_info = info
            self.video_field.setText(str(self.video_path))
            fps = f"{info.fps_num}/{info.fps_den}" if info.fps_num else "nieznany"
            self.metadata.setText(
                f"Czas: {info.duration_ms / 1000:.3f} s · FPS: {fps} · "
                f"Ścieżki audio: {len(info.audio_tracks)} · "
                f"Ścieżki napisów: {len(info.subtitle_tracks)}"
            )
            self.audio_combo.clear()
            self.audio_combo.addItem("Wybierz ścieżkę audio…", None)
            for track in info.audio_tracks:
                label = (
                    f"#{track.stream_index} · {track.language or 'język nieznany'} · "
                    f"{track.title or 'bez tytułu'} · {track.codec or '?'} · "
                    f"kanały: {track.channels or '?'}"
                )
                self.audio_combo.addItem(label, track.stream_index)
            self.status.setText(
                "Wideo odczytane. Wybierz właściwą ścieżkę audio."
                if info.audio_tracks
                else "Wideo nie zawiera ścieżki audio."
            )

        self._start(
            lambda cancel: probe_media(path, cancel=cancel),
            loaded,
            "Odczyt metadanych…",
            cancelable=True,
        )

    def choose_subtitles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Wybierz napisy", "", "Napisy (*.srt *.ass)")
        if path:
            self.load_subtitle_file(Path(path))

    def load_subtitle_file(self, path: Path):
        encoding = self.encoding_combo.currentData()

        def loaded(document: SubtitleDocument):
            self.document = document
            self.subtitle_field.setText(str(document.source_path))
            # Bounded preview, full document still exported intact.
            visible = document.cues[:500]
            self.table.setRowCount(len(visible))
            for row, cue in enumerate(visible):
                for col, value in enumerate((cue.id, cue.start_ms, cue.end_ms, cue.text)):
                    self.table.setItem(row, col, QTableWidgetItem(str(value)))
            text = f"Wczytano {len(document.cues)} kwestii. Podgląd: maksymalnie 500."
            if "ASS_EFFECTS_UNVERIFIED" in document.warnings:
                text += " Efekty ASS zachowano, lecz ich renderowanie nie jest zweryfikowane."
            if "UNSORTED_CUES" in document.warnings:
                text += " Uwaga: kwestie nie są uporządkowane czasowo."
            self.status.setText(text)

        self._start(lambda _: load_subtitles(path, encoding=encoding), loaded, "Odczyt napisów…")

    def choose_export(self):
        if self.document is None:
            return
        document = self.document
        default = document.source_path.with_name(
            f"{document.source_path.stem}.kopia.{document.format}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz nową kopię napisów", str(default), f"Napisy (*.{document.format})"
        )
        if path:
            self._start(
                lambda _: export_subtitles(document, Path(path)),
                lambda _: self.status.setText("Zapisano nową kopię napisów."),
                "Zapis kopii…",
            )

    def job_config(self) -> JobConfig:
        if self.video_path is None:
            raise ValueError("No video selected")
        return JobConfig(
            video_path=self.video_path,
            mode="inspect",
            subtitle_path=self.document.source_path if self.document else None,
            audio_stream_index=self.audio_combo.currentData(),
            source_language=self.language_combo.currentData(),
        )

    def choose_extract(self):
        if self.video_path is None or self.audio_combo.currentData() is None:
            return
        config = self.job_config()
        default = config.video_path.with_suffix(f".audio-{config.audio_stream_index}.wav")
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz nowy WAV 16 kHz mono", str(default), "Dźwięk (*.wav)"
        )
        if path:
            self._start(
                lambda cancel: extract_audio(
                    config.video_path, Path(path), config.audio_stream_index, cancel=cancel
                ),
                lambda _: self.status.setText("Zapisano WAV 16 kHz mono."),
                "Ekstrakcja wybranej ścieżki audio…",
                cancelable=True,
            )

    @staticmethod
    def _drop_path(event) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        return path if path.suffix.lower() in VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS else None

    def dragEnterEvent(self, event):
        if self.worker is None and self._drop_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self._drop_path(event)
        if self.worker is not None or path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            self.load_video(path)
        else:
            self.load_subtitle_file(path)

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.cancel()
            if not self.worker.wait(2500):
                self.status.setText("Trwa zamykanie operacji. Spróbuj ponownie za chwilę.")
                event.ignore()
                return
        event.accept()
