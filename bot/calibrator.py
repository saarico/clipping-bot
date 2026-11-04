"""Calibrator (makeover release 9, board review 3, approved by rico 2026-11-04).

Why: the board rejected Weeknd clips the judge scored 92, 85 and 84 (deck slide 2). A grader that disagrees with rico
cannot decide what reaches 1_CHECK. The Calibrator keeps the judge honest with rico's own verdicts:

  data/verdicts.csv     one row per clip rico (or the board) decided on: time, campaign, clip, verdict
                        (approved = moved to 3_APPROVED, redo = a note in 2_REDO while it waited, rejected = the board),
                        judge (the score the clip had), style
  data/calibration.json the bar that agrees best with those verdicts, the agreement and how many verdicts it rests on

  record(...)      run.py writes a row when a clip is approved or a critique arrives for the clips in 1_CHECK
  calibrate()      the bar in BAR_RANGE that sorts the verdicts best (ties: the lower bar); agreement on that bar
  bar()            the judge bar pipeline.py uses: the board's 80 until MIN_VERDICTS verdicts exist, then the
                   calibrated bar (never under 80: calibration only ever raises it)
  trusted()        (ok, note): the judge may pass clips on its own only while it agrees with rico on TRUST+ of them
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
VERDICTS = DATA / "verdicts.csv"
CALIB = DATA / "calibration.json"
COLS = ["time", "campaign", "clip", "verdict", "judge", "style"]
BOARD_BAR = 80
BAR_RANGE = range(80, 96)
MIN_VERDICTS = 6
TRUST = 0.8


def _rows(path):
    try:
        with open(path, newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def record(campaign, clip, verdict, judge, style="", path=None):
    """One verdict; a clip already decided keeps its first verdict (approved after a redo note is a new clip name)."""
    path = Path(path or VERDICTS)
    rows = _rows(path)
    if any(r["campaign"] == campaign and r["clip"] == clip for r in rows):
        return False
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({"time": datetime.now(timezone.utc).isoformat(timespec="minutes"), "campaign": campaign, "clip": clip,
                    "verdict": verdict, "judge": judge if judge is not None else "", "style": style or ""})
    return True


def calibrate(path=None, out=None):
    """{"bar", "agreement", "n", "at"} from the verdicts with a judge score; written to data/calibration.json."""
    pts = []
    for r in _rows(Path(path or VERDICTS)):
        try:
            pts.append((float(r["judge"]), r["verdict"] == "approved"))
        except (KeyError, ValueError):
            continue
    res = {"bar": BOARD_BAR, "agreement": None, "n": len(pts), "at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    if pts:
        def agree(b):
            return sum((j >= b) == ok for j, ok in pts) / len(pts)
        best = max(BAR_RANGE, key=lambda b: (agree(b), -b))   # the lowest bar that agrees best: the smallest raise
        res.update(bar=best, agreement=round(agree(best), 2), board_agreement=round(agree(BOARD_BAR), 2))
    if out is not False:
        Path(out or CALIB).write_text(json.dumps(res, indent=1))
    return res


def _calib():
    try:
        return json.loads(CALIB.read_text())
    except (OSError, ValueError):
        return {}


def bar():
    c = _calib()
    if c.get("n", 0) >= MIN_VERDICTS and c.get("bar"):
        return max(BOARD_BAR, int(c["bar"]))
    return BOARD_BAR


def trusted():
    """(ok, note) for the SUMMARY: how far the judge agrees with rico."""
    c = _calib()
    n, a = c.get("n", 0), c.get("agreement")
    if n < MIN_VERDICTS or a is None:
        return True, f"Calibrator: {n} verdict(s) from rico so far; the judge bar stays at {BOARD_BAR} until {MIN_VERDICTS}"
    if a < TRUST:
        return False, (f"Calibrator: the judge agrees with rico on {a:.0%} of {n} verdicts (under {TRUST:.0%}): bar raised to "
                       f"{bar()}; clips are marked for a closer look")
    return True, f"Calibrator: the judge agrees with rico on {a:.0%} of {n} verdicts; bar {bar()}"


if __name__ == "__main__":
    print(json.dumps(calibrate(), indent=1))
