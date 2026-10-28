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
import plan as planner  # noqa: E402

JUDGE_BAR = 76   # 2026-10-28: rico wants "amazing high tier quality"; under the bar = re-edit once, then the next moment
PY = sys.executable


def sh(args, log=None, timeout=3600):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
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
    spec_path = work / "renders" / f"{tag}_{Path(spec['out']).stem}_spec.json"   # unique per try: two renders of one slug raced on this file (run 2)
    spec_path.write_text(json.dumps(spec, indent=1))
    t0 = time.time()
    r = sh([PY, str(HERE / "render_clip.py"), str(spec_path)], spec_path.with_suffix(".log"), timeout=2400)
    out = Path(spec["out"])
    res = {"hook": spec["hook"], "why": why, "parts": spec.get("parts", []), "ok": False, "qa": "FAIL", "judge": 0, "fails": [], "dur": 0}
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
    qa, fails = qa_verdict(folder)
    js = judge_score(folder)
    jn = {}
    try:
        for line in (folder / "judge_report.md").read_text().splitlines():
            m = re.match(r"\| (\w+) \| (\d+)/(\d+) \| (.*) \|", line)
            if m and int(m.group(2)) < int(m.group(3)) * 0.6 and m.group(4).strip():
                jn[m.group(1)] = m.group(4).strip()
    except Exception:
        pass
    dur = sum(b - a for a, b in json.loads((folder / "cut_details.json").read_text()).get("cuts", [[0, 0]]))
    res.update({"folder": folder, "mp4": folder / f"{folder.name}.mp4", "qa": qa, "fails": fails, "judge": js, "dur": round(dur, 1), "caption": spec.get("caption", ""),
                "ok": qa == "PASS" and js >= JUDGE_BAR, "judge_notes": jn, "captions": (folder / "captions.txt").read_text() if (folder / "captions.txt").exists() else "",
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
    return specs, origin, words, [f"moments from: {origin}", f"transcript + graphics ready after {(time.time() - t0) / 60:.1f} min"]


def reedit(spec, res):
    """The one re-edit a failed clip gets (rico, 2026-10-28: "grade the outcome and throw it back to re-edit"):
    punch in harder on the actors, and when the opening failed start on the next spoken line."""
    v = json.loads(json.dumps(spec))
    v["zoom_boost"] = 1.15
    v["reedit"] = True
    fails = " ".join(res.get("fails", []))
    if "first 2 seconds" in fails or "Opener" in fails or res.get("judge_notes", {}).get("hook"):
        try:
            words = json.loads(Path(spec["words"]).read_text())
            a, b = v["parts"][0]
            nxt = [w["start"] for w in words if a + 0.8 <= w["start"] <= a + 4.0 and w["text"][:1].isupper()]
            if nxt and b - nxt[0] >= 10:
                v["parts"][0] = [round(nxt[0] - 0.1, 2), b]
        except Exception:
            pass
    v["out"] = str(Path(spec["out"]).with_name(Path(spec["out"]).stem + "-v2.mp4"))
    v["_why"] = "re-edit: " + str(res.get("why", "")) + " | after: " + "; ".join(res.get("fails", [])[:3])
    return v


def try_until(specs, work, source, words, tag, budget=3, log=print):
    """Grade-and-retry on one machine: render the first spec; under the bar -> one re-edit; still under ->
    the next spec (a better moment). At most `budget` renders. Returns (best result, all results)."""
    results, best, n = [], None, 0
    for spec in specs:
        if n >= budget:
            break
        log(f"render {tag} try {n + 1}: {spec['hook']}")
        res = one_clip(json.loads(json.dumps(spec)), work, source, words, tag if n == 0 else f"{tag}r{n}")
        n += 1
        results.append(res)
        if res["ok"]:
            return res, results
        best = res if best is None or res.get("judge", 0) > best.get("judge", 0) else best
        if res.get("error") or n >= budget:
            continue
        v = reedit(spec, res)
        log(f"render {tag} try {n + 1}: re-edit ({'; '.join(res.get('fails', [])[:2]) or 'judge ' + str(res.get('judge'))})")
        res2 = one_clip(v, work, source, words, f"{tag}r{n}")
        n += 1
        results.append(res2)
        if res2["ok"]:
            return res2, results
        best = res2 if res2.get("judge", 0) > best.get("judge", 0) else best
    return best, results


def decide(results, work, kept=None, notes=None):
    """Keep the first MAX_CLIPS results that passed QA and the judge; move the rest to work/dropped."""
    kept, notes = kept if kept is not None else [], notes if notes is not None else []
    for res in results:
        if res.get("error"):
            notes.append(f"render failed: {res['hook']} {res['error']}")
            continue
        line = f"{Path(res['folder']).name}: {res['dur']:.0f}s  qa {res['qa']}  judge {res['judge']}  {res.get('minutes', '?')} min  hook: {res['hook']}  [{res['why']}]"
        if res["ok"] and len(kept) < planner.MAX_CLIPS:
            kept.append({"folder": str(res["folder"]), "mp4": str(res["mp4"]), "hook": res["hook"], "parts": res["parts"], "judge": res["judge"],
                         "dur": res["dur"], "why": res["why"], "captions": res["captions"], "caption": res.get("caption", "")})
            notes.append("KEPT  " + line)
        else:
            notes.append("DROP  " + line + ("  " + "; ".join(res["fails"]) if res["fails"] else ""))
            dropped = Path(work) / "dropped" / Path(res["folder"]).name
            if Path(res["folder"]).exists() and not dropped.exists():
                dropped.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(res["folder"]), str(dropped))
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
    results = sorted([b for b, _ in outs if b], key=lambda r: (-int(r.get("ok", False)), -r.get("judge", 0)))
    for _, rs in outs:
        for r in rs[:-1]:
            notes.append(f"TRY   {Path(str(r.get('folder', r['hook']))).name}: qa {r.get('qa')} judge {r.get('judge')}  {'; '.join(r.get('fails', [])[:3])}")
    decide(results, work, kept, notes)
    notes.append(f"{len(kept)} clip(s) kept of {tried} rendered, {slots} lanes with grade-and-retry, in {(time.time() - t0) / 60:.0f} min")
    summary = "\n".join(notes)
    (work / "summary.txt").write_text(summary)
    log(summary)
    return kept, summary


if __name__ == "__main__":
    a = sys.argv[1:]
    w = a[a.index("--words") + 1] if "--words" in a else None
    brief = json.loads(Path(a[2]).read_text()) if len(a) > 2 and Path(a[2]).exists() else {"min_s": 20, "max_s": 60, "tags": []}
    run(a[0], a[1], brief, w, campaign=Path(a[0]).name)
