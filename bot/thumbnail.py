"""Thumbnail for an approved clip (rico, 2026-10-29: "what about the thumbnail on YouTube Shorts, make sure it's really good";
RULES.md 20): the actor's best reacting frame from the episode itself, framed 9:16 on the face, with two big lines of
text (white, then yellow) in the upper third. Only the episode's own frames, never outside images.

Shorts take no custom thumbnail file: YouTube's app lets you pick a FRAME of the video, so the thumbnail is also
appended as the clip's last two frames (invisible when watching, selectable in the frame picker). TikTok picks a cover
frame the same way; Instagram Reels take the PNG as a custom cover.

    python3 bot/thumbnail.py <source.mp4> <hook> <parts json> <out.png> [--append clip.mp4]
"""
import json
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


def _sharp(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def best_frame(source, parts, fps=5):
    """(t, (cx, cy, size)) of the sharpest big confident face inside the clip's parts."""
    best, pick = -1.0, None
    for a, b in parts:
        frames = analyze_shots._frames_at(source, a, b, fps, 1280, 720)
        for i, f in enumerate(frames):
            t = a + i / fps
            faces = [x for x in analyze_shots.detect_faces(f, 0.7) if 0.06 <= x[2] <= 0.45 and x[1] <= 0.75]
            if not faces:
                continue
            cx, cy, sz, conf = faces[0]
            x0, y0 = int((cx - sz / 2) * 1280), int((cy - sz / 2) * 720)
            crop = f[max(y0, 0):y0 + int(sz * 1280), max(x0, 0):x0 + int(sz * 1280)]
            if crop.size == 0:
                continue
            g = cv2.cvtColor(cv2.resize(crop, (96, 96)), cv2.COLOR_BGR2GRAY)
            score = conf * min(sz, 0.3) * np.log1p(_sharp(g)) * (1.0 + float(g.std()) / 64)   # confident, big, sharp, contrasty
            score *= 1.0 + 0.8 * (t - a) / max(b - a, 1)   # the payoff is at the end: the face that lands the punchline
            if score > best:
                best, pick = score, (t, (cx, cy, sz))
    return pick


def grab(source, t):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", source, "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def frame_on_face(img, face, face_frac=0.24, face_y=0.56):
    """9:16 crop of the source frame with the face `face_frac` of the output height, eyes at `face_y`."""
    sh, sw = img.shape[:2]
    cx, cy, sz = face[0] * sw, face[1] * sh, face[2] * sw
    zoom = min(1.8, max(1.0, face_frac * sh / max(sz, 1)))
    ch = int(sh / zoom); cw = int(ch * W / H)
    if cw > sw:
        cw = sw; ch = int(cw * H / W)
    x0 = int(min(max(cx - cw / 2, 0), sw - cw))
    y0 = int(min(max(cy - ch * face_y, 0), sh - ch))
    crop = img[y0:y0 + ch, x0:x0 + cw]
    return cv2.resize(crop, (W, H), interpolation=cv2.INTER_LANCZOS4)


def split_hook(hook, n=2):
    """The hook in n lines of about equal length (word boundaries)."""
    words = hook.strip().rstrip(".").split()
    if n == 1 or len(words) <= 3:
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
    return ImageFont.truetype(str(FONTS / "Montserrat-ExtraBold.ttf"), size)


def _fit_size(draw, lines, max_w, start=160, min_size=60):
    size = start
    while size > min_size:
        if all(draw.textlength(l, font=_font(size)) <= max_w for l in lines):
            return size
        size -= 4
    return min_size


def layout(draw, hook, max_w):
    """Lines and font size: 2 lines when they can be 96 px+, else 3 lines (big text beats more words)."""
    two = [l.upper() for l in split_hook(hook, 2) if l]
    s2 = _fit_size(draw, two, max_w)
    if s2 >= 96 or len(hook.split()) <= 4:
        return two, s2
    three = [l.upper() for l in split_hook(hook, 3) if l]
    s3 = _fit_size(draw, three, max_w)
    return (three, s3) if s3 > s2 else (two, s2)


def compose(picture_bgr, hook, out_png):
    im = Image.fromarray(cv2.cvtColor(picture_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    # dark gradient over the top 45% so the text reads on any picture, and a light one at the bottom
    grad = Image.new("L", (1, H))
    for y in range(H):
        a = int(190 * max(0.0, 1 - y / (0.45 * H)) ** 1.3) + int(110 * max(0.0, (y - 0.8 * H) / (0.2 * H)))
        grad.putpixel((0, y), min(a, 255))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shade.putalpha(grad.resize((W, H)))
    im = Image.alpha_composite(im, shade)
    draw = ImageDraw.Draw(im)
    lines, size = layout(draw, hook, W - 100)
    fonts = [_font(size)] * len(lines)
    y = 150
    for l, f, col in zip(lines, fonts, [WHITE, YELLOW, WHITE]):
        tw = draw.textlength(l, font=f)
        x = (W - tw) / 2
        # soft shadow, then a thick black outline, then the fill
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x + 6, y + 10), l, font=f, fill=(0, 0, 0, 200))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(10)))
        draw = ImageDraw.Draw(im)
        draw.text((x, y), l, font=f, fill=col, stroke_width=max(8, size // 12), stroke_fill=(0, 0, 0, 255))
        y += int(size * 1.18)
    im.convert("RGB").save(out_png, "PNG")
    return out_png


def make(source, hook, parts, out_png):
    pick = best_frame(source, parts)
    if not pick:
        t = parts[0][0] + 1.0
        pic = cv2.resize(grab(source, t)[:, :][:, :], (W, H))   # no face: centre crop fallback
        img = grab(source, t); sh, sw = img.shape[:2]; cw = int(sh * W / H)
        pic = cv2.resize(img[:, (sw - cw) // 2:(sw - cw) // 2 + cw], (W, H), interpolation=cv2.INTER_LANCZOS4)
    else:
        t, face = pick
        pic = frame_on_face(grab(source, t), face)
    compose(pic, hook, out_png)
    return out_png, (pick[0] if pick else None)


def append_cover(mp4, png, out=None, frames=2):
    """Re-encode the clip with the thumbnail as its last `frames` frames (silent), for the frame pickers."""
    out = out or mp4
    tmp = Path(str(out) + ".cover.mp4")
    d = frames / 30
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-loop", "1", "-t", f"{d:.3f}", "-i", str(png),
           "-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", f"[0:v]setsar=1[m];[1:v]scale={W}:{H},format=yuv420p,setsar=1,fps=30[c];[m][0:a][c][2:a]concat=n=2:v=1:a=1[v][a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(out)
    return out


if __name__ == "__main__":
    src, hook, parts, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
    png, t = make(src, hook, parts, out)
    print(f"thumbnail {png} from {t}")
    if "--append" in sys.argv:
        clip = sys.argv[sys.argv.index("--append") + 1]
        append_cover(clip, png)
        print(f"appended as the last frames of {clip}")
