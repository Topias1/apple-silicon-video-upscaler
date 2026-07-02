<!-- refreshed: 2026-07-02 -->
# Architecture

**Analysis Date:** 2026-07-02

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Desktop Shell (pywebview)                  │
│  `app.py` — native macOS window + JS API (file dialogs)      │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP (127.0.0.1:8080)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 Local Web/UI Server + Frontend                │
│  `gui.py` — stdlib HTTPServer, embedded HTML/CSS/JS,          │
│  task_state, spawns CLI subprocess, streams progress          │
└────────────────────────────┬────────────────────────────────┘
                             │ subprocess (VIDEO_UPSCALER_CLI=1)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       CLI Entry / Arg Layer                   │
│  `upscale.py` — argparse, tool verify, encoder select         │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Pipeline Package                      │
│  `upscaler/` — batch → pipeline → probe/plan/ffmpeg/encoders  │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│           External Binaries (invoked via subprocess)          │
│  ffmpeg / ffprobe  •  realesrgan-ncnn-vulkan (Vulkan/Metal)   │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Desktop shell | Native window, native file/folder dialogs via JS API, process cleanup on close | `app.py` |
| UI server | Serves embedded HTML UI, exposes `/upscale` `/status` `/cancel` `/explore` endpoints, manages `task_state`, spawns and streams the CLI child process | `gui.py` |
| CLI arg layer | Parse args, verify tools, resolve encoder, dispatch batch | `upscale.py` |
| Batch orchestration | Discover inputs, resolve output paths, iterate files, fail-fast handling | `upscaler/batch.py` |
| Single-file pipeline | Split → extract → upscale → encode → concat → remux, manifest resume, frame reconciliation | `upscaler/pipeline.py` |
| Media probing | ffprobe wrapper → `VideoInfo` (dims, fps, HDR, VFR, audio) | `upscaler/probe.py` |
| Planning/guards | Preset guard, VFR/HDR mode checks, disk estimation, output path resolution | `upscaler/plan.py` |
| ffmpeg command builders | Pure functions building ffmpeg/realesrgan argv lists | `upscaler/ffmpeg_cmds.py` |
| Encoder selection | Map quality→CRF, select HW/SW encoder, build encoder args | `upscaler/encoders.py` |
| Tool detection | Locate ffmpeg/ffprobe, parse versions, enumerate encoders | `upscaler/tools.py` |
| Error taxonomy | Shared `UpscalerError` hierarchy | `upscaler/__init__.py` |

## Pattern Overview

**Overall:** Layered pipeline with a thin desktop shell over a local HTTP UI that shells out to a self-contained CLI.

**Key Characteristics:**
- Single-binary reuse: `app.py` runs as GUI, or as CLI when `VIDEO_UPSCALER_CLI=1` (same executable, branch in `app.py:70`).
- Pure command builders (`ffmpeg_cmds.py`, `encoders.py`) separated from subprocess execution (`pipeline.py`), making them unit-testable.
- Resumable pipeline via per-file JSON manifest and frame-count reconciliation.
- No web framework: `gui.py` uses stdlib `http.server` with an embedded HTML string.

## Layers

**Desktop shell (`app.py`):**
- Purpose: Wrap the local server in a native macOS webview window; provide Finder dialogs.
- Depends on: `pywebview`, `gui.main`.
- Used by: PyInstaller bundle entry (`AppleSiliconVideoUpscaler.spec`).

**UI server (`gui.py`):**
- Purpose: Serve UI, translate form input into CLI args, stream child-process output into `task_state`.
- Depends on: stdlib `http.server`, `subprocess`, `upscale.py` (as child).
- Used by: `app.py` (thread) or run standalone.

**CLI layer (`upscale.py`):**
- Purpose: Argument surface + orchestration entry.
- Depends on: `upscaler.tools`, `upscaler.encoders`, `upscaler.batch`.

**Core package (`upscaler/`):**
- Purpose: All media logic. `batch` → `pipeline` → (`probe`, `plan`, `ffmpeg_cmds`, `encoders`, `tools`).

## Data Flow

### Primary Upscale Path (GUI)

1. User picks file via native dialog (`app.py:16` JS API `select_file`).
2. Browser POSTs to `/upscale` (`gui.py:212`); form fields → `cmd_args`.
3. `run_upscale_thread` spawns child with `VIDEO_UPSCALER_CLI=1` (`gui.py:47-49`).
4. Child runs `upscale.main` → `verify_tools` → `select_encoder` → `run_batch` (`upscale.py:161-183`).
5. `run_batch` discovers inputs, calls `run_single_file` per file (`upscaler/batch.py`).
6. Pipeline: split → extract frames → realesrgan → encode → concat → remux (`upscaler/pipeline.py:182`).
7. Child stdout streamed char-by-char, parsed for progress %, output path into `task_state` (`gui.py:60-88`).
8. Browser polls `/status` (`gui.py:124`) to render progress/logs.

### CLI-only Path

1. `python upscale.py INPUT --preset 4k ...` → `upscale.main` directly.

**State Management:**
- Global `active_process` and `task_state` dicts in `gui.py` (single in-flight job).
- Resumability via per-file manifest JSON in the work dir (`load_or_create_manifest`, `pipeline.py:131`).

## Key Abstractions

**`VideoInfo` (NamedTuple):**
- Purpose: Immutable probe result carrying dims/fps/HDR/VFR/audio flags.
- File: `upscaler/probe.py`.

**`UpscalerError` hierarchy:**
- Purpose: Distinguish clean user-facing failures from unexpected crashes.
- Subclasses: `ToolError`, `ProbeError`, `PresetGuardError`, `VFRError`, `HDRError`, `ReconciliationError`, `SubprocessError`, `ManifestMismatchError`, `DiskEstimateError` (`upscaler/__init__.py`).

**Command builders:**
- Pure functions returning argv lists: `build_split_cmd`, `build_extract_cmd`, `build_realesrgan_cmd`, `build_encode_cmd`, `build_concat_cmd`, `build_remux_cmd` (`upscaler/ffmpeg_cmds.py`).

## Entry Points

**GUI:** `app.py:main` — starts `gui.main` server thread, opens webview.
**CLI:** `upscale.py:main` — argparse pipeline.
**Server:** `gui.py:main` — `HTTPServer(("127.0.0.1", 8080), GUIHandler)`.
**Packaged app:** `AppleSiliconVideoUpscaler.spec` → bundles `app.py` + `upscale.py` + `upscaler/` + `gui.py`.

## Architectural Constraints

- **Threading:** UI server runs the upscale job on a background thread; Real-ESRGAN Vulkan on Apple Silicon requires single-threaded invocation to avoid a driver deadlock (see commit `77fa237`), so `--jobs`/worker concurrency is constrained on that path.
- **Global state:** `active_process` and `task_state` are module-level singletons in `gui.py` — only one upscale job at a time.
- **Single-executable dual mode:** behavior branches on `VIDEO_UPSCALER_CLI` env var (`app.py:71`); breaking that contract breaks GUI→CLI dispatch.
- **Argument sanitization:** macOS Cocoa (`-psn_`) and PyInstaller flags (`-B -S -I -c`) must be filtered in `upscale.py:15-16` or argparse fails inside the bundle.
- **Bundle path resolution:** asset lookups must handle `sys._MEIPASS` (frozen) vs source dir (`gui.py:35-37`).

## Anti-Patterns

### Embedded HTML/JS in a Python string
**What happens:** The entire frontend lives as a large string inside `gui.py`.
**Why it's wrong:** No template separation, hard to lint, easy to break on edits.
**Do this instead:** If the UI grows, extract to a static file served from disk / `_MEIPASS`.

### Char-by-char stdout parsing for progress
**What happens:** `gui.py:60` reads one byte at a time and string-matches progress markers.
**Why it's wrong:** Fragile coupling between CLI print format and UI parser.
**Do this instead:** Emit structured progress lines (e.g. `PROGRESS: <pct>`) and parse whole lines.

## Error Handling

**Strategy:** Raise typed `UpscalerError` subclasses deep in the stack; catch at CLI boundary (`upscale.py:160-194`) and print clean stderr messages with exit codes (1 error, 130 interrupt).

**Patterns:**
- Subprocess failures wrapped in `SubprocessError` with file/chunk/stage context (`pipeline.py:57-79`).
- Frame-count mismatches raise `ReconciliationError` (`pipeline.py:362-409`).

## Cross-Cutting Concerns

**Logging:** CLI prints to stdout/stderr; GUI captures into `task_state["logs"]` (capped at 100 lines).
**Validation:** argparse `choices`, preset/VFR/HDR guards in `plan.py`.
**Authentication:** None (localhost-only server).

---

*Architecture analysis: 2026-07-02*
