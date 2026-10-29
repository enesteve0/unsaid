import asyncio

from unsaid import jobs
from unsaid.config import Settings
from unsaid.ledger import LedgerEntry
from unsaid.pipeline import RunOptions
from unsaid.store import Store


def make_queue(tmp_path, **overrides):
    settings = Settings(_env_file=None, data_dir=tmp_path, nebius_api_key="test", **overrides)
    store = Store(tmp_path)
    return jobs.RunQueue(settings, tf=None, asr=None, store=store), store


def start(queue, store, run_id, lane="public", title="t"):
    store.create_run(run_id, f"session-{run_id}", lane, title, "")
    queue.submit(run_id, store.run_dir(run_id) / "source.mp4", RunOptions(title=title), lane)
    return queue._tasks[run_id]


async def test_a_failed_run_still_charges_its_model_calls(tmp_path, monkeypatch):
    async def fails(video, workdir, *, ledger, **kwargs):
        ledger.add(
            LedgerEntry(
                stage="watch",
                role="vision",
                model="nvidia/Nemotron-3.5-Super-VL",
                thinking=False,
                prompt_tokens=100_000,
            )
        )
        raise RuntimeError("boom")

    monkeypatch.setattr(jobs, "run_pipeline", fails)
    queue, store = make_queue(tmp_path)
    await start(queue, store, "r1")
    run = store.get_run("r1")
    assert run["status"] == "failed" and "boom" in run["error"]
    assert round(store.spend_today("public"), 4) == 0.03  # 100k prompt tokens at $0.30 per million
    assert round(run["cost_usd"], 4) == 0.03


async def test_a_judge_run_never_waits_behind_public_runs(tmp_path, monkeypatch):
    release, started = asyncio.Event(), []

    async def slow(video, workdir, *, options, **kwargs):
        started.append(options.title)
        await release.wait()

    monkeypatch.setattr(jobs, "run_pipeline", slow)
    queue, store = make_queue(tmp_path, max_concurrent_runs=2)
    tasks = [
        start(queue, store, f"r{i}", lane, f"{lane} {i}")
        for i, lane in enumerate(["public", "public", "judge"])
    ]
    await asyncio.sleep(0.05)
    assert started == [
        "public 0",
        "judge 2",
    ]  # the second public run waits; the judge takes the reserved slot
    assert queue.position("r1") == 1
    release.set()
    await asyncio.gather(*tasks)
    assert [store.get_run(f"r{i}")["status"] for i in range(3)] == ["done"] * 3


async def test_a_run_that_reaches_its_slot_after_the_budget_is_spent_does_not_start(tmp_path, monkeypatch):
    called = []

    async def pipeline(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr(jobs, "run_pipeline", pipeline)
    queue, store = make_queue(tmp_path)
    store.add_spend("public", 10.0)
    await start(queue, store, "r1")
    assert not called and store.get_run("r1")["status"] == "failed"


async def test_intermediate_media_is_deleted_when_a_run_ends(tmp_path, monkeypatch):
    names = [
        "audio.wav",
        "s1.mp4",
        "s1_0.jpg",
        "check_b001.mp4",
        "result.json",
        "descriptions.vtt",
        "source.mp4",
    ]

    async def pipeline(video, workdir, **kwargs):
        workdir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (workdir / name).write_text("x")

    monkeypatch.setattr(jobs, "run_pipeline", pipeline)
    queue, store = make_queue(tmp_path)
    await start(queue, store, "r1")
    kept = sorted(p.name for p in store.run_dir("r1").iterdir())
    assert kept == ["descriptions.vtt", "result.json", "source.mp4"]


async def test_provider_failures_pause_live_runs(tmp_path, monkeypatch):
    async def fails(*args, **kwargs):
        raise jobs.TokenFactoryError("every model failed")

    monkeypatch.setattr(jobs, "run_pipeline", fails)
    queue, store = make_queue(tmp_path)
    for i in range(jobs.PROVIDER_FAILURES_BEFORE_PAUSE):
        assert not queue.paused
        await start(queue, store, f"r{i}")
    assert queue.paused
