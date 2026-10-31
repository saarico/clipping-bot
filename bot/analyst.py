"""The Analyst (Studio v2 release 4): real views feed the judge's weights.

Two files in data/ (committed by every run):
  clip_scores.csv  one row per clip sent to 1_CHECK: time, campaign, clip (the name in 1_CHECK), style, judge,
                   areas (JSON of the judge's measured points per area). Written by run.publish via record().
  posts.csv        rico's log of what was posted: campaign, clip, platform, account, post_url, posted_at, views_7d.

review() joins the two on (campaign, clip). For every content type (profiles.WEIGHTS) with MIN_POSTS or more posts
that have 7-day views, it ranks the areas by how well their points track views (Spearman) and nudges the weights:
the two areas that track views best +STEP each, the two that track worst -STEP each. An area never moves more than
MAX_SHIFT from the board's table, never goes under 0, and the weights still sum to 100. The result goes to
data/weights_tuned.json, which profiles.weights() reads; the board's table stays the source of truth in profiles.py.
Below MIN_POSTS nothing changes and the SUMMARY says how many posts are still needed.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import profiles  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
SCORES = DATA / "clip_scores.csv"
POSTS = DATA / "posts.csv"
TUNED = DATA / "weights_tuned.json"
MIN_POSTS = 20     # per content type, with 7-day views
STEP = 2           # weight points moved per area per review
MAX_SHIFT = 6      # an area never moves further than this from the board's table


def record(campaign, clip, style, judge, areas, path=None):
    """One row per clip sent to rico. areas: {area: measured points}."""
    path = Path(path or SCORES)
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "campaign", "clip", "style", "judge", "areas"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="minutes"), campaign, clip, style or "podcast",
                    judge, json.dumps(areas or {})])


def areas_from_report(report_md):
    """{area: measured points} from a judge_report.md table (| area | 12/20 | weight | points | notes |)."""
    import re
    out = {}
    try:
        for line in Path(report_md).read_text().splitlines():
            m = re.match(r"\| (\w+) \| (\d+)/(\d+) \|", line)
            if m:
                out[m.group(1)] = int(m.group(2)) / int(m.group(3))   # 0-1, comparable across scales
    except OSError:
        pass
    return out


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(xs, ys):
    if len(xs) < 3:
        return 0.0
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def _rows(path):
    try:
        with open(path, newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def nudge(board, corr):
    """board: {area: weight} summing to 100; corr: {area: rho}. Returns new weights (sum 100)."""
    w = dict(board)
    ranked = sorted((a for a in corr if a in w), key=lambda a: corr[a])
    if len(ranked) < 4:
        return w
    down = [a for a in ranked[:2] if corr[a] < 0.1]
    up = [a for a in ranked[-2:][::-1] if corr[a] > 0.1]
    for a in up:
        w[a] = min(board[a] + MAX_SHIFT, w[a] + STEP)
    for a in down:
        w[a] = max(0, board[a] - MAX_SHIFT, w[a] - STEP)
    # keep the sum at 100: the difference comes off (or goes onto) the areas nobody moved, largest first
    diff = sum(w.values()) - 100
    rest = sorted((a for a in w if a not in up and a not in down), key=lambda a: -w[a])
    k = 0
    while diff and rest and k < 1000:
        a = rest[k % len(rest)]
        if diff > 0 and w[a] > 0:
            w[a] -= 1
            diff -= 1
        elif diff < 0:
            w[a] += 1
            diff += 1
        k += 1
    return w


def review(scores=None, posts=None, tuned=None):
    """Returns (notes, tuned dict). Writes tuned to data/weights_tuned.json when any content type has enough posts."""
    scores, posts, tuned_path = _rows(scores or SCORES), _rows(posts or POSTS), Path(tuned or TUNED)
    views = {}
    for p in posts:
        try:
            views[(p["campaign"].strip(), p["clip"].strip())] = float(p["views_7d"])
        except (KeyError, ValueError, AttributeError):
            continue
    by = {}
    for s in scores:
        v = views.get((s["campaign"].strip(), s["clip"].strip()))
        if v is not None:
            by.setdefault(s["style"] or "podcast", []).append((json.loads(s["areas"] or "{}"), v))
    try:
        out = json.loads(tuned_path.read_text())
    except (OSError, ValueError):
        out = {}
    notes = []
    for style in profiles.WEIGHTS:
        rows = by.get(style, [])
        if len(rows) < MIN_POSTS:
            if rows:
                notes.append(f"Analyst: {style} has {len(rows)} post(s) with 7-day views; weights move at {MIN_POSTS}")
            continue
        areas = profiles.WEIGHTS[style].keys()
        corr = {a: round(spearman([r[0].get(a, 0) for r in rows], [r[1] for r in rows]), 2) for a in areas}
        new = nudge(profiles.WEIGHTS[style], corr)
        out[style] = {"weights": new, "posts": len(rows), "corr": corr, "at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
        moved = ", ".join(f"{a} {profiles.WEIGHTS[style][a]}->{new[a]}" for a in new if new[a] != profiles.WEIGHTS[style][a])
        notes.append(f"Analyst: {style} weights from {len(rows)} posts: {moved or 'no change'}")
    if not by:
        notes.append(f"Analyst: no posted clip has 7-day views in data/posts.csv yet; judge weights stay at the board's table "
                     f"(they start moving at {MIN_POSTS} posts per content type)")
    if any(k in out for k in profiles.WEIGHTS):
        tuned_path.write_text(json.dumps(out, indent=1))
    return notes, out


if __name__ == "__main__":
    print("\n".join(review()[0]))
