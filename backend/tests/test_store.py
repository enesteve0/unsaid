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
