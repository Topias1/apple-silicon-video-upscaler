# Testing Patterns

**Analysis Date:** 2026-07-02

## Test Framework

**Runner:**
- `pytest` (listed in `requirements.txt`; `.pytest_cache/` present)
- No `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, or `conftest.py` — pytest runs with default configuration and auto-discovery.

**Assertion Library:**
- Plain `assert` statements (pytest rewriting). No separate assertion lib.

**Mocking:**
- `unittest.mock` (`patch`, `MagicMock`) from the standard library.

**Run Commands:**
```bash
pytest                          # Run all tests (unit + slow integration)
pytest tests/test_plan.py       # Run one module
pytest -k "preset"              # Run tests matching an expression
pytest -m "not slow"            # Skip slow integration tests (see marker note below)
```

> Note: The `slow` marker used by `tests/test_integration.py` is **not registered** in any config file, so pytest emits an "unknown marker" warning. Register it in a config file if `-m` filtering becomes important.

## Test File Organization

**Location:**
- Separate `tests/` directory at repo root (not co-located with source).

**Naming:**
- `test_<module>.py` mirrors `upscaler/<module>.py`:
  - `tests/test_plan.py`, `tests/test_probe.py`, `tests/test_encoders.py`, `tests/test_ffmpeg_cmds.py`, `tests/test_batch.py`
  - `tests/test_integration.py` — end-to-end runs
- Test functions: `test_<behavior>` describing the scenario, e.g. `test_check_preset_guard`, `test_resolve_output_paths_collision_raises`, `test_build_extract_cmd_hdr_tonemap`.

**Structure:**
```
tests/
├── test_plan.py            # pure validation / path resolution
├── test_probe.py           # ffprobe JSON parsing (subprocess mocked)
├── test_encoders.py        # encoder selection + arg mapping
├── test_ffmpeg_cmds.py     # argv command builders (pure)
├── test_batch.py           # discovery + batch orchestration (deps mocked)
├── test_integration.py     # real ffmpeg + stubbed realesrgan, marked slow
└── stub_realesrgan.py      # fake Real-ESRGAN binary used by integration tests
```

## Test Structure

**Suite Organization:**
- Flat functions, no test classes. One assertion cluster per function, often multiple related cases per test.
```python
def test_get_target_height():
    assert get_target_height("480p") == 480
    assert get_target_height("4k") == 2160
    with pytest.raises(ValueError):
        get_target_height("invalid")
```

**Patterns:**
- Setup via pytest's built-in `tmp_path` fixture for any filesystem work — no manual temp-dir management or teardown.
- Error-path testing with `pytest.raises`, frequently asserting on message substrings:
```python
with pytest.raises(ValueError) as exc:
    resolve_output_paths(inputs, "/custom/output.mp4", None, "1080p")
assert "can only be used when upscaling a single file" in str(exc.value)
```

## Mocking

**Framework:** `unittest.mock` (`patch`, `MagicMock`).

**Two mocking styles are used:**

1. Patch the stdlib call directly (probe tests mock `subprocess.run` and feed canned ffprobe JSON):
```python
@patch("subprocess.run")
def test_probe_video_sdr_cfr(mock_run):
    mock_res = MagicMock()
    mock_res.stdout = json.dumps(mock_data)
    mock_res.returncode = 0
    mock_run.return_value = mock_res
    info = probe_video("dummy.mp4")
    assert info.width == 1920
```

2. Patch collaborators *where they are imported* (batch tests isolate orchestration from real work):
```python
@patch("upscaler.batch.run_single_file")
@patch("upscaler.batch.probe_video")
@patch("upscaler.batch.discover_inputs")
def test_run_batch_skip_existing(mock_discover, mock_probe, mock_run_single, tmp_path):
    ...
    mock_run_single.assert_called_once_with(infile2, outfile2, opts, tools_info)
```
> Decorator patches are passed as args in bottom-up order.

**What to Mock:**
- External binaries (`ffprobe`/`ffmpeg`) via `subprocess.run` in unit tests.
- Cross-module collaborators in orchestration tests (`run_single_file`, `probe_video`, `discover_inputs`), patched at the `upscaler.batch.*` namespace where they're used.

**What NOT to Mock:**
- Pure functions — `plan.py`, `ffmpeg_cmds.py`, `encoders.py` are tested directly with real inputs (no mocks needed), since they only compute values / argv lists.
- The real filesystem — use `tmp_path` instead of mocking `os`.

## Fixtures and Factories

**Test Data:**
- Local `@pytest.fixture` definitions inside the test module that needs them (no shared `conftest.py`). Example — a real 2-second clip generated with ffmpeg for integration:
```python
@pytest.fixture
def test_clip(tmp_path):
    clip_path = tmp_path / "src_clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                    "-i", "testsrc=duration=2:size=320x240:rate=24", ...], check=True)
    return str(clip_path)
```
- ffprobe JSON responses are inline Python dicts serialized with `json.dumps` (see `tests/test_probe.py`).

**Real-ESRGAN stub:**
- `tests/stub_realesrgan.py` — a fake upscaler binary passed via `--realesrgan-bin` so integration tests exercise the full pipeline without a GPU or the real Vulkan binary.

**Location:**
- Fixtures and stubs live inside `tests/`. No central fixture module.

## Coverage

**Requirements:** None enforced. No coverage tool configured (`coverage`/`pytest-cov` not in `requirements.txt`).

**Effective coverage by design:**
- Pure logic layers (`plan`, `ffmpeg_cmds`, `encoders`, `probe` parsing, `batch` discovery) have direct unit tests.
- `pipeline.run_single_file` is exercised only end-to-end via integration tests, not unit tested directly.

## Test Types

**Unit Tests:**
- `test_plan.py`, `test_ffmpeg_cmds.py`, `test_encoders.py` — pure functions, no I/O, no mocks.
- `test_probe.py` — parsing logic with `subprocess.run` mocked.
- `test_batch.py` — discovery against `tmp_path`; orchestration with collaborators patched.

**Integration Tests:**
- `tests/test_integration.py` — runs the real CLI via `subprocess.run([sys.executable, "upscale.py", ...])`, uses real ffmpeg to generate/probe clips and the `stub_realesrgan.py` stand-in. Asserts on exit codes, output existence, and probed dimensions/duration/audio.
- Marked `pytestmark = pytest.mark.slow`. Requires `ffmpeg`/`ffprobe` on `PATH`.

**E2E Tests:**
- The integration suite is the E2E layer (drives the CLI as a subprocess). No browser/GUI (`gui.py`) automated tests.

## Common Patterns

**Subprocess / CLI Testing:**
```python
res = subprocess.run(cmd, capture_output=True, text=True)
assert res.returncode == 0, f"Upscaler failed: {res.stderr}\nStdout: {res.stdout}"
```

**Error / Exit-code Testing:**
```python
res = subprocess.run(cmd_run, capture_output=True, text=True)
assert res.returncode == 1
assert "PresetGuardError" in res.stderr or "already greater than or equal" in (res.stdout + res.stderr)
```

**Resume/idempotency Testing:**
- Run the batch, capture `st_mtime`, re-run, assert the output file's mtime is unchanged to prove completed work is skipped (`test_integration_batch_resume`).

**Custom-exception Testing:**
```python
from upscaler import PresetGuardError
with pytest.raises(PresetGuardError):
    check_preset_guard(1080, "1080p")
```

---

*Testing analysis: 2026-07-02*
