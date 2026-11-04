"""Makeover release 8 (board review 3, approved 2026-11-04): text look v2, one look per kind of content."""
import shutil

import pytest

import profiles
import render_clip as rc


def test_each_content_type_has_its_own_look():
    assert profiles.look("podcast")["kind"] == "pill"
    assert profiles.look("stream")["kind"] == "pop"
    assert profiles.look("performance")["kind"] == "minimal"
    assert profiles.look("podcast", {"style": "classic"})["cap_font"] == "Montserrat Black"   # the old look on request


def test_campaign_overrides_and_accent_names():
    lk = profiles.look("podcast", {"style": "pop", "accent": "cyan", "cap_size": 90})
    assert lk["kind"] == "pop" and lk["accent"] == profiles.ACCENTS["cyan"] and lk["cap_size"] == 90
    pill = profiles.look("podcast", {"accent": "pink"})
    assert pill["hook_box"] == "&H00" + profiles.ACCENTS["pink"][2:8]      # the hook's box takes the accent
    assert profiles.look("podcast", {"style": "nonsense"})["kind"] == "classic"   # never kills a render


def test_classic_styles_are_unchanged():
    lk = profiles.look("podcast", {"style": "classic"})
    cap = rc.ass_styles(lk).splitlines()[0]
    assert cap == ("Style: Cap,Montserrat Black,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,7,2,5,70,70,0,1")


def test_pill_draws_a_box_behind_captions():
    cap, hook, _ = rc.ass_styles(profiles.look("podcast")).splitlines()
    assert cap.split(",")[15] == "3" and hook.split(",")[15] == "3"     # BorderStyle 3: opaque box


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_look_sheet_renders_twelve_tiles(tmp_path):
    import subprocess

    import looks
    from PIL import Image
    frame = tmp_path / "f.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080", "-frames:v", "1", str(frame)], check=True)
    out = looks.sheet(frame, tmp_path / "sheet.png")
    im = Image.open(out)
    assert im.size[0] > 1600 and im.size[1] > 1000 and len(looks.GRID) == 12
