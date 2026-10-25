import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog

from ai_subtitle_studio.gui.main_window import MainWindow


@pytest.fixture
def view(qtbot):
    result = MainWindow()
    qtbot.addWidget(result)
    result.show()
    yield result
    result.close()
    wait_idle(qtbot, result)


def wait_idle(qtbot, view):
    qtbot.waitUntil(lambda: view.worker is None, timeout=10000)


def test_gui_real_video_picker_tracks_and_language(qtbot, view, media_files, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **kw: (str(media_files["multi"]), "")
    )
    qtbot.mouseClick(view.video_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    assert view.media_info is not None
    assert view.audio_combo.count() == 3
    assert view.audio_combo.currentData() is None  # don't guess language
    view.audio_combo.setCurrentIndex(2)
    view.language_combo.setCurrentIndex(3)
    assert view.job_config().audio_stream_index == 2
    assert view.job_config().source_language == "ja"
    assert view.extract_button.isEnabled()
    assert all(not b.isEnabled() and "Planowane" in b.text() for b in view.planned_buttons)


def test_real_drop_subtitles_and_export_copy(qtbot, view, fixtures_dir, tmp_path, monkeypatch):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(fixtures_dir / "ja_reference.srt"))])
    drag = QDragEnterEvent(
        view.rect().center(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view, drag)
    assert drag.isAccepted()
    drop = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view, drop)
    assert drop.isAccepted()
    wait_idle(qtbot, view)
    assert view.table.rowCount() == 4
    assert "お帰りなさい" in view.table.item(0, 3).text()
    output = tmp_path / "日本語.srt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(output), ""))
    qtbot.mouseClick(view.export_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    assert output.exists()
    before = output.read_bytes()
    qtbot.mouseClick(view.export_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    assert "Błąd" in view.status.text()
    assert output.read_bytes() == before


def test_remote_drop_is_rejected(qtbot, view):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/film.mp4")])
    drag = QDragEnterEvent(
        view.rect().center(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view, drag)
    assert not drag.isAccepted()
    assert view.worker is None


def test_gui_extracts_selected_track(qtbot, view, media_files, tmp_path, monkeypatch):
    view.load_video(media_files["multi"])
    wait_idle(qtbot, view)
    view.audio_combo.setCurrentIndex(2)
    target = tmp_path / "out.wav"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(target), ""))
    qtbot.mouseClick(view.extract_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    assert target.stat().st_size > 16000
    assert "Zapisano WAV" in view.status.text()


def test_gui_corrupt_video_recovers_and_imports_again(qtbot, view, media_files):
    view.load_video(media_files["corrupt"])
    wait_idle(qtbot, view)
    assert "Błąd" in view.status.text()
    assert view.video_path is None
    assert view.video_button.isEnabled()
    view.load_video(media_files["silent"])
    wait_idle(qtbot, view)
    assert "nie zawiera" in view.status.text()
    assert not view.extract_button.isEnabled()


def test_gui_cancellation_and_close_are_safe(qtbot, view):
    from ai_subtitle_studio.domain.errors import OperationCancelled

    def task(cancel):
        if cancel.wait(5):
            raise OperationCancelled()
        pytest.fail("cancel signal not received")

    view._start(task, lambda _: pytest.fail("not a success"), "Test", cancelable=True)
    qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    assert "anulowana" in view.status.text()
    view._start(task, lambda _: pytest.fail("not a success"), "Test", cancelable=True)
    view.close()
    wait_idle(qtbot, view)
    assert not view.isVisible()


def test_real_video_drop(qtbot, view, media_files):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(media_files["multi"]))])
    drag = QDragEnterEvent(
        view.rect().center(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view, drag)
    drop = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view, drop)
    assert drop.isAccepted()
    wait_idle(qtbot, view)
    assert view.video_path == media_files["multi"].resolve()
    assert view.audio_combo.count() == 3


def test_transcribe_blocked_without_native_backend(qtbot, view, media_files, monkeypatch):
    from ai_subtitle_studio.gui import main_window

    monkeypatch.setattr(main_window, "readiness", lambda _: "Brak lokalnego modelu MLX")
    view.load_video(media_files["multi"])
    wait_idle(qtbot, view)
    view.audio_combo.setCurrentIndex(1)
    assert not view.transcribe_button.isEnabled()
    assert "Brak lokalnego modelu" in view.speech_status.text()


@pytest.mark.parametrize("cancelled", [False, True])
def test_gui_transcription_wiring_and_responsiveness(
    qtbot, view, media_files, model_dir, tmp_path, monkeypatch, cancelled
):
    from threading import Event

    from PySide6.QtCore import QTimer

    from ai_subtitle_studio.domain.errors import OperationCancelled
    from ai_subtitle_studio.domain.models import TranscriptSegment, WordTiming
    from ai_subtitle_studio.gui import main_window
    from ai_subtitle_studio.speech.base import SpeechResult

    started = Event()
    closed = Event()

    class TestProvider:
        model_id = "test-only-provider"

        def transcribe(self, wav, *, language, cancel):
            started.set()
            if cancel.wait(2 if cancelled else 0.2):
                raise OperationCancelled()
            return SpeechResult(
                language="pl",
                segments=[
                    TranscriptSegment(
                        id="test",
                        text="Zażółć",
                        language="pl",
                        start_ms=100,
                        end_ms=800,
                        words=[WordTiming(text="Zażółć", start_ms=100, end_ms=800, confidence=0.9)],
                    )
                ],
            )

        def close(self):
            closed.set()

    monkeypatch.setattr(main_window, "readiness", lambda _: None)
    view.provider_factory = lambda directory: TestProvider()
    view.model_path.setText(str(model_dir))
    view.load_video(media_files["multi"])
    wait_idle(qtbot, view)
    view.audio_combo.setCurrentIndex(1)
    view.language_combo.setCurrentIndex(1)
    output = tmp_path / "transcript.srt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(output), ""))
    ticks = []
    timer = QTimer(view)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    qtbot.mouseClick(view.transcribe_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(started.is_set, timeout=5000)
    qtbot.waitUntil(lambda: len(ticks) > 2, timeout=1000)
    assert view.cancel_button.isEnabled()
    assert not view.video_button.isEnabled()
    if cancelled:
        qtbot.mouseClick(view.cancel_button, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, view)
    timer.stop()
    assert closed.is_set()
    assert output.exists() is not cancelled
    assert "anulowana" in view.status.text() if cancelled else "Zapisano" in view.status.text()
