"""Release 1 (board review 2, 2026-10-31): every gate gets tests with known answers."""
import profiles
import studio
import find_moments as fm
import plan
import campaign_scan as cs


def sent(t):
    return {"text": t, "n": len(t.split())}


# ---------- profiles / scorecards ----------
def test_every_profile_has_weights_summing_to_100():
    for name in profiles.PROFILES:
        assert sum(profiles.weights(name).values()) == 100, name


def test_profiles_share_one_set_of_keys():
    keys = set(profiles.PROFILES["podcast"])
    for name, p in profiles.PROFILES.items():
        assert set(p) == keys, name
    assert set(profiles.PROFILES) == set(profiles.LOOK) == set(profiles.WEIGHTS)


def test_detect_from_text():
    assert profiles.detect_from_text("clip the podcast episode interview with our guest host") == "podcast"
    assert profiles.detect_from_text("fan edits, montages and velocity edits") == "edit"
    assert profiles.detect_from_text("news documentary explainers and history") == "serious"


# ---------- weighted judge + area minimum ----------
MAXES = {"hook": 20, "pace": 10, "variety": 15, "framing": 10, "story": 10, "entertainment": 10, "comedy": 5, "captions": 10, "length": 10, "sound": 10}


def test_perfect_clip_scores_100():
    total, under, _ = studio.weighted_total(dict(MAXES), MAXES, "podcast")
    assert total == 100 and under == []


def test_weak_hook_is_held_even_with_high_total():
    rep = dict(MAXES, hook=4)   # 4/20 on a 20-point area
    total, under, _ = studio.weighted_total(rep, MAXES, "podcast")
    assert total >= 80 and any(u.startswith("hook") for u in under)


def test_small_area_never_triggers_minimum():
    rep = dict(MAXES, comedy=0)   # comedy is worth 5 on podcasts
    _, under, _ = studio.weighted_total(rep, MAXES, "podcast")
    assert under == []


# ---------- text & layout inspector ----------
def ass(lines):
    return "[Events]\n" + "\n".join(lines) + "\n"


def test_layout_passes_one_spot(tmp_path):
    p = tmp_path / "c.ass"
    p.write_text(ass([
        r"Dialogue: 2,0:00:00.00,0:00:05.00,Hook,,0,0,0,,{\an8\pos(540,150)}Hook",
        r"Dialogue: 1,0:00:00.20,0:00:20.00,Cap,,0,0,0,,{\an5\pos(540,1400)}ONE SPOT",
    ]))
    assert studio.layout_check(p)["fails"] == []


def test_layout_fails_jumping_captions_and_late_hook(tmp_path):
    p = tmp_path / "c.ass"
    p.write_text(ass([
        r"Dialogue: 2,0:00:00.00,0:00:30.00,Hook,,0,0,0,,{\an8\pos(540,150)}Hook",
        r"Dialogue: 1,0:00:00.00,0:00:10.00,Cap,,0,0,0,,{\an5\pos(540,1400)}LOW",
        r"Dialogue: 1,0:00:10.00,0:00:20.00,Cap,,0,0,0,,{\an5\pos(540,700)}HIGH",
    ]))
    fails = " ".join(studio.layout_check(p)["fails"])
    assert "one spot" in fails and "hook text" in fails


def test_layout_fails_text_in_like_rail(tmp_path):
    p = tmp_path / "c.ass"
    p.write_text(ass([r"Dialogue: 1,0:00:00.00,0:00:10.00,Cap,,0,0,0,,{\an5\pos(1000,1300)}RAIL"]))
    assert any("rail" in f for f in studio.layout_check(p)["fails"])


# ---------- clip cap ----------
def test_clip_cap():
    assert studio.clip_cap({}) == 3
    assert studio.clip_cap({"kits": {"a": 1}}) == 3
    assert studio.clip_cap({"kits": {"a": 1, "b": 2}}) == 6


# ---------- speaker check ----------
def test_speaker_check_flags_filler_heavy_talk():
    words = [{"text": t, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, t in enumerate(("um like you know so " * 100).split())]
    ok, why = studio.speaker_check(words)
    assert not ok and "fillers" in why


def test_speaker_check_passes_clean_talk():
    words = [{"text": t, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, t in enumerate(("we built the company from nothing in two years " * 40).split())]
    assert studio.speaker_check(words)[0]


# ---------- hook writer ----------
def test_opener_rejects_filler_and_dangling_lines():
    assert not fm.opener_ok(sent("Oh yeah, but he does this wrong, and he does like, now."))
    assert not fm.opener_ok(sent("Yeah I bought a house for 20 million."))


def test_opener_accepts_stakes_and_host_questions():
    assert fm.opener_ok(sent("I made $20 million from one Kylie Jenner story post."))
    assert fm.opener_ok(sent("So what did you do with 100 million?"))


def test_long_title_is_cut_at_a_clause():
    t = fm.hook_from_opener([sent("I don't know if you guys saw that movie, but be the anti Michael Jackson's dad, because he sold records")])
    assert t.endswith("...") and not t[:-3].rstrip().split()[-1].lower() in fm.DANGLING
    assert plan.hook_text({"hook": t}).endswith(".")


# ---------- campaign scout ----------
def card(**kw):
    base = dict(rate=1.5, budget_left=20000, budget_total=30000, platforms=["tiktok"])
    base.update(kw)
    return base


def test_scan_stops_gambling_crypto_and_low_pay():
    assert cs.auto_score(card(name="Roobet Kick Stream Clips", category="gaming"))[1] == "STOP"
    assert cs.auto_score(card(name="Memecoin launch clips", category="crypto"))[1] == "STOP"
    assert cs.auto_score(card(name="Joe Rogan podcast clips", category="podcast", rate=0.4))[1] == "STOP"


def test_scan_stops_game_reveal_trailers_but_not_streams():
    sega = card(name="SEGA - Virtua Fighter Crossroads", category="gaming",
                description="Post clips of the new character reveal. Show the story cinematics. Download the character trailer from the official content folder.")
    kai = card(name="Kai Cenat Stream Clips", category="entertainment", description="Clip Kai's stream reactions to the new character reveal")
    assert cs.auto_score(sega)[1] == "STOP"
    assert cs.auto_score(kai)[1] != "STOP"


# ---------- run report card ----------
def test_report_card_counts_gate_failures(tmp_path, monkeypatch):
    import csv, json as js, pipeline
    monkeypatch.setattr(pipeline, "REPORT_CARD", tmp_path / "rc.csv")
    results = [{"fails": ["| Somebody in frame | FAIL | no face |"], "judge": 70, "judge_notes": {"hook": "weak"}},
               {"fails": ["| Somebody in frame | FAIL | no face |", "| Audio | FAIL | clip |"], "judge": 76},
               {"error": "crash"}]
    pipeline.report_card(results, [], "Test")
    row = list(csv.DictReader(open(tmp_path / "rc.csv")))[0]
    assert row["rendered"] == "2" and row["kept"] == "0"
    g = js.loads(row["gate_fails"])
    assert g["Somebody in frame"] == 2 and g["Audio"] == 1 and g["judge: hook"] == 1


def test_advocacy_groups_are_stopped_and_shows_are_not():
    import campaign_scan as cs
    alliance = {"name": "Alliance Podcast/News Clipping [VIRAL]", "org": "The Alliance for Secure AI", "category": "Podcasts",
                "description": "Turn The Alliance for Secure AI's podcast and news footage into viral AI safety clips."}
    assert cs.advocacy(alliance)
    assert not cs.advocacy({"name": "Iced Coffee Hour Clipping", "org": "Graham Stephan", "category": "Podcasts",
                            "description": "Clip the best moments of the podcast about money and business."})
    assert not cs.advocacy({"name": "Diary of a CEO", "org": "Steven Bartlett", "category": "Podcasts",
                            "description": "Guests talk about health, policy and business."})
