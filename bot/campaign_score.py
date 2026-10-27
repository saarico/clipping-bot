"""Score a clipping campaign against scorecards/financial.md. Prints the ranking and writes
ranking.json next to the cards (the board reads it).

Usage:
  python3 campaign_score.py cards/*.json

card.json (facts Claude gathers; unknown = leave out = 0 points, never a guess):
{
 "name": "ClipFarm x Solved w/ Mark Manson", "host": "Content Rewards (ClipFarm)", "rate": 1.25,
 "budget_left": 14600, "days_left": 29, "clippers": 412, "platforms": ["instagram", "youtube"],
 "max_per_clip": 300, "min_payout": 1.0, "pay_to_join": false, "application_only": false,
 "audience_rule": "40% US/UK/CA/AU", "audience_ok": true, "banned_content": false, "scandal": false,
 "followers": 3100000, "avg_views_pct": 9, "trend": "flat",
 "library_10plus": true, "one_sentence_stories": true, "own_broll": false,
 "clips_top_views": 100000, "clips_have_comments": true, "creator_reposts": false,
 "rules_plain": true, "must_use_their_file": false, "must_post_promos": false,
 "lane": "A", "joined": false, "rico_decides": "", "notes": "..."
}

Scorecard audit (2026-10-26, rico asked "ensure the point system makes sense"):
  - Pay: the old card gave 3 points just for a $1.50 minimum payout, which almost every campaign has.
    Now: rate 10, budget left 8, crowding 4 (budget left per clipper already in), caps 3.
  - Crowding is new: 206 clippers on a $4K budget (Higgsfield) means pennies each, whatever the rate.
  - Rules load can't go below 0 or above 10; "application only" costs 2 instead of being a stop when the
    brief is public.
  - A hard stop now shows as a stop first, with the score only for the record (Clavicular scored 87
    while banned; the number must never read as a recommendation).
  - "JOIN NOW" = 70+ with proof that clips of this creator already get views (D >= 15) and $10k+ left: the one to
    join for sure. "JOIN? rico decides" = JOIN by points but with a judgment call rico owns.
  - Expected $ per clip uses our own median 7-day views from posts.csv once we have them; until then
    15k (the Shorts average for small accounts), times 0.6 counted when an audience rule applies.
"""
import csv
import json
import statistics
import sys
from pathlib import Path

LANES = {"A": "youtube", "B": "instagram", "C": "tiktok"}
ROOT = Path(__file__).resolve().parent.parent


def our_median_views():
    try:
        with open(ROOT / "data" / "posts.csv", newline="") as f:
            v = [float(r["views_7d"]) for r in csv.DictReader(f) if r.get("views_7d")]
        return statistics.median(v) if v else None
    except OSError:
        return None


def score(c):
    stops = []
    if c.get("rate") is None or c["rate"] < 0.75:
        stops.append("pays under $0.75/1k, or an auction/pool with no fixed rate")
    if c.get("budget_left", 0) < 1000:
        stops.append("budget left under $1,000")
    if c.get("days_left") is not None and c["days_left"] <= 3:
        stops.append("3 days or less left")
    if c.get("pay_to_join"):
        stops.append("pay to join")
    if not any(LANES[l] in [p.lower() for p in c.get("platforms", [])] for l in LANES):
        stops.append("no platform matches a lane")
    if c.get("audience_rule") and not c.get("audience_ok", True):
        stops.append(f"audience rule we can't meet: {c['audience_rule']}")
    if c.get("banned_content"):
        stops.append("content we don't post (gambling, adult, political, crypto pumps)")
    if c.get("application_only") and not c.get("brief_public", False):
        stops.append("application only and the brief is hidden")
    if c.get("scandal"):
        stops.append("creator or brand banned or in a scandal right now")

    pts = {}
    r = c.get("rate", 0)
    a = 10 if r >= 2 else 8 if r >= 1.5 else 5 if r >= 1 else 2
    b = c.get("budget_left", 0)
    a += 8 if b >= 10000 else 6 if b >= 5000 else 3 if b >= 2000 else 1
    if c.get("clippers"):
        per = b / max(c["clippers"], 1)
        a += 4 if per >= 100 else 2 if per >= 30 else 0
    else:
        a += 2
    m = c.get("max_per_clip")
    a += 2 if (m is None or m >= 300) else 0
    a += 1 if c.get("min_payout", 99) <= 1.5 else 0
    pts["A pay and budget"] = min(a, 25)

    f = c.get("followers", 0)
    bb = 10 if f >= 1e6 else 7 if f >= 250e3 else 4 if f >= 50e3 else 0
    e = c.get("avg_views_pct", 0)
    bb += 8 if e > 20 else 5 if e >= 5 else 1 if e > 0 else 0
    bb += {"rising": 7, "flat": 3, "falling": 0}.get(c.get("trend", ""), 0)
    pts["B creator reach"] = min(bb, 25)

    pts["C clip supply"] = (8 if c.get("library_10plus") else 0) + (7 if c.get("one_sentence_stories") else 0) + (5 if c.get("own_broll") else 0)

    v = c.get("clips_top_views", 0)
    d = 10 if v >= 100e3 else 6 if v >= 20e3 else 0
    d += 5 if c.get("clips_have_comments") else 0
    d += 5 if c.get("creator_reposts") else 0
    pts["D proof clips explode"] = d

    ee = 10 if c.get("rules_plain", True) else 5
    ee -= 3 if c.get("audience_rule") else 0
    ee -= 2 if c.get("must_use_their_file") else 0
    ee -= 5 if c.get("must_post_promos") else 0
    ee -= 2 if c.get("application_only") else 0
    pts["E rules load"] = max(0, min(ee, 10))

    total = sum(pts.values())
    if stops:
        verdict = "STOP"
    elif total >= 70 and d >= 15 and b >= 10000:
        verdict = "JOIN NOW"
    elif total >= 70:
        verdict = "JOIN"
    elif total >= 55:
        verdict = "MAYBE"
    else:
        verdict = "SKIP"
    if verdict.startswith("JOIN") and c.get("rico_decides"):
        verdict = "JOIN? rico decides"
    return total, verdict, pts, stops


def expected_per_clip(c, median_views=None):
    views = median_views or 15000
    counted = 0.6 if c.get("audience_rule") else 0.9
    return views * counted * c.get("rate", 0) / 1000 * 0.9


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:] if not p.endswith("ranking.json")]
    med = our_median_views()
    out = []
    for p in paths:
        c = json.load(open(p))
        total, verdict, pts, stops = score(c)
        out.append({"name": c["name"], "score": total, "verdict": verdict, "points": pts, "stops": stops,
                    "lane": c.get("lane", ""), "rate": c.get("rate"), "budget_left": c.get("budget_left"),
                    "days_left": c.get("days_left"), "platforms": c.get("platforms", []), "host": c.get("host", ""),
                    "joined": bool(c.get("joined")), "rico_decides": c.get("rico_decides", ""),
                    "expected_per_clip": round(expected_per_clip(c, med)), "notes": c.get("notes", ""),
                    "card": p.name})
    order = {"JOIN NOW": 0, "JOIN": 1, "JOIN? rico decides": 2, "MAYBE": 3, "SKIP": 4, "STOP": 5}
    out.sort(key=lambda x: (order[x["verdict"]], -x["score"]))
    if paths:
        (paths[0].parent / "ranking.json").write_text(json.dumps(out, indent=1))
    for x in out:
        print(f"{x['score']:3d} {x['verdict']:18s} | {x['name']}  (~${x['expected_per_clip']}/clip)")
        for k, v in x["points"].items():
            print(f"      {k}: {v}")
        for s in x["stops"]:
            print(f"      STOP: {s}")
