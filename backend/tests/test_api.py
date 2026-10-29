import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from unsaid import api, jobs
from unsaid.config import Settings
from unsaid.media import VideoInfo
from unsaid.store import Store

REPO = Path(__file__).resolve().parents[2]
SAMPLE_RESULT = REPO / "samples" / "fourier-machine" / "result.json"


@pytest.fixture
def app(tmp_path, monkeypatch):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>Unsaid</title>")
    (tmp_path / "secret.txt").write_text("NEBIUS_API_KEY=leaked")
    sample = tmp_path / "samples" / "demo"
    sample.mkdir(parents=True)
    (sample / "video.mp4").write_bytes(b"sample video bytes")
    (sample / "result.json").write_text("{}")
    (tmp_path / "samples" / "manifest.json").write_text(json.dumps([{"id": "demo", "title": "Demo lecture"}]))

    submitted: list[tuple[str, Path, str]] = []

    def submit(self, run_id, video, options, lane):
        submitted.append((run_id, video, lane))
        self._lanes[run_id] = lane  # queued, as far as the caps are concerned

    async def probe(path):
        return VideoInfo(duration=60.0, width=1280, height=720, fps=25.0, has_audio=True)

    monkeypatch.setattr(jobs.RunQueue, "submit", submit)
    monkeypatch.setattr(api.media, "probe", probe)
    settings = Settings(
        _env_file=None,
        provider="tokenfactory",
        nebius_api_key="test",
        tavily_api_key="",
        data_dir=tmp_path / "data",
        samples_dir=tmp_path / "samples",
        web_dist=web,
        judge_code="open-sesame-1234",
    )
    client = TestClient(api.create_app(settings))
    return client, settings, submitted


def test_the_web_route_never_serves_files_outside_the_built_app(app):
    client, _, _ = app
    for path in ("/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        response = client.get(path)
        assert "leaked" not in response.text, path


def test_an_oversized_upload_is_refused_before_it_is_read(app):
    client, settings, submitted = app
    too_big = str(settings.max_upload_mb * (1 << 20) + (2 << 20))
    response = client.post("/api/runs", content=b"x", headers={"content-length": too_big})
    assert response.status_code == 413 and not submitted


def test_a_live_run_of_an_example_gets_its_own_copy_of_the_video(app):
    client, settings, submitted = app
    response = client.post("/api/runs", data={"sample_id": "demo"})
    assert response.status_code == 200, response.text
    run_id, video, lane = submitted[0]
    assert video == settings.data_dir / "runs" / run_id / "source.mp4" and lane == "public"
    assert client.get(f"/api/runs/{run_id}/video").content == b"sample video bytes"


def test_one_public_run_at_a_time_per_visitor(app):
    client, _, _ = app
    assert client.post("/api/runs", data={"sample_id": "demo"}).status_code == 200
    second = client.post("/api/runs", data={"sample_id": "demo"})
    assert second.status_code == 429 and "already" in second.json()["detail"]


def test_a_run_that_could_overrun_the_daily_cap_is_not_accepted(app):
    client, settings, _ = app
    Store(settings.data_dir).add_spend("public", settings.public_daily_usd - settings.run_reserve_usd / 2)
    response = client.post("/api/runs", data={"sample_id": "demo"})
    assert response.status_code == 429 and "budget" in response.json()["detail"]


def test_the_judge_code_opens_its_own_lane_and_is_not_stored_in_the_cookie(app):
    client, _, submitted = app
    assert client.post("/api/judge", json={"code": "wrong"}).status_code == 403
    response = client.post("/api/judge", json={"code": "open-sesame-1234"})
    assert response.status_code == 200
    assert "open-sesame-1234" not in response.headers["set-cookie"]
    for _ in range(2):  # judges are not limited to one run at a time
        assert client.post("/api/runs", data={"sample_id": "demo"}).status_code == 200
    assert [lane for _, _, lane in submitted] == ["judge", "judge"]


def test_guessing_the_judge_code_is_rate_limited(app):
    client, _, _ = app
    codes = [client.post("/api/judge", json={"code": f"guess-{i}"}).status_code for i in range(12)]
    assert codes[:10] == [403] * 10 and codes[10:] == [429, 429]


def test_the_progress_stream_of_a_forgotten_run_ends(app):
    client, settings, _ = app
    run_id = client.post("/api/runs", data={"sample_id": "demo"}).json()["run_id"]
    Store(settings.data_dir).update_run(run_id, status="failed")
    events = client.get(f"/api/runs/{run_id}/events")  # the queue never saw it: submit is stubbed
    assert events.text.strip() == 'data: {"type": "finished", "status": "failed"}'


def test_an_accepted_edit_reaches_the_downloads(app):
    client, settings, _ = app
    run_id = client.post("/api/runs", data={"sample_id": "demo"}).json()["run_id"]
    workdir = settings.data_dir / "runs" / run_id
    shutil.copyfile(SAMPLE_RESULT, workdir / "result.json")
    cue = next(c for c in json.loads(SAMPLE_RESULT.read_text())["cues"] if c["extended"])
    response = client.patch(f"/api/runs/{run_id}/cues/{cue['id']}", json={"text": "Gears turn behind glass."})
    assert response.json()["passed"], response.json()
    assert "Gears turn behind glass." in (workdir / "descriptions.vtt").read_text()
    assert "Gears turn behind glass." in (workdir / "transcript.html").read_text()


def test_proxy_address_is_the_hop_the_proxy_appended(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    request = type("R", (), {})()
    request.headers = {"x-forwarded-for": "6.6.6.6, 203.0.113.9"}
    request.client = None
    assert api.client_ip(request) == "203.0.113.9"
    request.headers = {"fly-client-ip": "198.51.100.4", "x-forwarded-for": "6.6.6.6, 203.0.113.9"}
    assert api.client_ip(request) == "203.0.113.9"  # off Fly, anyone can send that header
    monkeypatch.setenv("FLY_APP_NAME", "unsaid-demo")
    assert api.client_ip(request) == "198.51.100.4"  # on Fly, its proxy writes it


def test_every_queued_run_holds_its_reserve_against_the_cap(app):
    client, settings, _ = app
    assert client.post("/api/judge", json={"code": "open-sesame-1234"}).status_code == 200
    Store(settings.data_dir).add_spend("judge", settings.judge_daily_usd - settings.run_reserve_usd - 0.05)
    assert client.post("/api/runs", data={"sample_id": "demo"}).status_code == 200  # its reserve still fits
    second = client.post("/api/runs", data={"sample_id": "demo"})  # the first is queued and holds its reserve
    assert second.status_code == 429 and "budget" in second.json()["detail"]
