"""The clip studio: who does what, and the checks that belong to no single editing step.

Board-approved 2026-10-31 (rico: "approve 1 - 3" on the deck in project files CLIPPING_SYSTEM/BOARD/):
  1. the studio design: 15 specialist roles, one content profile per kind of footage, a scorecard per profile,
     and a 9-checkpoint inspection line
  2. the campaign filter: real people only; no ads, gambling, crypto, CPM under $0.50 or hard-to-listen speakers
  3. the clip cap: 3 per campaign by default, up to 6 on a campaign whose clips rico already approved

This file holds the roster (which module plays which role and who it sends work back to), the
inspection line, and the pieces that are new with the board plan:
  weighted_total   the judge's areas weighted per kind of content (profiles.WEIGHTS) + the minimum-per-area rule
  layout_check     the Text & layout inspector: one caption spot, nothing in the platform UI, hook gone by ~6 s
  speaker_check    the campaign gate's listen: is the speaker easy to follow (fillers, restarts, mumbled runs)
  clip_cap         how many clips a campaign may keep this run (3, or up to 6 once rico has approved 2+)

Usage:  python3 studio.py              prints the roster and the inspection line
        python3 studio.py <clip dir>   runs the Text & layout inspector on one finished clip
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import profiles  # noqa: E402

VERSION = "2.2.0"   # Studio v2 release 2 (MAKE stage split into bot/agents/). Printed in every SUMMARY so a clip traces to the code that made it.

# (stage, role, job, module(s) that do it today, whom a failure goes back to)
ROSTER = [
    ("PLAN", "Campaign Scout", "ranks offers on pay, fit and risk; stops ads, gambling, crypto, low pay", "campaign_scan.py, campaign_score.py", "-"),
    ("PLAN", "Brief Reader", "copies every rule, tag, length and clip idea word for word", "brief.py", "Campaign Scout"),
    ("PLAN", "Content Classifier", "names the kind of content and loads its profile", "profiles.resolve", "Brief Reader"),
    ("FIND", "Moment Hunter", "reads the whole source and ranks the moments worth cutting", "find_moments.py, plan.py", "Content Classifier"),
    ("FIND", "Story Editor", "trims each moment to hook, context, escalation, payoff", "plan.refine, engage.py", "Moment Hunter"),
    ("FIND", "Hook Writer", "the spoken first line and the on-screen hook", "find_moments.opener_ok / hook_from_opener", "Story Editor"),
    ("MAKE", "Camera Operator", "framing per profile: still on talkers, follow on movies", "agents/camera.py, analyze_shots.py", "Story Editor"),
    ("MAKE", "Caption Designer", "one caption spot, keyword colour, safe zones", "agents/captions.py, profiles.LOOK", "Camera Operator"),
    ("MAKE", "Sound Designer", "voice levels, limiter, SFX only on reveals", "agents/sound.py", "Camera Operator"),
    ("MAKE", "Motion & Graphics", "punch-ins, number cards, pattern interrupts", "agents/graphics.py, graphics_map.py", "Story Editor"),
    ("MAKE", "Finisher", "cleaning, last frame, cover thumbnail", "agents/finisher.py, agents/editor.py (tighten), thumbnail.py", "Motion & Graphics"),
    ("PROVE", "Inspectors", "first-piece, in-process, layout and final inspection", "pitch.py, pipeline.faces_ok, qa_check.py, studio.layout_check", "the role that owns the failure"),
    ("PROVE", "Judge", "blind grade on the content's own scorecard", "judge_clip.py + studio.weighted_total", "Story Editor (one re-edit), then Moment Hunter"),
    ("PROVE", "Publisher", "post kit per platform, tags checked against the brief", "post_kit.py, lanes.py", "Brief Reader"),
    ("PROVE", "Analyst", "logs views per post and retunes the weights", "data/posts.csv (weekly review)", "Content Classifier"),
]

# the 9 checkpoints (board deck slide "Nine checkpoints"), and where each one is enforced
INSPECTION_LINE = [
    ("Campaign gate", "pay, fit, risk, real person on camera, speaker easy to follow", "campaign_scan.auto_score, studio.speaker_check"),
    ("First-piece inspection", "every moment's words graded before render; picture probed for faces", "pitch.gate, pipeline.faces_ok"),
    ("In-process inspection", "each step's output checked as it is handed on (edges, opener, framing)", "plan.refine, engage.read, render_clip"),
    ("Assembly", "cut, framed and captioned in one 9:16 look", "agents/finisher.py"),
    ("Finishing touches", "sound levels, punch-ins, number cards", "render_clip.py"),
    ("Cleaning", "flash frames, dead air, stutters, spelling", "render_clip.deflash / tighten, qa_check"),
    ("Text & layout", "one caption spot, out of the platform UI, hook gone by ~6 s", "studio.layout_check"),
    ("Final inspection", "every hard gate + the judge on the content's scorecard + the audience read", "qa_check, judge_clip, engage"),
    ("1_CHECK", "only now does rico see it", "run.publish"),
]


def weighted_total(rep, maxes, style):
    """rep = {area: measured points}, maxes = {area: scale}. Returns (total 0-100, [areas under half], {area: (points, weight)}).
    An area weighted AREA_MIN[0]+ that scores under AREA_MIN[1] of its scale is listed in `under` (board rule: a funny
    clip with no hook still fails)."""
    w = profiles.weights(style)
    floor_w, floor_share = profiles.AREA_MIN
    total, under, out = 0.0, [], {}
    for k, v in rep.items():
        share = max(0.0, min(1.0, v / maxes[k])) if maxes.get(k) else 0.0
        pts = share * w.get(k, 0)
        out[k] = (pts, w.get(k, 0))
        total += pts
        if w.get(k, 0) >= floor_w and share < floor_share:
            under.append(f"{k} {v}/{maxes[k]}")
    return round(total), under, out


# 1080 x 1920 frame. Platform chrome: the top ~10% (status, tabs), the bottom ~20% (caption, music, handle), the right
# ~14% from 45% to 90% of the height (like / comment / share). Captions belong between 62% and 80% (rule 42: y 1400).
H, W = 1920, 1080
CAP_ZONE = (0.62, 0.80)
RIGHT_RAIL = (0.86, 0.45, 0.90)   # x share, y from, y to
HOOK_MAX_S = 6.5


def _t(ts):
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def layout_check(ass_path):
    """The Text & layout inspector on a finished clip's captions.ass. Returns {"fails": [...], "notes": [...]}.
    FAIL: captions at more than one height, captions outside the caption zone, the hook on screen past ~6 s, any text
    centred in the like/share rail. Clips made before the rules (no \\pos tags) only get notes."""
    p = Path(ass_path)
    if not p.exists():
        return {"fails": [], "notes": ["no captions.ass to inspect"]}
    caps, hooks, other = [], [], []
    for line in p.read_text(errors="ignore").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        start, end, style, text = _t(parts[1]), _t(parts[2]), parts[3], parts[9]
        m = re.search(r"\\pos\((\d+(?:\.\d+)?),(\d+(?:\.\d+)?)\)", text)
        xy = (float(m.group(1)), float(m.group(2))) if m else None
        (caps if style == "Cap" else hooks if style in ("Hook", "Tag") else other).append((start, end, xy, style))
    fails, notes = [], []
    ys = sorted({round(c[2][1]) for c in caps if c[2]})
    # time on screen per caption height: the main spot is the one held longest. A short stretch at the seam of a
    # b-roll card (render_clip CAP_Y "bottom") is a note; captions away from the main spot for 15%+ of the time FAIL
    held = {}
    for s0, e0, xy, _ in caps:
        if xy:
            held[round(xy[1])] = held.get(round(xy[1]), 0) + max(0.0, e0 - s0)
    tot = sum(held.values()) or 1
    main = max(held, key=held.get) if held else None
    away = sum(v for y, v in held.items() if abs(y - main) > 40) / tot if held else 0
    if away >= 0.15:
        fails.append(f"captions away from their spot ({main} px) for {away:.0%} of the time: one spot the whole clip")
    elif away > 0:
        notes.append(f"captions moved off their spot for {away:.0%} of the time (a card's seam)")
    if main is not None and not (CAP_ZONE[0] * H <= main <= CAP_ZONE[1] * H):
        fails.append(f"captions at y {main} px, outside the caption zone ({int(CAP_ZONE[0] * H)}-{int(CAP_ZONE[1] * H)})")
    late = max((e for s, e, _, _ in hooks), default=0)
    if late > HOOK_MAX_S:
        fails.append(f"hook text on screen until {late:.1f} s (it should fade by ~{HOOK_MAX_S - 1.5:.0f} s)")
    rx, ry0, ry1 = RIGHT_RAIL
    rail = [st for s, e, xy, st in caps + hooks + other if xy and xy[0] >= rx * W and ry0 * H <= xy[1] <= ry1 * H]
    if rail:
        fails.append(f"{len(rail)} text line(s) centred in the like/share rail")
    top = [st for s, e, xy, st in caps + other if xy and xy[1] < 0.08 * H]
    if top:
        notes.append(f"{len(top)} text line(s) in the top 8% (under the platform tabs)")
    if not any(c[2] for c in caps):
        notes.append("captions carry no position tags: height not checked")
    else:
        notes.append(f"captions at y {main} px")
    return {"fails": fails, "notes": notes}


FILLER = r"\b(um+|uh+|erm|like|you know|i mean|kind of|sort of|basically|literally)\b"


def speaker_check(words):
    """The campaign gate's listen (board deck: skip hard-to-listen speakers; Higgsfield 2026-10-31). words = the
    episode's whisper words. Returns (ok, why). Hard to listen = fillers over 9% of words, or 6+ restarts per 100
    words (a word repeated straight away: "I I", "the the"), or the talk runs under 1.6 words/s when people talk.
    Decides on the first 20 minutes (a whole interview is not needed to hear how someone talks)."""
    ws = [w for w in words or [] if w.get("start", 0) <= 1200 and w.get("text")]
    if len(ws) < 300:
        return True, "too few words to judge"
    toks = [re.sub(r"[^a-z']", "", w["text"].lower()) for w in ws]
    toks = [t for t in toks if t]
    n = max(len(toks), 1)
    fill = len(re.findall(FILLER, " ".join(toks))) / n
    restarts = sum(1 for a, b in zip(toks, toks[1:]) if a == b and a not in ("ha", "no", "yeah", "very", "so", "bye")) * 100 / n
    talk = sum(min(b["start"] - a["end"], 0.7) + (a["end"] - a["start"]) for a, b in zip(ws, ws[1:]) if b["start"] - a["end"] < 2.0)
    wps = len(ws) / max(talk, 1)
    why = f"fillers {fill:.1%}, restarts {restarts:.1f}/100 words, {wps:.1f} words/s when talking"
    bad = []
    if fill > 0.09:
        bad.append("too many fillers")
    if restarts >= 6:
        bad.append("keeps restarting")
    if wps < 1.6:
        bad.append("slow, mumbled delivery")
    return (not bad), ("; ".join(bad) + f" ({why})") if bad else why


def clip_cap(state, default=3, winners=6, approved_needed=2):
    """Board decision 3 (2026-10-31): 3 clips per campaign per run by default; up to 6 on a campaign that has proven
    itself, i.e. rico already approved 2+ of its clips (they are in 3_APPROVED: state["kits"]). Views per post are not
    logged yet; once data/posts.csv has them, 'earned views' joins the test."""
    approved = len((state or {}).get("kits") or {})
    return winners if approved >= approved_needed else default


if __name__ == "__main__":
    if len(sys.argv) > 1:
        r = layout_check(Path(sys.argv[1]) / "captions.ass")
        print("FAIL: " + "; ".join(r["fails"]) if r["fails"] else "PASS", "|", "; ".join(r["notes"]))
    else:
        for st, role, job, mod, back in ROSTER:
            print(f"{st:5}  {role:18}  {job}  [{mod}]  -> back to: {back}")
        print()
        for i, (name, what, where) in enumerate(INSPECTION_LINE, 1):
            print(f"{i}. {name}: {what}  [{where}]")
