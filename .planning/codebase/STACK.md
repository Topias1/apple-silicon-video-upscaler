# Technology Stack

**Analysis Date:** 2026-07-02

## Languages

**Primary:**
- Python 3.14 - All application logic (CLI pipeline in `upscale.py` + `upscaler/`, GUI server in `gui.py`, native shell in `app.py`)

**Secondary:**
- HTML/CSS/JavaScript - Embedded single-page GUI served as a string literal from `gui.py` (see the `INDEX_HTML` payload and inline `<script>` around `gui.py:848`); talks to the Python backend over HTTP and the pywebview `js_api` bridge.

## Runtime

**Environment:**
- CPython 3.14.5 (Homebrew `python@3.14`, Apple Silicon / arm64)
- Virtualenv at `.venv/` (`.venv/pyvenv.cfg`), not committed

**Package Manager:**
- pip (`pip`, `pip3.14` in `.venv/bin/`)
- Lockfile: missing (only unpinned `requirements.txt`; no `poetry.lock`/`Pipfile.lock`)

## Frameworks

**Core:**
- pywebview - Native macOS window wrapping the local web GUI (`app.py`, imports `webview`; `webview.create_window`, `webview.start`)
- `http.server` (stdlib `BaseHTTPRequestHandler`/`HTTPServer`) - Local GUI backend on `127.0.0.1:8080` (`gui.py:7`)

**Testing:**
- pytest - Unit + integration tests under `tests/` (`tests/test_*.py`), config cache in `.pytest_cache/`

**Build/Dev:**
- PyInstaller - Packages the app into `AppleSiliconVideoUpscaler.app` (`AppleSiliconVideoUpscaler.spec`, `.venv/bin/pyinstaller`); UPX compression enabled, icon `logo.icns`
- UPX - Binary compression during PyInstaller `EXE`/`COLLECT`

## Key Dependencies

**Critical (Python packages, from `requirements.txt`):**
- `tqdm` - Progress bar rendering for CLI batch/pipeline stages
- `pytest` - Test runner (dev/test dependency listed alongside runtime deps)
- `Pillow` - Image handling for upscaled frame processing
- `pywebview` - Native GUI (imported in `app.py`; NOT listed in `requirements.txt` — undeclared runtime dependency)

**Critical (external native binaries, not Python packages):**
- `ffmpeg` / `ffprobe` - Demux, split, downscale, filter (HDR tonemap, VFR CFR conform, hqdn3d), and hardware/software re-encode. Resolved via `shutil.which` in `upscaler/tools.py` (`get_ffmpeg_path`, `get_ffprobe_path`). Requires ffmpeg >= 5.1.
- `realesrgan-ncnn-vulkan` - GPU (Vulkan) Real-ESRGAN frame upscaling. Located via `upscaler/tools.py:find_realesrgan`. A bundled universal (x86_64 + arm64) Mach-O binary plus models ships under `realesrgan/` (gitignored).

**Infrastructure:**
- Vulkan (via ncnn) - GPU inference backend for Real-ESRGAN, including Venus Vulkan virtualization under UTM on Apple Silicon
- Apple VideoToolbox / NVIDIA NVENC / Intel-AMD VAAPI / libx265 - Encoder backends selected at runtime (`upscaler/encoders.py`)

## Configuration

**Environment:**
- `VIDEO_UPSCALER_CLI=1` - Switches `app.py` from GUI mode to CLI helper mode (`app.py` `__main__`, set by `gui.py` when spawning the worker)
- `PYTHONUNBUFFERED=1` - Set by `gui.py` on the subprocess env to stream progress without buffering
- No `.env` file present; no secret-bearing configuration detected

**Build:**
- `AppleSiliconVideoUpscaler.spec` - PyInstaller build config; bundles `upscale.py`, `upscaler/`, `gui.py`, `logo.jpg` as data; entry point `app.py`
- No `pyproject.toml` / `setup.py` — project is script-based, not an installable package

## Platform Requirements

**Development:**
- macOS on Apple Silicon (arm64), Python 3.14 via Homebrew
- `ffmpeg` and `realesrgan-ncnn-vulkan` on PATH (`brew install ffmpeg realesrgan-ncnn-vulkan`)

**Production:**
- Packaged macOS `.app` bundle (PyInstaller) for Apple Silicon
- Also architected for Linux (NVENC / VAAPI / libx265) and Ubuntu-on-UTM with Venus Vulkan (see `README.md`)

---

*Stack analysis: 2026-07-02*
