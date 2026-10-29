from unsaid.store import Store


def test_orphaned_runs_are_failed_on_restart(tmp_path):
    store = Store(tmp_path)
    store.create_run("a", "s1", "public", "t", "1.2.3.4")
    store.create_run("b", "s1", "public", "t", "1.2.3.4")
    store.update_run("b", status="done")
    assert Store(tmp_path).fail_orphans() == 1
    assert store.get_run("a")["status"] == "failed"
    assert store.get_run("b")["status"] == "done"


def test_spend_and_rate_counters(tmp_path):
    store = Store(tmp_path)
    store.add_spend("public", 0.2)
    store.add_spend("public", 0.1)
    assert round(store.spend_today("public"), 3) == 0.3
    assert store.spend_this_month() >= 0.3
    store.create_run("a", "s1", "public", "t", "9.9.9.9")
    assert store.count_recent(session="s1", seconds=60) == 1
    assert store.count_recent(ip="9.9.9.9", seconds=60) == 1


def test_old_media_is_purged_but_results_stay(tmp_path):
    import os
    import time

    store = Store(tmp_path)
    run = store.run_dir("a")
    run.mkdir(parents=True)
    for name in ("source.mp4", "audio.wav", "s1_0.jpg", "result.json", "descriptions.vtt"):
        (run / name).write_text("x")
    old = time.time() - 25 * 3600
    for name in ("source.mp4", "audio.wav", "s1_0.jpg", "result.json"):
        os.utime(run / name, (old, old))
    assert store.purge_media(24 * 3600) == 3
    assert sorted(p.name for p in run.iterdir()) == ["descriptions.vtt", "result.json"]


def test_pending_runs_are_counted_per_browser_or_address(tmp_path):
    store = Store(tmp_path)
    store.create_run("a", "s1", "public", "t", "9.9.9.9")
    assert store.count_pending(session="s1", ip="1.1.1.1") == 1
    assert store.count_pending(session="s2", ip="9.9.9.9") == 1
    assert store.count_pending(session="s2", ip="") == 0
    store.update_run("a", status="done")
    assert store.count_pending(session="s1", ip="9.9.9.9") == 0
