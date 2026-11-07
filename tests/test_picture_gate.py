"""rico 2026-11-07: "why does it look 140p". The 3.1.0 Weeknd clip passed QA on crop arithmetic (480 source px) while
the delivered picture was a blurred view of a stadium screen (detail score 22). QA "Picture detail" now measures the
delivered frames and FAILs a blurry picture."""
import shutil
import subprocess

import pytest

import qa_check

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def _clip(path, vf):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
                    "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", str(path)],
                   check=True)


def _row(tmp_path, name, vf):
    _clip(tmp_path / name, vf)
    rep = qa_check.Report()
    qa_check.check_picture_detail(rep, tmp_path / name, tmp_path)
    return [r for r in rep.rows if r[0] == "Picture detail"][0]


def test_blurry_picture_fails(tmp_path):
    row = _row(tmp_path, "soft.mp4", "scale=160:284,scale=1080:1920,gblur=sigma=6")
    assert row[1] == "FAIL", row


def test_sharp_picture_passes(tmp_path):
    row = _row(tmp_path, "sharp.mp4", "null")
    assert row[1] == "PASS", row
