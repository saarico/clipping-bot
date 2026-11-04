"""Makeover release 5 (board review 3, approved 2026-11-04): fix and sharpen.

Each audit bug that release 5 fixes has a test here that fails on the old code:
  1 picture: windows are cut from a native-resolution master (picture.scale_graph) and match the 1080p framing
  4 encodes: the cover is joined without re-encoding the clip (thumbnail.append_cover)
  5 near: a HELD judge score is never handed over as "under the bar" (pipeline.one_clip "near")
  6 collapsed window: stops before the render (agents/editor.collapsed)
  7 analyst style: kept clips carry their content type (pipeline.decide)
  8 views log: approved clips get posts.csv rows; the VIEWS doc fills views_7d (analyst.log_posts / read_views)
"""
import json
import shutil
import subprocess

import numpy as np
import pytest

import analyst
import picture

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def test_norm_filter_scale_factor():
    assert picture.norm_filter(1920, 1080) == (None, 1.0)
    f, k = picture.norm_filter(3840, 2160)
    assert k == 2.0 and "scale=-2:2160" in f and "pad=3840:2160" in f
    f, k = picture.norm_filter(2560, 1440)
    assert abs(k - 1440 / 1080) < 1e-3
    f, k = picture.norm_filter(7680, 4320)          # 8K is brought down to 4K
    assert k == 2.0
    f, k = picture.norm_filter(3840, 2160, "crop=3840:1600:0:280")   # letterboxed 4K: bars cut, 1600 lines kept
    assert f.startswith("crop=3840:1600:0:280,") and abs(k - 1600 / 1080) < 1e-3


def test_zoom_cap_keeps_real_pixels():
    assert abs(picture.zoom_cap(1.0) - 607.5 / 480) < 1e-6
    assert picture.zoom_cap(2.0) > 2.5
    assert picture.src_px(1.0, 1.0) == 607 and picture.src_px(2.0, 2.0) == 607


def test_scale_graph_multiplies_source_crops_only():
    g = "[0:v]split[a][b];[a]crop=606:1080:'if(lt(t,1.000),100,200)':0,scale=1080:1920[base];" \
        "[b]crop=400:300:1200:80,scale=488:354,pad=500:366:6:6:white[card];[x]scale=-2:1920,crop=1080:1920,boxblur=30:3[bg]"
    out = picture.scale_graph(g, 2.0, "NORM")
    assert out.startswith("[0:v]NORM,split")
    assert "crop=1212:2160:'(if(lt(t,1.000),100,200))*2.0':0" in out
    assert "crop=800:600:2400:160" in out
    assert "crop=1080:1920,boxblur" in out          # the backdrop's crop happens after a scale: untouched
    assert "scale=1080:1920" in out                  # output sizes never change


@needs_ffmpeg
def test_master_window_matches_the_1080p_framing(tmp_path):
    """The same Camera graph on a 4K master and on its 1080p copy frames the same picture (bug 1)."""
    from render_clip import build_filter
    m4k, ep = tmp_path / "m.mp4", tmp_path / "e.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=3840x2160:r=30:d=1",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", str(m4k)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(m4k), "-vf", "scale=1920:1080",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", str(ep)], check=True)
    spec = picture.master_spec(m4k, picture.probe(ep)[2])
    assert spec and spec["k"] == 2.0
    g = build_filter("face", [(0.3, 0.45, 0.2)], 1.2, None, 0, 0)

    def grab(src, graph):
        out = tmp_path / "f.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "0.5", "-i", str(src), "-filter_complex", graph,
                        "-map", "[v]", "-frames:v", "1", str(out)], check=True)
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-vf", "scale=108:192,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).astype(float)

    a, b = grab(ep, g), grab(m4k, picture.scale_graph(g, spec["k"], spec["norm"]))
    assert np.abs(a - b).mean() < 6, "the master's window must show the same part of the picture"


@needs_ffmpeg
def test_cover_join_keeps_the_clip_encode(tmp_path):
    """Bug 4: the cover frames are appended with a stream copy; the clip's own frames are not re-encoded."""
    import thumbnail
    from PIL import Image
    clip, png = tmp_path / "c.mp4", tmp_path / "t.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2", "-f", "lavfi",
                    "-i", "sine=f=440:d=2:r=48000", "-ac", "2", *thumbnail.ENC, "-c:a", "aac", "-b:a", "160k", str(clip)], check=True)
    Image.new("RGB", (1080, 1920), (200, 30, 30)).save(png)

    def first_packets(p):
        return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=size", "-read_intervals",
                               "%+#10", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.split()
    before = first_packets(clip)
    thumbnail.append_cover(clip, png)
    n, _ = thumbnail._frames(clip)
    assert n == 62
    # the first packet may gain the stream's parameter sets in-band (concat); every other packet is the same bytes
    assert first_packets(clip)[1:] == before[1:], "the clip's frames were re-encoded"


def test_collapsed_window_stops_before_render():
    from agents import editor
    with pytest.raises(SystemExit, match="collapsed"):
        editor.collapsed({"parts": [[100.0, 125.0]], "brief": {"min_s": 12}}, [[123.7, 125.0]])
    editor.collapsed({"parts": [[100.0, 125.0]], "brief": {"min_s": 12}}, [[101.0, 124.0]])   # a normal trim passes


def test_decide_keeps_style_and_near_needs_no_hold(tmp_path, monkeypatch):
    import pipeline
    monkeypatch.setattr(pipeline, "REPORT_CARD", tmp_path / "report_card.csv")   # never the repo's data/
    f = tmp_path / "c01"
    f.mkdir()
    res = {"hook": "h", "why": "w", "parts": [[0, 20]], "ok": True, "qa": "PASS", "judge": 85, "fails": [], "dur": 20,
           "folder": str(f), "mp4": str(f / "c01.mp4"), "captions": "", "style": "performance"}
    kept, _ = pipeline.decide([res], tmp_path, [], [])
    assert kept[0]["style"] == "performance"
    held = dict(res, ok=False, judge=79, near=False, held=True, folder=str(f), hook="h2")
    kept, notes = pipeline.decide([held], tmp_path, [], [])
    assert not kept and any(n.startswith("DROP") for n in notes)


def test_views_log_and_views_doc(tmp_path):
    p = tmp_path / "posts.csv"
    p.write_text(",".join(analyst.POST_COLS) + "\n")
    assert analyst.log_posts("Weeknd", [{"clip": "01_the-crowd.mp4", "platform": "tiktok"}, {"clip": "02_duet.mp4"}], path=p) == 2
    assert analyst.log_posts("Weeknd", [{"clip": "01_the-crowd.mp4"}], path=p) == 0      # no duplicates
    assert analyst.read_views("Weeknd", "01 12,400 https://tiktok.com/x\nduet 3.4k\nnothing here", path=p) == 2
    rows = {r["clip"]: r for r in analyst._rows(p)}
    assert rows["01_the-crowd.mp4"]["views_7d"] == "12400" and rows["01_the-crowd.mp4"]["post_url"] == "https://tiktok.com/x"
    assert rows["02_duet.mp4"]["views_7d"] == "3400"
    json.dumps(rows)
