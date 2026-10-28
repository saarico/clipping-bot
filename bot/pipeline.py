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

JUDGE_BAR = 70
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
    spec_path = work / "renders" / (Path(spec["out"]).stem + "_spec.json")
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
    dur = sum(b - a for a, b in json.loads((folder / "cut_details.json").read_text()).get("cuts", [[0, 0]]))
    res.update({"folder": folder, "mp4": folder / f"{folder.name}.mp4", "qa": qa, "fails": fails, "judge": js, "dur": round(dur, 1),
                "ok": qa == "PASS" and js >= JUDGE_BAR, "captions": (folder / "captions.txt").read_text() if (folder / "captions.txt").exists() else "",
                "minutes": round((time.time() - t0) / 60, 1)})
    return res


def run(work, source, brief, words=None, campaign="campaign", log=print, used=(), plan_dir=None):
    work, source = Path(work), Path(source)
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    words = Path(words) if words else work / "words.json"
    if not words.exists():
        log("transcribing (whisper small, CPU)")
        sh([PY, str(HERE / "transcribe.py"), str(source), str(words)], work / "transcribe.log", timeout=5 * 3600)
        if not words.exists():
            raise RuntimeError("transcription failed, see transcribe.log")
    gfx = work / "gfx.json"
    if not gfx.exists():
        sh([PY, str(HERE / "graphics_map.py"), str(source), str(gfx)], work / "gfx.log")
    specs, origin = planner.load(plan_dir or work, words, gfx if gfx.exists() else None, source, brief, campaign, work / "renders", used=used)
    (work / "renders").mkdir(exist_ok=True)
    kept, tried, notes = [], 0, [f"moments from: {origin}", f"transcript + graphics ready after {(time.time() - t0) / 60:.1f} min"]
    queue = list(specs[:planner.MAX_TRIES])
    # batches of up to PAR candidates rendered at the same time; the next batch only fills what is still missing
    while queue and len(kept) < planner.MAX_CLIPS:
        batch, queue = queue[:max(1, min(PAR, planner.MAX_CLIPS - len(kept)))], queue[max(1, min(PAR, planner.MAX_CLIPS - len(kept))):]
        for spec in batch:
            log(f"render {tried + 1}: {spec['hook']}")
            tried += 1
        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            results = list(ex.map(lambda sp: one_clip(sp[1], work, source, words, f"c{sp[0]:02d}"), enumerate(batch, tried - len(batch) + 1)))
        for res in results:
            if res.get("error"):
                notes.append(f"render failed: {res['hook']} {res['error']}")
                continue
            line = f"{Path(res['folder']).name}: {res['dur']:.0f}s  qa {res['qa']}  judge {res['judge']}  {res.get('minutes', '?')} min  hook: {res['hook']}  [{res['why']}]"
            if res["ok"] and len(kept) < planner.MAX_CLIPS:
                kept.append({"folder": str(res["folder"]), "mp4": str(res["mp4"]), "hook": res["hook"], "parts": res["parts"], "judge": res["judge"],
                             "dur": res["dur"], "why": res["why"], "captions": res["captions"]})
                notes.append("KEPT  " + line)
            else:
                notes.append("DROP  " + line + ("  " + "; ".join(res["fails"]) if res["fails"] else ""))
                dropped = work / "dropped" / Path(res["folder"]).name
                if not dropped.exists():
                    shutil.move(str(res["folder"]), str(dropped))
    notes.append(f"{len(kept)} clip(s) kept of {tried} rendered, {PAR} at a time, in {(time.time() - t0) / 60:.0f} min")
    summary = "\n".join(notes)
    (work / "summary.txt").write_text(summary)
    log(summary)
    return kept, summary


if __name__ == "__main__":
    a = sys.argv[1:]
    w = a[a.index("--words") + 1] if "--words" in a else None
    brief = json.loads(Path(a[2]).read_text()) if len(a) > 2 and Path(a[2]).exists() else {"min_s": 20, "max_s": 60, "tags": []}
    run(a[0], a[1], brief, w, campaign=Path(a[0]).name)
