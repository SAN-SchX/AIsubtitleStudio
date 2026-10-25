# Architecture — phases 0–1

`domain` contains validated Pydantic models and typed errors. `media` probes JSON
and streams audio through bounded FFmpeg processes. `subtitles` wraps pysubs2 with
strict validation and safe same-format copies; the source ASS document remains
available to retain styles. `files` owns atomic no-overwrite output publication.
`gui` presents Polish controls and runs file operations in a cancellable QThread.
`config` contains local tool settings. `doctor` only checks tools and local Ollama.
CLI imports Qt lazily so diagnostics do not require a display.

The implementation does not allocate decoded movie-length arrays. FFmpeg streams
to disk. One operation runs at a time. Subtitle inputs are size limited to 16 MiB.
Heavy model scheduling and chunked transcription belong to phase 2 and later.

## Phase 2 additions

`speech/base.py` defines SpeechProvider, SpeechResult and StageProgress. `models.py`
controls local readiness and explicit downloads; importing it loads no model.
`mlx_whisper.py` owns a per-job subprocess; `mlx_worker.py` alone imports the MLX
runtime. `chunks.py` reads bounded WAV windows; `stitch.py` assigns absolute word
ownership and deduplicates overlap; `cues.py` creates reviewed subtitle intervals.
`jobs/transcribe.py` orchestrates probe/extract/transcribe/export, independent of Qt.
The GUI injects a provider factory and receives progress via queued Qt signals.
Tests inject providers only in test code; production always selects the MLX adapter.
