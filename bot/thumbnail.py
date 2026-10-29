"""Thumbnail for an approved clip (rico, 2026-10-29: "make sure it's really good", then "the one you made is very
creepy, no one would want to watch that, also the text is bad"; RULES.md 20): a frame from the episode itself (outside
images are banned by the briefs), chosen for a face people want to click on, not the loudest one: frontal, sharp,
mid-size, mouth closed or nearly (a mid-scream face is grotesque as a still), two faces in a stand-off beat one. The text
is SHORT (2-6 words, the reviewer's `thumb_text` or a cut of the hook), huge Montserrat Black, white with one yellow key
word, in the upper third. The picture gets a light "pop" grade (contrast, colour, lift on dark frames).

Besides the pick, a 2x2 OPTIONS sheet of the four best different frames (composed, numbered, with their times) goes
beside the clip so rico can say "clip 01, option 3": the reviewer then pins `thumb_t` (episode seconds) in plan.json.

Shorts and TikTok take no custom thumbnail file: their apps let you pick a FRAME of the video, so the thumbnail is also
appended as the clip's last two frames (invisible when watching, selectable in the frame picker). Instagram Reels take
the PNG as a custom cover.

    python3 bot/thumbnail.py <source.mp4> <hook> <parts json> <out.png> [--text "..."] [--at seconds]
                             [--options sheet.jpg] [--append clip.mp4]
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import analyze_shots  # noqa: E402

FONTS = Path(__file__).parent / "fonts"
W, H = 1080, 1920
WHITE, YELLOW = (255, 255, 255), (255, 214, 0)
DW, DH = 1280, 720          # detection size
STOP = {"a", "an", "the", "of", "to", "and", "or", "over", "on", "in", "at", "for", "with", "is", "it", "that", "this"}


# ---------------------------------------------------------------- gender (rico 2026-10-29: "females get more clicks, lean in on that")
GENDER_MODEL = Path(__file__).parent / "models" / "genderage.onnx"   # InsightFace buffalo_l attribute head (1.3 MB, MIT), 96x96 face
_GNET = {}
# 2026-10-29 03:59 UTC: on DIGGER the model called two cats, the man in the parka, the old man on oxygen and the
# long-haired man at the window "women" (margins 2-6), and the bot told rico the window shot was a woman. It was
# not. The automatic preference is OFF until a detector is proven on real footage; "women first" is applied by the
# reviewer by eye through thumb_t, and only after rico confirms the frame. The margin is still measured and kept
# in the candidate so the options sheet can be checked against it.
WOMAN_BOOST = 0.0


def _gender_net():
    if "net" not in _GNET:
        try:
            _GNET["net"] = cv2.dnn.readNetFromONNX(str(GENDER_MODEL))
        except Exception:
            _GNET["net"] = None
    return _GNET["net"]


def woman_margin(frame, x, y, bw, bh):
    """How clearly the face reads as a woman: female logit minus male logit (> 1 is clear, < -1 clearly a man,
    around 0 unsure, e.g. a 3/4 view). 0.0 when the model is missing."""
    net = _gender_net()
    if net is None:
        return 0.0
    cx, cy, sz = x + bw / 2, y + bh / 2, max(bw, bh) * 1.15
    crop = frame[max(int(cy - sz / 2), 0):int(cy + sz / 2), max(int(cx - sz / 2), 0):int(cx + sz / 2)]
    if crop.size == 0:
        return 0.0
    net.setInput(cv2.dnn.blobFromImage(cv2.resize(crop, (96, 96)), 1.0, (96, 96), (0, 0, 0), swapRB=True))
    out = net.forward()[0]
    return float(out[0] - out[1])


# ---------------------------------------------------------------- faces with landmarks
def faces_lm(frame, min_conf=0.7, gender=False):
    """YuNet faces with the measures the picker needs: cx, cy, size (box width / frame width), conf,
    frontal (eye distance / box width: ~0.4 facing camera, ~0.2 profile), mouth (nose-to-mouth drop / eye distance:
    ~0.3-0.6 closed, 0.75+ open, 1.0 screaming), sharp (Laplacian variance), bright (mean grey)."""
    h, w = frame.shape[:2]
    det = analyze_shots._yunet(w, h)
    out = []
    if det is None:
        return out
    _, res = det.detect(frame)
    for r in (res if res is not None else []):
        x, y, bw, bh, conf = [float(v) for v in (r[0], r[1], r[2], r[3], r[14])]
        if conf < min_conf or bw <= 0:
            continue
        re_, le, no, rm, lm = [(float(r[j]), float(r[j + 1])) for j in (4, 6, 8, 10, 12)]
        eye = max(math.hypot(le[0] - re_[0], le[1] - re_[1]), 1.0)
        crop = frame[max(int(y), 0):int(y + bh), max(int(x), 0):int(x + bw)]
        if crop.size == 0:
            continue
        g = cv2.cvtColor(cv2.resize(crop, (96, 96)), cv2.COLOR_BGR2GRAY)
        out.append({"cx": (x + bw / 2) / w, "cy": (y + bh / 2) / h, "size": bw / w, "conf": conf,
                    "frontal": eye / bw, "mouth": ((rm[1] + lm[1]) / 2 - no[1]) / eye,
                    "sharp": float(cv2.Laplacian(g, cv2.CV_64F).var()), "bright": float(g.mean()),
                    "fem": woman_margin(frame, x, y, bw, bh) if gender else 0.0})
    out.sort(key=lambda d: -d["size"])
    return out


def _ramp(x, lo, hi):
    """0 at lo, 1 at hi (clamped), linear."""
    return min(1.0, max(0.0, (x - lo) / (hi - lo))) if hi > lo else 1.0


def face_score(d):
    """How clickable one face is as a still (the mouth is judged from the sound, see loudness())."""
    sz = d["size"]
    size_pref = _ramp(sz, 0.05, 0.11) * (0.8 + 0.2 * _ramp(sz, 0.11, 0.20)) * (1.0 - 0.6 * _ramp(sz, 0.28, 0.45))   # mid-size, the close-up (the lead) a little ahead, no pores
    frontal = 0.25 + 0.75 * _ramp(d["frontal"], 0.22, 0.38)                      # facing the camera
    sharp = min(1.0, math.log1p(d["sharp"]) / math.log1p(250))
    bright = 0.5 + 0.5 * _ramp(d["bright"], 35, 70)
    woman = 1.0 + WOMAN_BOOST * _ramp(d.get("fem", 0.0), 0.6, 1.5)   # rico: a woman's face gets the click (see WOMAN_BOOST)
    return d["conf"] * size_pref * frontal * sharp * bright * woman


def loudness(source, a, b, step=0.2):
    """dB of the sound in `step` windows over [a, b] (mono 8 kHz RMS). A shout is a peak: the face at that
    instant is mid-scream, which is grotesque as a still (YuNet's mouth landmarks cannot tell an open mouth,
    measured 2026-10-29). A quiet window is a reaction shot: mouth shut, eyes doing the work."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", source,
                          "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    pcm = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    n = max(int(step * 8000), 1)
    out = []
    for i in range(0, len(pcm), n):
        w = pcm[i:i + n]
        out.append(20 * math.log10(float(np.sqrt(np.mean(w * w))) + 1e-6) if len(w) else -120.0)
    return out


def candidates(source, parts, fps=5):
    """[(score, t, faces)] for every sampled frame with a usable face, best first."""
    out = []
    for a, b in parts:
        frames = analyze_shots._frames_at(source, a, b, fps, DW, DH)
        db = loudness(source, a, b)
        med = float(np.median([x for x in db if x > -80])) if any(x > -80 for x in db) else -30.0
        for i, f in enumerate(frames):
            t = a + i / fps
            here = db[min(int((t - a) / 0.2), len(db) - 1)] if db else med
            quiet = 1.0 - 0.65 * _ramp(here - med, 2.0, 8.0)      # a shout: down to 0.35; a pause or the other's line: 1.0
            faces = [d for d in faces_lm(f, 0.7, gender=WOMAN_BOOST > 0) if d["size"] >= 0.05 and d["cy"] <= 0.8]
            if not faces:
                continue
            main = faces[0]
            s = face_score(main)
            others = [d for d in faces[1:] if d["size"] >= 0.6 * main["size"] and abs(d["cx"] - main["cx"]) + main["size"] <= 0.25
                      and abs(d["cy"] - main["cy"]) < 0.15]   # both fit one 9:16 crop (0.25 of a 16:9 width)
            if others and face_score(others[0]) > 0.4 * s:
                s *= 1.25                                   # two people in one frame: a stand-off reads as a story
            s *= quiet
            s *= 0.92 + 0.16 * math.sin(math.pi * min(1.0, (t - a) / max(b - a, 1)))   # a nudge towards the middle of the clip
            out.append((s, t, faces[:2] if others else faces[:1]))
    out.sort(key=lambda c: -c[0])
    return out


def top_picks(cands, n=4, gap=1.5):
    """The n best candidates at least `gap` seconds apart and not the same framing (face size) twice in a row."""
    picks = []
    for c in cands:
        if any(abs(c[1] - p[1]) < gap for p in picks):
            continue
        if any(abs(c[1] - p[1]) < 6 and abs(c[2][0]["size"] - p[2][0]["size"]) < 0.02 and len(c[2]) == len(p[2]) for p in picks):
            continue
        picks.append(c)
        if len(picks) >= n:
            break
    # a woman's face among the options when the clip has one (rico 2026-10-29); off while WOMAN_BOOST is 0 (see above)
    if WOMAN_BOOST > 0 and n > 1 and picks and not any(p[2][0].get("fem", 0) > 0.8 for p in picks):
        women = [c for c in cands if c[2][0].get("fem", 0) > 0.8 and not any(abs(c[1] - p[1]) < gap for p in picks[:-1])]
        if women:
            picks[-1] = women[0]
    return picks


def best_frame(source, parts, fps=5):
    """(t, faces) of the best thumbnail frame inside the clip's parts, or None."""
    p = top_picks(candidates(source, parts, fps), 1)
    return (p[0][1], p[0][2]) if p else None


# ---------------------------------------------------------------- picture
def grab(source, t):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", source, "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def frame_on_faces(img, faces, face_frac=0.20, face_y=0.55, max_zoom=1.5):
    """9:16 crop of the source frame. One face: `face_frac` of the output height, eyes at `face_y`.
    Two faces: both inside the middle 70% of the width, centred between them."""
    sh, sw = img.shape[:2]
    full_cw = min(sw, int(sh * W / H))
    xs = [f["cx"] * sw for f in faces[:2]]
    span = abs(xs[0] - xs[1]) + max(f["size"] for f in faces[:2]) * sw if len(faces) >= 2 else 0
    if len(faces) >= 2 and span <= 0.8 * full_cw:
        cw = int(min(full_cw, max(span / 0.75, full_cw / max_zoom)))
        cx = sum(xs) / 2
        cy = sum(f["cy"] for f in faces[:2]) / 2 * sh
    else:
        f = faces[0]
        cx, cy, sz = f["cx"] * sw, f["cy"] * sh, f["size"] * sw
        zoom = min(max_zoom, max(1.0, face_frac * sh / max(sz, 1)))
        cw = int(full_cw / zoom)
    ch = int(cw * H / W)
    if ch > sh:
        ch = sh; cw = int(ch * W / H)
    x0 = int(min(max(cx - cw / 2, 0), sw - cw))
    y0 = int(min(max(cy - ch * face_y, 0), sh - ch))
    crop = img[y0:y0 + ch, x0:x0 + cw]
    top = min((f["cy"] * sh - f["size"] * sw * 0.65 - y0) / ch for f in faces[:2])   # highest face's top edge, 0-1 of the picture
    return cv2.resize(crop, (W, H), interpolation=cv2.INTER_LANCZOS4), top


def pop(bgr):
    """A light thumbnail grade: a touch more contrast and colour, a lift when the frame is dark, soft vignette."""
    f = bgr.astype(np.float32)
    mean = float(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).mean())
    if mean < 85:                                           # dark scene: lift the mids, keep the blacks
        gamma = 0.9 if mean > 60 else 0.8
        f = 255.0 * (f / 255.0) ** gamma
    f = (f - 128.0) * 1.10 + 128.0
    f = np.clip(f, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.18, 0, 255)
    f = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vig = 1.0 - 0.22 * np.clip((r - 0.6) / 0.8, 0, 1) ** 1.5
    f *= vig[..., None]
    return np.clip(f, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- text
def key_words(text, emphasis=()):
    """Up to two words to paint yellow: numbers and money first, then the reviewer's emphasis words, else the longest."""
    words = [w for w in re.findall(r"[A-Za-z0-9$%'’.-]+", text)]
    def key(w):
        return re.sub(r"[^a-z0-9$]", "", w.lower())
    picks = [w for w in words if re.search(r"\d|\$", w)]
    emph = {e.lower() for e in emphasis}
    picks += [w for w in words if w not in picks and (key(w) in emph or any(key(w).startswith(e) for e in emph if len(e) > 3))]
    if not picks:
        content = [w for w in words if key(w) not in STOP and len(key(w)) > 2]
        picks = content[-1:] or words[-1:]
    return {key(w) for w in picks[:2]}


def short_text(hook, emphasis=()):
    """2-6 words for the thumbnail: the hook when it is short; else the clause with the most emphasis words;
    else the first words with an ellipsis (a cliffhanger beats a paragraph)."""
    hook = hook.strip()
    words = hook.rstrip(".").split()
    if len(words) <= 6:
        return hook.rstrip(".")
    emph = {e.lower() for e in emphasis}
    def hits(ws):
        return sum(1 for w in ws if re.sub(r"[^a-z0-9$]", "", w.lower()) in emph or re.search(r"\d|\$", w))
    segs = [s.strip() for s in re.split(r"(?<=[?!:;,])\s+|\s*\.\.\.\s*|\s*…\s*", hook) if s.strip()]
    good = [s for s in segs if 2 <= len(s.split()) <= 6]
    if good:
        best = max(good, key=lambda s: (hits(s.split()), -abs(len(s.split()) - 4)))
        if hits(best.split()):
            return best.rstrip(".,;:")
    if len(segs) > 1 and 2 <= len(segs[0].split()) <= 6:
        return segs[0].rstrip(".,;:")
    cut = words[:5]
    while cut and cut[-1].lower().strip(",.;:") in STOP:
        cut = cut[:-1]
    return " ".join(cut).rstrip(".,;:") + "..."


def split_lines(text, n=2):
    """The text in n lines of about equal length (word boundaries)."""
    words = text.split()
    if n == 1 or len(words) <= 2:
        return [" ".join(words)]
    if n == 2:
        best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
        return [" ".join(words[:best]), " ".join(words[best:])]
    total = len(" ".join(words)); target = total / n
    lines, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > target * 1.05 and len(lines) < n - 1:
            lines.append(" ".join(cur)); cur = []
        cur.append(w)
    lines.append(" ".join(cur))
    return lines


def _font(size):
    return ImageFont.truetype(str(FONTS / "Montserrat-Black.ttf"), size)


def _fit_size(draw, lines, max_w, start=210, min_size=90):
    size = start
    while size > min_size:
        if all(draw.textlength(l, font=_font(size)) <= max_w for l in lines):
            return size
        size -= 4
    return min_size


def layout(draw, text, max_w, max_lines=3):
    """Lines and font size: one line if it can be 150 px+, else two, else three (big beats many).
    `max_lines=2` for the low block (under the face there is less room)."""
    one = [text.upper()]
    s1 = _fit_size(draw, one, max_w)
    if s1 >= 150:
        return one, s1
    two = [l.upper() for l in split_lines(text, 2) if l]
    s2 = _fit_size(draw, two, max_w, min_size=84)
    if s2 >= 120 or len(text.split()) <= 4 or max_lines <= 2:
        return two, s2
    three = [l.upper() for l in split_lines(text, 3) if l]
    s3 = _fit_size(draw, three, max_w)
    return (three, s3) if s3 > s2 else (two, s2)


def compose(picture_bgr, text, out_png, emphasis=(), low=False):
    """`low`: the text block sits in the lower third (faces are high in the picture) instead of the upper third."""
    im = Image.fromarray(cv2.cvtColor(pop(picture_bgr), cv2.COLOR_BGR2RGB)).convert("RGBA")
    grad = Image.new("L", (1, H))      # light shade behind the text block only; the face keeps its light
    for y in range(H):
        yy = (H - y) if low else y
        grad.putpixel((0, y), int(135 * max(0.0, 1 - yy / (0.40 * H)) ** 1.4))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shade.putalpha(grad.resize((W, H)))
    im = Image.alpha_composite(im, shade)
    draw = ImageDraw.Draw(im)
    lines, size = layout(draw, text, W - 90, max_lines=2 if low else 3)
    font = _font(size)
    keys = key_words(text, emphasis)
    block = int(size * 1.12) * len(lines)
    y = (H - 280 - block) if low else 130        # low: above the bottom 280 px (where the apps draw their UI)
    for l in lines:
        words = l.split()
        widths = [draw.textlength(w, font=font) for w in words]
        gap = draw.textlength(" ", font=font)
        x = (W - (sum(widths) + gap * (len(words) - 1))) / 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x + 6, y + 12), l, font=font, fill=(0, 0, 0, 210))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(12)))
        draw = ImageDraw.Draw(im)
        for w, wd in zip(words, widths):
            col = YELLOW if re.sub(r"[^a-z0-9$]", "", w.lower()) in keys else WHITE
            draw.text((x, y), w, font=font, fill=col, stroke_width=max(10, size // 11), stroke_fill=(0, 0, 0, 255))
            x += wd + gap
        y += int(size * 1.12)
    im.convert("RGB").save(out_png, "PNG")
    return out_png


def _picture(source, t, faces):
    """(9:16 picture, text_low): text goes low when a face's top edge lands inside the upper text block."""
    img = grab(source, t)
    if not faces:
        sh, sw = img.shape[:2]; cw = int(sh * W / H)
        return cv2.resize(img[:, (sw - cw) // 2:(sw - cw) // 2 + cw], (W, H), interpolation=cv2.INTER_LANCZOS4), False
    pic, top = frame_on_faces(img, faces)
    return pic, top < 0.33


def options_sheet(source, picks, text, out_jpg, emphasis=()):
    """2x2 sheet of the composed alternatives, numbered, with their episode times (for "clip 01, option 3")."""
    tiles = []
    for i, (_, t, faces) in enumerate(picks[:4], 1):
        tmp = Path(out_jpg).with_suffix(f".opt{i}.png")
        pic, low = _picture(source, t, faces)
        compose(pic, text, str(tmp), emphasis, low=low)
        tile = Image.open(tmp).convert("RGB").resize((540, 960), Image.LANCZOS)
        tmp.unlink(missing_ok=True)
        d = ImageDraw.Draw(tile)
        label = f"OPTION {i}  ({t:.1f} s)"
        f = ImageFont.truetype(str(FONTS / "Montserrat-ExtraBold.ttf"), 34)
        tw = d.textlength(label, font=f)
        d.rectangle([0, 960 - 60, tw + 40, 960], fill=(0, 0, 0))
        d.text((20, 960 - 50), label, font=f, fill=YELLOW)
        tiles.append(tile)
    while len(tiles) < 4:
        tiles.append(Image.new("RGB", (540, 960), (20, 20, 20)))
    sheet = Image.new("RGB", (1080 + 12, 1920 + 12), (255, 255, 255))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * 552, (i // 2) * 972))
    sheet.save(out_jpg, "JPEG", quality=88)
    return out_jpg


def make(source, hook, parts, out_png, text=None, at=None, emphasis=(), options=None):
    """Write the thumbnail PNG (and the options sheet when `options` is a path). Returns (png, t used).
    `text`: the reviewer's thumb_text (else a short cut of the hook). `at`: a pinned episode second (reviewer's thumb_t)."""
    text = (text or "").strip() or short_text(hook, emphasis)
    cands = candidates(source, parts)
    picks = top_picks(cands, 4)
    if at is not None:
        near = [c for c in cands if abs(c[1] - at) <= 0.3]
        faces = max(near, key=lambda c: c[0])[2] if near else faces_lm(cv2.resize(grab(source, at), (DW, DH)), 0.5)[:1]
        t = at
    elif picks:
        _, t, faces = picks[0]
    else:
        t, faces = parts[0][0] + 1.0, []
    pic, low = _picture(source, t, faces)
    compose(pic, text, out_png, emphasis, low=low)
    if options and picks:
        try:
            options_sheet(source, picks, text, options, emphasis)
        except Exception as e:   # the sheet is a nicety
            print(f"options sheet failed: {e}")
    return out_png, t


def duration(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def append_cover(mp4, png, out=None, frames=2, strip_old=False):
    """Re-encode the clip with the thumbnail as its last `frames` frames (silent), for the frame pickers.
    `strip_old`: the clip already ends with an earlier cover (same number of frames): cut it off first."""
    out = out or mp4
    tmp = Path(str(out) + ".cover.mp4")
    d = frames / 30
    main = "[0:v]setsar=1[m];[0:a]anull[ma]"
    if strip_old:
        keep = max(duration(mp4) - d - 0.001, 1.0)
        main = f"[0:v]trim=0:{keep:.3f},setpts=PTS-STARTPTS,setsar=1[m];[0:a]atrim=0:{keep:.3f},asetpts=PTS-STARTPTS[ma]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-loop", "1", "-t", f"{d:.3f}", "-i", str(png),
           "-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", f"{main};[1:v]scale={W}:{H},format=yuv420p,setsar=1,fps=30[c];[m][ma][c][2:a]concat=n=2:v=1:a=1[v][a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(out)
    return out


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    src, hook, parts, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
    at = _arg("--at"); at = float(at) if at else None
    png, t = make(src, hook, parts, out, text=_arg("--text"), at=at, options=_arg("--options"))
    print(f"thumbnail {png} from {t:.2f} s")
    if "--append" in sys.argv:
        append_cover(_arg("--append"), png)
        print(f"appended as the last frames of {_arg('--append')}")
