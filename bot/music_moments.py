"""Music mode: moments for footage with (almost) no speech - a live performance, a concert, a music video.

rico, 2026-11-03 ("Build music mode, retry", The Weeknd - Hong Kong Performance): the moment picker reads the
transcript (find_moments.sentences), so a performance video with three transcribed words gave 0 windows. Here the
windows come from the SOUND and the PICTURE instead:

  energy    bot/audio_energy.py: loudness per second (RMS dB) of the whole episode
  cuts      the episode's own shot changes (ffmpeg scene detection at 320 px)
  windows   lo-hi s long (the brief's min/max), opened on a shot change when one is near, scored on how loud the
            window is against the episode, how much of it is loud, whether it OPENS on a peak (the brief: "hook in
            the first two seconds"), whether it builds to its loudest point late (a payoff) and ends on a shot change,
            and how many cuts it carries (variety). Non-overlapping, the best first.
  specs     render_clip specs like plan.spec_for makes, with "music": {...} (the measurements the judge reads),
            "tighten": False (no dead air to cut: silence between notes is music), no captions (no words), the
            hook text from the reviewer's plan.json "music_hooks" or the campaign name.

When it applies: the transcript is under WPM_MUSIC words per minute of episode, or the reviewer pins
brief_overrides "music": true (false switches it off). The pitch (words), the audience read (words) and the caption
checks do not apply; judge_areas() scores hook, pace, story and entertainment from the sound and the shots.

  python3 bot/music_moments.py episode.mp4 [lo] [hi]     -> prints the top windows
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_energy  # noqa: E402

WPM_MUSIC = 6.0      # under this many transcribed words per minute the episode is music, not talk
POOL = 24            # windows handed to the render queue (plan.PITCH_POOL)
LOUD_DB = 6.0        # a second this far above the episode median is "loud"
OPEN_S = 2.0         # the brief's hook window: the first two seconds
SCENE = 0.30         # ffmpeg scene-change threshold (0-1); 0.3 catches camera cuts, not lighting flicker


def duration(src):
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                    capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        return 0.0


def is_music(words, dur, brief=None):
    """True when the picker should listen instead of read: the reviewer's pin, else the transcript's density."""
    pin = (brief or {}).get("music")
    if isinstance(pin, bool):
        return pin
    if not dur or dur <= 0:
        return False
    return len(words or []) / (dur / 60.0) < WPM_MUSIC


def cuts(src, cache=None):
    """Shot-change times (seconds) of the whole file, from ffmpeg's scene detector at 320 px. Cached as JSON."""
    if cache and Path(cache).exists():
        return json.loads(Path(cache).read_text())
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{SCENE})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    times = sorted({round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)})
    if cache:
        Path(cache).write_text(json.dumps(times))
    return times


def median(xs):
    s = sorted(xs)
    return s[len(s) // 2] if s else 0.0


def measure(energy, start, end, med=None):
    """What the judge and the pick read about one window of the episode's loudness curve."""
    a, b = int(start), max(int(end), int(start) + 1)
    seg = energy[a:b]
    if not seg:
        return None
    med = median(energy) if med is None else med
    n = len(seg)
    peak_i = max(range(n), key=lambda i: seg[i])
    loud = sum(1 for v in seg if v > med + LOUD_DB)
    first = seg[:max(int(OPEN_S), 1)]
    return {
        "rel_db": round(sum(seg) / n - med, 1),                 # mean loudness against the episode
        "loud_share": round(loud / n, 2),                       # share of loud seconds
        "peak_db": round(max(seg) - med, 1),
        "peak_at": peak_i,                                      # seconds into the window
        "opens_on_peak": max(first) >= med + LOUD_DB * 0.6 or peak_i < OPEN_S,   # the hook: loud from the first second
        "builds": peak_i >= 0.4 * n,                            # the loudest second sits late: a payoff, not a fade
        "ends_quiet": seg[-1] < med - LOUD_DB,                  # ends in a hole (the song stopped)
    }


def score_window(energy, cut_times, start, end, med):
    m = measure(energy, start, end, med)
    if not m:
        return 0, {}, None
    pts = {}
    pts["energy"] = int(max(0, min(35, 35 * (m["rel_db"] + 3) / 9)))
    pts["loud"] = int(25 * m["loud_share"])
    pts["hook"] = 15 if m["opens_on_peak"] else 0
    pts["payoff"] = 10 if m["builds"] and not m["ends_quiet"] else 0 if not m["ends_quiet"] else -10
    inside = [c for c in cut_times if start + 0.5 < c < end - 0.5]
    per10 = len(inside) / max((end - start) / 10, 0.1)
    pts["variety"] = 10 if 0.5 <= per10 <= 4 else 5 if inside else 0
    pts["on_cut"] = 5 if any(abs(c - start) < 0.3 for c in cut_times) else 0
    return sum(pts.values()), pts, m


def windows(energy, cut_times, lo, hi, used=(), top=POOL, step=2.0):
    """The best non-overlapping lo-hi s windows: [{"start", "end", "score", "pts", "music"}], best first.
    Starts: every shot change, and every `step` seconds where the picture never cuts. Ends: the shot change
    inside [start+lo, start+hi] that scores best, else start+lo..hi in steps."""
    n = len(energy)
    if n < lo:
        return []
    med = median(energy)
    starts = sorted({round(c, 1) for c in cut_times if c < n - lo} | {float(t) for t in range(0, int(n - lo) + 1, int(step))})
    cands = []
    for s in starts:
        ends = [c for c in cut_times if s + lo <= c <= s + hi] or []
        ends = ends + [s + lo + k * ((hi - lo) / 3.0) for k in range(4)]
        best = None
        for e in sorted(set(round(min(x, n), 1) for x in ends)):
            if e - s < lo - 0.01:
                continue
            tot, pts, m = score_window(energy, cut_times, s, e, med)
            if best is None or tot > best[0]:
                best = (tot, pts, m, e)
        if best:
            tot, pts, m, e = best
            cands.append({"start": round(s, 2), "end": round(e, 2), "dur": round(e - s, 1), "score": tot, "pts": pts, "music": m})
    cands.sort(key=lambda c: (-c["score"], c["start"]))
    picked = []
    for c in cands:
        if any(min(c["end"], b) - max(c["start"], a) > 0 for a, b in used):
            continue
        if all(min(c["end"], p["end"]) - max(c["start"], p["start"]) < 0.25 * min(c["dur"], p["dur"]) for p in picked):
            picked.append(c)
        if len(picked) >= top:
            break
    return picked


def hook_text(brief, campaign, k):
    """The on-screen hook for the k-th clip: the reviewer's music_hooks (cycled), else the campaign's name without
    the campaign words ("The Weeknd - Hong Kong Performance Clipping" -> "The Weeknd - Hong Kong Performance")."""
    hooks = [h for h in (brief.get("music_hooks") or []) if isinstance(h, str) and h.strip()]
    if hooks:
        return hooks[k % len(hooks)].strip()
    name = re.sub(r"\b(clipping|clips?|campaign|official)\b", "", campaign, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" -|:")
    return name or campaign


def specs(source, words_path, brief, campaign, out_dir, used=(), log=print):
    """Render specs for a music episode (plan.load calls this instead of the scorecard)."""
    import plan as planner
    out_dir = Path(out_dir)
    work = out_dir.parent
    work.mkdir(parents=True, exist_ok=True)
    ep = work / "energy.json"
    if not ep.exists():
        json.dump(audio_energy.energy(source), open(ep, "w"))
    energy = json.load(open(ep))
    cut_times = cuts(source, work / "cuts.json")
    lo, hi = brief.get("min_s", 12), brief.get("max_s", 30)
    wins = windows(energy, cut_times, lo, hi, used=used)
    log(f"music mode: {len(energy)} s of sound, {len(cut_times)} shot changes, {len(wins)} windows of {lo}-{hi} s")
    out = []
    for k, w in enumerate(wins):
        hook = hook_text(brief, campaign, k)
        why = f"music {w['score']}: " + ", ".join(f"{a} {b}" for a, b in w["pts"].items() if b) + \
              f" | {w['music']['rel_db']:+.1f} dB vs the episode, loud {w['music']['loud_share']:.0%}, peak at {w['music']['peak_at']} s"
        out.append({
            "campaign": campaign, "source": str(source), "words": str(words_path),
            "parts": [[w["start"], w["end"]]], "hook": hook, "emphasis": [], "focus": [], "overlays": [], "callouts": [],
            "sfx": False, "tighten": False, "music": dict(w["music"], score=w["score"], pts=w["pts"]),
            "disclosure": brief.get("disclosure", ""), "style": brief.get("style") or "performance",
            "genres": brief.get("genres") if isinstance(brief.get("genres"), dict) else {"music": 1.0},
            "look": brief.get("look") or {}, "tag": brief.get("speaker_tag") or "",
            "brief": planner.brief_lengths(brief), "thumb_text": hook,
            "out": str(out_dir / f"{planner.slug(hook)}-{int(w['start'])}s.mp4"),
            "_why": why,
        })
    return out


def judge_areas(music, shots, dur, silences=()):
    """The judge's hook / pace / story / entertainment for a music clip, on the areas' own scales
    (judge_clip.MAXES: hook 20, pace 10, story 10, entertainment 10). Returns (areas, notes)."""
    m = music or {}
    areas, notes = {}, {}
    areas["hook"] = 20 if m.get("opens_on_peak") else 8
    notes["hook"] = ["opens on a peak (loud from the first second)" if m.get("opens_on_peak") else "opens before the drop: the first 2 s are quieter than the rest"]
    changes = sorted(s["from"] for s in shots) if shots else []
    gaps = [b - a for a, b in zip(changes, changes[1:] + [dur])] if changes else [dur]
    longest = max(gaps) if gaps else dur
    p = 10
    if longest > 10: p -= 4
    elif longest > 6: p -= 2
    p -= min(4, 2 * len(list(silences)))
    areas["pace"] = max(0, p)
    notes["pace"] = [f"longest stretch without a cut {longest:.1f} s", f"{len(list(silences))} silence(s) over 0.8 s"]
    st = 10 if m.get("builds") and not m.get("ends_quiet") else 5 if not m.get("ends_quiet") else 0
    areas["story"] = st
    notes["story"] = ["builds to its loudest point and ends on it" if st == 10 else "ends in a quiet hole" if st == 0 else "the peak comes early; the end holds"]
    rel, loud = m.get("rel_db", 0.0), m.get("loud_share", 0.0)
    ent = int(max(0, min(10, round(5 * (rel + 3) / 9 + 5 * loud))))
    areas["entertainment"] = ent
    notes["entertainment"] = [f"{rel:+.1f} dB against the episode, loud {loud:.0%} of the clip (crowd, chorus, drop)"]
    return areas, notes


if __name__ == "__main__":
    a = sys.argv[1:]
    src = a[0]
    lo, hi = (float(a[1]) if len(a) > 1 else 12), (float(a[2]) if len(a) > 2 else 30)
    e = audio_energy.energy(src)
    c = cuts(src)
    for w in windows(e, c, lo, hi, top=10):
        print(f"{int(w['start']) // 60}:{int(w['start']) % 60:02d}  {w['dur']:5.1f}s  score {w['score']:3d}  {w['pts']}  {w['music']}")
