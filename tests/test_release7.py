"""Makeover release 7 (board review 3, approved 2026-11-04): the creative studio.

A synthetic 60 s "concert": a crowd with phone lights (0-20 s), a spotlit performer (20-40 s), a light show (40-60 s),
over a 120 BPM beat. The Visual Tagger must tell them apart, the beat tracker must find the beat, and the Creative
Director must brainstorm a song-bed concept whose cutaways land on beats, outside the song's own window, and render.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import director
import montage
import tagger

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture(scope="module")
def show(tmp_path_factory):
    d = tmp_path_factory.mktemp("show")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=100:d=0.05,apad=pad_dur=0.45", "-t", "0.5",
                    str(d / "beat.wav")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "119", "-i", str(d / "beat.wav"), "-f", "lavfi", "-i",
                    "sine=f=440:d=60", "-filter_complex", "[0:a][1:a]amix=inputs=2:weights='3 0.3'", "-t", "60", str(d / "song.wav")], check=True)
    w, h, fps = 640, 360, 30
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                          "-i", str(d / "song.wav"), "-vf", "scale=1920:1080", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                          "-c:a", "aac", "-shortest", str(d / "show.mp4")], stdin=subprocess.PIPE)
    rng = np.random.default_rng(1)
    yy, xx = np.mgrid[0:h, 0:w]
    for i in range(60 * fps):
        t = i / fps
        f = np.full((h, w, 3), 20, np.uint8)
        if t < 20:
            f[:] = 35
            f[rng.integers(h // 2, h, 300), rng.integers(0, w, 300)] = 255
        elif t < 40:
            cx = w * (0.3 + 0.03 * np.sin(t * 2))
            f[((xx - cx) / (w * 0.05)) ** 2 + ((yy - h * 0.45) / (h * 0.22)) ** 2 <= 1] = 230
        else:
            f[:] = (0, 40, 255) if int(t * 2) % 2 == 0 else (30, 30, 30)
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
    (d / "words.json").write_text("[]")
    return d


def test_beats_at_120_bpm(show):
    b = montage.beats(str(show / "song.wav"), 10, 30)
    assert len(b) >= 35
    assert np.allclose(np.diff(b), 0.5, atol=0.03)


def test_tagger_tells_crowd_performer_and_lights_apart(show):
    t = tagger.tag_windows(str(show / "show.mp4"), [(5, 10), (25, 30), (45, 50)])
    crowd, stage, lights = (tagger.summary(t[k]) for k in ((5, 10), (25, 30), (45, 50)))
    assert crowd["crowd"] > 0.8 and stage["crowd"] == 0 and lights["lights"] > 0.3


def test_director_brainstorms_a_song_bed_and_it_renders(show, tmp_path):
    spec = {"source": str(show / "show.mp4"), "words": str(show / "words.json"), "parts": [[22.0, 38.0]], "hook": "HONG KONG SANG",
            "music": {"score": 50}, "style": "performance", "tighten": False, "out": str(tmp_path / "c.mp4"), "_why": "music 50"}
    out, notes = director.brainstorm([spec], str(show / "show.mp4"), {"style": "performance"}, tmp_path)
    assert notes[0].startswith("Creative Director: 2 concept(s)")
    sb = next(s for s in out if s.get("concept") == "song-bed")
    swaps = sb["video_swap"]
    assert len(swaps) >= 2 and all(not (22 <= s[2] <= 38) for s in swaps)
    assert sum(s[1] - s[0] for s in swaps) <= montage.MAX_SHARE * 16 + 0.01
    beats = montage.beats(str(show / "show.mp4"), 22, 38)
    assert all(min(abs(s[0] - b) for b in beats) < 0.05 for s in swaps)
    (tmp_path / "sb.json").write_text(json.dumps(sb))
    r = subprocess.run([sys.executable, str(ROOT / "bot" / "render_clip.py"), str(tmp_path / "sb.json")], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-600:]
    fr = json.loads(Path(sb["out"]).with_suffix(".agents.json").read_text())["frame"]
    assert sum(1 for f in fr if f["src"] < 22 or f["src"] > 38) >= 2     # the cutaways are on screen
