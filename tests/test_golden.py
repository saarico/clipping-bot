"""The golden set must still pass: rico's approved clips keep their judge scores (within 3 points) on every change."""
import json

import pytest

import golden_tools as g


@pytest.mark.parametrize("clip", g.clips(), ids=lambda p: p.name)
def test_golden_clip_keeps_its_score(clip):
    base = json.loads(g.BASELINE.read_text())[clip.name]
    total, areas = g.judge(clip)
    assert abs(total - base["total"]) <= g.GOLD_TOLERANCE, f"{clip.name}: {total} vs baseline {base['total']} ({areas} vs {base['areas']})"
