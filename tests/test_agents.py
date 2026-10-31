"""Release 2: the MAKE stage runs as separate agents and every hand-off leaves a contract.

Renders a 12 s synthetic source (test pattern + tone with pauses) end to end through render_clip.py in a
subprocess, the way pipeline.py calls it, then checks each agent's contract in <name>.agents.json.
Byte-identical output vs the old single-function render was proven by frame hashes when the split landed
(2026-10-31); this test keeps the contracts honest from here on.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    d = tmp_path_factory.mktemp("agents")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=12",
                    "-f", "lavfi", "-i", "sine=f=300:d=12,volume='if(lt(mod(t,3),2.4),1,0.01)':eval=frame",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(d / "src.mp4")],
                   check=True)
    vocab = "so the money was gone and nobody knew what happened next".split()
    words, t, i = [], 0.1, 0
    while t < 11.5:
        if t % 3 < 2.3:
            words.append({"text": vocab[i % len(vocab)], "start": round(t, 2), "end": round(t + 0.3, 2)})
            i += 1
        t += 0.4
    (d / "words.json").write_text(json.dumps(words))
    spec = {"source": str(d / "src.mp4"), "words": str(d / "words.json"), "style": "podcast",
            "hook": "HE LOST ALL THE MONEY IN ONE NIGHT", "tag": "host of a show", "emphasis": ["money"],
            "parts": [[1.0, 10.5]], "callouts": [{"from": 6.0, "to": 8.0, "text": "$1,000,000"}],
            "out": str(d / "clip.mp4")}
    (d / "spec.json").write_text(json.dumps(spec))
    r = subprocess.run([sys.executable, str(ROOT / "bot" / "render_clip.py"), str(d / "spec.json")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    return d, json.loads((d / "clip.agents.json").read_text())


def test_every_agent_left_its_contract(rendered):
    d, c = rendered
    assert set(c) == {"edits", "frame", "audio", "cards", "captions", "clip"}
    assert (d / "clip.mp4").stat().st_size > 0
    assert (d / "clip.ass").exists() and (d / "clip.layout.json").exists()


def test_editor_pieces_are_whole_frames_and_back_to_back(rendered):
    _, c = rendered
    off = 0
    for s, e, o in c["edits"]["pieces"]:
        assert abs((e - s) * FPS - round((e - s) * FPS)) < 1e-6
        assert abs(o - off) < 1e-6
        off += e - s
    assert abs(off - c["clip"]["total"]) < 0.05


def test_camera_covers_the_whole_clip_without_gaps(rendered):
    d, c = rendered
    fr = c["frame"]
    assert fr and fr[0]["from"] == 0
    for a, b in zip(fr, fr[1:]):
        assert abs(a["to"] - b["from"]) < 0.002
    assert abs(fr[-1]["to"] - c["clip"]["total"]) < 0.05
    shots = json.loads((d / "clip.layout.json").read_text())["shots"]
    assert len(shots) == len(fr)


def test_sound_and_cards(rendered):
    _, c = rendered
    assert c["audio"]["mode"] == "loudnorm"           # podcast profile: linear loudnorm, not plain gain
    assert c["cards"]["callouts"][0]["text"] == "$1,000,000"
    assert c["cards"]["watermark"] is None


def test_captions_contract_feeds_the_layout_inspector(rendered):
    import studio
    d, _ = rendered
    lay = studio.layout_check(d / "clip.ass")
    assert lay["fails"] == [], lay
