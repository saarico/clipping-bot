"""Release 4: the three experiments (edge guard, candid genre, wide-shot punch-in) and the Analyst's views loop."""
import csv
import json


# ---------- edge guard ----------
W = [{"text": "about", "start": 10.0, "end": 10.3}, {"text": "it.", "start": 10.35, "end": 10.6},
     {"text": "So", "start": 11.2, "end": 11.4}, {"text": "I", "start": 11.4, "end": 11.5},
     {"text": "think", "start": 11.5, "end": 11.9}, {"text": "money", "start": 12.0, "end": 12.4},
     {"text": "matters.", "start": 12.45, "end": 12.9}, {"text": "That's", "start": 13.5, "end": 13.8},
     {"text": "all.", "start": 13.85, "end": 14.1}]
mid = lambda lo, hi: (lo + hi) / 2


def test_start_inside_the_last_word_of_a_sentence_moves_after_it():
    from agents import editor
    (s, e), = editor.guard_edges(None, [[10.45, 12.95]], W, audio_fn=mid)
    assert 10.6 < s < 11.2 and e == 12.95                  # "it." dropped whole, the cut sits in the pause


def test_start_inside_a_sentence_opener_moves_before_it():
    from agents import editor
    (s, _), = editor.guard_edges(None, [[11.3, 12.95]], W, audio_fn=mid)
    assert 10.6 < s < 11.2                                 # "So" kept whole


def test_end_inside_the_next_sentence_opener_moves_before_it():
    from agents import editor
    (_, e), = editor.guard_edges(None, [[11.1, 13.65]], W, audio_fn=mid)
    assert 12.9 < e < 13.5                                 # "That's" not started


def test_end_inside_a_word_mid_sentence_keeps_the_word():
    from agents import editor
    (_, e), = editor.guard_edges(None, [[11.1, 12.2]], W, audio_fn=mid)
    assert 12.4 < e < 12.45


def test_edges_in_silence_and_zero_length_words_never_move():
    from agents import editor
    assert editor.guard_edges(None, [[10.9, 13.2]], W, audio_fn=mid) == [[10.9, 13.2]]
    flat = [{"text": "a", "start": 5.0, "end": 5.0}, {"text": "b", "start": 5.0, "end": 5.0}]
    assert editor.guard_edges(None, [[5.0, 9.0]], flat, audio_fn=mid) == [[5.0, 9.0]]


# ---------- candid genre ----------
def test_candid_story_reads_as_entertaining():
    import re
    import genres
    txt = ("Kylie Jenner posted us in her story. This was just impromptu? Totally organic. You had no idea. Wow. "
           "We didn't get one Amazon search. We did not see one tick-up in sales. How? We would be sold out in 12 hours.")
    low = txt.lower()
    sents = [{"text": t, "n": len(t.split())} for t in re.split(r"(?<=[.?!])\s+", low) if t.strip()]
    gs = genres.genre_scores(sents, low)
    assert gs["candid"] >= 10
    assert "candid" in genres.detect_mix("Kylie posted Bloom for free. Sales didn't move.", low)


def test_interview_brief_points_at_candid():
    import genres
    assert "candid" in genres.detect_mix("A sit-down interview where the founder opens up about his life story")


# ---------- wide-shot punch-in ----------
def test_punch_in_past_1_6x_is_sharpened_and_below_is_unchanged():
    import render_clip
    assert render_clip.WIDE_PUNCH_MAX == 2.5
    assert "unsharp" in render_clip.face_crop(0.5, zoom=2.5, cy=0.4) and "lanczos" in render_clip.face_crop(0.5, zoom=2.5, cy=0.4)
    assert render_clip.face_crop(0.5, zoom=1.6, cy=0.4).endswith("scale=1080:1920")


# ---------- the Analyst ----------
def _write(tmp, n, track):
    import analyst
    sc, po = tmp / "scores.csv", tmp / "posts.csv"
    with open(po, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["campaign", "clip", "platform", "account", "post_url", "posted_at", "views_7d", "notes"])
        for i in range(n):
            areas = {a: (i if a == track else (n - i if a == "pace" else 5)) for a in ("hook", "pace", "variety", "framing", "story",
                                                                                  "entertainment", "comedy", "captions", "length", "sound")}
            areas["sound"] = (i * 7) % n
            areas["length"] = (i * 3) % n
            analyst.record("C", f"{i:02d}_clip.mp4", "podcast", 80, areas, path=sc)
            w.writerow(["C", f"{i:02d}_clip.mp4", "youtube", "@x", "", "", 1000 * (i + 1), ""])
    return sc, po


def test_analyst_waits_for_enough_posts(tmp_path):
    import analyst
    sc, po = _write(tmp_path, 5, "entertainment")
    notes, out = analyst.review(sc, po, tmp_path / "tuned.json")
    assert "podcast" not in out and "weights move at 20" in " ".join(notes)
    assert not (tmp_path / "tuned.json").exists()


def test_analyst_moves_weight_toward_what_earns_views(tmp_path, monkeypatch):
    import analyst
    import profiles
    sc, po = _write(tmp_path, 24, "entertainment")
    notes, out = analyst.review(sc, po, tmp_path / "tuned.json")
    board, new = profiles.WEIGHTS["podcast"], out["podcast"]["weights"]
    assert sum(new.values()) == 100
    assert new["entertainment"] == board["entertainment"] + analyst.STEP
    assert new["pace"] == board["pace"] - analyst.STEP      # pace fell as views rose
    assert all(abs(new[a] - board[a]) <= analyst.MAX_SHIFT for a in board)
    # profiles.weights picks the tuned copy up only without the board override
    monkeypatch.delenv("STUDIO_BOARD_WEIGHTS")
    monkeypatch.setattr(profiles, "__file__", str(tmp_path / "bot" / "profiles.py"))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "weights_tuned.json").write_text(json.dumps(out))
    assert profiles.weights("podcast") == new
