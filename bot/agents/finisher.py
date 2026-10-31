"""Finisher: puts the picture, captions, watermark and sound together into the clip.

In:  video.mp4 (Camera), audio.m4a (Sound), captions.ass (Captions), cards.json (Graphics: watermark, end hold).
Out: clip.mp4 at spec["out"] and <name>.layout.json {cuts, shots} for qa_check.py / judge_clip.py.
"""
import json
from pathlib import Path

from render_clip import FONTS_DIR, WM_W, WM_X, WM_Y, run


def assemble(spec, cards, ranges, layouts, total, tmp):
    wm = cards["watermark"]
    pre = ""
    if spec.get("hold_end_from"):
        # the show cuts away (wipe, wide shot) under the last words: hold the speaker's last
        # clean frame and fade the picture out; captions stay live on top
        h = spec["hold_end_from"]
        pre = (f"trim=end={h:.3f},setpts=PTS-STARTPTS,tpad=stop_duration={total - h + 0.1:.3f}:stop_mode=clone,"
               f"fade=out:st={h - 0.1:.3f}:d={total - h + 0.1:.3f},")
    vf = f"{pre}ass={tmp / 'caps.ass'}:fontsdir={FONTS_DIR}"
    ins = ["-i", str(tmp / "video.mp4"), "-i", str(tmp / "audio.m4a")]
    if wm:   # the required watermark on top of everything, the whole clip (the brief: big, readable, never covered)
        ins += ["-i", wm]
        vargs = ["-filter_complex", f"[0:v]{vf}[base];[2:v]format=rgba,scale={WM_W}:-2[wm];[base][wm]overlay={WM_X}:{WM_Y}[v]", "-map", "[v]"]
    else:
        vargs = ["-vf", vf, "-map", "0:v"]
    run(["ffmpeg", "-loglevel", "error", "-y", *ins, *vargs, "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart",
         spec["out"]])
    Path(spec["out"]).with_suffix(".layout.json").write_text(json.dumps(
        {"cuts": ranges, "shots": [{"from": round(a, 2), "to": round(b, 2), "layout": l}
                                   for a, b, l in layouts]}, indent=1))
