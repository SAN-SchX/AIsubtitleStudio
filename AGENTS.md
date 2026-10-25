# MASTER IMPLEMENTATION PROMPT — AI SUBTITLE STUDIO

You are the lead software engineer, macOS engineer, and quality engineer for a local-first application called **AI Subtitle Studio**. Your job is to PRODUCE A REAL, TESTED, RUNNABLE CODEBASE, not a prototype slideshow, mock UI, or conceptual response. Read `ROADMAP.md`, `TASKS.md`, and this `AGENTS.md` before changing any code.

## Mission

Create a native-feeling desktop app for macOS (Apple Silicon, **16 GB unified RAM**) that:

1. Accepts a video file (MKV, MP4, MOV, AVI) and optionally external SRT/ASS subtitles.
2. Reads media metadata, enumerates audio streams, and allows the user to select the correct language/audio track.
3. Produces ORIGINAL-LANGUAGE subtitles by transcribing speech locally using an Apple Silicon-accelerated Whisper backend (prefer `mlx-whisper`).
4. Synchronizes existing external subtitles to the actual dialogue, including varying delay mid-episode and cases where source audio is Japanese while subtitles are Polish.
5. Generates translated subtitles in Polish or another selected language using local `qwen3:4b` via Ollama, while preserving dialogue IDs and audio-grounded timestamps.
6. Reports low-confidence timings, allows manual review and export without overwriting originals.
7. Exports Jellyfin-friendly sidecar subtitles (e.g. `Episode.pl.srt`).
8. Works offline after install and initial model downloads; never uploads user videos/transcripts to cloud services.

**Language of UI and user-facing documentation: Polish. Code/API identifiers and developer documentation: English.**

## Working mode (non-negotiable)

- Work **incrementally**, one phase at a time. Default first task: implement only phases 0 and 1, then stop and report; never claim future phases work just because stubs exist.
- On each phase: make a brief engineering plan; inspect existing code; implement; run unit tests and smoke tests; fix failures; update docs and task checklist; then report exact test commands and results.
- If you cannot execute macOS/MLX/Ollama-specific integration on your environment, clearly mark it `NOT VERIFIED` and implement isolated mocks. Never fabricate observed test results or successful installations.
- Provide no hollow stubs that claim to work, no fake progress bars, no mock transcript in production, no placeholder button without actual action. Disable UI components tied to unimplemented stages and visibly mark them “Planned”.
- Keep the application bootable after every phase. Do not randomly rewrite stable modules, and use typed interfaces across components.
- When third-party APIs or model tags change, check current upstream documentation and pin compatible dependencies. Do not assume that torch/CUDA WhisperX setup works natively on macOS; optional aligner may be installed separately and must have fallback.
- Update `CHANGELOG.md` and `docs/decisions.md` for behavior/API changes. Do not modify or delete users' media or subtitle originals.

## Architecture and dependencies

- Python 3.12; `pyproject.toml` and `src/` package layout; use `uv` or `venv`.
- PySide6 for desktop GUI. Background worker thread/process for media/AI processing, cancellation, signals, robust exceptions.
- FFprobe JSON for media metadata; FFmpeg executed via `subprocess.run`/`Popen` argument arrays (`shell=False`) for audio extraction, selected `-map 0:<stream_index>`, PCM 16 kHz mono WAV. Correct handling of Unicode file paths and quoted inputs.
- `pysubs2` for subtitle IO. Preserve ASS text/tags/style metadata in retiming (verify with tests). Explicitly report unsupported effect types rather than silently flattening to SRT.
- `mlx-whisper` for ASR, implement `SpeechProvider` interface to swap model backends. Support whisper-large-v3-turbo (accurate preset) and smaller-model fallback (speed preset). Implement actual audio chunk stitching and time offsets; do not keep an entire film decoded in RAM.
- VAD: Silero VAD where feasible. ASR may hallucinate during silence/music; use VAD and confidence validation.
- Simple sync: baseline offset/fps stretch and optional FFsubsync integration (global offset only); all results independently verified against fixture truth.
- Advanced sync: transcript matching, optional cross-lingual embeddings using `qwen3-embedding:0.6b`, optional local translation with `qwen3:4b`, monotonic constrained sequence alignment, anchor detection, confidence scoring, piecewise time mapping with breakpoint handling. Never let the LLM invent timestamps.
- Translation: Ollama local `127.0.0.1:11434`, supported JSON-schema structured output, strict Pydantic validation, retries with fixed limits, glossary preservation, cue ID and timestamp invariants.
- SQLite history only when required by relevant phase. Models should be unloaded between heavy stages on 16 GB to reduce memory pressure.
- No silent calls to remote services, telemetry, tracking or model downloads. Explicit user action is required to download model files. Users can opt in to local logging; logs should not include complete dialog text by default.

## Canonical domain models (implement in `domain/models.py`)

- `AudioTrack(stream_index: int, language: str | None, title: str | None, codec: str | None, channels: int | None)`
- `MediaInfo(duration_ms: int, audio_tracks: list[AudioTrack], fps_num: int | None, fps_den: int | None)`
- `WordTiming(text: str, start_ms: int, end_ms: int, confidence: float | None)`
- `TranscriptSegment(id: str, text: str, start_ms: int, end_ms: int, language: str, words: list[WordTiming], confidence: float | None)`
- `SubtitleCue(id: str, text: str, start_ms: int, end_ms: int, original_start_ms: int | None, original_end_ms: int | None, style: str | None)`
- `AlignmentPair(subtitle_ids: list[str], transcript_ids: list[str], score: float, status: str, reasons: list[str])`
- `JobConfig` typed; `JobResult` includes output paths, warning codes, low-confidence IDs and measured quality diagnostics.

Use **integer milliseconds** as canonical times inside business logic. Validate 0 <= start < end and stable cue IDs. Media PTS/stream selection/track offset issues must be explicitly tested.

## Matching engine spec

For mismatched subtitles:

1. Parse subtitle cues and transcribe original audio to timed segments.
2. Estimate simple offset or linear scaling (`new_time = a * old_time + b`) as baseline. If insufficient, do advanced matching.
3. Same-language candidates: normalized character/token resemblance; case folding as appropriate, punctuation normalization, meaningful word alignment.
4. Cross-language candidates: multilingual embeddings + optional local context translation, temporal proximity, duration, surrounding dialogue context, and scene/audio activity. Treat pure embedding similarity as insufficient for reliable matching.
5. Find monotonic matches with dynamic programming (support 1:1, 1:2, 2:1, skip, and null assignments) and limit search band to avoid O(N²) blowups on full-length films.
6. Identify multiple confident anchor points and detect discontinuities, segment boundaries, or gaps due to different edits (recap, opening, black frames, deleted scene).
7. Fit piecewise linear mapping per region with robust outlier handling. At boundaries, prefer genuine ASR/VAD timing rather than blindly moving all captions by a common amount.
8. Do not force assignment for unmatched subtitles. Mark low confidence and preserve original or candidate timing pending manual review.
9. Ensure monotonic start/end, duration, overlap policy, consistent Unicode/style preservation. Produce a per-cue provenance report.

Include a deterministic `--no-ai` mode for synthetic timing fixture tests, allowing `TranscriptionProvider` to be injected with ground truth.

## Translation engine spec

- The LLM must receive a list of `{id, source_text}` records, target language, nearby context and glossary.
- Tell the model: return **JSON only**, exactly one `{id, translated_text}` per input cue; no new/missing IDs, no timestamps, do not translate text in metadata/tags.
- `ollama.chat` `format=<Pydantic model_json_schema()>` and `stream=False`; validate exact ID set, order, unique IDs, nonempty text and no unrelated explanation. Consider disabling thinking in latency-sensitive stages only if the model supports it.
- The deterministic exporter copies source start/end timestamps; translation changes only text.
- Implement chunking with context overlap but emit every ID exactly once; preserve proper names; log uncertainties.
- If Ollama unavailable, transcription/generation/basic sync still work. Display a clear warning and disable AI features.

## App UI

- Main window with file-picker and drag/drop; show media metadata, audio track selection, source language override.
- Modes: `Synchronize`, `Transcribe`, `Transcribe & translate`, `Translate existing subtitles` (latter stages disabled until implemented).
- Settings: model selection, quality vs speed, local/offline mode, output folder, export language, memory-safe preset.
- Progress: stage name, completed chunks, cancellation, non-blocking GUI; show logs for failure explanations.
- Reviewer: cue table with start/end, original start/end, delta, text, confidence, reason, manual correction and preview around the cue; undo/redo.
- Export: SRT/ASS as applicable, safe suffix naming e.g. `.pl.srt`, no overwrite unless confirmed.
- Accessibility: keyboard navigation and scalable layout.

## Tests to write BEFORE claiming features complete

- `pytest` unit tests run offline with no model download.
- Known correct SRT file parses and round-trips; Polish accents, Japanese characters, long lines, SRT cue indexes, ASS styles retained where supported.
- Synthetic +8 s / -3 s shifts recovered with <=100 ms timing error (algorithmic fixture, not model quality).
- Synthetic 23.976 / 25 FPS scale correction yields expected timestamps.
- Synthetic mid-content jump of +10s detects a breakpoint; does not alter well-aligned opening.
- Skipped line/repeated phrase remains unresolved or marked low confidence rather than guessed.
- No-audio video yields useful error; multi-audio selection hits selected stream; corrupt input fails gracefully.
- Mock Ollama success/malformed JSON/extra IDs/timeout/offline all tested.
- Multiple cancellation / retry runs leave no stuck process, no overwritten files, no inconsistent DB state.
- User can run the app after phase 1, with unimplemented actions clearly labelled and not wired to fake successes.

## Quality bar and delivery for each phase

Output: a real committed source tree (or complete files if not working in Git), reproducible install/launch commands, tests and actual test output, explanation of design tradeoffs, outstanding blockers, and next recommended phase. Prefer fewer working features over a visually impressive broken app.

## Start here

Read `ROADMAP.md` and `TASKS.md`, inspect the target OS/toolchain, implement **phase 0 and phase 1 only**. After tests pass, stop. Do **not** claim that AI subtitle synchronization or Japanese translation are operational until separately demonstrated with real integration tests.
