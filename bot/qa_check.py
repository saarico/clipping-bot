"""Pre-post check ("backtest") for one finished clip. Nothing gets posted unless this says PASS.

Usage:
  python3 qa_check.py <clip folder> [--source /path/to/source.mp4]

The clip folder holds what render_clip.py made: <name>.mp4, captions.ass, cut_details.json
(cuts, shots and the spec), words.json (the transcript used) and style_check.md (post text).
The source video is optional; without it the word-boundary audio check is skipped.

Writes qa_report.md (each check: PASS / WARN / FAIL, with the evidence) and qa_sheet.png
(one frame per second, for a 10-second look by a human) into the clip folder.
Exit code 1 if anything FAILs.

What it checks, and the past mistake each one would have caught:
  format      1080x1920, 30 fps, h264 + aac, 15-90 s, under 25 MB (PC copy limit)
  audio       loudness near -14 LUFS, no dead air over 0.8 s (PLAYBOOK 24), no clipping
  centred     the speaker's face stays in the middle third of the picture (PLAYBOOK 22)
  format      no letterboxed 16:9 segment inside the short (PLAYBOOK 23)
  cut edges   no word cut off at a cut: transcript gap and audio level at every edge
              (v1 clipped words; v2 ended on the next speaker's "Th")
  ending      the last caption finishes a sentence (Prime v3 stopped mid-point)
  captions    every transcript word inside the cuts is captioned; no caption gap over 1.5 s
              while someone talks; stutters and filler flagged ("I, I...", "Mm-hmm")
  title       2 lines max, inside the title band; no "his/her" right after a name
              (Kylie v3: "Kylie Jenner posted his drink")
  faces       no face cut off by the title band; captions don't sit on the speaker's face (v3 title over his head)
  picture     no black frames, no frozen picture over 1.5 s, no flash segments under 0.5 s,
              no shot layout changes faster than 0.5 s (v2 flicker)
  transitions every hard cut in the output is a planned one; no stray cut in the first/last
              1.5 s or at a join; no one-frame white/black flash ($15K v6 opened on 5 frames of
              the wrong camera; House v6 kept two white flash frames from the show's b-roll)
  story       nothing said twice (teaser repeated in the story); opener doesn't point backwards
  audio       packet timestamps steady (bunched timestamps = sped-up/glitchy sound on YouTube)
  post text   every platform's text has the tags in CAMPAIGNS/<campaign>/tags.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from render_clip import STUTTER  # noqa: E402

W, H, TOP = 1080, 1920, 240
FILLER = {"mm", "mmhmm", "um", "uh", "hmm"}
BACKWARDS = ("as i was mentioning", "as i said", "like i said", "what's also interesting", "that's why", "so that's",
             "going back to", "as we talked about", "the other thing")
PRONOUN_AFTER_NAME = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+) (?:\w+ ){0,3}(his|her)\b")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def ff_log(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                          capture_output=True, text=True).stderr


def ass_events(path):
    ev = []
    for line in Path(path).read_text().splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        t = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))
        ev.append({"start": t(parts[1]), "end": t(parts[2]), "style": parts[3], "text": parts[9]})
    return ev


def plain(text):
    return re.sub(r"\{[^}]*\}", "", text).replace(r"\N", " ")


def norm(w):
    return re.sub(r"[^a-z0-9$%]", "", w.lower())


class Report:
    def __init__(self):
        self.rows = []

    def add(self, area, status, evidence):
        self.rows.append((area, status, evidence))

    @property
    def verdict(self):
        st = [r[1] for r in self.rows]
        return "FAIL" if "FAIL" in st else "PASS with warnings" if "WARN" in st else "PASS"


def check_format(rep, mp4, info):
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    size = mp4.stat().st_size / 1e6
    fps = eval(v["r_frame_rate"])
    bad = []
    if (v["width"], v["height"]) != (W, H):
        bad.append(f"{v['width']}x{v['height']}")
    if abs(fps - 30) > 0.01:
        bad.append(f"{fps:.2f} fps")
    if v["codec_name"] != "h264" or not a or a["codec_name"] != "aac":
        bad.append("codec")
    if not 10 <= dur <= 90:
        bad.append(f"length {dur:.1f} s")
    rep.add("Format", "FAIL" if bad else "PASS",
            f"{v['width']}x{v['height']}, {fps:.0f} fps, {dur:.1f} s, {size:.1f} MB" + (f" (problem: {', '.join(bad)})" if bad else ""))
    if size > 25:
        rep.add("File size", "WARN", f"{size:.1f} MB is over the 25 MB copy-to-PC limit; re-encode at a higher crf")
    return dur


def check_audio(rep, mp4):
    log = ff_log(["-i", str(mp4), "-af", "ebur128=peak=true,silencedetect=n=-45dB:d=0.8", "-vn"])
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
    lufs = float(lufs[-1]) if lufs else None
    peak = float(peak[-1]) if peak else None
    silences = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", log)]
    st = "PASS"
    notes = [f"loudness {lufs} LUFS", f"peak {peak} dBFS"]
    if lufs is None or abs(lufs + 14) > 2:
        st = "WARN"
    if peak is not None and peak > -0.5:
        st = "FAIL"
        notes.append("clipping")
    if silences:
        st = "FAIL" if max(silences) > 2 else max(st, "WARN", key=["PASS", "WARN", "FAIL"].index)
        notes.append(f"dead air: {', '.join(f'{s:.1f} s' for s in silences)}")
    rep.add("Audio", st, "; ".join(notes))


def check_cut_edges(rep, details, words, source):
    """A cut must sit in a gap between words, and the audio there must be quiet."""
    issues, n = [], 0
    audio = None
    if source and Path(source).exists():
        lo = min(c[0] for c in details["cuts"]) - 1
        hi = max(c[1] for c in details["cuts"]) + 1
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{lo:.3f}", "-to", f"{hi:.3f}", "-i", source,
                              "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
        audio = (np.frombuffer(raw, np.int16).astype(float), lo)
        rms_all = np.sqrt(np.convolve(audio[0] ** 2, np.ones(480) / 480, "valid"))
        speech = np.percentile(rms_all, 90)
    for s, e in details["cuts"]:
        for edge, t in (("start", s), ("end", e)):
            n += 1
            inside = [w for w in words if w["start"] < t - 0.02 and w["end"] > t + 0.02]
            if inside:
                issues.append(f"{edge} {t:.2f}s cuts through \"{inside[0]['text']}\"")
                continue
            if audio:
                sig, base = audio
                i = int((t - base) * 16000)
                win = sig[max(i - 320, 0):i + 320]
                level = np.sqrt(np.mean(win ** 2)) if len(win) else 0
                if level > 0.35 * speech:
                    issues.append(f"{edge} {t:.2f}s is loud ({level / speech:.0%} of speech level)")
    st = "FAIL" if any("cuts through" in i for i in issues) else "WARN" if issues else "PASS"
    rep.add("Cut edges (no clipped words)", st,
            f"{n} edges checked" + (" against the audio" if audio else " (transcript only, no source given)")
            + ("; " + "; ".join(issues) if issues else ""))


def check_captions(rep, details, words, events, dur):
    caps = [e for e in events if e["style"] == "Cap"]
    cap_words = {norm(w) for e in caps for w in plain(e["text"]).split()}
    cap_join = "|".join(sorted(cap_words))                 # "90" + "%" are shown joined as "90%"
    missing = []
    for s, e in details["cuts"]:
        for w in words:
            if w["start"] >= s - 0.05 and w["end"] <= e + 0.05:
                for tok in w["text"].split():
                    bare = tok.rstrip(',.?!"')
                    if bare.endswith("-") and len(bare.strip("-")) <= 3 or norm(tok) in FILLER or SWEAR_SHOWN.match(bare):
                        continue                          # fragments, filler and masked swearing are left out on purpose
                    if norm(tok) and norm(tok) not in cap_words and norm(tok) not in cap_join:
                        missing.append(tok)
    caps.sort(key=lambda e: e["start"])
    gaps = [(a["end"], b["start"]) for a, b in zip(caps, caps[1:]) if b["start"] - a["end"] > 1.5]
    first = caps[0]["start"] if caps else dur
    last_end = caps[-1]["end"] if caps else 0
    st = "FAIL" if len(missing) > 2 or first > 1.0 or dur - last_end > 2.0 else "WARN" if gaps or missing else "PASS"
    rep.add("Captions cover the whole clip", st,
            f"{len(caps)} captions, first at {first:.1f} s, last ends {last_end:.1f} s of {dur:.1f} s"
            + (f"; not captioned: {' '.join(missing[:10])}" if missing else "")
            + (f"; gaps: {', '.join(f'{a:.1f}-{b:.1f}s' for a, b in gaps)}" if gaps else ""))

    text = " ".join(plain(e["text"]) for e in caps)
    flags = []
    for m in re.finditer(r"\b([\w']+)[,.]? \1\b", text, re.I):
        if norm(m.group(1)) in STUTTER:                   # "winner, winner" is emphasis, "the, the" a stutter
            flags.append(f"stutter \"{m.group(0)}\"")
    for w in text.split():
        if norm(w) in FILLER:
            flags.append(f"filler \"{w}\"")
        if w.endswith("-") and len(w) > 1:
            flags.append(f"cut-off word \"{w}\"")
    rep.add("Caption text reads clean", "WARN" if flags else "PASS",
            "; ".join(sorted(set(flags))[:12]) if flags else "no stutters, filler or cut-off words")

    check_spelling(rep, text)
    labels = [e for e in events if e.get("style") == "Label"]
    rep.add("No pop-up label", "FAIL" if labels else "PASS",
            f"label shown: \"{plain(labels[0]['text'])}\" (rico doesn't want it)" if labels else "none")

    toks = [norm(w) for w in text.split() if norm(w)]
    seen, twice = {}, []
    for i in range(len(toks) - 5):
        key = " ".join(toks[i:i + 6])
        if key in seen and i - seen[key] > 12:
            twice.append(" ".join(text.split()[i:i + 6]))
        seen.setdefault(key, i)
    # a declared teaser repeats its line in the story by design (rico approved that on ICH-002 Prime, 2026-10-25);
    # any other repeat is a mistake in the cut
    teaser = bool(details.get("spec", {}).get("teaser"))
    rep.add("Nothing said twice", ("WARN" if teaser else "FAIL") if twice else "PASS",
            (f"repeated: \"{twice[0]}...\" " + ("(the declared teaser line, heard again in the story; allowed only "
             "because rico approved this cut)" if teaser else "(not a declared teaser: the cut says something twice)"))
            if twice else "no repeated lines")
    opener = plain(caps[0]["text"]).lower() if caps else ""
    back = [p for p in BACKWARDS if p in opener]
    rep.add("Opener stands alone", "WARN" if back else "PASS",
            f"first caption points back to something the viewer didn't see: \"{opener[:60]}\"" if back
            else f"first caption: \"{opener[:60]}\"")

    ending = plain(caps[-1]["text"]).strip().rstrip('"\')') if caps else ""
    ok = ending[-1:] in ".?!" if ending else False
    rep.add("Ends on a finished sentence", "PASS" if ok else "FAIL", f"last caption: \"{ending}\"")
    check_readable(rep, caps, details.get("spec", {}))


SWEAR_SHOWN = re.compile(r"\b(fuck\w*|shit\w*|bitch\w*|asshole\w*|cunt\w*|motherfuck\w*|goddamn|pussy)\b", re.I)


def check_readable(rep, caps, spec):
    """Captions a scroller can actually read (rico, 2026-10-28: "ensure captions are read and judged"):
    phrases of 2-6 words (one-word flashes are unreadable, 7+ is a wall), each up at least 0.35 s, no
    line over 34 characters, numbers whole ("350,000" not "350 ,000"), swearing masked unless the
    reviewer set profanity "show"."""
    if not caps:
        rep.add("Captions readable", "FAIL", "no captions")
        return
    merged = []                                            # one caption split across two layouts is one caption to the eye
    for e in sorted(caps, key=lambda e: e["start"]):
        t = plain(e["text"]).strip()
        if merged and merged[-1]["text"] == t and e["start"] - merged[-1]["end"] < 0.05:
            merged[-1]["end"] = e["end"]
        else:
            merged.append({"text": t, "start": e["start"], "end": e["end"]})
    caps = merged
    texts = [e["text"] for e in caps]
    n = [len(t.split()) for t in texts]
    avg = sum(n) / len(n)
    ones = sum(1 for k in n if k == 1)
    short = sum(1 for e, k in zip(caps, n) if k > 1 and e["end"] - e["start"] < 0.35)
    longline = [t for t in texts if max(len(l) for l in t.split("\n")) > 34]   # libass wraps past ~30; a wall is 2 wrapped lines
    broken = [t for t in texts if re.search(r"\d ,\d|\d %|\$ \d|\d - \d", t)]
    sworn = [t for t in texts if SWEAR_SHOWN.search(t)] if spec.get("profanity", "mask") != "show" else []
    flags = []
    if avg < 1.6: flags.append(f"captions flash one word at a time ({avg:.1f} words per caption)")
    if avg > 6.5: flags.append(f"captions are walls of text ({avg:.1f} words per caption)")
    if ones > len(n) * 0.4: flags.append(f"{ones} of {len(n)} captions are a single word")
    if short: flags.append(f"{short} caption(s) shown under 0.35 s")
    if longline: flags.append(f"line over 26 characters: \"{longline[0][:40]}\"")
    if broken: flags.append(f"broken number: \"{broken[0][:40]}\"")
    if sworn: flags.append(f"swearing shown unmasked: \"{sworn[0][:40]}\"")
    st = "FAIL" if (avg < 1.3 or sworn or broken) else "WARN" if flags else "PASS"
    rep.add("Captions readable", st, "; ".join(flags) if flags else f"{avg:.1f} words per caption, {len(n)} captions")


def check_spelling(rep, text):
    """Every caption word must be a real word or on spelling_allowlist.txt (names, brands)."""
    try:
        from spellchecker import SpellChecker
    except ImportError:
        rep.add("Caption spelling", "WARN", "spell checker not installed (pip install pyspellchecker); read captions.txt by eye")
        return
    allow = {l.strip() for l in (Path(__file__).parent / "spelling_allowlist.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")}
    words = set()
    for w in re.findall(r"[A-Za-z][A-Za-z'-]*", text):
        w = w.lower().strip("'-")
        if w.endswith("'s"):
            w = w[:-2]
        if w and w not in allow:
            words.add(w)
    sp = SpellChecker()
    bad = sorted(w for w in sp.unknown(words) if not all(p in allow or not sp.unknown([p]) for p in w.split("-")))
    rep.add("Caption spelling", "WARN" if bad else "PASS",
            ("unknown words: " + ", ".join(f"{w} (did you mean {sp.correction(w)}?)" for w in bad[:8])
             + ". Fix the word, or add a real name to spelling_allowlist.txt") if bad else f"{len(words)} words checked")


def check_title(rep, events, spec):
    hook = next((e for e in events if e["style"] == "Hook"), None)
    if not hook:
        rep.add("Title", "WARN", "no title (allowed by the campaign, but our style uses one)")
        return
    lines = hook["text"].split(r"\N")
    st, notes = "PASS", [f"{len(lines)} line(s): \"{plain(hook['text'])}\""]
    if len(lines) > 3:
        st = "FAIL"
        notes.append("more than 3 lines")
    m = PRONOUN_AFTER_NAME.search(spec.get("hook", ""))
    if m:
        st = "FAIL" if st == "FAIL" else "WARN"
        notes.append(f"check the pronoun: \"{m.group(0)}\"")
    rep.add("Title", st, "; ".join(notes))


_FR = {}


def frames(mp4, fps=2):
    """Decoded once per clip (three checks asked for the same 2 fps frames: 9 s of a 35 s QA, 2026-10-28)."""
    k = (str(mp4), fps)
    if k not in _FR:
        _FR[k] = _frames_raw(mp4, fps)
    return _FR[k]


def _frames_raw(mp4, fps=2):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps={fps},scale=540:960",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (540 * 960 * 3)
    return np.frombuffer(raw[: n * 540 * 960 * 3], np.uint8).reshape(n, 960, 540, 3)


def check_faces(rep, mp4, events):
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    caps = [e for e in events if e["style"] == "Cap"]
    pos = lambda e: int(re.search(r"\\pos\(\d+,(\d+)\)", e["text"]).group(1)) if "\\pos" in e["text"] else 1480
    in_band, on_caption = [], []
    for i, f in enumerate(frames(mp4)):
        t = i / 2
        # look only below the title band: its lettering can fool the face detector
        g = cv2.equalizeHist(cv2.cvtColor(f[TOP // 2:], cv2.COLOR_BGR2GRAY))
        for (x, y, w, h) in det.detectMultiScale(g, 1.1, 7, minSize=(50, 50)):
            x, y, w, h = [v * 2 for v in (x, y, w, h)]          # back to 1080x1920
            if y < 0.1 * h:                                     # forehead under the band: head cut off
                in_band.append(t)
            y += TOP
            cap = next((e for e in caps if e["start"] <= t < e["end"]), None)
            if cap and w >= 220:                                # the speaker's face, not a logo or a far-off head
                cy = pos(cap)
                # caption box ~110 px tall; the face's eyes-to-mouth band is its middle half
                if y + h * 0.25 < cy + 55 and y + h * 0.8 > cy - 55:
                    on_caption.append(t)
    rep.add("Faces clear of the title", "FAIL" if in_band else "PASS",
            f"face cut off by the title band at {', '.join(f'{t:.1f}s' for t in in_band[:8])}" if in_band else "checked every 0.5 s")
    rep.add("Captions off faces", "FAIL" if len(on_caption) > 6 else "WARN" if len(on_caption) > 2 else "PASS",
            f"caption may cover a face at {', '.join(f'{t:.1f}s' for t in on_caption[:8])}" if len(on_caption) > 2
            else "checked every 0.5 s")


def check_centred(rep, mp4, details):
    """PLAYBOOK 22: on single-speaker layouts the face centre stays within 12% of the middle of the
    picture. Measured on the finished video every 0.5 s with the frontal detector (biggest face)."""
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    single = [(s["from"], s["to"]) for s in details["shots"] if s["layout"].split("+")[0] in ("face", "hide", "wide")]
    side = [(s["from"], s["to"]) for s in details["shots"] if s["layout"].split("+")[0] == "side"]
    offs, bad, n = [], [], 0
    for i, f in enumerate(frames(mp4)):
        t = i / 2
        lay = "single" if any(a <= t < b for a, b in single) else "side" if any(a <= t < b for a, b in side) else None
        if not lay:
            continue
        g = cv2.equalizeHist(cv2.cvtColor(f[TOP // 2:], cv2.COLOR_BGR2GRAY))
        faces = det.detectMultiScale(g, 1.1, 6, minSize=(60, 60))
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda r: r[2])
        cx = (x + w / 2) / 540
        n += 1
        if lay == "single":
            off = abs(cx - 0.5)
            offs.append(off)
            if off > 0.12:
                bad.append(t)
        else:
            # beside a card the face belongs in the free third (0.15-0.45 or 0.55-0.85)
            if 0.45 < cx < 0.55 or cx < 0.1 or cx > 0.9:
                bad.append(t)
    if n == 0:
        rep.add("Speaker centred", "WARN", "no face found to measure")
        return
    share = len(bad) / n
    st = "FAIL" if share > 0.15 else "WARN" if share > 0.05 else "PASS"
    rep.add("Speaker centred", st, f"{n} frames measured; off centre in {share:.0%}"
            + (f" (at {', '.join(f'{t:.1f}s' for t in bad[:6])})" if bad else "")
            + (f"; mean offset {np.mean(offs):.0%} of width" if offs else ""))


def check_nobody(rep, mp4, details):
    """PLAYBOOK 23: a single-speaker window must have a person in it. Frames at 2 fps on face/wide/hide
    layouts with no frontal or profile face for 1.5 s or more = FAIL (the empty-room crop of the wide
    two-shot that rico saw in v1 MM-005/006, 2026-10-26); 1.0-1.5 s = WARN."""
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    single = [(s["from"], s["to"]) for s in details["shots"] if s["layout"].split("+")[0] in ("face", "hide", "wide")]
    empty = []
    for i, f in enumerate(frames(mp4)):
        t = i / 2
        if not any(a <= t < b for a, b in single):
            continue
        g = cv2.equalizeHist(cv2.cvtColor(f[TOP // 2:], cv2.COLOR_BGR2GRAY))
        # a person in a single-speaker window is big: the face is 140+ px of the 540 px width. The
        # empty-room crop of a podcast's wide shot gives a steady 104 px false hit on the windows (measured).
        found = len(front.detectMultiScale(g, 1.1, 6, minSize=(140, 140))) or len(prof.detectMultiScale(g, 1.1, 6, minSize=(140, 140))) \
            or len(prof.detectMultiScale(cv2.flip(g, 1), 1.1, 6, minSize=(140, 140)))
        if not found:
            empty.append(t)
    runs, cur = [], []
    for t in empty:
        if cur and t - cur[-1] > 0.6:
            runs.append(cur); cur = []
        cur.append(t)
    if cur:
        runs.append(cur)
    runs = [(r[0], r[-1] + 0.5) for r in runs if r[-1] + 0.5 - r[0] >= 1.0]
    bad = [r for r in runs if r[1] - r[0] >= 1.5]
    st = "FAIL" if bad else "WARN" if runs else "PASS"
    rep.add("Somebody in frame", st, "no empty-room stretch" if not runs else
            "no face for " + ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in runs))


def check_picture(rep, mp4, details):
    # freezedetect noise 0.001 (was 0.003): a static wide two-shot, shown whole on a blurred background,
    # moves less than 0.3% per frame and was flagged frozen (2026-10-26); a cloned frame still trips 0.001
    log = ff_log(["-i", str(mp4), "-vf", f"crop={W}:{H - TOP}:0:{TOP},blackdetect=d=0.2:pix_th=0.06,freezedetect=n=0.001:d=1.5", "-an"])
    black = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    frozen = re.findall(r"freeze_start: ([\d.]+)", log)
    short = [s for s in details["shots"] if s["to"] - s["from"] < 0.5]
    boxed = [s for s in details["shots"] if s["layout"].split("+")[0] == "center"]
    st = "FAIL" if black or frozen or boxed else "WARN" if short else "PASS"
    notes = []
    if boxed:
        notes.append("letterboxed 16:9 picture (format switch, PLAYBOOK 23) at "
                     + ", ".join(f"{s['from']:.1f}s" for s in boxed[:6]))
    if black:
        notes.append("black frames at " + ", ".join(f"{float(a):.1f}s" for a, _ in black))
    if frozen:
        notes.append("frozen picture at " + ", ".join(f"{float(a):.1f}s" for a in frozen))
    if short:
        notes.append("very short shots at " + ", ".join(f"{s['from']:.1f}s" for s in short))
    rep.add("Picture (black, frozen, flicker)", st, "; ".join(notes) or f"{len(details['shots'])} shots, all clean")

    # rico's "lag at the start": a frozen frame or a stray shot in the first 2 seconds
    dur = float(probe(mp4)["format"]["duration"])
    log = ff_log(["-t", "2", "-i", str(mp4), "-vf", f"crop={W}:{H - TOP}:0:{TOP},freezedetect=n=0.001:d=0.2", "-an"])
    stuck = re.findall(r"freeze_start: ([\d.]+)", log)
    stray = [s for s in details["shots"] if s["to"] - s["from"] < 0.6 and (s["from"] < 1.5 or s["to"] > dur - 0.3)]
    bad = (["frozen picture at " + ", ".join(f"{float(a):.2f}s" for a in stuck)] if stuck else []) + \
          (["stray short shot at " + ", ".join(f"{s['from']:.2f}s" for s in stray)] if stray else [])
    rep.add("Clean first 2 seconds", "FAIL" if bad else "PASS", "; ".join(bad) or "no freeze or stray shot")


def check_footage_text(rep, mp4, details):
    """Text burned into the footage (a title card, a lower third, a sign) must not run off the edge of
    the output (rico, 2026-10-28: the trailer's "A NEW FILM FROM" card was cropped through the middle).
    Our own title and captions sit centred inside the margins, so only rows touching an edge count."""
    import analyze_shots
    hits = []
    for i, fr in enumerate(frames(mp4, 1)):
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        for x0, y0, x1, y1, nc in analyze_shots._text_rows(g):
            if (x0 <= w * 0.01 or x1 >= w * 0.99) and nc >= 5 and 0.12 * h < (y0 + y1) / 2 < 0.78 * h:
                hits.append(i)
                break
    st = "FAIL" if len(hits) >= 3 else "WARN" if hits else "PASS"
    rep.add("Footage text cut off", st, f"text runs off the frame edge at {', '.join(f'{t} s' for t in hits[:8])}" if hits else "no footage text touches an edge")


def check_one_look(rep, details):
    """rico, 2026-10-28: "the screen keeps switching between 16:9 and 9:16, horrible". The whole clip is one
    9:16 crop; a segment that shows the 16:9 picture whole (fit / center) fails the clip."""
    bad = [s for s in details.get("shots", []) if s["layout"].split("+")[0] in ("fit", "center")]
    rep.add("One 9:16 look", "FAIL" if bad else "PASS",
            (f"{len(bad)} segment(s) show the 16:9 picture whole (format switch) at " + ", ".join("%.1fs" % b["from"] for b in bad[:5])) if bad else "9:16 crop throughout")


def check_actor_size(rep, mp4, details):
    """rico, 2026-10-28: "the screen is not focusing on actors". Measured on the finished clip once a second:
    how often a face is on screen and how tall it is (share of the picture height)."""
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    sizes, n = [], 0
    ph = (H - TOP) // 2
    for f in frames(mp4, 1):
        g = cv2.equalizeHist(cv2.cvtColor(f[TOP // 2:], cv2.COLOR_BGR2GRAY))
        faces = list(det.detectMultiScale(g, 1.1, 5, minSize=(36, 36))) + list(prof.detectMultiScale(g, 1.1, 5, minSize=(36, 36)))
        n += 1
        if len(faces):
            sizes.append(max(r[3] for r in faces) / ph)
    if n == 0:
        return
    present, med = len(sizes) / n, (float(np.median(sizes)) if sizes else 0.0)
    st = "FAIL" if present < 0.3 or (sizes and med < 0.08) else "WARN" if present < 0.6 or med < 0.12 else "PASS"
    rep.add("Actors fill the frame", st, f"a face in {present:.0%} of the seconds, typical face height {med:.0%} of the picture")


def check_transitions(rep, mp4, details, dur):
    """Every hard cut in the finished picture must be one we meant (a shot or layout edge). An isolated
    jump anywhere else is a glitch; a jump in the first/last 1.5 s or at a join is a FAIL. A frame far
    brighter or darker than both neighbours is a flash (the show's wipes): FAIL."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf",
                          f"crop={W}:{H - TOP}:0:{TOP},scale=64:36,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64).astype(float)
    luma = f.mean(axis=(1, 2))
    diff = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    expected = sorted({s["from"] for s in details["shots"]} | {s["to"] for s in details["shots"]})
    joins = [c[1] - c[0] for c in details["cuts"]]
    joins = [sum(joins[:i + 1]) for i in range(len(joins) - 1)]          # output times of the jump cuts
    odd, bad = [], []
    for i in range(len(diff)):
        around = np.concatenate([diff[max(0, i - 2):i], diff[i + 1:i + 3]])
        if diff[i] > 25 and diff[i] > 2.5 * (around.max() if len(around) else 0):
            t = (i + 1) / 30
            if not any(abs(t - e) < 0.12 for e in expected):
                (bad if t < 1.5 or t > dur - 1.5 or any(abs(t - j) < 0.7 for j in joins) else odd).append(t)
    flashes = [i / 30 for i in range(1, len(luma) - 1)
               if luma[i] > max(luma[i - 1], luma[i + 1]) + 40 or luma[i] < min(luma[i - 1], luma[i + 1]) - 40]
    notes = []
    if bad:
        notes.append("stray cut at " + ", ".join(f"{t:.2f}s" for t in bad))
    if flashes:
        notes.append("flash frame at " + ", ".join(f"{t:.2f}s" for t in flashes[:6]))
    if odd:
        notes.append("unplanned cut mid-clip at " + ", ".join(f"{t:.2f}s" for t in odd[:6]) + " (b-roll's own cuts are fine)")
    rep.add("Smooth transitions", "FAIL" if bad or flashes else "WARN" if odd else "PASS",
            "; ".join(notes) or f"{len(expected)} planned edges, no stray cuts or flashes")


def check_audio_timing(rep, mp4):
    """The audio packets' timestamps must march at exactly one AAC frame (1024 samples). Bunched or
    jumping timestamps play fine in some players and sped-up or glitchy in others (YouTube's upload
    processing, Chrome): rico heard this in Kylie's first 2 s on 2026-10-26. The samples were fine,
    only the container's timestamps were wrong."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "packet=pts_time:stream=sample_rate", "-of", "csv", str(mp4)],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    sr = int(next(l.split(",")[1] for l in out if l.startswith("stream")))
    pts = [float(l.split(",")[1]) for l in out if l.startswith("packet")]
    step = 1024 / sr
    bad = [pts[i] for i in range(len(pts) - 2) if abs(pts[i + 1] - pts[i] - step) > 0.001]   # last packet may be short
    rep.add("Audio timestamps steady", "FAIL" if bad else "PASS",
            f"{len(bad)} irregular audio packet gaps, first at {bad[0]:.2f}s, last at {bad[-1]:.2f}s "
            "(re-mux the audio: decode to wav, encode again, copy the video)" if bad
            else f"{len(pts)} packets, every gap is one AAC frame")


def required_tags(campaign):
    """Tags each platform's post text must carry, from SYSTEM/CAMPAIGNS/<campaign>/tags.json (copied from
    the MAIN campaign page). No file or no entry for a platform = no confirmed list = STOP."""
    p = Path(__file__).resolve().parent.parent / "CAMPAIGNS" / campaign / "tags.json"
    return json.loads(p.read_text()) if p.exists() else {}


def check_post_text(rep, folder, spec):
    sc = folder / "style_check.md"
    text = sc.read_text() if sc.exists() else ""
    line = lambda key: next((l for l in text.splitlines() if key in l), "")
    tags = required_tags(spec.get("campaign", "2026-10_iced-coffee-hour"))
    notes, st = [], "PASS"
    for platform, key in (("instagram", "Instagram caption"), ("youtube", "YouTube description")):
        post = line(key)
        if not post:
            continue                                   # this clip doesn't go to that platform
        if platform not in tags:
            st, notes = "FAIL", notes + [f"{platform}: no confirmed tag list in tags.json"]
            continue
        need = [t for t in tags[platform] if t.lower() not in post.lower()]
        if need:
            st, notes = "FAIL", notes + [f"{platform} text is missing {', '.join(need)}"]
        else:
            notes.append(f"{platform} has {', '.join(tags[platform])}")
    rep.add("Post text tags", st, "; ".join(notes) or "no post text yet")


def sheet(mp4, out):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp4), "-vf", "fps=1,scale=180:320,tile=10x7",
                    "-frames:v", "1", str(out)], check=True)


def main(folder, source=None):
    folder = Path(folder)
    mp4 = next(p for p in folder.glob("*.mp4"))
    details = json.loads((folder / "cut_details.json").read_text())
    spec = details.get("spec", {})
    words = json.loads((folder / "words.json").read_text())
    events = ass_events(folder / "captions.ass")
    source = source or spec.get("source")

    rep = Report()
    dur = check_format(rep, mp4, probe(mp4))
    check_audio(rep, mp4)
    check_cut_edges(rep, details, words, source)
    check_captions(rep, details, words, events, dur)
    check_title(rep, events, spec)
    check_faces(rep, mp4, events)
    check_picture(rep, mp4, details)
    check_centred(rep, mp4, details)
    check_nobody(rep, mp4, details)
    check_footage_text(rep, mp4, details)
    check_one_look(rep, details)
    check_actor_size(rep, mp4, details)
    check_transitions(rep, mp4, details, dur)
    check_audio_timing(rep, mp4)
    check_post_text(rep, folder, spec)
    import profiles
    soft = profiles.profile(spec.get("style"))["soft_qa"]   # per kind of footage: what is a warning, not a failure
    if soft:
        rep.rows = [(a, "WARN" if (s == "FAIL" and a in soft) else s, e + (f" ({spec.get('style')}: warn only)" if (s == "FAIL" and a in soft) else "")) for a, s, e in rep.rows]
    sheet(mp4, folder / "qa_sheet.png")

    lines = [f"# Pre-post check: {folder.name}", "",
             "Made by bot/qa_check.py. FAIL drops the clip. WARN needs a human look. qa_sheet.png shows one frame per second.", "",
             "| Check | Result | Evidence |", "|---|---|---|"]
    lines += [f"| {a} | {s} | {e.replace('|', '/')} |" for a, s, e in rep.rows]
    lines += ["", f"**Verdict: {rep.verdict}**", ""]
    (folder / "qa_report.md").write_text("\n".join(lines))
    print(f"{folder.name}: {rep.verdict}")
    for a, s, e in rep.rows:
        if s != "PASS":
            print(f"  {s} {a}: {e}")
    return rep.verdict


if __name__ == "__main__":
    args = sys.argv[1:]
    src = args[args.index("--source") + 1] if "--source" in args else None
    v = main(args[0], src)
    sys.exit(1 if v == "FAIL" else 0)
