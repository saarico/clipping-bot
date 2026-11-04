"""Makeover release 10 (rico 2026-11-04 05:00, "Frame the big screen"): stage screen shows.

The Weeknd footage is one locked-off stadium shot: a giant screen plays a film above a dark stage where the artist is
a few pixels tall. A synthetic stadium: the top 65% changes picture every second (the screen), the rows below stay
dark and still. The Subject Finder must take the screen as the subject; a spotlit performer on a dark stage (release 6)
must not read as a screen.
"""
import shutil
import subprocess

import pytest

import subject

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture(scope="module")
def stadium(tmp_path_factory):
    d = tmp_path_factory.mktemp("stadium")
    # screen: a test pattern whose hue and position jump every second; stage: dark with a tiny moving figure
    vf = ("geq=lum='if(lt(Y,H*0.65),40+180*mod(floor(T)*37+floor(X/(W/8))*53+floor(Y/(H/6))*29,7)/6,"
          "if(lte(abs(X-W*(0.5+0.05*sin(T))),6)*lte(abs(Y-H*0.8),14),200,12))':cb=128:cr=128")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=25:d=16",
                    "-vf", "format=yuv420p," + vf, "-c:v", "libx264", "-preset", "ultrafast", str(d / "src.mp4")], check=True)
    return d


def test_screen_found_in_a_locked_off_stadium_shot(stadium):
    box = subject.screen(str(stadium / "src.mp4"), 0, 16)
    assert box is not None
    assert box[1] < 0.05 and 0.55 < box[3] < 0.75 and box[2] - box[0] > 0.9, box


def test_pan_takes_the_screen_as_the_subject(stadium):
    p = subject.pan(str(stadium / "src.mp4"), 2, 14)
    assert p and p["kind"] == "screen" and p["cover"] == 1.0
    assert 0.25 < p["cy"] < 0.4


def test_spotlit_performer_is_not_a_screen(tmp_path):
    vf = ("geq=lum='if(lte(pow((X-W*(0.25+0.02*sin(T*3)))/(W*0.05),2)+pow((Y-H*0.45)/(H*0.22),2),1),235,22+6*random(1))':cb=128:cr=128")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=25:d=8",
                    "-vf", "format=yuv420p," + vf, "-c:v", "libx264", "-preset", "ultrafast", str(tmp_path / "s.mp4")], check=True)
    assert subject.screen(str(tmp_path / "s.mp4"), 0, 8) is None
