"""The look sheet (makeover release 8): rico picks the text look per content type from rendered samples, never from
a description.

  python3 bot/looks.py <frame.png or video.mp4[@seconds]> <out.png> [hook text] [caption text]

renders 12 tiles: the four looks (classic = before release 8, pill, pop, minimal) x three accent colours, each one
with the bot's own caption engine (the same ASS styles render_clip writes) on the given frame. Tiles are numbered;
the pick goes into the campaign's plan.json: "brief_overrides": {"look": {"style": "pill", "accent": "cyan"}}, or
into profiles.DEFAULT_LOOK for a whole content type.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import profiles  # noqa: E402
import render_clip as rc  # noqa: E402

GRID = [(style, accent) for style in ("classic", "pill", "pop", "minimal") for accent in ("yellow", "cyan", "pink")]


def tile_ass(style, accent, hook, caption, keyword):
    lk = profiles.look("podcast" if style == "classic" else None, {"style": style, "accent": accent})
    rc.ACCENT[0] = lk.get("hook_accent", lk["accent"])
    rc.ACCENT[1] = "&H" + lk.get("hook_primary", "&H00FFFFFF")[-6:] + "&"
    size, title = rc.title_lines(hook, [keyword], lk)
    size = min(size, lk.get("hook_max", rc.HOOK_MAX))
    sp = f"\\fsp{lk['title_spacing']}" if lk.get("title_spacing") else ""
    cap = " ".join((r"{\c" + lk["accent"] + "}" + rc.esc(w if not lk.get("upper", True) else w.upper()) + r"{\c&HFFFFFF&}")
                   if rc.norm(w) == rc.norm(keyword) else rc.esc(w.upper() if lk.get("upper", True) else w) for w in caption.split())
    return (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {rc.W}\nPlayResY: {rc.H}\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
            "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"{rc.ass_styles(lk)}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            f"Dialogue: 2,0:00:00.00,0:00:05.00,Hook,,0,0,0,,{{\\an8\\pos(540,150)\\fs{size}{sp}}}{title}\n"
            f"Dialogue: 1,0:00:00.00,0:00:05.00,Cap,,0,0,0,,{{\\an5\\pos(540,{rc.CAP_DEFAULT})}}{cap}\n")


def sheet(frame, out, hook="Hong Kong sang every word", caption="the crowd knew it", keyword="every"):
    from PIL import Image, ImageDraw, ImageFont
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "base.png"
        src, _, at = str(frame).partition("@")
        # the frame, cropped to 9:16 from the middle and scaled to 1080x1920
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *(["-ss", at] if at else []), "-i", src, "-frames:v", "1",
                        "-vf", "crop='min(iw,ih*9/16)':ih,scale=1080:1920", str(base)], check=True)
        tiles = []
        for i, (style, accent) in enumerate(GRID):
            ass = tmp / f"t{i}.ass"
            ass.write_text(tile_ass(style, accent, hook, caption, keyword))
            png = tmp / f"t{i}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(base), "-vf", f"ass={ass}:fontsdir={rc.FONTS_DIR}",
                            "-frames:v", "1", str(png)], check=True)
            tiles.append(Image.open(png).convert("RGB").resize((270, 480)))
        cols, pad, label = 6, 12, 40
        rows = (len(tiles) + cols - 1) // cols
        im = Image.new("RGB", (cols * (270 + pad) + pad, rows * (480 + label + pad) + pad), (245, 245, 245))
        dr = ImageDraw.Draw(im)
        font = ImageFont.truetype(str(rc.FONTS_DIR / "Inter-Bold.otf"), 22)
        for i, t in enumerate(tiles):
            x, y = pad + (i % cols) * (270 + pad), pad + (i // cols) * (480 + label + pad)
            im.paste(t, (x, y + label))
            style, accent = GRID[i]
            dr.text((x, y + 8), f"{i + 1}. {style} / {accent}", fill=(20, 20, 20), font=font)
        im.save(out)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    sheet(a[0], a[1], *(a[2:4]))
    print(f"look sheet: {a[1]}")
