"""Brand mode: clips for a campaign whose source material is silent product footage (app demos,
b-roll) instead of a talking episode. The reviewer writes short scripts; the bot gives them a voice
(edge-tts, free, word-timed), lays the approved footage under it, and adds the usual title band,
word captions and the campaign's disclosure line. One QA pass, no re-cut loops, max 3 clips.

  python3 bot/brand_mode.py <work dir> <footage dir> <plan.json> [brief.json]

plan.json (campaigns/<c>/plan.json), written by the reviewer:
  {
    "brand_clips": [
      {
        "hook": "YOUR COFFEE JUST PAID YOU BACK IN BITCOIN",   # title band, 2 lines max
        "hook_hi": ["BITCOIN"],                                 # title words in yellow
        "script": ["line one.", "line two.", ...],              # spoken as written, one TTS call per line
        "emphasis": ["Fold", "bitcoin"],                        # caption words in yellow
        "footage": [                                            # in order; each entry covers script lines a..b
          {"file": "general navigation", "lines": [0, 1], "from": 2.0},
          {"file": "transactions-menu", "lines": [2, 2]}
        ],
        "voice": "en-US-AndrewNeural",                          # optional
        "caption": "post text for the POST KIT"                 # optional
      }
    ],
    "why": "..."
  }
Footage entries name a file by a case-insensitive substring of its name. Lines not covered by an
entry are given to the entry before them. A clip whose source is shorter than its slot holds its
last frame. Offline test: BRAND_FAKE_VOICE=1 writes silence with estimated word timings.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import render_clip as rc  # noqa: E402  (constants, title_lines, ts, esc, norm)

W, H, FPS = rc.W, rc.H, rc.FPS
TOP = 240             # brand mode (parked) keeps its own title band; the main renderer has none since 2026-10-31
HC = H - TOP
MAX_CLIPS = 3
VOICES = ["en-US-AndrewNeural", "en-US-BrianNeural", "en-US-GuyNeural"]
RATE = "+8%"
GAP = 0.18            # seconds of air between script lines
TAIL = 0.9            # footage after the last word
CAP_Y = 1430          # caption centre line (clear of the platform UI at the bottom)
DISC_Y = TOP + 34     # disclosure sits right under the title band, never behind the TikTok UI
WORDS_PER_CAP = 3
# claims the brand briefs forbid (future value, financial-product words, competitor call-outs)
CLAIM_RE = re.compile(r"\b(will (go|be worth|grow|rise|moon)|worth more than|grow in value|guaranteed|risk.?free|"
                      r"interest|yield|staking|savings account|high.?yield|fdic|apy|lock.?up|"
                      r"chase|amex|american express|capital one|coinbase|cash app|robinhood|venmo|paypal|"
                      r"reserve)\b", re.I)


def log(*a):
    print(*a, flush=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe(path):
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(path)])
    j = json.loads(r.stdout)
    s = (j.get("streams") or [{}])[0]
    return float(j["format"]["duration"]), int(s.get("width", 0)), int(s.get("height", 0))


def dur_of(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip() or 0)


# ---------- 1. voice ----------

async def _tts(text, voice, out_mp3):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=RATE, boundary="WordBoundary")   # 7.x defaults to sentence marks
    words = []
    with open(out_mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"], "start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7})
    return words


def speak(text, voice, out_wav):
    """One script line -> wav (48 kHz) + word timings in seconds from the start of that line."""
    out_wav = Path(out_wav)
    if os.environ.get("BRAND_FAKE_VOICE"):
        toks = text.split()
        d = 0.32 * len(toks) + 0.3
        sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", f"{d:.2f}", str(out_wav)])
        return [{"text": t, "start": 0.15 + 0.32 * i, "end": 0.15 + 0.32 * i + 0.28} for i, t in enumerate(toks)]
    mp3 = out_wav.with_suffix(".mp3")
    errors = []
    for attempt, v in enumerate([voice] + [x for x in VOICES if x != voice]):
        try:
            words = asyncio.run(_tts(text, v, mp3))
            size = mp3.stat().st_size if mp3.exists() else 0
            if size > 1000:
                sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "2", str(out_wav)])
                if not words:   # no word marks came back: spread the words evenly over the audio
                    toks, d = text.split(), dur_of(out_wav)
                    step = max(d - 0.2, 0.1) / max(len(toks), 1)
                    words = [{"text": t, "start": 0.1 + i * step, "end": 0.1 + (i + 0.9) * step} for i, t in enumerate(toks)]
                return words
            errors.append(f"{v}: {size} bytes, {len(words)} marks")
        except Exception as e:  # network hiccup, blocked endpoint or a retired voice: try the next one
            errors.append(f"{v}: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2 + attempt)
    last = " | ".join(errors)
    raise RuntimeError(f"voice failed: {last}")


def build_voice(lines, voice, tmp):
    """All lines -> one wav; returns (wav, line_starts, line_ends, words with absolute times)."""
    starts, ends, words, wavs, t = [], [], [], [], 0.0
    for i, line in enumerate(lines):
        w = tmp / f"line{i:02d}.wav"
        ws = speak(line, voice, w)
        d = dur_of(w)
        starts.append(t)
        ends.append(t + d)
        words += [{"text": x["text"], "start": t + x["start"], "end": t + x["end"], "line": i} for x in ws]
        wavs.append((w, t))
        t += d + GAP
    total = t - GAP + TAIL
    ins, fc = [], []
    for i, (w, off) in enumerate(wavs):
        ins += ["-i", str(w)]
        ms = int(off * 1000)
        fc.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(wavs))) + f"amix=inputs={len(wavs)}:normalize=0:duration=longest,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={total:.3f},atrim=0:{total:.3f}[v]")
    out = tmp / "voice.wav"
    sh(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-ar", "48000", "-ac", "2", str(out)])
    return out, starts, ends, words, total


# ---------- 2. footage ----------

def find_footage(name, footage_dir):
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    files = sorted(p for p in Path(footage_dir).iterdir() if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".m4v"))
    for p in files:
        if key and key in re.sub(r"[^a-z0-9]", "", p.stem.lower()):
            return p
    raise FileNotFoundError(f"no footage file matching '{name}' in {footage_dir} (have: {', '.join(p.name for p in files)[:300]})")


def slots(entries, n_lines, starts, ends, total):
    """Which stretch of the clip each footage entry covers: from the start of its first line to the
    start of the next entry's first line (the last one runs to the end)."""
    firsts = []
    for k, e in enumerate(entries):
        a = e.get("lines", [None])[0]
        firsts.append(0 if k == 0 else (a if a is not None else round(k * n_lines / len(entries))))
    firsts = sorted(set(min(max(f, 0), n_lines - 1) for f in firsts))
    out = []
    for i, f in enumerate(firsts):
        a = 0.0 if i == 0 else starts[f] - GAP / 2
        b = total if i == len(firsts) - 1 else starts[firsts[i + 1]] - GAP / 2
        out.append((a, b))
    while len(out) < len(entries):   # entries that collapsed onto the same line share nothing: drop extras
        entries = entries[:len(out)]
    return list(zip(entries[:len(out)], out))


def render_segment(src, start, length, out):
    """Footage -> 1080x1680, fit inside, the same picture blurred behind it; held on the last frame if short."""
    fit = f"scale={W}:{HC}:force_original_aspect_ratio=decrease:flags=lanczos"
    bg = (f"scale={W // 4}:{HC // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{HC // 4},boxblur=10:3,"
          f"eq=brightness=-0.2:saturation=0.8,scale={W}:{HC}:flags=bicubic")
    vf = (f"[0:v]fps={FPS},trim=start={start:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={length + 1:.3f},"
          f"trim=duration={length:.3f},split[a][b];[a]{bg}[bg];[b]{fit}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto,format=yuv420p[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", vf, "-map", "[v]", "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-r", str(FPS), str(out)])
    return out


# ---------- 3. text ----------

def caption_events(words, emph):
    emph = {rc.norm(e) for e in emph}
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= WORDS_PER_CAP or w["text"].rstrip()[-1:] in ".?!," or (w is words[-1]):
            groups.append(cur)
            cur = []
        elif cur and words[words.index(w) + 1]["line"] != w["line"]:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    caps = []
    for g in groups:
        toks = []
        for w in g:
            t = rc.esc(w["text"].upper().strip())
            if rc.norm(w["text"]) in emph:
                t = r"{\c&H00D7FF&}" + t + r"{\c&HFFFFFF&}"
            toks.append(t)
        caps.append([g[0]["start"], g[-1]["end"] + 0.08, " ".join(toks)])
    for c, nxt in zip(caps, caps[1:]):
        if 0 < nxt[0] - c[1] < 0.5:
            c[1] = nxt[0]
    return [f"Dialogue: 1,{rc.ts(a)},{rc.ts(b)},Cap,,0,0,0,,{{\\an5\\pos(540,{CAP_Y})}}{t}" for a, b, t in caps]


def build_ass(spec, words, total):
    size, title = rc.title_lines(spec["hook"], spec.get("hook_hi", []))
    ev = [f"Dialogue: 2,{rc.ts(0)},{rc.ts(total)},Hook,,0,0,0,,{{\\an5\\pos(540,{TOP // 2 + 4})\\fs{size}}}{title}"]
    ev += caption_events(words, spec.get("emphasis", []))
    if spec.get("disclosure"):
        ev.append(f"Dialogue: 4,{rc.ts(0)},{rc.ts(total)},Disc,,0,0,0,,{{\\an8\\pos(540,{DISC_Y})}}{rc.esc(spec['disclosure'])}")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{rc.CAP_FONT},74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,7,3,5,70,70,0,1
Style: Hook,{rc.TITLE_FONT},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,50,50,0,1
Style: Disc,{rc.CAP_FONT},30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,3,10,0,8,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(ev) + "\n"


# ---------- 4. QA (one pass) ----------

def qa(spec, out, total, brief, fake):
    rows = []
    lo, hi = brief.get("min_s", 20), brief.get("max_s", 60)
    rows.append(("length", lo <= total <= hi, f"{total:.1f} s (campaign {lo}-{hi})"))
    d, w, h = probe(out) if out.exists() else (0, 0, 0)
    rows.append(("file", out.exists() and w == W and h == H and abs(d - total) < 1.0, f"{w}x{h}, {d:.1f} s"))
    text = " ".join(spec["script"])
    bad = sorted({m.group(0).lower() for m in CLAIM_RE.finditer(text + " " + spec["hook"])})
    rows.append(("no forbidden claims", not bad, "found: " + ", ".join(bad) if bad else "future value, product words, competitors: none"))
    n_brand = len(re.findall(r"\bfold\b", text, re.I))
    rows.append(("brand named", n_brand >= 2, f"Fold said {n_brand}x"))
    rows.append(("disclosure", bool(spec.get("disclosure")), spec.get("disclosure", "MISSING")[:60]))
    rows.append(("hook length", len(spec["hook"].split()) <= 12, f"{len(spec['hook'].split())} words"))
    if not fake and out.exists():
        r = subprocess.run(["ffmpeg", "-i", str(out), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"mean_volume: (-?[\d.]+)", r.stderr)
        mean = float(m.group(1)) if m else -99
        rows.append(("voice audible", mean > -35, f"mean {mean:.1f} dB"))
    fails = [r for r in rows if not r[1]]
    rep = ["# QA report (brand mode)", "", "Made by bot/brand_mode.py. FAIL drops the clip.", "",
           "| check | result | note |", "|---|---|---|"]
    rep += [f"| {n} | {'PASS' if ok else 'FAIL'} | {note} |" for n, ok, note in rows]
    rep += ["", f"Overall: {'FAIL' if fails else 'PASS'}"]
    # machine score: a plain heuristic so the SUMMARY can rank the three (not a view prediction)
    score = 70
    hook = spec["hook"].lower()
    score += 10 if re.search(r"\?|\d|\byou\b|\bpov\b|honest", hook) else 0
    score += 10 if re.search(r"coffee|gas|grocer|lunch|shopping|target|morning|rent|paycheck", text, re.I) else 0
    score += 5 if total <= 35 else 0
    score -= 25 * len(fails)
    rep += ["", f"Machine score: {max(score, 0)}/100"]
    return ("FAIL" if fails else "PASS"), [f"{n}: {note}" for n, _, note in fails], max(score, 0), "\n".join(rep)


# ---------- 5. one clip ----------

def make_clip(spec, footage_dir, brief, out_dir, k):
    out_dir = Path(out_dir)
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    fake = bool(os.environ.get("BRAND_FAKE_VOICE"))
    lines = [l.strip() for l in spec["script"] if l.strip()]
    voice_wav, starts, ends, words, total = build_voice(lines, spec.get("voice", VOICES[0]), tmp)
    lo = brief.get("min_s", 20)
    if total < lo:          # short script: hold the last footage so the platform minimum is met
        total = lo + 0.3
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_wav), "-af", f"apad=whole_dur={total:.3f}", str(tmp / "voice_pad.wav")])
        voice_wav = tmp / "voice_pad.wav"
    segs = []
    for i, (entry, (a, b)) in enumerate(slots(spec["footage"], len(lines), starts, ends, total)):
        src = find_footage(entry["file"], footage_dir)
        seg = render_segment(src, float(entry.get("from", 0)), b - a, tmp / f"seg{i:02d}.mp4")
        segs.append(seg)
    lst = tmp / "segs.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    video = tmp / "video.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)])
    ass = tmp / "text.ass"
    ass.write_text(build_ass(spec, words, total))
    out = out_dir / f"{out_dir.name}.mp4"
    fonts = str(rc.FONTS_DIR)
    vf = (f"[1:v]setpts=PTS-STARTPTS[fg];[0:v][fg]overlay=0:{TOP}:shortest=1,"
          f"ass={ass}:fontsdir={fonts}[v]")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.3f}",
        "-i", str(video), "-i", str(voice_wav), "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    (out_dir / "captions.txt").write_text("\n".join(lines) + "\n")
    (out_dir / "words.json").write_text(json.dumps(words, indent=0))
    verdict, fails, score, rep = qa(spec, out, total, brief, fake)
    (out_dir / "qa_report.md").write_text(rep)
    shutil.rmtree(tmp, ignore_errors=True)
    return {"folder": str(out_dir), "mp4": str(out), "hook": spec["hook"], "parts": [], "judge": score, "dur": round(total, 1),
            "why": spec.get("_why", ""), "captions": "\n".join(lines), "caption": spec.get("caption", ""),
            "qa": verdict, "fails": fails}


def run(work, footage_dir, brief, plan, campaign="campaign", log=log):
    work = Path(work)
    t0 = time.time()
    specs = plan.get("brand_clips", [])[:MAX_CLIPS]
    kept, notes = [], [f"brand mode: {len(specs)} script(s) from plan.json, voice {specs[0].get('voice', VOICES[0]) if specs else '-'}"]
    for k, spec in enumerate(specs, 1):
        spec = dict(spec)
        spec.setdefault("disclosure", brief.get("disclosure", ""))
        spec.setdefault("_why", plan.get("why", "reviewer's script"))
        slugged = re.sub(r"[^a-z0-9]+", "-", spec["hook"].lower()).strip("-")[:28].rstrip("-")
        folder = work / "clips" / f"{len(kept) + 1:02d}_{slugged}"
        log(f"brand clip {k}: {spec['hook']}")
        try:
            c = make_clip(spec, footage_dir, brief, folder, k)
        except Exception as e:
            notes.append(f"FAILED {spec['hook']}: {type(e).__name__}: {str(e)[:200]}")
            continue
        line = f"{folder.name}: {c['dur']}s  qa {c['qa']}  score {c['judge']}  hook: {c['hook']}"
        if c["qa"] == "PASS":
            kept.append(c)
            notes.append("KEPT  " + line)
        else:
            notes.append("DROP  " + line + "  " + "; ".join(c["fails"]))
            (work / "dropped").mkdir(exist_ok=True)
            shutil.move(str(folder), str(work / "dropped" / folder.name)) if not (work / "dropped" / folder.name).exists() else None
    notes.append(f"{len(kept)} clip(s) kept of {len(specs)} in {(time.time() - t0) / 60:.1f} min")
    summary = "\n".join(notes)
    (work / "summary.txt").write_text(summary)
    log(summary)
    return kept, summary


if __name__ == "__main__":
    a = sys.argv[1:]
    brief = json.loads(Path(a[3]).read_text()) if len(a) > 3 else {"min_s": 20, "max_s": 60}
    run(a[0], a[1], brief, json.loads(Path(a[2]).read_text()), campaign=Path(a[0]).name)
