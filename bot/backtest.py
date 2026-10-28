"""Backtest the moment scorecard on a transcript (rico, 2026-10-28: "BACKTEST").

  python3 bot/backtest.py words.json [--brief campaigns/X/brief.json] [--style cinematic] [--genres comedy,drama]
                          [--truth 26.4-60.1,177.5-194.9] [--top 10] [--min 15 --max 60]

Prints the top candidates the scorecard would cut (score, genres, hook, first line) and, for each
"truth" window (a clip a reviewer or rico approved), where it ranks. A good scorecard puts every truth
window in the top 5; a truth window that ranks 20+ means the scorecard is missing what people liked.
No rendering: this runs in seconds on words.json alone.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plan  # noqa: E402
import profiles  # noqa: E402


def main(argv):
    words_path = argv[0]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    brief = json.load(open(opt("--brief"))) if opt("--brief") else {}
    if opt("--style"):
        brief["style"] = opt("--style")
    if opt("--genres"):
        brief["genres"] = opt("--genres").split(",")
    brief["min_s"] = float(opt("--min", brief.get("min_s", 15)))
    brief["max_s"] = float(opt("--max", brief.get("max_s", 60)))
    words = json.load(open(words_path))
    dur = words[-1]["end"] if words else 0
    style = brief.get("style") or profiles.resolve(brief, words, dur)
    mix = plan.genre_mix(brief, words)
    print(f"{Path(words_path).name}: {len(words)} words, {dur / 60:.1f} min, profile {style}, mix {mix}")
    cands = plan.fm_candidates(words_path, None, brief, style, None)
    top = int(opt("--top", 10))
    for i, c in enumerate(cands[:top], 1):
        r = c["reasons"]
        print(f"{i:2d}. {c['score']:3d}  {c['start']:7.1f}-{c['end']:7.1f} ({c['dur']:4.1f}s)  ent {r.get('entertainment', 0)} com {r.get('comedy', 0)} [{r.get('genres', '')}]")
        print(f"      hook: {c['hook']}")
        print(f"      line: {c['first_line'][:110]}")
    if opt("--truth"):
        print("\ntruth windows (approved clips):")
        for t in opt("--truth").split(","):
            a, b = map(float, t.split("-"))
            best = None
            for i, c in enumerate(cands, 1):
                ov = min(b, c["end"]) - max(a, c["start"])
                if ov > 0.5 * min(b - a, c["dur"]) and (best is None or i < best[0]):
                    best = (i, c)
            if best:
                print(f"  {a:.1f}-{b:.1f}: rank {best[0]} (score {best[1]['score']}, {best[1]['start']}-{best[1]['end']})  {'OK' if best[0] <= 5 else 'MISSED' if best[0] > 20 else 'low'}")
            else:
                print(f"  {a:.1f}-{b:.1f}: not among the {len(cands)} candidates  MISSED")


if __name__ == "__main__":
    main(sys.argv[1:])
