# Coding Conventions

**Analysis Date:** 2026-07-02

## Naming Patterns

**Files:**
- Lowercase `snake_case` module names: `ffmpeg_cmds.py`, `probe.py`, `plan.py`, `batch.py`, `encoders.py`, `pipeline.py`, `tools.py`
- Package lives in `upscaler/`; CLI entry point is top-level `upscale.py`; GUI is top-level `gui.py`; PyInstaller launcher is `app.py`
- Test modules mirror source with `test_` prefix: `tests/test_plan.py` ↔ `upscaler/plan.py`

**Functions:**
- `snake_case`, verb-first, descriptive: `check_preset_guard`, `resolve_output_paths`, `build_encode_cmd`, `get_exact_frame_count`, `run_cmd_checked`
- Command builders consistently prefixed `build_*` (`upscaler/ffmpeg_cmds.py`): `build_split_cmd`, `build_extract_cmd`, `build_realesrgan_cmd`, `build_encode_cmd`, `build_concat_cmd`, `build_remux_cmd`
- Tool discovery prefixed `get_*`: `get_ffmpeg_path`, `get_ffprobe_path`, `get_ffmpeg_version` (`upscaler/tools.py`)
- Validation guards prefixed `check_*` and raise on failure: `check_preset_guard`, `check_vfr_mode`, `check_hdr_mode` (`upscaler/plan.py`)

**Variables:**
- `snake_case` throughout: `target_height`, `seg_in_dir`, `frames_per_chunk`, `resolved_params`
- Path variables suffixed `_path`, `_dir`, `_abs`: `input_abs`, `work_dir`, `manifest_path`, `seg_out_dir`

**Types:**
- Module-level constants `UPPER_SNAKE`: `PRESETS`, `PRESET_BITRATES`, `SUPPORTED_EXTENSIONS`
- `NamedTuple` for structured returns: `VideoInfo` (`upscaler/probe.py:9`)
- Exception classes `CamelCase` ending in `Error`, all subclass `UpscalerError` (`upscaler/__init__.py`)

## Code Style

**Formatting:**
- No formatter config present (no `.prettierrc`, no `black`/`ruff` config, no `pyproject.toml`)
- De facto style: 4-space indentation, PEP 8 aligned, roughly 100-char lines
- Some trailing whitespace on blank lines exists (e.g. `upscaler/pipeline.py`) — not enforced

**Linting:**
- No linter configured. Conventions are enforced by convention, not tooling.

## Import Organization

**Order** (observed consistently across `upscaler/*.py`):
1. Standard library, alphabetical: `import json`, `import os`, `import shutil`, `import subprocess`
2. `from` stdlib imports: `from pathlib import Path`, `from typing import ...`
3. Intra-package relative imports: `from . import ProbeError, ToolError`, `from .probe import probe_video`, `from .tools import get_ffprobe_path`

**Path Aliases:**
- None. Package uses explicit relative imports (`from .`) within `upscaler/`; entry points use absolute package imports (`from upscaler.tools import verify_tools`).

**Deferred imports:**
- Optional/heavy deps imported inside functions to keep them optional: `from tqdm import tqdm` (`upscaler/pipeline.py:289`), `from PIL import Image` (`upscaler/probe.py:213`), `from .probe import detect_video_type` (`upscaler/pipeline.py:197`)

## Error Handling

**Custom exception hierarchy** (`upscaler/__init__.py`) — the central convention:
- `UpscalerError` is the base for all *expected, user-facing* errors.
- Subclasses signal specific conditions: `ToolError`, `ProbeError`, `PresetGuardError`, `VFRError`, `HDRError`, `ReconciliationError`, `SubprocessError`, `ManifestMismatchError`, `DiskEstimateError`.
- All exported via `__all__`.

**Patterns:**
- Library code raises typed `UpscalerError` subclasses with rich, multi-line messages including context (file, chunk, stage, expected vs actual). Example: `SubprocessError` in `run_cmd_checked` (`upscaler/pipeline.py:57`).
- The CLI boundary (`upscale.py:main`) is the *only* place that catches broadly: catches `ToolError`/`UpscalerError` → prints `ERROR: ...` to stderr and returns exit code `1`; `KeyboardInterrupt` → returns `130`; unexpected `Exception` → prints traceback and returns `1`.
- Subprocess wrappers re-raise their own typed error but avoid double-wrapping: `if isinstance(e, SubprocessError): raise` (`upscaler/pipeline.py:72`).
- Best-effort fallbacks swallow exceptions with bare `except Exception: pass` when a degraded result is acceptable (frame counting `upscaler/pipeline.py:47`, content-type detection `upscaler/probe.py`).

## Logging

**Framework:** None. Uses `print()` for user-facing progress (stdout) and `print(..., file=sys.stderr)` for errors.

**Patterns:**
- Progress rendered as a manual ASCII bar in `run_realesrgan_stream` (`upscaler/pipeline.py:106`) using `█`/`░` and `\r` carriage returns.
- Optional `tqdm` progress bar for sequential segment processing.
- Warnings surfaced as `print(f"WARNING: {warning}")` (e.g. remux stream drops, `upscaler/pipeline.py:486`).
- GUI (`gui.py`) captures subprocess output into a shared `task_state` dict guarded by `task_lock`.

## Comments

**When to Comment:**
- Explain *why*, especially non-obvious pipeline/ffmpeg decisions and platform quirks (e.g. macOS bundle CWD fallback `upscaler/pipeline.py:225`, Cocoa/PyInstaller arg filtering `upscale.py:14`).
- Numbered stage comments narrate the pipeline (`# 1. Probe input`, `# 2. Preset Guard`, ... in `run_single_file`).

**Docstrings:**
- Triple-quoted docstrings on non-trivial public functions describe purpose, return shape, and raise conditions (e.g. `resolve_output_paths`, `estimate_disk_usage`). Google-ish prose, not reStructuredText/Napoleon.
- Exception classes carry one-line docstrings describing the condition.
- Simple guard/getter functions often have no docstring.

## Function Design

**Size:** Small, single-purpose functions preferred. Exception: `run_single_file` (`upscaler/pipeline.py:182`) is a large orchestrator (~320 lines) containing a nested `process_segment` closure.

**Parameters:**
- Type hints on nearly all signatures (params and returns), using `typing` (`Dict`, `List`, `Optional`, `Tuple`, `Any`).
- Options threaded through the pipeline as an `opts: Dict[str, Any]` dict (derived from `vars(argparse.Namespace)`), accessed with `opts["key"]` for required and `opts.get("key", default)` for optional. New CLI flags flow automatically from `upscale.py` into `opts`.
- `tools_info: Dict[str, Any]` similarly carries resolved tool paths/capabilities.

**Return Values:**
- Pure/testable functions return values (command lists, path mappings, `VideoInfo`); side-effecting orchestration returns `None` or an exit-code `int`.
- Command builders return `List[str]` argv lists (never shell strings) — always invoked without `shell=True`.

## Module Design

**Separation of concerns** (key architectural convention):
- `plan.py` — pure validation + path/disk planning (no subprocess execution)
- `ffmpeg_cmds.py` — pure argv builders (no execution), making commands unit-testable
- `pipeline.py` — orchestration + subprocess execution
- `encoders.py` — encoder selection + arg mapping
- `probe.py` / `tools.py` — external tool interaction

**Exports:**
- Only `upscaler/__init__.py` defines `__all__` (the error hierarchy + `__version__`). Other modules rely on direct name imports.

**Barrel Files:** None beyond the package `__init__.py`, which exports only the shared exception types and version.

---

*Convention analysis: 2026-07-02*
