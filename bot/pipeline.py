"""The cutting line for ONE campaign, with no Drive in it (so it can run and be tested anywhere):

  words + graphics + brief  ->  specs (plan.py)  ->  render  ->  QA  ->  machine judge  ->  keep / next

  python3 bot/pipeline.py <work dir> <episode.mp4> <brief.json> [--words words.json]

Writes <work dir>/clips/<n>_<slug>/ (mp4, captions, qa_report.md, judge_report.md) and
<work dir>/summary.txt. Bar: QA has no FAIL and the machine judge >= JUDGE_BAR. Under the bar means
the next moment is tried; nothing is re-cut in a loop (max MAX_TRIES renders).
"""
import json
import re
import shutil
import subprocess
import sys
import time
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
    kept, tried, notes = [], 0, [f"moments from: {origin}"]
    for spec in specs:
        if len(kept) >= planner.MAX_CLIPS or tried >= planner.MAX_TRIES:
            break
        tried += 1
        why = spec.pop("_why", "")
        spec_path = work / "renders" / (Path(spec["out"]).stem + "_spec.json")
        spec_path.write_text(json.dumps(spec, indent=1))
        log(f"render {tried}: {spec['hook']}")
        r = sh([PY, str(HERE / "render_clip.py"), str(spec_path)], spec_path.with_suffix(".log"), timeout=2400)
        out = Path(spec["out"])
        if r.returncode != 0 or not out.exists():
            notes.append(f"render failed: {spec['hook']} ({(r.stderr or r.stdout)[-200:].strip()})")
            continue
        folder = work / "clips" / f"{len(kept) + 1:02d}_{out.stem}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "cut_details.json").write_text("{}")
        sh([PY, str(HERE / "build_clip_folder.py"), str(out), str(folder), str(spec_path)], folder / "build.log")
        shutil.copy(words, folder / "words.json")
        sh([PY, str(HERE / "qa_check.py"), str(folder), "--source", str(source)], folder / "qa.log", timeout=1800)
        sh([PY, str(HERE / "judge_clip.py"), str(folder)], folder / "judge.log")
        qa, fails = qa_verdict(folder)
        js = judge_score(folder)
        dur = sum(b - a for a, b in json.loads((folder / "cut_details.json").read_text()).get("cuts", [[0, 0]]))
        line = f"{folder.name}: {dur:.0f}s  qa {qa}  judge {js}  hook: {spec['hook']}  [{why}]"
        if qa == "PASS" and js >= JUDGE_BAR:
            kept.append({"folder": str(folder), "mp4": str(folder / f"{folder.name}.mp4"), "hook": spec["hook"], "parts": spec.get("parts", []),
                         "judge": js, "dur": round(dur, 1), "why": why, "captions": (folder / "captions.txt").read_text()})
            notes.append("KEPT  " + line)
        else:
            notes.append("DROP  " + line + ("  " + "; ".join(fails) if fails else ""))
            shutil.move(str(folder), str(work / "dropped" / folder.name)) if not (work / "dropped" / folder.name).exists() else None
    notes.append(f"{len(kept)} clip(s) kept of {tried} rendered in {(time.time() - t0) / 60:.0f} min")
    summary = "\n".join(notes)
    (work / "summary.txt").write_text(summary)
    log(summary)
    return kept, summary


if __name__ == "__main__":
    a = sys.argv[1:]
    w = a[a.index("--words") + 1] if "--words" in a else None
    brief = json.loads(Path(a[2]).read_text()) if len(a) > 2 and Path(a[2]).exists() else {"min_s": 20, "max_s": 60, "tags": []}
    run(a[0], a[1], brief, w, campaign=Path(a[0]).name)
