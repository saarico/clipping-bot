"""Makeover release 6 (board review 3, approved 2026-11-04): the camera stays on the subject.

A synthetic "stage": a dark picture with one lit, moving performer on the left third and nobody else. Before release 6
no face over 2.5% of the width meant the window sat on the middle of the picture; the Subject Finder follows the
light, and the QA "Subject in crop" row reads the Camera's record of it.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import subject

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture(scope="module")
def stage(tmp_path_factory):
    d = tmp_path_factory.mktemp("stage")
    # a spotlit performer (bright ellipse, swaying) at ~25% of the width on a dark, slightly noisy stage
    vf = ("geq=lum='if(lte(pow((X-W*(0.25+0.02*sin(T*3)))/(W*0.05),2)+pow((Y-H*0.45)/(H*0.22),2),1),235,22+6*random(1))':cb=128:cr=128")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30:d=12",
                    "-f", "lavfi", "-i", "sine=f=220:d=12", "-vf", "format=yuv420p," + vf, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                    str(d / "src.mp4")], check=True)
    (d / "words.json").write_text("[]")
    return d


def test_subject_finder_follows_the_lit_performer(stage):
    p = subject.pan(str(stage / "src.mp4"), 2.0, 6.0)
    assert p is not None
    assert all(0.15 < cx < 0.36 for _, cx in p["keys"]), p["keys"]


def test_cover_reads_frame_records():
    fr = [{"from": 0, "to": 6, "layout": "face", "face": [0.3, 0.4, 0.05], "subject": 1.0},
          {"from": 6, "to": 10, "layout": "wide", "face": None, "subject": 0.0}]
    assert abs(subject.cover(fr) - 0.6) < 1e-6
    assert subject.cover([{"from": 0, "to": 4, "layout": "face", "face": [0.5, 0.4, 0.2]}]) == 1.0   # podcast records


def test_stage_clip_frames_the_performer_not_the_middle(stage):
    spec = {"source": str(stage / "src.mp4"), "words": str(stage / "words.json"), "style": "performance", "music": {"x": 1},
            "hook": "HONG KONG SANG EVERY WORD", "parts": [[1.0, 11.0]], "tighten": False, "out": str(stage / "clip.mp4")}
    (stage / "spec.json").write_text(json.dumps(spec))
    r = subprocess.run([sys.executable, str(ROOT / "bot" / "render_clip.py"), str(stage / "spec.json")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    frames = json.loads((stage / "clip.agents.json").read_text())["frame"]
    assert frames and all(f["layout"] == "face" and f["face"] and f["face"][0] < 0.4 for f in frames), frames
    assert all(f.get("subject") is not None for f in frames)
