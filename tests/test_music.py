"""Music mode (rico 2026-11-03, The Weeknd - Hong Kong Performance): windows from sound and picture, no words."""
import music_moments as mm


def curve(n=120, loud=()):
    """A quiet episode (-30 dB) with loud stretches (-12 dB) at the given (start, end) seconds."""
    e = [-30.0] * n
    for a, b in loud:
        for t in range(a, b):
            e[t] = -12.0
    return e


# ---------- when it applies ----------
def test_three_words_in_seven_minutes_is_music():
    words = [{"text": "Let's"}, {"text": "get"}, {"text": "started."}]
    assert mm.is_music(words, 7 * 60)


def test_a_podcast_is_not_music():
    words = [{"text": "w"}] * 9000          # a one-hour talk
    assert not mm.is_music(words, 3600)


def test_reviewer_pin_wins_both_ways():
    assert mm.is_music([{"text": "w"}] * 9000, 3600, {"music": True})
    assert not mm.is_music([], 600, {"music": False})


def test_no_duration_means_no_music_mode():
    assert not mm.is_music([], 0)


# ---------- the pick ----------
def test_windows_land_on_the_loud_part_and_open_on_the_peak():
    e = curve(loud=[(60, 90)])
    wins = mm.windows(e, [60.0, 75.0, 90.0], 12, 30, top=3)
    assert wins, "no window found"
    best = wins[0]
    assert 58 <= best["start"] <= 62 and best["end"] <= 90.5
    assert best["music"]["opens_on_peak"] and best["music"]["loud_share"] >= 0.9
    assert best["pts"]["on_cut"] == 5


def test_windows_do_not_overlap_each_other_or_used_moments():
    e = curve(loud=[(20, 50), (70, 100)])
    wins = mm.windows(e, [20.0, 50.0, 70.0, 100.0], 12, 30, used=[(70, 100)], top=5)
    assert wins
    for w in wins:
        assert not (w["start"] < 100 and w["end"] > 70), "a used moment was picked again"
    for a in wins:
        for b in wins:
            if a is not b:
                ov = min(a["end"], b["end"]) - max(a["start"], b["start"])
                assert ov < 0.25 * min(a["dur"], b["dur"])


def test_windows_respect_the_briefs_length():
    e = curve(loud=[(10, 110)])
    for w in mm.windows(e, [], 12, 30, top=6):
        assert 11.9 <= w["dur"] <= 30.1


def test_a_window_that_ends_in_a_hole_loses_its_payoff_points():
    e = curve(loud=[(30, 50)])
    e[50:60] = [-45.0] * 10
    med = mm.median(e)
    tot_hole, pts_hole, m_hole = mm.score_window(e, [], 40, 60, med)
    tot_ok, pts_ok, m_ok = mm.score_window(e, [], 30, 50, med)
    assert m_hole["ends_quiet"] and pts_hole["payoff"] == -10
    assert not m_ok["ends_quiet"] and tot_ok > tot_hole


def test_hook_text_from_the_reviewer_or_the_campaign_name():
    assert mm.hook_text({"music_hooks": ["A", "B"]}, "x", 0) == "A"
    assert mm.hook_text({"music_hooks": ["A", "B"]}, "x", 3) == "B"
    assert mm.hook_text({}, "The Weeknd - Hong Kong Performance Clipping", 0) == "The Weeknd - Hong Kong Performance"


# ---------- the judge ----------
def test_judge_reads_the_sound_not_the_words():
    m = {"opens_on_peak": True, "builds": True, "ends_quiet": False, "rel_db": 6.0, "loud_share": 0.9}
    shots = [{"from": 0, "to": 4}, {"from": 4, "to": 9}, {"from": 9, "to": 14}, {"from": 14, "to": 20}]
    areas, notes = mm.judge_areas(m, shots, 20, silences=[])
    assert areas["hook"] == 20 and areas["story"] == 10 and areas["pace"] == 10 and areas["entertainment"] >= 9
    weak, _ = mm.judge_areas({"opens_on_peak": False, "builds": False, "ends_quiet": True, "rel_db": -3, "loud_share": 0.0},
                             [{"from": 0, "to": 20}], 20, silences=[1.0, 1.2])
    assert weak["hook"] == 8 and weak["story"] == 0 and weak["pace"] <= 2 and weak["entertainment"] == 0


def test_music_spec_carries_what_the_render_and_judge_need(tmp_path, monkeypatch):
    e = curve(loud=[(60, 90)])
    monkeypatch.setattr(mm.audio_energy, "energy", lambda src: e)
    monkeypatch.setattr(mm, "cuts", lambda src, cache=None: [60.0, 75.0, 90.0])
    monkeypatch.setattr(mm, "duration", lambda src: 120.0)
    out = tmp_path / "renders"
    brief = {"min_s": 12, "max_s": 30, "style": "performance", "platforms": ["tiktok", "instagram"]}
    specs = mm.specs("episode.mp4", "words.json", brief, "The Weeknd - Hong Kong Performance Clipping", out, log=lambda *a: None)
    assert specs and specs[0]["music"]["opens_on_peak"]
    sp = specs[0]
    assert sp["tighten"] is False and sp["callouts"] == [] and sp["style"] == "performance"
    assert sp["hook"] == "The Weeknd - Hong Kong Performance" and sp["out"].endswith("s.mp4")
    assert sp["brief"] == {"min_s": 12, "max_s": 30}
