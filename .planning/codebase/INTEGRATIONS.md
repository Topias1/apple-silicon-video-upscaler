# External Integrations

**Analysis Date:** 2026-07-02

## APIs & External Services

**Cloud/network APIs:**
- None. This is a fully local, offline desktop application. No outbound network calls, no third-party SaaS, no telemetry detected.

**Local subprocess "services" (external native binaries):**
- `ffmpeg` - Video demux/split, downscale, filtering, and re-encode
  - Invocation: `subprocess.run` / `subprocess.Popen` throughout `upscaler/tools.py`, `upscaler/ffmpeg_cmds.py`, `upscaler/pipeline.py`, `upscaler/probe.py`
  - Discovery: `shutil.which("ffmpeg")` in `upscaler/tools.py:get_ffmpeg_path`
  - Auth: none (local binary)
- `ffprobe` - Media stream/metadata probing (resolution, fps, HDR, VFR detection)
  - Invocation: `upscaler/probe.py` (`subprocess.run(probe_cmd, ...)`)
  - Discovery: `shutil.which("ffprobe")` in `upscaler/tools.py:get_ffprobe_path`
- `realesrgan-ncnn-vulkan` - GPU Real-ESRGAN frame upscaling
  - Invocation: spawned as a subprocess by the pipeline (`upscaler/pipeline.py`)
  - Discovery: `upscaler/tools.py:find_realesrgan` (custom path override via `--realesrgan-bin`, else PATH, else bundled `realesrgan/` binary)
  - Auth: none (local binary)

## Data Storage

**Databases:**
- None. No database of any kind.

**File Storage:**
- Local filesystem only. Intermediate chunk/frame artifacts written to a working directory (`--work-dir`, else derived), cleaned up unless `--keep-work`. Disk-usage estimation/guarding in `upscaler/plan.py` (`estimate_disk_usage`, `verify_disk_space`).
- Output videos written alongside source or to `--output-dir` (`upscaler/plan.py:resolve_output_paths`).

**Caching:**
- None (aside from per-chunk resume: pipeline skips already-completed segments on restart — `upscaler/pipeline.py` / `upscaler/batch.py`).

## Authentication & Identity

**Auth Provider:**
- None. No authentication, users, sessions, or credentials anywhere in the application.

## Monitoring & Observability

**Error Tracking:**
- None. Errors surface via typed exceptions (`UpscalerError`, `ToolError`, `ProbeError`, `PresetGuardError`, `VFRError`, `HDRError`, `DiskEstimateError` in `upscaler/__init__.py`) printed to stderr and shown in the GUI log panel.

**Logs:**
- CLI: stdout/stderr, `tqdm` progress bars
- GUI: subprocess stdout streamed char-by-char into `task_state["logs"]` and polled by the frontend (`gui.py:run_upscale_thread`)

## CI/CD & Deployment

**Hosting:**
- N/A — distributed as a local macOS `.app` bundle (PyInstaller, `AppleSiliconVideoUpscaler.spec`)

**CI Pipeline:**
- None detected (no `.github/workflows`, no CI config files present)

## Environment Configuration

**Required env vars:**
- `VIDEO_UPSCALER_CLI` - `"1"` selects CLI helper mode in `app.py`
- `PYTHONUNBUFFERED` - `"1"` set by `gui.py` for unbuffered subprocess output

**Secrets location:**
- None. No secrets, API keys, or credential files in the project.

## Webhooks & Callbacks

**Incoming:**
- Local HTTP endpoints only — the embedded GUI backend on `http://127.0.0.1:8080` handles GET/POST requests from the pywebview frontend (`gui.py`, `HTTPServer`). Not exposed beyond loopback.
- pywebview JS bridge: `window.pywebview.api.select_file()` / `select_folder()` call the native `Api` class in `app.py` for macOS Finder dialogs.

**Outgoing:**
- None.

---

*Integration audit: 2026-07-02*
