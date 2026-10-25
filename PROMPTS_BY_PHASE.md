# Copy-paste prompts for coding agents — one at a time

Before sending any prompt, share the entire specification pack or place these files in the repository. Avoid telling an agent to build all phases at once.

## Start (phases 0–1)

```
Read AGENTS.md, ROADMAP.md and TASKS.md in full. Create a production-minded Python 3.12 src-layout desktop project named AI Subtitle Studio. Implement ONLY Phase 0 and Phase 1: typed domain models, FFprobe media scanner/audio track enumeration, safe FFmpeg wrapper, SRT and ASS parser/export with encoding and Unicode handling, config, doctor diagnostics, basic PySide6 GUI with real drag-and-drop and status messages. Make unimplemented actions visibly disabled. Add offline unit tests including synthetic subtitle fixtures. Use macOS Apple Silicon 16 GB RAM as the target. Run tests and a smoke launch if the environment permits. Show exact results; do not pretend MLX transcription or LLM syncing is implemented. Update TASKS.md. Stop.
```

## Phase 2

```
Inspect and preserve the working code. Implement ONLY Phase 2 in ROADMAP/TASKS. Add real MLX Whisper local ASR provider with model selection, explicit model-download consent, audio stream extraction to mono 16k PCM, safe chunking with overlap and absolute timestamp reconstruction, language auto/manual override, cue segmentation and UTF-8 SRT output. Keep UI responsive; expose progress and cancellation. Use mock provider for unit tests, and an actual local audio fixture for integration when available. Run tests and report actual outcomes. Stop.
```

## Phase 3

```
Implement ONLY Phase 3: deterministic shift and rate correction engine, optional ffsubsync adapter, per-cue delta report and quality score. Do not modify subtitle text in sync mode. Write golden tests for +8 s / -3 s / 23.976→25 FPS synthetic transformations and test no-overwrite, then run tests. Stop.
```

## Phase 4

```
Implement ONLY Phase 4: transcript-to-subtitle matching for same-language and cross-language cases. Use qwen3-embedding:0.6b for candidates where available and qwen3:4b only for disambiguation; include deterministic fallback. Constrained monotonic sequence matching with skip and 1:2 / 2:1 merges, high-confidence anchors and robust piecewise time warping across jumps and edits. Never ask LLM to produce subtitle timestamps. Add confidence and manual-review flags. Golden test for mid-episode cut; report accuracy on real JA/PL fixtures only if actual test data exists. Stop.
```

## Phase 5

```
Implement ONLY Phase 5: local translation via Ollama qwen3:4b. Process batches with context/glossary; force and validate JSON schema records {id, translated_text}; preserve all source IDs and timings exactly; detect missing/duplicate/hallucinated records and retry or mark review. Handle service unavailable gracefully. Add unit tests with a mocked Ollama client plus optional real endpoint smoke test. Stop.
```

## Phase 6

```
Implement ONLY Phase 6: working reviewer/editor GUI: video preview, cue table, seek-to-cue, A/B comparison of old/new timing, per-line confidence/provenance, editable timestamps/text, undo/redo and safe export. Keep work off the UI thread. Demonstrate with an existing local fixture and report limitations. Stop.
```

## Phase 7 (optional)

```
Implement ONLY optional Phase 7 with strict memory limits: scene cuts via PySceneDetect and selectively sampled frames for OCR. Treat image observations as secondary evidence; no automatic frame-by-frame scanning. Keep this feature disabled by default and ensure the audio-only sync pipeline still works without vision dependencies. Add tests and stop.
```

## Phase 8

```
Implement ONLY Phase 8: seasonal batch processing, checkpoint/restart, Jellyfin-safe language sidecars, reliable .app packaging on Apple Silicon, offline-after-install verification, explicit license and dependency audit. Do not claim code signing/notarization without credentials or actual notarization. Produce installer/docs/test reports and stop.
```

## Bug-fix prompt

```
Do not rewrite the project. Reproduce the reported bug with a minimal failing automated test using the attached log/fixture. Identify root cause, fix only implicated components, rerun the affected tests and full regression suite, then summarize exact before/after results. If you could not reproduce, say so and request only indispensable missing data.
```

## Quality-audit prompt

```
Audit the current codebase against AGENTS.md and TASKS.md. For each claimed feature classify WORKS / PARTIAL / STUB / UNVERIFIED, with direct evidence and tests. Focus on preserving existing SRT text, avoiding hallucinated timestamps, cross-language matching quality, UI responsiveness, 16 GB RAM memory safety, and no network data exfiltration. Recommend ranked fixes; do not claim that untested AI model outputs are correct.
```
