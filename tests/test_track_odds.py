"""Tests for the odds-history tracker."""
import json

from scripts.track_odds import merge, snapshot


def test_snapshot_keeps_only_champion_probs():
    sim = {"as_of": "2026-07-04", "n_sims": 20000,
           "teams": {"Spain": {"r16": 1.0, "champion": 0.196},
                     "Argentina": {"r16": 1.0, "champion": 0.184}}}
    s = snapshot(sim)
    assert s == {"date": "2026-07-04",
                 "champion": {"Spain": 0.196, "Argentina": 0.184}}


def test_merge_unions_and_sorts_by_date():
    a = [{"date": "2026-07-04", "champion": {"Spain": 0.2}}]
    b = [{"date": "2026-06-28", "champion": {"Spain": 0.15}}]
    merged = merge(a, b)
    assert [e["date"] for e in merged] == ["2026-06-28", "2026-07-04"]


def test_merge_later_argument_wins_a_date_collision():
    stale = [{"date": "2026-07-04", "champion": {"Spain": 0.1}}]
    fresh = [{"date": "2026-07-04", "champion": {"Spain": 0.2}}]
    assert merge(stale, fresh)[0]["champion"]["Spain"] == 0.2
    assert merge(fresh, stale)[0]["champion"]["Spain"] == 0.1


def test_main_upserts_and_writes_both_copies(tmp_path, monkeypatch):
    import scripts.track_odds as mod
    (tmp_path / "models").mkdir()
    (tmp_path / "static" / "data").mkdir(parents=True)
    (tmp_path / "models" / "simulation.json").write_text(json.dumps(
        {"as_of": "2026-07-05", "teams": {"Spain": {"champion": 0.21}}}))
    (tmp_path / "static" / "data" / "odds_history.json").write_text(json.dumps(
        [{"date": "2026-06-28", "champion": {"Spain": 0.15}},
         {"date": "2026-07-05", "champion": {"Spain": 0.999}}]))  # stale same-day entry
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "fetch_live", lambda: [])

    mod.main()

    for p in [tmp_path / "models" / "odds_history.json",
              tmp_path / "static" / "data" / "odds_history.json"]:
        hist = json.loads(p.read_text())
        assert [e["date"] for e in hist] == ["2026-06-28", "2026-07-05"]
        assert hist[-1]["champion"]["Spain"] == 0.21   # fresh sim replaced stale entry
