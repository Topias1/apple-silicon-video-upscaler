# Codebase Concerns

**Analysis Date:** 2026-07-02

## Tech Debt

**Inconsistent tool-path resolution (`"ffmpeg"` hardcoded vs. resolved path):**
- Issue: `verify_tools()` carefully resolves `ffmpeg`/`ffprobe` via `shutil.which()` and returns `tools_info["ffmpeg_path"]`, but the command builders and one probe helper ignore it and hardcode the bare string `"ffmpeg"`.
- Files: `upscaler/ffmpeg_cmds.py` (lines 16, 49, 124, 144, 165), `upscaler/probe.py` (`detect_video_type`, lines 183, 197). `ffprobe` is resolved correctly via `get_ffprobe_path()`, so the two binaries are handled differently.
- Impact: In a double-clicked PyInstaller `.app` bundle the process `PATH` frequently omits `/opt/homebrew/bin`, so `ffmpeg` invocations fail with `FileNotFoundError` even though `tools_info` holds a valid absolute path. Any environment where ffmpeg is not on the child process PATH breaks silently at the split/extract/encode stage.
- Fix approach: Thread `tools_info["ffmpeg_path"]` into every `build_*_cmd` in `ffmpeg_cmds.py` and into `detect_video_type`, replacing the literal `"ffmpeg"`. Prefer absolute paths everywhere the subprocess is spawned.

**Argparse arg-filtering hack for macOS/PyInstaller:**
- Issue: `upscale.py` (lines 14-16) strips `-B -S -I -c` and `-psn_*` from `argv` to survive Cocoa/PyInstaller-injected flags. This is a fragile denylist; a legitimate future flag colliding with these single letters would be silently dropped.
- Files: `upscale.py:14-16`.
- Impact: Low today, but brittle. Any new short option must avoid these letters.
- Fix approach: Detect frozen/bundled execution explicitly (`getattr(sys, "frozen", False)`) and filter only in that context, or route GUI invocations through a dedicated entrypoint that never passes these flags.

**Large inline HTML/CSS/JS blob inside `gui.py`:**
- Issue: `gui.py` is 1015 lines; `HTML_CONTENT` (starts line 262) is a single ~750-line triple-quoted string mixing markup, OKLCH CSS, and client JS.
- Files: `gui.py:262`+.
- Impact: No syntax highlighting, no linting, hard to diff, easy to introduce unclosed-brace bugs. Frontend and server logic are coupled in one module.
- Fix approach: Extract to a static `templates/index.html` served from disk (with a `sys._MEIPASS` fallback identical to the existing `/logo.jpg` handler at lines 145-160).

## Known Bugs

**Manifest resume ignores `interpolate_fps` and `temporal_denoise`:**
- Symptoms: Resuming an interrupted run in the same work directory with different `--interpolate-fps` or `--temporal-denoise` settings reuses previously encoded segments without detecting the mismatch, producing an output that mixes settings.
- Files: `upscaler/pipeline.py:244-253` (`resolved_params` dict) and `load_or_create_manifest` (lines 131-176), which only raises `ManifestMismatchError` for keys present in `resolved_params`.
- Trigger: Run, cancel mid-way, re-run with `--interpolate-fps 60` or `--temporal-denoise` toggled, same/derived work dir.
- Workaround: Use a fresh `--work-dir` or delete `manifest.json` when changing interpolation/denoise. Real fix: add `interpolate_fps` and `temporal_denoise` to `resolved_params`.

**Batch skip-if-output-exists ignores production parameters:**
- Symptoms: `run_batch` skips any input whose target output already exists and has `frame_count > 0`, regardless of the preset/model/quality used to produce it.
- Files: `upscaler/batch.py:88-102`.
- Trigger: Re-run a batch at a different `--preset` or `--quality` into a directory that already contains prior outputs — the files are silently skipped instead of re-encoded.
- Workaround: Delete or relocate prior outputs before re-running at new settings.

**Cancel leaves orphaned ffmpeg/realesrgan grandchildren:**
- Symptoms: The GUI `/cancel` endpoint calls `active_process.terminate()` on the `python upscale.py` child only. The ffmpeg and realesrgan subprocesses that `upscale.py` spawns are not in a killed process group and keep running (GPU/CPU stays pinned after "cancel").
- Files: `gui.py:130-143` (cancel handler), `gui.py:49-56` (Popen with no `start_new_session`/process group), grandchildren spawned in `upscaler/pipeline.py` (`run_cmd_checked`, `run_realesrgan_stream`).
- Trigger: Start an upscale via GUI, click cancel during a segment.
- Workaround: None from UI. Fix: launch the child with `start_new_session=True` and on cancel kill the whole process group (`os.killpg`).

## Security Considerations

**Local HTTP server exposes filesystem browsing without auth:**
- Risk: `/explore?path=...` lists any directory on the machine (`os.path.abspath(path_param)`), and `/upscale` starts a subprocess with user-supplied `input_file`/`output_file` paths. No authentication or CSRF token.
- Files: `gui.py:162-206` (`/explore`), `gui.py:211-260` (`/upscale`), bind at `gui.py:1003` (`HTTPServer(("127.0.0.1", 8080), ...)`).
- Current mitigation: Bound to `127.0.0.1` only, so not reachable off-host. Subprocess args are passed as a list (no shell), so no shell-injection.
- Recommendations: Keep the loopback bind. Add a same-origin/CSRF check (any local process or malicious webpage via DNS-rebinding could POST to `127.0.0.1:8080`). Consider constraining `/explore` to a root directory.

**Broad exception swallowing hides failures:**
- Risk: Numerous `except Exception: pass` / bare fallbacks silently mask real errors (corrupt manifest, failed frame counts, probe failures downgraded to `"cinema"`).
- Files: `upscaler/pipeline.py:47-48, 107-108, 325-326`; `upscaler/probe.py:136-137, 206-207, 222-228`; `upscaler/batch.py:96-97`; `app.py:35`.
- Current mitigation: Reconciliation checks downstream catch some inconsistencies.
- Recommendations: Narrow the caught exception types and log the swallowed error at least to stderr.

## Performance Bottlenecks

**GPU stage is globally serialized, capping `--workers` benefit:**
- Problem: `--workers > 1` parallelizes segment processing via `ThreadPoolExecutor`, but the Real-ESRGAN call is wrapped in a single `gpu_lock`, so only one segment can be on the GPU at a time.
- Files: `upscaler/pipeline.py:300-302` (`gpu_lock`), `370-379` (lock around `run_realesrgan_stream`), `431-437` (executor).
- Cause: Intentional — concurrent Vulkan invocations deadlock on Apple Silicon (see commit `77fa237`). The upscale step is the dominant cost, so wall-clock gain from workers is limited to overlapping ffmpeg extract/encode with one GPU job.
- Improvement path: Document that `--workers` mainly overlaps CPU (extract/encode) with the single GPU stage; consider a dedicated pipeline (producer/consumer) rather than N symmetric workers to make the overlap explicit.

**Threaded I/O reads subprocess output one byte at a time:**
- Problem: Both `run_realesrgan_stream` (`upscaler/pipeline.py:91-93`) and the GUI log pump (`gui.py:59-64`) call `.read(1)` in a loop to catch `\r` progress updates.
- Files: `upscaler/pipeline.py:79-129`, `gui.py:58-91`.
- Cause: Progress bars use `\r` without newlines, so line-buffered reads miss them.
- Improvement path: Read in larger chunks and split on `\r`/`\n`, or use a small buffered reader. Low priority (I/O bound by the encode/upscale, not the parse).

## Fragile Areas

**Frame-count reconciliation across split → extract → upscale → encode:**
- Files: `upscaler/pipeline.py:344-413` (three `ReconciliationError` checks) plus `get_exact_frame_count` (lines 30-55).
- Why fragile: Correctness hinges on exact PNG counts matching probed packet counts. Open-GOP seeking, VFR sources, or ffmpeg version differences in `-fps_mode` behavior can throw counts off and abort the run. `count_packets` and `nb_frames` can disagree across containers.
- Safe modification: Never change extract/encode filter chains in `ffmpeg_cmds.py` without re-verifying all three reconciliation gates. Test against VFR and open-GOP samples.
- Test coverage: `tests/test_integration.py` (4 tests) exercises the real binary path via `tests/stub_realesrgan.py`; the per-stage reconciliation branches are not directly unit-tested.

**Content-type auto-detection heuristic:**
- Files: `upscaler/probe.py:172-230` (`detect_video_type`) — extracts one frame at t=1s, downscales to 64x64, thresholds unique colors `<= 800` to decide animation vs. cinema.
- Why fragile: A hardcoded magic threshold on a single frame; dark/low-color live-action intros or colorful animation can be misclassified, silently selecting the wrong model.
- Safe modification: Expose the threshold or sample multiple frames; log the color count that drove the decision.

## Scaling Limits

**Single global GUI task:**
- Current capacity: One upscale task at a time; `task_state` and `active_process` are module-level globals.
- Files: `gui.py:9-19`.
- Limit: Multiple browser tabs share the same state; a second `/upscale` POST is rejected while one runs (`gui.py:213-219`). No queue.
- Scaling path: Introduce a task registry keyed by job id if concurrent jobs are ever needed.

**Hardcoded port 8080:**
- Files: `gui.py:1003`.
- Limit: Startup fails if 8080 is occupied; no retry/fallback port.
- Scaling path: Try a range of ports or accept `PORT` env var and print the chosen URL.

## Dependencies at Risk

**Undeclared runtime dependencies on external binaries:**
- Risk: `requirements.txt` lists only `tqdm`, `pytest`, `Pillow`. The core runtime depends on `ffmpeg`/`ffprobe` (>= 5.1) and `realesrgan-ncnn-vulkan` (or Upscayl's `upscayl-bin`), none of which are captured by pip.
- Impact: Fresh environments appear "installed" but fail at `verify_tools()`.
- Migration plan: Document required system binaries in `README.md`/install docs and keep the actionable install hints in `upscaler/tools.py:106-117`.

**Hardcoded Upscayl path:**
- Risk: `gui.py:242` hardcodes `/Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin`.
- Impact: GUI silently picks Upscayl if present at that exact path, else falls back; a moved/renamed install is not found.
- Migration plan: Make the Upscayl path configurable or discover it more robustly.

## Missing Critical Features

**No continuous integration / linting / formatting:**
- Problem: No CI workflow, no `.eslintrc`/`ruff`/`black`/`flake8` config, no pre-commit. Tests exist (`tests/`, 36 test functions) but are run manually.
- Blocks: Regressions (e.g. the `"ffmpeg"` path issue) are not caught automatically; style drift across modules.

**No packaging of external binaries into the `.app`:**
- Problem: `AppleSiliconVideoUpscaler.spec` bundles `upscale.py`, `upscaler/`, `gui.py`, `logo.jpg` but no ffmpeg/realesrgan binaries (`binaries=[]`). The shipped app still depends on system-installed tools resolvable on PATH.
- Blocks: A distributed `.app` will not run on a machine without Homebrew ffmpeg + realesrgan on PATH — combined with the hardcoded-`"ffmpeg"` issue above, this is the most likely field failure.

## Test Coverage Gaps

**GUI server untested:**
- What's not tested: `gui.py` HTTP handlers (`/upscale`, `/explore`, `/cancel`, `/status`), the log/progress parser, and subprocess launch logic.
- Files: `gui.py` (entire module).
- Risk: Command-assembly bugs (`cmd_args` construction, lines 234-251), progress parsing, and cancel behavior can break with no test signal.
- Priority: Medium.

**CLI entrypoint and pipeline orchestration untested:**
- What's not tested: `upscale.py:main` (argparse, arg-filtering hack, encoder resolution) and `upscaler/pipeline.py` per-stage branches (manifest resume, reconciliation error paths, parallel worker path).
- Files: `upscale.py`, `upscaler/pipeline.py`.
- Risk: The most complex logic (manifest resume mismatch, frame reconciliation, worker parallelism/`gpu_lock`) is only indirectly covered by `tests/test_integration.py`.
- Priority: High.

**Well-covered modules (for reference):**
- `upscaler/plan.py` (`tests/test_plan.py`, 10), `upscaler/ffmpeg_cmds.py` (`tests/test_ffmpeg_cmds.py`, 10), `upscaler/probe.py` (`tests/test_probe.py`, 5), `upscaler/encoders.py` (`tests/test_encoders.py`, 4), `upscaler/batch.py` (`tests/test_batch.py`, 3).

---

*Concerns audit: 2026-07-02*
