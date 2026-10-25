# Architecture decision records

## ADR 001 — Scope and local-first boundary (phase 0)

Accepted: implement phases 0–1 only. The desktop imports media and subtitles,
selects streams/languages, exports copies and diagnoses dependencies. ASR, VAD,
retiming, translation, editor, database and packaging are later phases, not stubs.
No runtime telemetry, remote API or implicit downloads. Doctor alone can explicitly
query the fixed loopback Ollama endpoint. Logs are opt-in and exclude dialogue.

## ADR 002 — Time and PTS

All business intervals use validated integer milliseconds, `0 <= start < end`.
Signed FFprobe start PTS are metadata, not cue times. The video/container timeline
starts at zero. Audio extraction retains track delay relative to that timeline,
padding initial silence rather than moving dialogue to zero. FPS is a rational,
never the internal clock. Positive offset means later display. Phase 0 synthetic
transformations generate test inputs; they are not a synchronization algorithm.

## ADR 003 — Contracts and providers

Use Pydantic v2 exclusively for cross-component data. Domain IDs stay stable for
the lifetime of an imported document; SRT numeric indexes are presentation, not IDs.
Future speech adapters will receive local chunks and return TranscriptSegment
records, cancellable and independent of Qt. No MLX/PyTorch/LLM dependency until its
phase. FFmpeg is a subprocess with argv, no shell, bounded timeout and cancellation.
Workers communicate via Qt signals and do not mutate widgets.

## ADR 004 — Files and subtitle fidelity

Never overwrite any existing output, including symlinks/hardlinks. Write a sibling
temporary file, then publish using an atomic no-replace hard link. No unsafe
fallback on unsupported filesystems. Preserve ASS document/styles/events with
pysubs2; export in the same format only. Retain source ASS text as well, so a
copy preserves unknown extension sections. Preserve raw SRT cue text to avoid
loss from conversion through ASS formatting. ASS to SRT is explicitly unsupported
because it loses metadata. Karaoke/drawing/animation effects are preserved as
text but reported as unverified. No retiming of these effects in phase 1.
UTF-8/BOM is default, UTF-16 BOM supported; legacy encoding requires explicit choice.

## ADR 005 — Test corpus and target validation

Author synthetic multilingual text and FFmpeg-generated tones/color clips; no
copyrighted films, downloaded speech, or claimed ASR accuracy. Golden timing JSON
is literal reference data, independent of the transformation generator. Real
Apple Silicon and native macOS UI checks are required separately from Linux Qt
offscreen tests. Freeze dependencies with uv.lock; do not install AI models in CI.

## ADR 006 — Phase 1 behavior and failure boundaries

Phase 1 preview is read-only and limited to 500 rows, while exports include the
whole document. Track choice is explicit; no arbitrary language selection. Source
language only configures a future job and does not run ASR. Standard ASS event
column order is required; unsupported layouts fail visibly. GUI file IO runs in
one background thread. Process cancellation terminates and reaps child processes.
No original is opened for writing. Multimedia commands are limited to 60 seconds
and local file/pipe protocols; chunked long-running ASR is outside phase 1.

QApplication and windows must outlive queued events. Qt integration fixtures hold
a strong reference through event processing and explicit close before destruction.
Production entry point keeps the window alive for the application's event loop.
