"""The cutting line for ONE campaign, with no Drive in it (so it can run and be tested anywhere):

  words + graphics + brief  ->  specs (plan.py)  ->  render  ->  QA  ->  machine judge  ->  keep / next

  python3 bot/pipeline.py <work dir> <episode.mp4> <brief.json> [--words words.json]

Writes <work dir>/clips/<n>_<slug>/ (mp4, captions, qa_report.md, judge_report.md) and
<work dir>/summary.txt. Bar: QA has no FAIL and the machine judge >= JUDGE_BAR. Under the bar means
the next moment is tried; nothing is re-cut in a loop (max MAX_TRIES renders).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import engage  # noqa: E402
import plan as planner  # noqa: E402
import lanes  # noqa: E402

JUDGE_BAR = 80    # 2026-10-28: rico wants "amazing high tier quality"; under the bar = re-edit once, then the next moment
NEAR_BAR = 75     # a clip that passes every hard gate at 75-79 is handed over marked "under the bar" when nothing reaches 80
PY = sys.executable


def sh(args, log=None, timeout=3600):
    """A step as a subprocess. A step that runs out of time comes back as a failed result (returncode 124) instead of
    an exception: one stuck render used to take the whole machine's other work down with it."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        r = subprocess.CompletedProcess(args, 124, (e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                                        f"timed out after {timeout} s: {Path(str(args[1])).name if len(args) > 1 else args[0]}")
    if log:
        Path(log).write_text(r.stdout + "\n" + r.stderr)
    return r


def qa_verdict(folder):
    rep = (Path(folder) / "qa_report.md").read_text() if (Path(folder) / "qa_report.md").exists() else ""
    fails = [l.strip() for l in rep.splitlines() if re.match(r"^\|[^|]+\|\s*FAIL\s*\|", l)]   # table rows only
    return ("PASS" if not fails and "PASS" in rep else "FAIL"), fails[:6]


def judge_score(folder):
    rep = Path(folder) / "judge_report.md"
    if not rep.exists():
        return 0
    m = re.search(r"achine[^\d]{0,20}(\d{1,3})\s*/\s*100", rep.read_text())
    return int(m.group(1)) if m else 0


PAR = int(os.environ.get("CLIP_PARALLEL", "3"))   # renders at the same time (GitHub runners have 4 cores)


def one_clip(spec, work, source, words, tag):
    """Render one candidate, build its folder, run QA + judge. Returns a result dict (never raises)."""
    why = spec.pop("_why", "")
    if (Path(work) / "watermark.png").exists():   # the campaign's required watermark (run.get_watermark), on screen the whole clip
        spec.setdefault("watermark", str(Path(work) / "watermark.png"))
    spec_path = work / "renders" / f"{tag}_{Path(spec['out']).stem}_spec.json"   # unique per try: two renders of one slug raced on this file (run 2)
    spec_path.write_text(json.dumps(spec, indent=1))
    t0 = time.time()
    r = sh([PY, str(HERE / "render_clip.py"), str(spec_path)], spec_path.with_suffix(".log"), timeout=2400)
    out = Path(spec["out"])
    res = {"hook": spec["hook"], "why": why, "parts": spec.get("parts", []), "ok": False, "qa": "FAIL", "judge": 0, "fails": [], "dur": 0,
           "style": spec.get("style", ""), "lane_pin": spec.get("lane"),
           "thumb_text": spec.get("thumb_text", ""), "thumb_t": spec.get("thumb_t"), "emphasis": spec.get("emphasis", [])}
    if r.returncode != 0 or not out.exists():
        res["error"] = f"render failed ({(r.stderr or r.stdout)[-200:].strip()})"
        return res
    folder = work / "clips" / f"{tag}_{out.stem}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cut_details.json").write_text("{}")
    sh([PY, str(HERE / "build_clip_folder.py"), str(out), str(folder), str(spec_path)], folder / "build.log")
    shutil.copy(words, folder / "words.json")
    sh([PY, str(HERE / "qa_check.py"), str(folder), "--source", str(source)], folder / "qa.log", timeout=1800)
    sh([PY, str(HERE / "judge_clip.py"), str(folder)], folder / "judge.log")
    sh([PY, str(HERE / "engage.py"), str(folder)], folder / "engage.log")
    thumb = None
    try:
        # thumbnail (rico 2026-10-29): the actor's best reacting frame + the hook in big text, saved beside the clip
        # and appended as the clip's last two frames for the YouTube / TikTok frame pickers (after QA: QA ignores it)
        import thumbnail
        thumb = folder / "thumbnail.png"
        thumbnail.make(str(source), spec.get("hook", ""), spec.get("parts", []), str(thumb), text=spec.get("thumb_text"),
                       at=spec.get("thumb_t"), emphasis=spec.get("emphasis", []), options=str(folder / "thumbnail_options.jpg"))
        thumbnail.append_cover(folder / f"{folder.name}.mp4", thumb)
    except Exception as e:
        print(f"thumbnail failed: {e}")
        thumb = None
    qa, fails = qa_verdict(folder)
    js = judge_score(folder)
    # the audience read (engage.py): a second pass with its own gates; a gate failure counts like a QA failure
    aud = {"total": 0, "fails": ["audience read missing"], "fix": {}}
    try:
        aud = engage.read_folder(folder)
    except Exception as e:
        aud["fails"] = [f"audience read failed: {e}"]
    if aud["fails"]:
        fails = fails + [f"| Audience read | FAIL | {f} |" for f in aud["fails"]]
        qa = "FAIL"
    elif aud["total"] < engage.BAR:
        fails = fails + [f"| Audience read | UNDER | {aud['total']} under {engage.BAR} |"]
    jn = {}
    try:
        for line in (folder / "judge_report.md").read_text().splitlines():
            m = re.match(r"\| (\w+) \| (\d+)/(\d+) \| (.*) \|", line)
            if m and int(m.group(2)) < int(m.group(3)) * 0.6 and m.group(4).strip():
                jn[m.group(1)] = m.group(4).strip()
    except Exception:
        pass
    dur = sum(b - a for a, b in json.loads((folder / "cut_details.json").read_text()).get("cuts", [[0, 0]]))
    areas = ""
    try:
        last = [l for l in (folder / "judge.log").read_text().splitlines() if "machine" in l]
        areas = last[-1].split("machine", 1)[1].strip() if last else ""
    except Exception:
        pass
    res.update({"folder": folder, "mp4": folder / f"{folder.name}.mp4", "thumb": str(thumb) if thumb and thumb.exists() else "",
                "qa": qa, "fails": fails, "judge": js, "dur": round(dur, 1), "caption": spec.get("caption", ""),
                "ok": qa == "PASS" and js >= JUDGE_BAR and aud["total"] >= engage.BAR,
                "near": qa == "PASS" and js >= NEAR_BAR and aud["total"] >= engage.BAR - 5,
                "audience": aud["total"], "audience_fix": aud.get("fix", {}), "judge_notes": jn, "areas": areas,
                "captions": (folder / "captions.txt").read_text() if (folder / "captions.txt").exists() else "",
                "minutes": round((time.time() - t0) / 60, 1)})
    return res


def prepare(work, source, brief, words=None, campaign="campaign", log=print, used=(), plan_dir=None):
    """Everything before rendering: transcript, graphics map, the picks. Returns (specs, origin, words, notes)."""
    work, source = Path(work), Path(source)
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    words = Path(words) if words else work / "words.json"
    if not words.exists():
        log("transcribing (whisper on CPU: medium under 25 min, else small)")
        sh([PY, str(HERE / "transcribe.py"), str(source), str(words)], work / "transcribe.log", timeout=5 * 3600)
        if not words.exists():
            raise RuntimeError("transcription failed, see transcribe.log")
    gfx = work / "gfx.json"
    if not gfx.exists():
        sh([PY, str(HERE / "graphics_map.py"), str(source), str(gfx)], work / "gfx.log")
    specs, origin = planner.load(plan_dir or work, words, gfx if gfx.exists() else None, source, brief, campaign, work / "renders", used=used)
    (work / "renders").mkdir(exist_ok=True)
    notes = [f"moments from: {origin}", f"style: {brief.get('style') or 'podcast'}" + (f", look: {json.dumps(brief['look'])}" if brief.get("look") else ""),
             f"transcript + graphics ready after {(time.time() - t0) / 60:.1f} min"]
    # the pitch (rico 2026-10-29): read every candidate's words against the campaign's style before spending a render on it
    import pitch
    specs, pnotes = pitch.gate(specs, json.loads(Path(words).read_text()), brief, log=log)
    return specs, origin, words, notes + pnotes


def reedit(spec, res):
    """The one re-edit a failed clip gets (rico, 2026-10-28: "grade the outcome and throw it back to re-edit"):
    punch in harder on the actors; when the opening failed start on the next spoken line; when an edge clipped a
    word or the clip ended mid-sentence (2026-10-30, Higgsfield c02 was re-rendered identically and failed twice),
    move the start to the next sentence start and the end back to the last finished sentence that keeps the clip
    inside the brief's length window."""
    v = json.loads(json.dumps(spec))
    v["zoom_boost"] = 1.15
    v["reedit"] = True
    fails = " ".join(res.get("fails", []))
    words = None
    try:
        words = json.loads(Path(spec["words"]).read_text())
    except Exception:
        pass
    a, b = v["parts"][0]
    if words and ("first 2 seconds" in fails or "Opener" in fails or res.get("judge_notes", {}).get("hook")):
        nxt = [w["start"] for w in words if a + 0.8 <= w["start"] <= a + 4.0 and w["text"][:1].isupper()]
        if nxt and b - nxt[0] >= 10:
            a = round(nxt[0] - 0.1, 2)
    if words and ("Cut edges" in fails or "finished sentence" in fails or "cuts through" in fails):
        import find_moments as fm
        lens = spec.get("brief") or {}
        min_s, max_s = lens.get("min_s", 20), lens.get("max_s", 60)
        sents = [x for x in fm.sentences(words) if x["text"].rstrip('"\')').endswith((".", "?", "!"))]
        if "start" in fails and "cuts through" in fails:
            starts = [x["start"] for x in sents if a - 0.3 < x["start"] <= a + 6.0]
            if starts and b - starts[0] >= min_s:
                a = round(starts[0] - 0.12, 2)
        # the end: the last finished sentence that ends before the old end and keeps the clip long enough;
        # when nothing fits, the first one after it that still fits the maximum
        ends = sorted(x["end"] for x in sents if a + min_s <= x["end"] <= b - 0.25)
        if not ends:
            ends = sorted(x["end"] for x in sents if b - 0.25 < x["end"] <= a + max_s)
        if ends:
            b = round(ends[-1] + 0.1, 2) if ends[-1] <= b else round(ends[0] + 0.1, 2)
    # a stray cut (the show's own camera change) inside the first or last 1.5 s: move that edge past it
    for m in re.finditer(r"stray cut at ([\d.]+)s", fails):
        t = float(m.group(1))
        if t < 1.5 and b - (a + t + 0.3) >= 8:
            a = round(a + t + 0.3, 2)
        elif res.get("dur") and t > res["dur"] - 1.5:
            b = round(b - (res["dur"] - t) - 0.3, 2)
    # the audience read says where the clip should start and end instead (host preamble, aside endings)
    fx = res.get("audience_fix") or {}
    if "Audience read" in fails:
        if fx.get("start") and fx["start"] > a and b - fx["start"] >= 8:
            a = round(fx["start"] - 0.12, 2)
        if fx.get("end") and a < fx["end"] < b:
            b = round(fx["end"] + 0.1, 2)
    if [a, b] != v["parts"][0] and b - a >= 8:
        v["parts"][0] = [a, b]
    v["out"] = str(Path(spec["out"]).with_name(Path(spec["out"]).stem + "-v2.mp4"))
    v["_why"] = "re-edit: " + str(res.get("why", "")) + " | after: " + "; ".join(res.get("fails", [])[:3])
    return v


def try_until(specs, work, source, words, tag, budget=3, log=print):
    """Grade-and-retry on one machine: render the first spec; under the bar -> one re-edit; still under ->
    the next spec (a better moment). At most `budget` renders. Returns (best result, all results)."""
    results, best, n = [], None, 0
    # the best failed try: one that passed every production gate (near) beats a higher judge score with a QA failure,
    # because decide() may still hand a "near" clip to rico and never a QA-FAIL one
    rank = lambda r: (int(bool(r.get("near"))), int(r.get("qa") == "PASS"), r.get("judge", 0))
    for spec in specs:
        if n >= budget:
            break
        log(f"render {tag} try {n + 1}: {spec['hook']}")
        res = one_clip(json.loads(json.dumps(spec)), work, source, words, tag if n == 0 else f"{tag}r{n}")
        n += 1
        results.append(res)
        if res["ok"]:
            return res, results
        best = res if best is None or rank(res) > rank(best) else best
        if res.get("error") or n >= budget:
            continue
        v = reedit(spec, res)
        log(f"render {tag} try {n + 1}: re-edit ({'; '.join(res.get('fails', [])[:2]) or 'judge ' + str(res.get('judge'))})")
        res2 = one_clip(v, work, source, words, f"{tag}r{n}")
        n += 1
        results.append(res2)
        if res2["ok"]:
            return res2, results
        best = res2 if rank(res2) > rank(best) else best
    return best, results


def decide(results, work, kept=None, notes=None):
    """Keep the first MAX_CLIPS results that passed QA and the judge; move the rest to work/dropped."""
    kept, notes = kept if kept is not None else [], notes if notes is not None else []
    for res in results:
        if res.get("error"):
            notes.append(f"render failed: {res['hook']} {res['error']}")
            continue
        line = f"{Path(res['folder']).name}: {res['dur']:.0f}s  qa {res['qa']}  judge {res['judge']} ({res.get('areas', '')})  {res.get('minutes', '?')} min  hook: {res['hook']}  [{res['why']}]"
        if res["ok"] and len(kept) < planner.MAX_CLIPS:
            kept.append({"folder": str(res["folder"]), "mp4": str(res["mp4"]), "thumb": res.get("thumb", ""), "hook": res["hook"], "parts": res["parts"], "judge": res["judge"], "audience": res.get("audience"),
                         "dur": res["dur"], "why": res["why"], "captions": res["captions"], "caption": res.get("caption", "")})
            notes.append("KEPT  " + line)
        elif res.get("near") and not any(r.get("ok") for r in results) and len(kept) < planner.MAX_CLIPS:
            # every hard production gate passed but the entertainment judge stayed under the bar, and nothing
            # in this run reached it: hand rico the best of them, clearly marked, rather than an empty folder
            res["why"] = f"UNDER THE BAR (judge {res['judge']} < {JUDGE_BAR}, every production gate passed) | " + res["why"]
            kept.append({"folder": str(res["folder"]), "mp4": str(res["mp4"]), "thumb": res.get("thumb", ""), "hook": res["hook"], "parts": res["parts"], "judge": res["judge"], "audience": res.get("audience"),
                         "dur": res["dur"], "why": res["why"], "captions": res["captions"], "caption": res.get("caption", "")})
            notes.append("KEPT (under the bar)  " + line)
        else:
            notes.append("DROP  " + line + ("  " + "; ".join(res["fails"]) if res["fails"] else ""))
            dropped = Path(work) / "dropped" / Path(res["folder"]).name
            if Path(res["folder"]).exists() and not dropped.exists():
                dropped.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(res["folder"]), str(dropped))
    # one platform per clip, by what the clip is about (bot/lanes.py); shown in the SUMMARY and used by the POST KIT
    by_hook = {r["hook"]: r for r in results if not r.get("error")}
    picks = lanes.assign([{"hook": k["hook"], "text": " ".join(k.get("captions", "").split()),
                           "style": by_hook.get(k["hook"], {}).get("style", ""), "lane": by_hook.get(k["hook"], {}).get("lane_pin")} for k in kept])
    for k, (lane, why) in zip(kept, picks):
        k["lane"], k["lane_why"] = lane, why
        notes.append(f"LANE  {Path(k['folder']).name}: {lane} ({why})")
    return kept, notes


def run(work, source, brief, words=None, campaign="campaign", log=print, used=(), plan_dir=None):
    """One machine: prepare, then render PAR candidates at a time until MAX_CLIPS pass (local runs, fallback)."""
    t0 = time.time()
    specs, origin, words, notes = prepare(work, source, brief, words, campaign, log, used, plan_dir)
    work = Path(work)
    kept = []
    slots = min(planner.MAX_CLIPS, len(specs))
    lanes = [specs[i::slots] for i in range(slots)]   # each slot: its moment, then the fallbacks it may fall through to
    with ThreadPoolExecutor(max_workers=max(1, min(PAR, slots))) as ex:
        outs = list(ex.map(lambda it: try_until(it[1], work, source, words, f"c{it[0] + 1:02d}", log=log), enumerate(lanes)))
    tried = sum(len(r) for _, r in outs)
    rendered = [r for _, rs in outs for r in rs if not r.get("error")]   # every finished render, for the campaign's tried_moments
    results = sorted([b for b, _ in outs if b], key=lambda r: (-int(r.get("ok", False)), -r.get("judge", 0)))
    for _, rs in outs:
        for r in rs[:-1]:
            notes.append(f"TRY   {Path(str(r.get('folder', r['hook']))).name}: qa {r.get('qa')} judge {r.get('judge')}  {'; '.join(r.get('fails', [])[:3])}")
    decide(results, work, kept, notes)
    notes.append(f"{len(kept)} clip(s) kept of {tried} rendered, {slots} lanes with grade-and-retry, in {(time.time() - t0) / 60:.0f} min")
    summary = "\n".join(notes)
    (work / "summary.txt").write_text(summary)
    log(summary)
    return kept, summary, rendered


if __name__ == "__main__":
    a = sys.argv[1:]
    w = a[a.index("--words") + 1] if "--words" in a else None
    brief = json.loads(Path(a[2]).read_text()) if len(a) > 2 and Path(a[2]).exists() else {"min_s": 20, "max_s": 60, "tags": []}
    run(a[0], a[1], brief, w, campaign=Path(a[0]).name)[:2]
