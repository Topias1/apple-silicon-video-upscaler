"""Interlaced sources must be woven back before upscaling.

An interlaced frame holds two half-pictures captured at different instants.
Upscaling it as-is magnifies the comb into thick stripes: the output comes out
worse than the input, on exactly the VHS and DV captures this app exists for.

Measured on a synthetic interlaced clip: extraction used to hand the upscaler
50 combed frames out of 50 (ffmpeg's idet reported TFF:50, Progressive:0).
"""
import subprocess
import re

import pytest

from upscaler.ffmpeg_cmds import build_extract_cmd
from upscaler.tools import get_ffmpeg_path


def make_interlaced(tmp_path, seconds=1, size="720x576", rate=50):
    src = tmp_path / "src.mp4"
    subprocess.run(
        [get_ffmpeg_path(), "-y", "-f", "lavfi",
         "-i", f"testsrc=duration={seconds}:size={size}:rate={rate}",
         "-vf", "interlace=scan=tff", "-c:v", "libx264",
         "-flags", "+ilme+ildct", "-top", "1", "-pix_fmt", "yuv420p", str(src)],
        capture_output=True, check=True)
    return str(src)


def idet_counts(png_dir, rate=50):
    """ffmpeg's own interlace detector, over the extracted frames."""
    res = subprocess.run(
        [get_ffmpeg_path(), "-framerate", str(rate),
         "-i", f"{png_dir}/f_%08d.png", "-vf", "idet", "-f", "null", "-"],
        capture_output=True, text=True)
    line = [l for l in res.stderr.splitlines() if "Multi frame detection" in l]
    if not line:
        return None
    m = re.search(r"TFF:\s*(\d+)\s*BFF:\s*(\d+)\s*Progressive:\s*(\d+)", line[-1])
    return {"tff": int(m.group(1)), "bff": int(m.group(2)),
            "progressive": int(m.group(3))}


def extract(src, out_dir, is_interlaced):
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        build_extract_cmd(src, str(out_dir), "50/1", False, "tonemap",
                          False, "cfr", is_interlaced=is_interlaced),
        capture_output=True, check=True)
    return sorted(out_dir.glob("*.png"))


def test_deinterlacing_removes_the_comb(tmp_path):
    src = make_interlaced(tmp_path)
    frames = extract(src, tmp_path / "out", is_interlaced=True)
    counts = idet_counts(str(tmp_path / "out"))
    assert counts is not None
    # Nearly every frame should read as progressive once woven back.
    assert counts["progressive"] > counts["tff"] + counts["bff"]


def test_without_the_flag_the_comb_reaches_the_upscaler(tmp_path):
    """Guards the regression: this is what the pipeline used to do."""
    src = make_interlaced(tmp_path)
    extract(src, tmp_path / "out", is_interlaced=False)
    counts = idet_counts(str(tmp_path / "out"))
    assert counts["tff"] + counts["bff"] > counts["progressive"]


def test_frame_count_is_preserved(tmp_path):
    """send_frame keeps one output per input, so reconciliation still holds."""
    src = make_interlaced(tmp_path)
    plain = extract(src, tmp_path / "plain", is_interlaced=False)
    woven = extract(src, tmp_path / "woven", is_interlaced=True)
    assert len(woven) == len(plain)


def test_filter_is_absent_on_progressive_sources():
    cmd = build_extract_cmd("in.mkv", "/tmp/x", "25/1", False, "tonemap",
                            False, "cfr", is_interlaced=False)
    assert "bwdif" not in " ".join(cmd)


def test_deinterlace_runs_before_the_other_filters():
    """Fields must be woven before any resampling or tonemapping touches them."""
    cmd = build_extract_cmd("in.mkv", "/tmp/x", "25/1", True, "tonemap",
                            True, "cfr", is_interlaced=True)
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.index("bwdif") < vf.index("fps=")
    assert vf.index("bwdif") < vf.index("tonemap")
