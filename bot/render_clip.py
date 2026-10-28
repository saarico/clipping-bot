"""Render one true 9:16 podcast clip: opener, hook title, word-timed captions, framing that
follows the people on screen, punch-in zooms on key lines, and the show's own graphics
(phone stories, definition cards) brought forward instead of cropped away.

Usage:
  python3 render_clip.py spec.json

spec.json:
  {
    "source": "/path/ich_2196.mp4",
    "words": "/path/words_D.json",          # list of {"text","start","end"} in SOURCE seconds (words or short phrases)
    "teaser": [262.68, 265.94],              # optional: a complete punchline played first (only when it lands on its own)
    "teaser_exact": false,                   # optional: true = use the teaser cut as given, no snapping
    "parts": [[224.16, 281.38]],             # the main story, in order; several ranges = jump cuts
    "hook": "KYLIE JENNER POSTED HIS DRINK", # title at the top, shown the whole clip
    "teaser_cut": false,                     # optional: true = straight cut from teaser to story (no dip)
    "label": "",                             # optional, normally left out (rico dislikes it): shown 1.5 s after the teaser
    "emphasis": ["Kylie", "Jenner"],         # words to highlight (case-insensitive, punctuation ignored)
    "focus": [[262.68, 265.94]],             # optional: source ranges to punch in on (key lines)
    "overlays": [                            # optional: graphics the show put on screen
      {"from": 234.1, "to": 246.5, "box": [1337, 51, 541, 977], "style": "side"},   # tall phone story -> card on the right
      {"from": 110.2, "to": 116.4, "box": [1005, 246, 825, 585], "style": "bottom"}, # wide card -> bottom half
      {"from": 131.5, "to": 135.7, "box": [107, 59, 1704, 971], "style": "fit"},    # framed clip -> whole, full width
      {"from": 123.75, "to": 128.2, "box": [44, 54, 534, 966], "style": "side",
       "card_window": [124.35, 127.4]},  # optional: card shows only this clean stretch (held at the edges)
                                             # "card_speed": 0.75 plays that stretch slowed over the whole overlay (no pause)
      {"from": 173.2, "to": 179.1, "box": [300, 872, 1312, 188], "style": "banner",
       "hard_out": true},  # headline strip -> under the speaker; hard_out = leave with the camera cut, no slide
      {"from": 973.2, "to": 985.0, "box": [80, 990, 1500, 70], "style": "hide"}  # tiny strip: just crop it out
    ],
    "hook_hi": ["Sales", "didn't", "move."],   # optional: title words shown in yellow
    "video_swap": [[266.34, 266.63, 259.69]], # optional: [from, to, take picture from]: hides a stray
                                             # short shot at a jump with the speaker's own frames
    "hold_end_from": 54.77,                  # optional: output second where the show cuts away; hold + fade from there
    "tighten": true,                         # default on: pauses over 0.7 s inside the cut are removed (PLAYBOOK 24)
    "sfx": true,                             # optional: soft whoosh under each card / callout reveal (PLAYBOOK 29)
    "wide_split": [[0.22, 0.38, 0.06], [0.74, 0.40, 0.055]],  # optional: the two people in the show's wide two-shot
                                             # (cx, cy, size, 0-1), used when the detector misses one; never an empty room
    "callouts": [                            # optional: our own big yellow text card for a number or a name (PLAYBOOK 26)
      {"from": 2767.4, "to": 2772.1, "text": "$1,000,000 A YEAR", "sub": "her bare minimum to raise a kid"}
    ],
    "out": "/path/clip.mp4"
  }

How it works:
  1. Every cut point is moved to the quietest moment between words, so nothing is clipped.
  2. analyze_shots.py finds camera cuts and faces. One person -> a 9:16 window that tracks
     the face (frontal detector, nearest-previous, 0.5 s eased pans, dead zone) so the speaker
     is centred the whole shot. Two people (also the show's wide two-shot, faces found at full
     resolution) -> stacked split. Nobody -> full-height 9:16 window. Never letterbox.
  3. Overlays: the speaker stays on screen and the graphic slides in beside or below him.
     A graphic on the left of the source slides in on the left. "fit" shows a whole framed
     clip or card full width; "banner" puts a headline strip under the speaker.
  4. Teaser (if any) -> quick dip to black -> main story. Every piece's edges move onto a
     camera cut if one falls within 0.6 s (no stray frames of another camera), one-frame white
     or black flashes in the show's b-roll are patched out, and the audio is levelled in two
     passes (measure, then linear gain) so the volume never pumps. "teaser_exact": true keeps the
     teaser cut exactly as given (use when the next speaker starts mid-word).
  5. The title sits in its own black band at the top (2 lines max, auto-sized), so it never
     covers a face; the picture fills the 1080x1680 area below it.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import analyze_shots  # noqa: E402
import profiles  # noqa: E402

FONTS_DIR = Path(__file__).parent / "fonts"
TITLE_FONT, CAP_FONT = "Montserrat ExtraBold", "Montserrat Black"
W, H, FPS = 1080, 1920, 30
TOP = 240             # title band height; the picture uses the rest (keep HC/2 even)
HC = H - TOP
SRC_W, SRC_H = 1920, 1080
SR = 16000
SLIDE = 0.35          # seconds for an overlay to slide in or out
MIN_SPLIT = 1.5       # two-person shots shorter than this get a single crop instead of a split


def norm(w):
    return re.sub(r"[^a-z0-9$%]", "", w.lower())


def ts(t):
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def run(cmd):
    subprocess.run(cmd, check=True)


# ---------- 1. snap cut points to silence ----------

def load_audio(src, a, b):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src,
                          "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float)


def quietest(audio, base, lo, hi):
    """Time (source s) of the quietest 30 ms in [lo, hi]."""
    win = int(0.03 * SR)
    i0, i1 = int((lo - base) * SR), int((hi - base) * SR)
    seg = audio[max(i0, 0):max(i1, i0 + win)]
    if len(seg) <= win:
        return (lo + hi) / 2
    energy = np.convolve(seg ** 2, np.ones(win), "valid")
    return lo + (int(np.argmin(energy)) + win / 2) / SR


def snap(src, ranges, words):
    base = max(min(r[0] for r in ranges) - 1, 0)
    audio = load_audio(src, base, max(r[1] for r in ranges) + 1)
    out = []
    for s, e in ranges:
        first = min((w["start"] for w in words if w["start"] >= s - 0.05), default=s)
        last = max((w["end"] for w in words if w["end"] <= e + 0.05), default=e)
        prev_end = max((w["end"] for w in words if w["end"] < first - 0.01), default=first - 0.5)
        next_start = min((w["start"] for w in words if w["start"] > last + 0.01), default=last + 0.45)
        # transcript times run a little late at word starts, so stay well clear of the
        # neighbouring words on both sides
        # (when the neighbour is very close, cut halfway into the gap instead of into a word)
        lo_s = max(prev_end + 0.12, first - 0.4)
        if lo_s > first - 0.06:
            new_s = quietest(audio, base, prev_end + 0.01, max(first - 0.01, prev_end + 0.02))
        else:
            new_s = quietest(audio, base, lo_s, first - 0.02)
        hi_e = min(next_start - 0.2, last + 0.6)
        if hi_e < last + 0.06:
            new_e = quietest(audio, base, last + 0.01, max(next_start - 0.02, last + 0.02))
        else:
            new_e = quietest(audio, base, last + 0.05, hi_e)
        out.append([new_s, new_e])
    return out


def tighten(ranges, words, max_gap=0.7, keep=0.16):
    """Cut dead air: any pause longer than max_gap inside a piece becomes a jump cut that keeps
    `keep` s of silence on each side (rico, 2026-10-26: "dead air, not engaging"). The pieces that
    come out of one range alternate the punch-in level, so each jump reads as a deliberate cut."""
    out = []
    for s, e in ranges:
        ws = [w for w in words if s - 0.05 <= w["start"] and w["end"] <= e + 0.05]
        cur = s
        for w1, w2 in zip(ws, ws[1:]):
            if w2["start"] - w1["end"] > max_gap:
                out.append([cur, w1["end"] + keep])
                cur = w2["start"] - keep
        out.append([cur, e])
    return out


def check_source(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", src], capture_output=True, text=True, check=True).stdout.strip()
    if out != f"{SRC_W},{SRC_H}":
        raise SystemExit(f"source is {out}, this script expects {SRC_W}x{SRC_H}: re-encode it first")


def trim_to_cuts(src, ranges, words):
    """If the show cuts to another camera within 0.6 s of a piece's start or end, move the edge to
    that cut, so a few frames of someone else never leak in (the $15K v6 start had 5 such frames).
    The edge only moves where no word is lost."""
    out = []
    for s, e in ranges:
        first = min((w["start"] for w in words if w["start"] >= s - 0.05), default=e)
        last = max((w["end"] for w in words if w["end"] <= e + 0.05), default=s)
        c = analyze_shots.cut_in(src, s, min(s + 0.6, first))
        if c and c <= first - 0.02:
            s = c
        c = analyze_shots.cut_in(src, max(e - 0.6, last), e)
        if c and c >= last + 0.02:
            e = c - 1 / FPS
        out.append([s, e])
    return out


# ---------- 2. framing ----------

def people(faces, box=None):
    """The 1-2 people worth framing; faces inside an on-screen graphic (box, source px) don't count."""
    def in_box(f):
        if not box:
            return False
        bx, by, bw, bh = box
        return bx <= f[0] * SRC_W <= bx + bw and by <= f[1] * SRC_H <= by + bh
    keep = [f for f in faces if 0.12 <= f[2] <= 0.26 and f[1] <= 0.6 and not in_box(f)]
    keep.sort(key=lambda f: -f[2])
    chosen = []
    for f in keep:
        if all(abs(f[0] - c[0]) > 0.2 for c in chosen):
            chosen.append(f)
    return chosen[:2]


def talker(ppl):
    """Of two people, the one whose mouth moves clearly more; otherwise the bigger face."""
    if len(ppl) == 2 and len(ppl[0]) > 3 and len(ppl[1]) > 3:
        a, b = ppl
        if max(a[3], b[3]) > 1.5 * max(min(a[3], b[3]), 0.5):
            return a if a[3] > b[3] else b
    return ppl[0]


class Framer:
    """Keeps one crop position per camera angle, so a camera that comes back gets the same framing."""

    def __init__(self):
        self.seen = []

    def x(self, cx):
        for s in self.seen:
            if abs(s - cx) < 0.06:
                return s
        self.seen.append(cx)
        return cx


def crop_x(cx, cw, place, left_limit, right_limit):
    return int(min(max(cx * SRC_W - cw * place, left_limit), right_limit - cw))


def pan_expr(keys, cw, place, left_limit, right_limit, ease=0.5):
    """ffmpeg x-expression that follows the face: `keys` = [(t_rel, cx)] change points from pan_keys.
    Between change points the crop glides over `ease` seconds, so the camera drifts with the speaker
    instead of jumping. One key = a fixed number."""
    xs = [(t, crop_x(cx, cw, place, left_limit, right_limit)) for t, cx in keys]
    if len(xs) == 1:
        return str(xs[0][1])
    expr = str(xs[-1][1])
    for (t0, x0), (t1, x1) in reversed(list(zip(xs, xs[1:]))):
        expr = f"if(lt(t,{t1:.3f}),{x0},if(lt(t,{t1 + ease:.3f}),{x0}+({x1}-{x0})*(t-{t1:.3f})/{ease},{expr}))"
    return expr


def face_crop(cx, zoom=1.0, place=0.5, right_limit=SRC_W, left_limit=0, max_h=SRC_H, keys=None, cy=None):
    """Window the shape of the picture area with the face at `place` of the width; tighter when
    zoomed, and no taller than max_h (to keep a source graphic at the bottom out of frame).
    With `keys` (face tracking) the window glides after the speaker."""
    ch = min(int(SRC_H / zoom), max_h) // 2 * 2
    cw = int(ch * W / HC) // 2 * 2
    x = pan_expr(keys, cw, place, left_limit, right_limit) if keys else str(crop_x(cx, cw, place, left_limit, right_limit))
    if ch == SRC_H or max_h < SRC_H:
        y = 0
    elif cy is not None:        # zoomed: eyes about 40% down the window, never a head at the bottom edge
        y = int(min(max(cy * SRC_H - ch * 0.40, 0), SRC_H - ch))
    else:
        y = int((SRC_H - ch) * 0.18)
    return f"crop={cw}:{ch}:'{x}':{y},scale={W}:{HC}"


def panel_crop(f, right_limit=SRC_W, left_limit=0, cw=630, keys=None):
    ch = int(cw * (HC // 2) / W) // 2 * 2
    x = pan_expr(keys, cw, 0.5, left_limit, right_limit) if keys else str(crop_x(f[0], cw, 0.5, left_limit, right_limit))
    y = int(min(max(f[1] * SRC_H - ch * 0.42, 0), SRC_H - ch))
    return f"crop={cw}:{ch}:'{x}':{y},scale={W}:{HC // 2}"


def pan_keys(src, a, b, box=None, start_cx=None):
    """Face-tracking change points [(t_rel, cx)] for one segment, or None when nobody is found.
    Median-smoothed over 1.25 s, with a dead zone: the window only moves once the face has drifted
    more than 4% of the frame width, so breathing and nodding never make the picture wobble."""
    tr = analyze_shots.track(src, a, b, box=box)
    seen = [p[0] for _, p in tr if p]
    if not seen:
        return None, None
    seq, last = [], seen[0]
    for _, p in tr:
        last = p[0] if p else last
        seq.append(last)
    sm = [float(np.median(seq[max(0, i - 2):i + 3])) for i in range(len(seq))]
    cur = start_cx if start_cx is not None and abs(start_cx - sm[0]) < 0.08 else sm[0]
    keys = [(0.0, cur)]
    for i, x in enumerate(sm):
        if abs(x - cur) > 0.04:
            cur = x
            keys.append((i / 4.0, cur))
    size = float(np.median([p[2] for _, p in tr if p]))
    return keys[:40], size


BLUR_BG = f"scale=-2:{HC},crop={W}:{HC},boxblur=30:3,eq=brightness=-0.25"


def build_filter(lay, ppl, zoom, ov, t_in, t_out, card_pre=None, keys=None, panel_w=630):
    """Return a -filter_complex graph ending in [v]. t_in/t_out: seconds since the overlay
    started / until it ends, at the start of this segment (for the slide animation).
    keys = face-tracking change points for the speaker (see pan_keys)."""
    cx0 = ppl[0][0] if ppl else 0.5
    cy0 = ppl[0][1] if ppl else None
    if lay in ("face", "wide"):
        # "wide": nobody big enough to track (b-roll, an empty room): a full-height 9:16 window on the
        # middle of the picture. Never a letterboxed 16:9 picture (rico, 2026-10-26: "no format switch").
        return f"[0:v]{face_crop(cx0, zoom, keys=keys, cy=cy0)}[v]"
    if lay == "split":
        top, bottom = sorted(ppl, key=lambda f: f[0])
        return (f"[0:v]split[a][b];[a]{panel_crop(top, cw=panel_w)}[p0];[b]{panel_crop(bottom, cw=panel_w)}[p1];"
                f"[p0][p1]vstack[v]")
    if lay == "center":   # legacy letterbox, kept only so old specs still render; qa_check FAILs it
        return f"[0:v]split[bg][fg];[bg]{BLUR_BG}[b];[fg]scale={W}:-2[f2];[b][f2]overlay=0:(H-h)/2[v]"

    bx, by, bw, bh = ov["box"]
    if lay == "hide":
        # the show's own strip (e.g. a book citation along the bottom) kept out of the crop, nothing added
        return f"[0:v]{face_crop(cx0, zoom, max_h=by - 40, keys=keys, cy=cy0)}[v]"
    # slide: position goes from off-screen to final over SLIDE s, and back out at the end
    prog_in = f"min(1,(t+{t_in:.3f})/{SLIDE})"
    prog_out = f"min(1,max(0,({t_out:.3f}-t)/{SLIDE}))"
    prog = f"min({prog_in},{prog_out})"
    card = f"crop={bw}:{bh}:{bx}:{by}"
    left = bx + bw / 2 < SRC_W / 2          # graphic sits on the left of the source
    if lay == "side":
        # the card takes one side of the frame and the speaker sits in the other third, so the card
        # can never cover the face (v4 put the face at 62% of the width, under a right-hand card:
        # rico, 2026-10-26 "b-roll is blocking his face"). A wide text card gets a wider panel so its
        # words stay readable on a phone.
        pw = 500 if bw / bh < 1.4 else 640
        ph = int(bh * pw / bw) // 2 * 2
        py = 200
        place = 0.72 if pw == 500 else 0.76
        if left:
            px = 24
            base = face_crop(ppl[0][0] if ppl else (bx + bw + SRC_W) / 2 / SRC_W, place=place,
                             left_limit=bx + bw + 40, keys=keys)
            x_expr = f"-{pw}+({px}+{pw})*{prog}"
        else:
            px = W - pw - 24
            base = face_crop(ppl[0][0] if ppl else bx / SRC_W / 2, place=1 - place, right_limit=bx - 40, keys=keys)
            x_expr = f"{W}+({px}-{W})*{prog}"
        return _card_input(f"[0:v]split[a][b];[a]{base}[base];"
                f"[b]{card},scale={pw - 12}:{ph - 12},pad={pw}:{ph}:6:6:white[card];"
                f"[base][card]overlay=x='{x_expr}':y={py}[v]", card_pre)
    if lay == "fit" and ov.get("full"):
        # the whole source frame, full width, over a blurred copy: cinematic shots with burned-in text
        # (never crop through a title card) or with nobody close enough to frame on
        ph = int(SRC_H * W / SRC_W) // 2 * 2
        py = (HC - ph) // 2 - 110
        return f"[0:v]split[a][b];[a]{BLUR_BG}[base];[b]scale={W}:{ph}[card];[base][card]overlay=x=0:y={py}[v]"
    if lay == "fit":
        # the whole graphic, full width, over a blurred copy of itself
        pw = W - 40
        ph = int(bh * pw / bw) // 2 * 2
        py = (HC - ph) // 2 - 80
        if ph > HC - 500:   # tall (phone story): fit the height and keep the captions below it
            ph = HC - 500
            pw = int(bw * ph / bh) // 2 * 2
            py = 20
        px = (W - pw) // 2
        x_expr = f"{W}+20+({px}-{W}-20)*{prog}"
        bg = BLUR_BG if bw / bh >= W / HC else BLUR_BG.replace("scale=-2:" + str(HC), f"scale={W}:-2", 1)
        if card_pre is not None:
            # blurred backdrop from the same clean stretch as the card, so the live picture
            # (the show's own graphic sliding in) never flickers behind it
            return (f"[1:v]{card_pre}split[a][b];[a]{card},{bg}[base];"
                    f"[b]{card},scale={pw - 12}:{ph - 12},pad={pw}:{ph}:6:6:white[card];"
                    f"[base][card]overlay=x='{x_expr}':y={py}[v]")
        return _card_input(f"[0:v]split[a][b];[a]{card},{bg}[base];"
                f"[b]{card},scale={pw - 12}:{ph - 12},pad={pw}:{ph}:6:6:white[card];"
                f"[base][card]overlay=x='{x_expr}':y={py}[v]", card_pre)
    if lay == "banner":
        # speaker framed above the strip (the source's own strip kept out of the crop)
        pw = W - 60
        ph = int(bh * pw / bw) // 2 * 2
        py = 1320                       # under the captions
        base = face_crop(cx0, max_h=by - 60, keys=keys)
        y_expr = f"{HC}+({py}-{HC})*{prog}"
        return _card_input(f"[0:v]split[a][b];[a]{base}[base];"
                f"[b]{card},scale={pw - 12}:{ph - 12},pad={pw}:{ph}:6:6:white[card];"
                f"[base][card]overlay=x=30:y='{y_expr}'[v]", card_pre)
    # bottom: speaker on top half, the card on the bottom half
    lim = dict(left_limit=bx + bw + 60) if left else dict(right_limit=bx - 60)
    top = panel_crop(ppl[0], keys=keys, **lim) if ppl else f"crop={SRC_W // 2}:{SRC_H}:0:0,scale={W}:{HC // 2}"
    pw = W - 80
    ph = int(bh * pw / bw) // 2 * 2
    py = HC // 2 + (HC // 2 - ph) // 2
    y_expr = f"{HC}+({py}-{HC})*{prog}"
    return _card_input(f"[0:v]split[a][b];[a]split[a1][a2];[a1]{top}[t];[a2]{BLUR_BG}[bg];"
            f"[bg][t]overlay=0:0[base];"
            f"[b]crop={bw}:{bh}:{bx}:{by},scale={pw - 12}:{ph - 12},pad={pw}:{ph}:6:6:white[card];"
            f"[base][card]overlay=x=40:y='{y_expr}'[v]", card_pre)


def _card_input(graph, card_pre):
    """With card_pre, the card comes from a second input (a held, fully-on-screen stretch of the
    graphic) instead of the live picture, so the source's own slide in/out never shows in the card."""
    if card_pre is None:
        return graph
    graph = graph.replace("[0:v]split[a][b];[a]", "[0:v]", 1)
    return graph.replace("[b]crop=", f"[1:v]{card_pre}crop=", 1)


def card_source(ov, a, n):
    """(-ss for the second input, filter prefix) holding the graphic within its clean window."""
    c0, c1 = ov["card_window"]
    sp = ov.get("card_speed")
    if sp:
        # slowed card: the clean stretch is stretched over the whole overlay, so it never pauses
        start = c0 + (a - ov["from"]) * sp
        pre = (f"trim=duration={max(c1 - start, 0.05):.3f},setpts=(PTS-STARTPTS)/{sp},"
               f"tpad=stop_mode=clone:stop_duration={n / FPS + 1:.3f},")
        return start, pre
    start = min(max(a, c0), c1 - 0.05)
    hold_before = max(0.0, c0 - a)
    usable = max(c1 - start, 0.05)
    pre = (f"trim=duration={usable:.3f},setpts=PTS-STARTPTS,"
           f"tpad=start_duration={hold_before:.3f}:start_mode=clone:stop_mode=clone:stop_duration={n / FPS + 1:.3f},")
    return start, pre


def loudnorm_pass2(wav):
    """Measure the mix, then return a linear loudnorm (no pumping) that lands at -14 LUFS, -1.5 dBTP."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af",
                          "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
    return (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")


def deflash(video):
    """Remove one- or two-frame white (or black) flashes the show's own b-roll transitions leave
    behind: a frame far brighter or darker than both neighbours is replaced by the frame before it.
    Rewrites the file in place only if a flash was found."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", "scale=64:36,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    luma = np.frombuffer(raw, np.uint8).reshape(-1, 36 * 64).mean(axis=1)
    bad = set()
    for i in range(1, len(luma) - 1):
        for span in (1, 2):
            j = i + span - 1
            if j >= len(luma) - 1:
                continue
            before, after = luma[i - 1], luma[j + 1]
            inside = luma[i:j + 1]
            if (inside.min() > max(before, after) + 40) or (inside.max() < min(before, after) - 40):
                bad.update(range(i, j + 1))
    if not bad:
        return
    fixed = video.with_name("video_deflashed.mp4")
    # drop the flash frames but keep every timestamp: fps= then fills each hole with the frame before it
    sel = "+".join(f"eq(n\\,{i})" for i in sorted(bad))
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vf", f"select='not({sel})',fps={FPS}",
         "-frames:v", str(len(luma)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(fixed)])
    fixed.replace(video)
    print(f"deflash: replaced {len(bad)} flash frame(s) at {', '.join(f'{i / FPS:.2f}s' for i in sorted(bad))}")


# ---------- 3. captions ----------

# caption centre line (full-frame y) per layout: on the seam for stacked layouts, low otherwise
CAP_Y = {"split": TOP + HC // 2, "bottom": TOP + HC // 2, "center": 1500, "side": 1490, "fit": 1500}
CAP_DEFAULT = 1480


ACCENT = ["&H00D7FF&"]   # set per render from the look


def paint(words, hi):
    return " ".join(r"{\c" + ACCENT[0] + "}" + esc(w) + r"{\c&HFFFFFF&}" if norm(w) in hi else esc(w) for w in words)


def title_lines(text, hi, lk=None):
    """Split the title into at most 2 lines at the biggest font size that fits the width (the look's font)."""
    from PIL import ImageFont
    lk = lk or profiles.look(None)
    ffile, top = str(FONTS_DIR / lk["title_file"]), lk["title_max"]
    hi = {norm(h) for h in hi}
    words = text.split()
    # two sentences -> one per line, if that fits at a decent size; otherwise balanced lines
    ends = [i + 1 for i, w in enumerate(words[:-1]) if w[-1] in ".?!"]
    if len(ends) == 1:
        for size in range(top, int(top * 0.68), -2):
            font = ImageFont.truetype(ffile, size)
            a, b = " ".join(words[:ends[0]]), " ".join(words[ends[0]:])
            if font.getlength(a) <= W - 110 and font.getlength(b) <= W - 110:
                return size, r"\N".join(paint(l, hi) for l in (words[:ends[0]], words[ends[0]:]))
    for size in range(top, int(top * 0.5), -2):
        font = ImageFont.truetype(ffile, size)
        fits = lambda t: font.getlength(t) <= W - 110
        best = None
        for i in range(1, len(words) + 1):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            if fits(a) and fits(b):
                score = abs(font.getlength(a) - font.getlength(b))
                if best is None or score < best[0]:
                    best = (score, words[:i], words[i:])
        if best:
            return size, r"\N".join(paint(l, hi) for l in best[1:] if l)
    raise ValueError(f"title too long for 2 lines: {text}")


STUTTER = {"a", "the", "my", "i", "ive", "im", "that", "to", "we", "and", "so", "its", "they", "in", "of", "she",
           "he", "you", "it", "is", "was"}


def clean_caption(texts):
    """Readable captions from a verbatim transcript: drop "uh"/"um" and broken-off fragments ("co-", "h-"),
    drop the trailing dash of an interrupted word, and collapse stutters ("the, the" -> "the").
    Repeats said for emphasis ("totally, totally", "winner, winner") are kept."""
    toks = []                                              # [entry index, token]
    for i, text in enumerate(texts):
        for tok in text.split():
            bare = tok.rstrip(',.?!"')
            if norm(tok) in ("uh", "um"):
                continue                                   # filler sounds stay in the audio, not the captions
            if bare.endswith("-"):
                if len(bare.strip("-")) <= 3 and norm(bare) not in STUTTER:
                    continue                               # "co-", "tw-", "h-"
                tok = bare[:-1] + tok[len(bare):]          # "baseline-" -> "baseline"
            if toks and norm(tok) == norm(toks[-1][1]) and norm(tok) in STUTTER:
                toks.pop()                                 # "the, the owners" -> "the owners"
            toks.append([i, tok])
    # whisper splits numbers and hyphens into their own tokens: "350 ,000" "90 %" "DRILL -IN -ACT" "$ 18"
    fixed = []
    for j, tok in toks:
        glue = re.match(r"^[,%]", tok) or (tok.startswith("-") and len(tok) > 1 and not tok.startswith("--")) or fixed and fixed[-1][1] in ("$", "£", "€")
        if fixed and glue and (fixed[-1][0] == j or re.match(r"^(,\d|%)", tok) or fixed[-1][1] in ("$", "£", "€")):   # "90 %" even across two word entries
            fixed[-1][1] += tok
        else:
            fixed.append([j, tok])
    toks = fixed
    return [" ".join(t for j, t in toks if j == i) for i in range(len(texts))]


SWEAR = re.compile(r"^(fuck\w*|shit\w*|bitch\w*|asshole\w*|cunt\w*|motherfuck\w*|goddamn|dick\w*|pussy)([,.?!\"']*)$", re.I)


def mask_swear(tok):
    """F***ING: the audio keeps the word, the caption keeps the platform happy (default; spec "profanity": "show" turns it off)."""
    m = SWEAR.match(tok)
    if not m:
        return tok
    w = m.group(1)
    return w[0] + "*" * (len(w) - 2) + w[-1] + m.group(2) if len(w) > 3 else w[0] + "*" * (len(w) - 1) + m.group(2)


def phrases(inside, texts, lk):
    """Group words into caption phrases of lk["cap_group"] words: a new phrase at a sentence end, a pause
    over 0.45 s, the word cap, or 1.8 s on screen (rico, 2026-10-28: one word at a time flashed and was unreadable)."""
    lo, hi = lk["cap_group"]
    groups, cur = [], []
    for w, text in zip(inside, texts):
        if not text:
            continue
        if cur:
            gap = w["start"] - cur[-1][0]["end"]
            ended = cur[-1][1].rstrip('"\'')[-1:] in ".?!"
            long = w["end"] - cur[0][0]["start"] > 1.8
            if len(cur) >= hi or gap > 0.45 or long or (ended and len(cur) >= lo):
                groups.append(cur); cur = []
        cur.append((w, text))
    if cur:
        groups.append(cur)
    # a one-word straggler joins the phrase before it when the pause is short
    out = []
    for g in groups:
        if out and len(g) == 1 and len(out[-1]) < hi + 1 and g[0][0]["start"] - out[-1][-1][0]["end"] < 0.45:
            out[-1] = out[-1] + g
        else:
            out.append(g)
    return out


def build_ass(spec, pieces, layouts):
    """pieces: (src_s, src_e, out_off); layouts: (out_s, out_e, layout)."""
    emph = {norm(e) for e in spec.get("emphasis", [])}
    words = json.loads(Path(spec["words"]).read_text())
    total = sum(e - s for s, e, _ in pieces)

    def layout_at(t):
        for a, b, lay in layouts:
            if a <= t < b:
                return lay
        return "face"

    lk = profiles.look(spec.get("style"))
    ACCENT[0] = lk["accent"]
    mask = spec.get("profanity", "mask") != "show"
    hook = " ".join(mask_swear(t) if mask else t for t in spec["hook"].split())
    size, title = title_lines(hook, spec.get("hook_hi", []), lk)
    sp = f"\\fsp{lk['title_spacing']}" if lk.get("title_spacing") else ""
    ev = [f"Dialogue: 2,{ts(0)},{ts(total)},Hook,,0,0,0,,{{\\an5\\pos(540,{TOP // 2 + 4})\\fs{size}{sp}}}{title}"]
    if spec.get("teaser") and spec.get("label"):   # rico dislikes the label: off unless a spec asks
        start_main = pieces[1][2]
        ev.append(f"Dialogue: 2,{ts(start_main)},{ts(start_main + 1.5)},Label,,0,0,0,,"
                  f"{{\\an8\\pos(540,{TOP + 40})}}{esc(spec['label'].upper())}")
    caps = []
    for s, e, off in pieces:
        # a word belongs to this piece only if it starts inside it with time to be heard
        inside = [w for w in words if s - 0.05 <= w["start"] < e - 0.1]
        groups = phrases(inside, clean_caption([w["text"] for w in inside]), lk)
        for gi, group in enumerate(groups):
            ws, we = max(group[0][0]["start"], s), min(group[-1][0]["end"], e)
            # hold each phrase at least 0.6 s (a fast line otherwise flashes), never into the next phrase
            nxt = groups[gi + 1][0][0]["start"] - 0.02 if gi + 1 < len(groups) else e
            we = min(max(we, ws + 0.6), max(nxt, ws + 0.3), e)
            a, b = ws - s + off, we - s + off
            toks = []
            for w, text in group:
                for tok in text.split():
                    if mask:
                        tok = mask_swear(tok)
                    t = esc(tok.upper())
                    if norm(tok) in emph:
                        t = r"{\c" + lk["accent"] + "}" + t + r"{\c&HFFFFFF&}"
                    toks.append(t)
            # one event per layout the caption spans, so it jumps to the right spot with the picture
            edges = sorted({a, b, *[x for x, _, _ in layouts if a < x < b]})
            for a1, b1 in zip(edges, edges[1:]):
                caps.append([a1, b1, f"{{\\an5\\pos(540,{CAP_Y.get(layout_at(a1), CAP_DEFAULT)})}}{' '.join(toks)}"])
    # hold each caption until the next one if the gap is short, so they don't flicker
    for c, nxt in zip(caps, caps[1:]):
        if 0 < nxt[0] - c[1] < 0.4:
            c[1] = nxt[0]
    ev += [f"Dialogue: 1,{ts(a)},{ts(b)},Cap,,0,0,0,,{t}" for a, b, t in caps]
    if spec.get("disclosure"):   # paid-partnership line a brand campaign requires, visible the whole clip
        ev.append(f"Dialogue: 4,{ts(0)},{ts(total)},Disc,,0,0,0,,{{\\an2\\pos(540,{H - 60})}}{esc(spec['disclosure'])}")
    # callouts (PLAYBOOK 26): our own big text card for a number or a name the speaker says, timed in
    # source seconds like overlays. It is text, like the captions, so it is allowed where outside
    # footage is not. Never over a face: below the chin on single layouts, above the top panel on a split.
    for c in spec.get("callouts", []):
        text = esc(c["text"])
        if c.get("sub"):
            text += r"\N{\fs50\c&HFFFFFF&}" + esc(c["sub"])
        for s, e, off in pieces:
            a, b = max(c["from"], s), min(c["to"], e)
            if b - a < 0.3:
                continue
            oa, ob = off + a - s, off + b - s
            lay = layout_at(oa)
            y = TOP + 70 if lay in ("split", "bottom") else CAP_Y.get(lay, CAP_DEFAULT) - 230
            ev.append(f"Dialogue: 3,{ts(oa)},{ts(ob)},Callout,,0,0,0,,{{\\an5\\pos(540,{y})\\fad(150,200)}}{text}")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{lk['cap_font']},{lk['cap_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{lk['cap_bold']},0,0,0,100,100,1,0,1,{lk['outline']},{lk['shadow']},5,70,70,0,1
Style: Hook,{lk['title_font']},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,{lk['title_bold']},0,0,0,100,100,0,0,1,0,0,5,50,50,0,1
Style: Label,{TITLE_FONT},44,&H00000000,&H00000000,&H0000D7FF,&H0000D7FF,0,0,0,0,100,100,2,0,3,12,0,8,80,80,0,1
Style: Callout,{TITLE_FONT},96,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,3,16,0,5,60,60,0,1
Style: Disc,{CAP_FONT},34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,3,10,0,2,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(ev) + "\n", total


def add_sfx(wav, pieces, overlays, tmp):
    """Optional ("sfx": true): a soft, synthesised whoosh (pink noise, 0.45 s, -22 dB) under each card
    as it slides in. Royalty-free by construction. The campaign brief has no rule against sound; rico
    asked (2026-10-26) whether small sounds help: subtle ones on reveals, never on speech."""
    times = []
    for ov in overlays:
        for s, e, off in pieces:
            if s - 0.05 <= ov["from"] < e:
                times.append(off + max(ov["from"] - s, 0))
    if not times:
        return
    whoosh = tmp / "whoosh.wav"
    run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:r=48000:a=0.7",
         "-af", "highpass=f=500,lowpass=f=3000,afade=t=in:d=0.15,afade=t=out:st=0.2:d=0.25,volume=-22dB",
         "-ac", "2", str(whoosh)])
    ins, fc = ["-i", str(wav)], []
    for i, t in enumerate(times):
        ins += ["-i", str(whoosh)]
        ms = int(t * 1000)
        fc.append(f"[{i + 1}:a]adelay={ms}|{ms}[w{i}]")
    fc.append("[0:a]" + "".join(f"[w{i}]" for i in range(len(times))) + f"amix=inputs={len(times) + 1}:normalize=0:duration=first[m]")
    mixed = tmp / "audio_sfx.wav"
    run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[m]",
         "-ar", "48000", "-c:a", "pcm_s16le", str(mixed)])
    mixed.replace(wav)


# ---------- main ----------

def sub_ranges(a, b, marks, min_len=0.6):
    # marks closer than min_len to a shot edge are dropped, so no flash-frame segments
    cuts = sorted({a, b, *[m for m in marks if a + min_len < m < b - min_len]})
    return list(zip(cuts, cuts[1:]))


def main(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    src = spec["source"]
    words = json.loads(Path(spec["words"]).read_text())
    has_teaser = bool(spec.get("teaser"))
    ranges = ([spec["teaser"]] if has_teaser else []) + spec["parts"]
    check_source(src)
    if spec.get("tighten", True):
        n_before = len(ranges)
        ranges = tighten(ranges, words, spec.get("max_gap", 0.7))
        if len(ranges) > n_before:
            print(f"dead air: {len(ranges) - n_before} pause(s) cut")
    ranges = snap(src, ranges, words)
    if has_teaser and spec.get("teaser_exact"):
        ranges[0] = list(spec["teaser"])   # hand-checked cut (e.g. the next speaker starts mid-word)
    ranges = trim_to_cuts(src, ranges, words)
    overlays = spec.get("overlays", [])
    focus = spec.get("focus", [])
    marks = [m for o in overlays for m in (o["from"], o["to"])] + [m for f in focus for m in f]

    pieces, off = [], 0
    for s, e in ranges:
        n = round((e - s) * FPS)
        pieces.append((s, s + n / FPS, off))
        off += n / FPS

    framer = Framer()
    whole_when_lost = not profiles.profile(spec.get("style"))["cards"]   # cinematic / stream / performance
    last_cx, last_shot = None, None
    wide_pair = None   # the two small faces of the wide two-shot, once found in this render
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segs, layouts = [], []
        for pi, (s, e, poff) in enumerate(pieces):
            # pieces alternate a light punch-in (1.0 / 1.06), so every join between two moments or
            # across a cut pause reads as an edit, not a glitch
            piece_zoom = 1.0 if pi % 2 == 0 else 1.06
            for sh in analyze_shots.shots(src, s, e):
                subs = sub_ranges(max(sh["start"], s), min(sh["end"], e), marks)
                for w in spec.get("video_swap", []):   # always split where a swap ends
                    subs = [r for a, b in subs for r in (((a, w[1]), (w[1], b)) if a < w[1] < b else ((a, b),))]
                for a, b in subs:
                    n = round((b - a) * FPS)
                    if n <= 0:
                        continue
                    mid = (a + b) / 2
                    # stray shot after a jump: show other frames of the speaker instead (audio stays)
                    sw = next((w for w in spec.get("video_swap", []) if w[0] - 0.05 <= a < w[1]), None)
                    vs = sw[2] + (a - sw[0]) if sw else a
                    ov = next((o for o in overlays if o["from"] <= mid < o["to"]), None)
                    zoom = 1.17 if any(f[0] <= mid < f[1] for f in focus) else piece_zoom
                    keys, panel_w, small_used = None, 630, False
                    same_shot = last_shot is not None and abs(last_shot - sh["start"]) < 0.01
                    if ov and ov["style"] == "hide" and not people(analyze_shots.faces_in(src, a, b), box=ov["box"]):
                        ov = None      # nobody to crop the strip away from (wide shot, b-roll): frame as usual
                    if ov:
                        ppl = people(analyze_shots.faces_in(src, a, b), box=ov["box"])[:1]
                        lay = ov["style"]
                        t_in, t_out = a - ov["from"], ov["to"] - a
                    else:
                        part_of_shot = (b - a) < (sh["end"] - sh["start"]) - 0.1   # e.g. after a b-roll
                        # a piece of a long shot gets its own face position (the speaker may have moved)
                        ppl = people(analyze_shots.faces_in(src, vs, vs + b - a) if sw or part_of_shot else sh["faces"])
                        if len(ppl) == 2 and (sh["end"] - sh["start"]) < MIN_SPLIT:
                            ppl = [talker(ppl)]   # short two-person shot: crop on whoever is speaking
                        if not ppl:
                            # nobody big: the wide two-shot? (faces ~45 px) -> stacked split on both people.
                            # If the detector misses one of them (dark set, a turned head) fall back to the
                            # pair found earlier in this render, then to the spec's "wide_split", so the
                            # window never lands on an empty room (rico, 2026-10-26: v1 MM-005/006 showed
                            # 6 s of empty room where the wide shot was cropped down the middle).
                            # the whole shot, not this piece of it: the pair does not move and the result is cached
                            small = analyze_shots.small_faces(src, *((vs, vs + b - a) if sw else (sh["start"], sh["end"])))
                            small_used = True
                            fixed = [tuple(p) for p in spec.get("wide_split", [])]
                            if len(small) == 2 and len(fixed) == 2 and any(
                                    min(abs(f[0] - q[0]) for f in fixed) > 0.12 for q in small):
                                small = []      # a face in the show's photo card + a false hit: not the two people
                            if len(small) == 2 and abs(small[0][0] - small[1][0]) > 0.3:
                                ppl, panel_w = small, 520
                                wide_pair = list(small)
                            else:
                                pair = wide_pair or fixed
                                if len(pair) == 2:
                                    ppl, panel_w = pair, 520
                                elif len(small) == 1:
                                    ppl = small
                        lay = "split" if len(ppl) == 2 else "face" if ppl else "wide"
                        t_in = t_out = 0
                        if whole_when_lost:
                            # trailers and scene clips: never crop through burned-in text; nobody close = whole frame
                            tb = analyze_shots.text_box(src, vs, vs + b - a)
                            if tb or lay == "wide" or small_used:   # a two-shot found by the small-face pass is not split on movies: whole frame
                                ov = {"box": [0, 0, SRC_W, SRC_H], "style": "fit", "from": a, "to": b, "full": True, "hard_out": True}
                                lay, ppl, t_in, t_out = "fit", [], 1e6, 1e6
                    if lay in ("face", "side", "bottom", "banner", "hide") and ppl and ppl[0][2] >= 0.1:
                        keys, _ = pan_keys(src, vs, vs + b - a, box=ov["box"] if ov else None,
                                           start_cx=last_cx if same_shot else None)
                        if keys:
                            ppl = [(keys[0][1], ppl[0][1], ppl[0][2])] + ppl[1:]
                            last_cx = keys[-1][1]
                    if ppl and not keys:
                        ppl = [(framer.x(p[0]), p[1], p[2]) for p in ppl]
                    last_shot = sh["start"]
                    extra, card_pre = [], None
                    if ov and ov.get("card_window"):
                        c_ss, card_pre = card_source(ov, a, n)
                        extra = ["-ss", f"{c_ss:.3f}", "-i", src]
                    if ov and ov.get("hard_out"):
                        t_out = 1e6   # leave on the camera cut instead of sliding out (no half-gone card)
                    graph = build_filter(lay, ppl, zoom, ov, t_in, t_out, card_pre, keys=keys, panel_w=panel_w)
                    fades = []
                    if spec.get("teaser_cut"):
                        pass   # straight cut out of the teaser, no dip
                    elif has_teaser and pi == 0 and abs(b - e) < 0.05:
                        fades.append(f"fade=out:st={max(n / FPS - 0.15, 0):.3f}:d=0.15:color=black")
                    if has_teaser and pi == 1 and abs(a - s) < 0.05:
                        fades.append("fade=in:st=0:d=0.15:color=black")
                    if fades:
                        graph = graph[:-3] + "[pre];[pre]" + ",".join(fades) + "[v]"
                    out = tmp / f"v{len(segs):03d}.mp4"
                    run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{vs:.3f}", "-i", src, *extra,
                         "-filter_complex", graph, "-map", "[v]", "-an", "-r", str(FPS), "-frames:v", str(n),
                         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p", str(out)])
                    o = poff + (a - s)
                    layouts.append((o, o + n / FPS, lay + ("+zoom" if zoom > 1 and lay == "face" else "")))
                    segs.append(out)
        (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in segs))
        run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-c", "copy", str(tmp / "video.mp4")])
        deflash(tmp / "video.mp4")

        # audio: each piece with short fades so joins don't click; a softer fade at the very end
        ins, fc = [], []
        for i, (s, e, _) in enumerate(pieces):
            d = e - s
            tail = 0.25 if i == len(pieces) - 1 else 0.06
            ins += ["-ss", f"{s:.3f}", "-t", f"{d:.3f}", "-i", src]
            fc.append(f"[{i}:a]asetpts=PTS-STARTPTS,afade=in:d=0.04,afade=out:st={d - tail:.3f}:d={tail}[a{i}]")
        fc.append("".join(f"[a{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[cat]")
        run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[cat]",
             "-ar", "48000", "-c:a", "pcm_s16le", str(tmp / "audio_raw.wav")])
        # loudnorm works at 192 kHz inside and the resample back can leave bunched or jumping packet
        # timestamps (rico heard Kylie's first 2 s sped up on YouTube, 2026-10-26). So: normalise into a
        # wav (no timestamps to get wrong), then encode that wav to AAC plainly.
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "audio_raw.wav"), "-af", loudnorm_pass2(tmp / "audio_raw.wav"),
             "-ar", "48000", "-c:a", "pcm_s16le", str(tmp / "audio_norm.wav")])
        if spec.get("sfx"):
            add_sfx(tmp / "audio_norm.wav", pieces, overlays + list(spec.get("callouts", [])), tmp)
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "audio_norm.wav"),
             "-c:a", "aac", "-b:a", "160k", str(tmp / "audio.m4a")])

        layouts_simple = [(a, b, l.split("+")[0]) for a, b, l in layouts]
        ass, total = build_ass(spec, pieces, layouts_simple)
        (tmp / "caps.ass").write_text(ass)
        Path(spec["out"]).with_suffix(".ass").write_text(ass)   # kept for qa_check.py
        pre = ""
        if spec.get("hold_end_from"):
            # the show cuts away (wipe, wide shot) under the last words: hold the speaker's last
            # clean frame and fade the picture out; captions stay live on top
            h = spec["hold_end_from"]
            pre = (f"trim=end={h:.3f},setpts=PTS-STARTPTS,tpad=stop_duration={total - h + 0.1:.3f}:stop_mode=clone,"
                   f"fade=out:st={h - 0.1:.3f}:d={total - h + 0.1:.3f},")
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp / "video.mp4"), "-i", str(tmp / "audio.m4a"),
             "-vf", f"{pre}pad={W}:{H}:0:{TOP}:color=0x0E0E0E,ass={tmp / 'caps.ass'}:fontsdir={FONTS_DIR}", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart",
             spec["out"]])
        Path(spec["out"]).with_suffix(".layout.json").write_text(json.dumps(
            {"cuts": ranges, "shots": [{"from": round(a, 2), "to": round(b, 2), "layout": l}
                                       for a, b, l in layouts]}, indent=1))
    print(f"rendered {spec['out']} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
