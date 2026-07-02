# Codebase Structure

**Analysis Date:** 2026-07-02

## Directory Layout

```
video-upscaler/
├── app.py                          # Desktop shell entry (pywebview) + CLI dispatch
├── gui.py                          # Local HTTP UI server + embedded frontend
├── upscale.py                      # CLI argparse entry / orchestration
├── upscaler/                       # Core pipeline package
│   ├── __init__.py                 # Version + UpscalerError hierarchy
│   ├── batch.py                    # Input discovery + multi-file orchestration
│   ├── pipeline.py                 # Single-file split→upscale→encode→remux
│   ├── probe.py                    # ffprobe wrapper → VideoInfo
│   ├── plan.py                     # Presets, guards, disk estimation, output paths
│   ├── ffmpeg_cmds.py              # Pure ffmpeg/realesrgan argv builders
│   ├── encoders.py                 # Encoder selection + quality→CRF mapping
│   └── tools.py                    # ffmpeg/ffprobe detection + versions
├── tests/                          # pytest suite (mirrors upscaler modules)
│   ├── test_batch.py
│   ├── test_encoders.py
│   ├── test_ffmpeg_cmds.py
│   ├── test_plan.py
│   ├── test_probe.py
│   ├── test_integration.py
│   └── stub_realesrgan.py          # Fake realesrgan binary for tests
├── realesrgan/                     # Bundled Real-ESRGAN binary + models/*.bin/.param
├── docs/                           # Design docs (superpowers/specs)
├── AppleSiliconVideoUpscaler.spec  # PyInstaller build spec
├── requirements.txt                # tqdm, pytest, Pillow
├── logo.icns / logo.jpg            # App icon + UI logo
├── build/ dist/                    # PyInstaller output (generated)
└── README.md
```

## Directory Purposes

**`upscaler/`:**
- Purpose: All media-processing logic, importable and unit-testable.
- Key files: `pipeline.py` (orchestration core), `ffmpeg_cmds.py` + `encoders.py` (pure builders).

**`tests/`:**
- Purpose: pytest unit + integration coverage; one test module per source module.
- Contains: `stub_realesrgan.py` fake binary so integration tests avoid GPU.

**`realesrgan/`:**
- Purpose: Bundled `realesrgan-ncnn-vulkan` binary and `models/` (committed weights).

## Key File Locations

**Entry Points:**
- `app.py`: Desktop app (default) / CLI when `VIDEO_UPSCALER_CLI=1`.
- `upscale.py`: Direct CLI pipeline.
- `gui.py:main`: HTTP server on `127.0.0.1:8080`.

**Configuration:**
- `AppleSiliconVideoUpscaler.spec`: PyInstaller datas/bundle config.
- `requirements.txt`: Python deps.

**Core Logic:**
- `upscaler/pipeline.py`: `run_single_file`.
- `upscaler/batch.py`: `run_batch`, `discover_inputs`.

**Testing:**
- `tests/`: `test_*.py`, `stub_realesrgan.py`.

## Naming Conventions

**Files:**
- Source modules: lowercase, single word or snake_case (`ffmpeg_cmds.py`).
- Tests: `test_<module>.py` mirroring the source module name.

**Functions:**
- snake_case verbs: `build_split_cmd`, `select_encoder`, `probe_video`, `run_single_file`.

**Types/Exceptions:**
- PascalCase; errors suffixed `Error` and subclass `UpscalerError`.

## Where to Add New Code

**New pipeline stage / ffmpeg command:**
- Builder (pure): `upscaler/ffmpeg_cmds.py`; execution: `upscaler/pipeline.py`.
- Tests: `tests/test_ffmpeg_cmds.py` + `tests/test_integration.py`.

**New CLI option:**
- Add argparse arg in `upscale.py`; thread through `opts` dict to pipeline.
- Expose in GUI form + append to `cmd_args` in `gui.py` `do_POST` (`/upscale`).

**New encoder / preset:**
- `upscaler/encoders.py` (encoder map, `PRESET_BITRATES`) and `upscaler/plan.py` (`PRESETS`).

**New UI endpoint:**
- Add branch in `GUIHandler.do_GET`/`do_POST` in `gui.py`.

## Special Directories

**`build/`, `dist/`:** PyInstaller output — generated, not source of truth.
**`.venv/`, `.pytest_cache/`:** Local env/cache — not committed.
**`realesrgan/models/`:** Committed model weights (large binaries).

---

*Structure analysis: 2026-07-02*
