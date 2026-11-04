"""Makeover release 9 (board review 3, approved 2026-11-04): grading that agrees with the board."""
import calibrator
import judge_clip
import profiles


def test_scorecard_v3_weights_have_picture_and_visual():
    for name, w in profiles.WEIGHTS.items():
        assert sum(w.values()) == 100 and {"picture", "visual"} <= set(w), name
    assert profiles.WEIGHTS["performance"]["framing"] >= 10     # subject focus is held under half on a stage show


def test_picture_points_read_the_qa_row():
    row = "| Picture detail | {} | {} source px across the window (worst 400; 0% of the clip under 480) |"
    assert judge_clip.picture_points(row.format("PASS", 1215))[0] == 10
    assert judge_clip.picture_points(row.format("PASS", 607))[0] == 8
    assert judge_clip.picture_points(row.format("WARN", 450))[0] == 4
    assert judge_clip.picture_points(row.format("FAIL", 300))[0] == 0
    assert judge_clip.picture_points("")[0] == 7


def test_calibrator_raises_the_bar_to_match_rico(tmp_path, monkeypatch):
    v, c = tmp_path / "verdicts.csv", tmp_path / "calibration.json"
    monkeypatch.setattr(calibrator, "CALIB", c)
    # the board rejected 92, 85, 84 and rico approved clips at 94 and 96
    for clip, verdict, judge in [("a", "rejected", 92), ("b", "rejected", 85), ("c", "rejected", 84), ("d", "approved", 94),
                                 ("e", "approved", 96), ("f", "redo", 81)]:
        assert calibrator.record("W", clip, verdict, judge, "performance", path=v)
    assert not calibrator.record("W", "a", "approved", 92, path=v)        # first verdict stands
    res = calibrator.calibrate(path=v, out=c)
    assert res["bar"] == 93 and res["agreement"] == 1.0 and res["board_agreement"] < 0.5
    assert calibrator.bar() == 93
    ok, note = calibrator.trusted()
    assert ok and "100%" in note


def test_calibrator_waits_for_enough_verdicts(tmp_path, monkeypatch):
    v, c = tmp_path / "verdicts.csv", tmp_path / "calibration.json"
    monkeypatch.setattr(calibrator, "CALIB", c)
    calibrator.record("W", "a", "rejected", 92, path=v)
    calibrator.calibrate(path=v, out=c)
    assert calibrator.bar() == calibrator.BOARD_BAR
