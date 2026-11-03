"""Music mode: moments for footage with (almost) no speech - a live performance, a concert, a music video.

rico, 2026-11-03 ("Build music mode, retry", The Weeknd - Hong Kong Performance): the moment picker reads the
transcript (find_moments.sentences), so a performance video with three transcribed words gave 0 windows. Here the
windows come from the SOUND and the PICTURE instead:

  energy    bot/audio_energy.py: loudness per second (RMS dB) of the whole episode
  stats     the episode's own loudness landmarks (median, percentiles). A concert is loud from the first second to
            the last, so "loud" is judged against the episode's spread, never a fixed 6 dB (the first Weeknd run
            read every window as "+0.2 dB, loud 0%" and the judge gave entertainment 1-2)
  cuts      the episode's own shot changes (ffmpeg scene detection at 320 px)
  windows   lo-hi s long (the brief's min/max), opened just after a shot change when one is near and ended just
            BEFORE the next one (ending on a cut leaves a flash frame as the last shot), never in the opening shot
            (a title card). Scored on where the window's loudness ranks in the episode, how much of it is loud,
            whether it OPENS loud (the brief: "hook in the first two seconds"), whether it builds to its loudest
            point late (a payoff), how many cuts it carries (variety) and a preference for the middle of the
            brief's length range over the shortest allowed. Non-overlapping, the best first.
  specs     render_clip specs like plan.spec_for makes, with "music": {...} (the measurements the judge reads),
            "tighten": False (no dead air to cut: silence between notes is music), no captions (no words), the
            hook text from the reviewer's plan.json "music_hooks" or the campaign name.

When it applies: the transcript is under WPM_MUSIC words per minute of episode, or the reviewer pins
brief_overrides "music": true (false switches it off). The pitch (words), the audience read (words) and the caption
checks do not apply; judge_areas() scores hook, pace, story and entertainment from the sound and the shots.

  python3 bot/music_moments.py episode.mp4 [lo] [hi]     -> prints the top windows
"""
import bisect
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_energy  # noqa: E402

WPM_MUSIC = 6.0      # under this many transcribed words per minute the episode is music, not talk
POOL = 24            # windows handed to the render queue (plan.PITCH_POOL)
OPEN_S = 2.0         # the brief's hook window: the first two seconds
SCENE = 0.30         # ffmpeg scene-change threshold (0-1); 0.3 catches camera cuts, not lighting flicker
START_PAD = 0.1      # a window opens this far after a shot change: safely inside the new shot
END_PAD = 0.3        # a window ends this far before the next shot change, never on it (a flash frame as the last shot)
EDGE_S = 0.6         # the render may move an edge to a cut this far away: windows are cut this much longer than the brief's minimum
OPENING_SHOT_S = 15  # an opening shot this short (a title card, the walk-on) is never where a window starts


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


def stats(energy):
    """The episode's loudness landmarks (dB) and the thresholds the measures use: "loud" is a second above three
    quarters of the episode (at least 1 dB over the median), "quiet" is under its quietest tenth (at least 3 dB under)."""
    s = sorted(energy)
    n = len(s)
    if not n:
        return {"med": 0.0, "p10": 0.0, "p60": 0.0, "p75": 0.0, "p90": 0.0, "spread": 0.0, "loud": 0.0, "hook": 0.0, "quiet": 0.0, "_sorted": []}
    q = lambda p: s[min(n - 1, int(p * (n - 1)))]
    med = q(0.5)
    st = {"med": med, "p10": q(0.10), "p60": q(0.60), "p75": q(0.75), "p90": q(0.90)}
    st["spread"] = round(st["p90"] - med, 1)
    st["loud"] = max(st["p75"], med + 1.0)
    st["hook"] = max(st["p60"], med)
    st["quiet"] = min(st["p10"], med - 3.0)
    st["_sorted"] = s
    return st


def measure(energy, start, end, st=None):
    """What the judge and the pick read about one window of the episode's loudness curve."""
    a, b = int(start), max(int(end), int(start) + 1)
    seg = energy[a:b]
    if not seg:
        return None
    st = st or stats(energy)
    n = len(seg)
    mean = sum(seg) / n
    peak_i = max(range(n), key=lambda i: seg[i])
    first = seg[:max(int(OPEN_S), 1)]
    open_mean = sum(first) / len(first)
    ranked = st.get("_sorted") or sorted(energy)
    return {
        "rel_db": round(mean - st["med"], 1),                                  # mean loudness against the episode's median
        "p_rank": round(bisect.bisect_left(ranked, mean) / max(len(ranked), 1), 2),   # louder than this share of the episode's seconds
        "loud_share": round(sum(1 for v in seg if v > st["loud"]) / n, 2),     # share of loud seconds
        "peak_db": round(max(seg) - st["med"], 1),
        "peak_at": peak_i,                                                     # seconds into the window
        # the hook: the first two seconds are loud for this episode, or at least as loud as the window itself (no quiet lead-in)
        "opens_on_peak": open_mean >= st["hook"] or open_mean >= mean - 1.5 or peak_i < OPEN_S,
        "builds": peak_i >= 0.4 * n,                                           # the loudest second sits late: a payoff, not a fade
        "ends_quiet": seg[-1] < st["quiet"],                                   # ends in a hole (the song stopped)
    }


def length_pts(dur, lo, hi):
    """The brief's range is not a target of its minimum: a 12-30 s brief wants 17-30 s clips, not twelve 12 s ones."""
    span = max(hi - lo, 1.0)
    return 8 if dur >= lo + 0.4 * span else 4 if dur >= lo + 0.15 * span else 0


def score_window(energy, cut_times, start, end, st, lo=None, hi=None):
    m = measure(energy, start, end, st)
    if not m:
        return 0, {}, None
    pts = {}
    pts["energy"] = int(35 * m["p_rank"])
    pts["loud"] = int(25 * m["loud_share"])
    pts["hook"] = 15 if m["opens_on_peak"] else 0
    pts["payoff"] = 10 if m["builds"] and not m["ends_quiet"] else 0 if not m["ends_quiet"] else -10
    inside = [c for c in cut_times if start + 0.5 < c < end - 0.5]
    per10 = len(inside) / max((end - start) / 10, 0.1)
    pts["variety"] = 10 if 0.5 <= per10 <= 4 else 5 if inside else 0
    pts["on_cut"] = 5 if any(abs(c - start) < 0.3 for c in cut_times) else 0
    if lo is not None and hi is not None:
        pts["length"] = length_pts(end - start, lo, hi)
    return sum(pts.values()), pts, m


def windows(energy, cut_times, lo, hi, used=(), top=POOL, step=2.0):
    """The best non-overlapping lo-hi s windows: [{"start", "end", "score", "pts", "music"}], best first.
    Starts: just after every shot change, and every `step` seconds where the picture never cuts, never inside a
    short opening shot. Ends: just before the shot change inside the length range that scores best, else
    start+lo..hi in steps. The minimum is cut EDGE_S longer than the brief's so the render's edge moves never
    leave the clip under it."""
    n = len(energy)
    lo_c, hi_c = lo + EDGE_S, max(hi - END_PAD, lo + EDGE_S)
    if n < lo_c:
        return []
    st = stats(energy)
    first_ok = cut_times[0] if cut_times and cut_times[0] <= OPENING_SHOT_S else 0.0
    starts = {round(c + START_PAD, 1) for c in cut_times if first_ok <= c and c + START_PAD < n - lo_c}
    # the stepped starts fill the stretches without cuts; one that lands on a cut would open on its last frame
    starts |= {float(t) for t in range(int(math.ceil(first_ok)), int(n - lo_c) + 1, int(step))
               if not any(c - 0.3 <= t <= c + 0.3 for c in cut_times)}
    cands = []
    for s in sorted(starts):
        ends = [c - END_PAD for c in cut_times if s + lo_c <= c - END_PAD <= s + hi_c]
        ends = ends + [s + lo_c + k * ((hi_c - lo_c) / 3.0) for k in range(4)]
        best = None
        for e in sorted(set(round(min(x, n), 1) for x in ends)):
            if e - s < lo_c - 0.01:
                continue
            tot, pts, m = score_window(energy, cut_times, s, e, st, lo, hi)
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
    st = stats(energy)
    wins = windows(energy, cut_times, lo, hi, used=used)
    log(f"music mode: {len(energy)} s of sound (median {st['med']:.1f} dB, loudest tenth {st['p90']:.1f} dB, spread {st['spread']:.1f} dB), "
        f"{len(cut_times)} shot changes, {len(wins)} windows of {lo}-{hi} s")
    out = []
    for k, w in enumerate(wins):
        hook = hook_text(brief, campaign, k)
        m = w["music"]
        why = f"music {w['score']}: " + ", ".join(f"{a} {b}" for a, b in w["pts"].items() if b) + \
              f" | louder than {m['p_rank']:.0%} of the episode ({m['rel_db']:+.1f} dB), loud {m['loud_share']:.0%}, peak at {m['peak_at']} s"
        out.append({
            "campaign": campaign, "source": str(source), "words": str(words_path),
            "parts": [[w["start"], w["end"]]], "hook": hook, "emphasis": [], "focus": [], "overlays": [], "callouts": [],
            "sfx": False, "tighten": False, "music": dict(m, score=w["score"], pts=w["pts"]),
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
    notes["hook"] = ["opens loud (the first two seconds carry the sound)" if m.get("opens_on_peak") else "opens before the drop: the first 2 s are quieter than the rest"]
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
    rank = m.get("p_rank")
    if rank is None:   # a spec from before the ranked measure (2.5.0): the old fixed-dB read
        rank = max(0.0, min(1.0, (rel + 3) / 9))
    ent = int(max(0, min(10, round(10 * (0.6 * rank + 0.4 * loud)))))
    areas["entertainment"] = ent
    notes["entertainment"] = [f"louder than {rank:.0%} of the episode ({rel:+.1f} dB), loud {loud:.0%} of the clip (crowd, chorus, drop)"]
    return areas, notes


if __name__ == "__main__":
    a = sys.argv[1:]
    src = a[0]
    lo, hi = (float(a[1]) if len(a) > 1 else 12), (float(a[2]) if len(a) > 2 else 30)
    e = audio_energy.energy(src)
    c = cuts(src)
    st = stats(e)
    print(f"{len(e)} s, median {st['med']:.1f} dB, loudest tenth {st['p90']:.1f} dB, spread {st['spread']:.1f} dB, {len(c)} cuts")
    for w in windows(e, c, lo, hi, top=10):
        print(f"{int(w['start']) // 60}:{int(w['start']) % 60:02d}  {w['dur']:5.1f}s  score {w['score']:3d}  {w['pts']}  {w['music']}")
