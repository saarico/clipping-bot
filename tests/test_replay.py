"""Offline replay (Release 1): the moment finder re-run on a cached transcript, no rendering. The DIGGER clips rico
approved must stay in the scorecard's top 5."""
import json
from pathlib import Path

import plan

ROOT = Path(__file__).resolve().parent.parent
DIGGER = ROOT / "campaigns" / "DIGGER x ClipFarm"
TRUTH = [(26.4, 60.1), (177.5, 194.9), (194.5, 216.4)]


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0])) / min(a[1] - a[0], b[1] - b[0])


def test_digger_approved_moments_rank_top5():
    brief = json.loads((DIGGER / "brief.json").read_text())
    brief.update(style="cinematic", min_s=15, max_s=60)
    cands = plan.fm_candidates(str(DIGGER / "words.json"), None, brief, "cinematic", None)
    top = [(c["start"], c["end"]) for c in cands[:5]]
    for t in TRUTH:
        assert any(overlap(t, c) >= 0.5 for c in top), f"approved {t} fell out of the top 5: {top}"
