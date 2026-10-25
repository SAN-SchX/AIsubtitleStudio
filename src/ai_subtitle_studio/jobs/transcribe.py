"""One bounded-memory transcription job, independent of Qt and Ollama."""

import logging
import shutil
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from threading import Event

from ai_subtitle_studio.config import DEFAULT_SETTINGS, Settings
from ai_subtitle_studio.domain.models import JobConfig, JobResult
from ai_subtitle_studio.files import output_target
from ai_subtitle_studio.media.extract import extract_audio
from ai_subtitle_studio.media.probe import probe_media
from ai_subtitle_studio.speech.base import (
    ProgressCallback,
    SpeechError,
    SpeechProvider,
    StageProgress,
    check_cancel,
)
from ai_subtitle_studio.speech.chunks import plan_chunks, wav_duration_ms, write_chunk
from ai_subtitle_studio.speech.cues import make_cues
from ai_subtitle_studio.speech.stitch import append_chunk
from ai_subtitle_studio.subtitles.io import save_cues

TRANSCRIPTION_SETTINGS = replace(DEFAULT_SETTINGS, process_timeout_s=3600)


def transcribe_video(
    config: JobConfig,
    output: Path,
    provider: SpeechProvider,
    *,
    cancel: Event | None = None,
    progress: ProgressCallback | None = None,
    settings: Settings = TRANSCRIPTION_SETTINGS,
    core_ms: int = 25000,
    context_ms: int = 1000,
) -> JobResult:
    started = time.perf_counter()
    cancel = cancel if cancel is not None else Event()

    def report(stage: str, completed: int = 0, total: int = 0):
        if progress:
            progress(StageProgress(stage=stage, completed=completed, total=total))

    try:
        check_cancel(cancel)
        if config.mode != "transcribe" or config.audio_stream_index is None:
            raise SpeechError("Wybierz tryb transkrypcji i konkretną ścieżkę audio.")
        if output.suffix.lower() != ".srt":
            raise SpeechError("Wynik transkrypcji należy zapisać jako nowy plik SRT.")
        sources = (config.video_path,) + ((config.subtitle_path,) if config.subtitle_path else ())
        output_target(output, sources)
        report("Odczyt metadanych")
        info = probe_media(config.video_path, settings, cancel)
        segments = []
        warnings = {"SILENCE_GATE_ONLY"}
        language = config.source_language
        silent = 0
        with tempfile.TemporaryDirectory(prefix="aisub-job-") as temporary:
            root = Path(temporary)
            if shutil.disk_usage(root).free < info.duration_ms * 32 + 32 * 1024 * 1024:
                raise SpeechError("Za mało wolnego miejsca na tymczasowy dźwięk PCM.")
            wav = root / "audio.wav"
            report("Ekstrakcja audio")
            extract_audio(
                config.video_path, wav, config.audio_stream_index, settings=settings, cancel=cancel
            )
            windows = plan_chunks(wav_duration_ms(wav), core_ms=core_ms, context_ms=context_ms)
            report("Transkrypcja", 0, len(windows))
            for window in windows:
                check_cancel(cancel)
                chunk = root / "chunk.wav"
                if write_chunk(wav, chunk, window):
                    result = provider.transcribe(chunk, language=language, cancel=cancel)
                    check_cancel(cancel)
                    if language is not None and result.language != language:
                        raise SpeechError("Backend zwrócił inny język niż wybrany dla zadania.")
                    if result.segments:
                        language = result.language  # lock auto-language after first nonempty chunk
                    warnings.update(append_chunk(segments, result, window))
                else:
                    silent += 1
                chunk.unlink(missing_ok=True)
                report("Transkrypcja", window.index + 1, len(windows))
            check_cancel(cancel)
            if not segments:
                raise SpeechError(
                    "Nie wykryto wypowiedzi. Nie utworzono pustych ani przykładowych napisów."
                )
            cues, review, cue_warnings = make_cues(segments)
            warnings.update(cue_warnings)
            report("Zapis SRT")
            save_cues(cues, output, sources=sources, cancel=cancel)
        elapsed = time.perf_counter() - started
        logging.getLogger(__name__).info(
            "ASR model=%s elapsed_s=%.3f chunks=%d", provider.model_id, elapsed, len(windows)
        )
        return JobResult(
            output_paths=[output],
            warnings=sorted(warnings),
            low_confidence_cue_ids=review,
            metrics={
                "elapsed_s": elapsed,
                "chunks_completed": len(windows),
                "silent_chunks": silent,
                "cue_count": len(cues),
                "review_cue_count": len(review),
                "max_cps": max(
                    len(c.text.replace("\n", "")) * 1000 / (c.end_ms - c.start_ms) for c in cues
                ),
                "audio_duration_ms": windows[-1].end_ms,
            },
            summary=f"Zapisano {len(cues)} kwestii SRT ({language}). "
            f"Model: {provider.model_id}. Czas: {elapsed:.1f} s. "
            f"Do kontroli: {len(review)}. Filtr ciszy nie zastępuje VAD."
            + (
                " Brak czasów słów w części wyniku; sprawdź granice napisów."
                if "WORD_TIMESTAMPS_MISSING" in warnings
                else ""
            ),
        )
    finally:
        provider.close()
