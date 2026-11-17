import pytest


fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")


def test_webapp_homepage_loads():
    from fastapi.testclient import TestClient
    from segcraft.webapp import create_app

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "SegCraft" in response.text
    assert "/jobs" in response.text
    assert "Upload video" in response.text
    assert "YouTube URL" in response.text
    assert "pascal_video" in response.text
    assert "/runtime" in response.text
    assert "Stop" in response.text
    assert "/cancel" in response.text


def test_webapp_health_reports_ready():
    from fastapi.testclient import TestClient

    from segcraft.webapp import create_app

    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "segcraft"}


def test_webapp_runtime_endpoint_loads():
    from fastapi.testclient import TestClient
    from segcraft.webapp import create_app

    client = TestClient(create_app())
    response = client.get("/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert "python_executable" in payload
    assert "packages" in payload
    assert "torch" in payload


def test_webapp_cancel_unknown_job_returns_404():
    from fastapi.testclient import TestClient
    from segcraft.webapp import create_app

    client = TestClient(create_app())
    response = client.post("/jobs/missing/cancel")

    assert response.status_code == 404


def test_webapp_cancel_marks_running_job():
    from fastapi.testclient import TestClient
    from segcraft.webapp import JOBS, JOBS_LOCK, create_app

    with JOBS_LOCK:
        JOBS.clear()
        JOBS["abc123"] = {"id": "abc123", "status": "running", "output_dir": "outputs/test"}

    client = TestClient(create_app())
    response = client.post("/jobs/abc123/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceling"
    with JOBS_LOCK:
        assert JOBS["abc123"]["cancel_requested"] is True


def test_webapp_cancel_leaves_completed_job_completed():
    from fastapi.testclient import TestClient
    from segcraft.webapp import JOBS, JOBS_LOCK, create_app

    with JOBS_LOCK:
        JOBS.clear()
        JOBS["done"] = {"id": "done", "status": "completed", "output_dir": "outputs/test"}

    client = TestClient(create_app())
    response = client.post("/jobs/done/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    with JOBS_LOCK:
        assert "cancel_requested" not in JOBS["done"]


def test_run_job_marks_prediction_cancellation(monkeypatch):
    from segcraft.prediction import PredictionCancelled
    from segcraft.webapp import JOBS, JOBS_LOCK, _run_job

    with JOBS_LOCK:
        JOBS.clear()
        JOBS["job1"] = {"id": "job1", "status": "queued", "output_dir": "outputs/test"}

    monkeypatch.setattr("segcraft.webapp._job_config", lambda _params, _input: {})

    def cancel_prediction(*_args, **_kwargs):
        raise PredictionCancelled("Prediction was canceled.")

    monkeypatch.setattr("segcraft.webapp.run_prediction", cancel_prediction)

    _run_job(
        {
            "job_id": "job1",
            "input_path": "input.mp4",
            "youtube_url": None,
        }
    )

    with JOBS_LOCK:
        assert JOBS["job1"]["status"] == "canceled"
        assert JOBS["job1"]["cancel_requested"] is False
        assert JOBS["job1"]["progress"]["stage"] == "canceled"


def test_cancel_after_prediction_before_completion_wins(monkeypatch):
    from segcraft import webapp

    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.JOBS["job1"] = {"id": "job1", "status": "queued", "output_dir": "outputs/test"}
    monkeypatch.setattr(webapp, "_job_config", lambda _params, _input: {})

    def predict(*_args, **_kwargs):
        assert webapp._request_cancel("job1") == "canceling"
        return {"frames_processed": 3}

    monkeypatch.setattr(webapp, "run_prediction", predict)
    webapp._run_job({"job_id": "job1", "input_path": "input.mp4", "youtube_url": None})
    assert webapp._get_job("job1")["status"] == "canceled"
    assert "summary" not in webapp._get_job("job1")


def test_cancel_accepted_before_failure_is_committed_wins(tmp_path, monkeypatch):
    import json
    import threading

    from fastapi.testclient import TestClient

    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    monkeypatch.setattr(webapp, "RECOVERED_ROOTS", set())
    job_id = "abcdef012345"
    output = tmp_path / "jobs" / job_id / "output"
    output.mkdir(parents=True)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp._set_job(job_id, id=job_id, status="queued", cancel_requested=False,
                        output_dir=str(output), _persistent=True)
    client = TestClient(webapp.create_app())
    monkeypatch.setattr(webapp, "_job_config", lambda _params, _input: {})

    def predict(*_args, **_kwargs):
        raise RuntimeError("prediction failed")

    entered = threading.Event()
    release = threading.Event()
    original = webapp._record_terminal_failure

    def hold_failure(job_id, status, error):
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test did not release the failure boundary")
        original(job_id, status, error)

    monkeypatch.setattr(webapp, "run_prediction", predict)
    monkeypatch.setattr(webapp, "_record_terminal_failure", hold_failure)
    thread = threading.Thread(
        target=webapp._run_job,
        args=({"job_id": job_id, "input_path": "input.mp4", "youtube_url": None},),
    )
    thread.start()
    try:
        assert entered.wait(timeout=5)
        response = client.post(f"/jobs/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "canceling"
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert webapp._get_job(job_id)["status"] == "canceled"
    manifest = json.loads((output.parent / "job.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "canceled" and manifest["error"] == "prediction failed"
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.RECOVERED_ROOTS.clear()
    restarted = TestClient(webapp.create_app()).get(f"/jobs/{job_id}")
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "canceled"


def test_failure_committed_before_cancel_remains_failed(monkeypatch):
    from segcraft import webapp

    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.JOBS["job1"] = {"id": "job1", "status": "queued", "output_dir": "outputs/test"}
    monkeypatch.setattr(webapp, "_job_config", lambda _params, _input: {})

    def predict(*_args, **_kwargs):
        raise RuntimeError("prediction failed")

    monkeypatch.setattr(webapp, "run_prediction", predict)
    webapp._run_job({"job_id": "job1", "input_path": "input.mp4", "youtube_url": None})
    assert webapp._request_cancel("job1") == "failed"
    assert webapp._get_job("job1")["error"] == "prediction failed"


def test_completion_committed_before_cancel_remains_completed():
    from segcraft import webapp

    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.JOBS["job1"] = {"id": "job1", "status": "running", "output_dir": "outputs/test"}
    webapp._finish_job("job1", {"frames_processed": 3})
    assert webapp._request_cancel("job1") == "completed"
    assert webapp._get_job("job1")["summary"]["frames_processed"] == 3


def test_partial_artifact_is_not_offered_or_served(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from segcraft import webapp

    (tmp_path / "overlay.mp4").write_bytes(b"still being written")
    monkeypatch.setattr(webapp, "verify_video", lambda _path: None)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.JOBS["job1"] = {"id": "job1", "status": "running", "output_dir": str(tmp_path)}
    client = TestClient(webapp.create_app())
    assert client.get("/jobs/job1").json()["downloads"] == {}
    assert client.get("/jobs/job1/download/overlay.mp4").status_code == 404
    webapp._finish_job("job1", {"frames_processed": 3})
    assert "overlay.mp4" in client.get("/jobs/job1").json()["downloads"]
    assert client.get("/jobs/job1/download/overlay.mp4").status_code == 200
    (tmp_path / "overlay.mp4").write_bytes(b"changed after verification")
    assert client.get("/jobs/job1/download/overlay.mp4").status_code == 404


def test_saved_running_job_recovers_as_interrupted_without_restarting(tmp_path, monkeypatch):
    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    job_id = "abcdef012345"
    output = tmp_path / "jobs" / job_id / "output"
    output.mkdir(parents=True)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp._set_job(job_id, id=job_id, status="running", cancel_requested=False,
                        output_dir=str(output), _persistent=True)
        webapp.JOBS.clear()
    webapp._recover_jobs()
    recovered = webapp._get_job(job_id)
    assert recovered["status"] == "interrupted"
    assert "Start a new job" in recovered["progress"]["message"]
    assert webapp._request_cancel(job_id) == "interrupted"
    assert webapp._download_links(job_id) == {}


def test_saved_completed_job_only_offers_unchanged_verified_artifacts(tmp_path, monkeypatch):
    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    monkeypatch.setattr(webapp, "verify_video", lambda _path: None)
    job_id = "abcdef012346"
    output = tmp_path / "jobs" / job_id / "output"
    output.mkdir(parents=True)
    (output / "overlay.mp4").write_bytes(b"verified video")
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp._set_job(job_id, id=job_id, status="running", output_dir=str(output), _persistent=True)
    webapp._finish_job(job_id, {"frames_processed": 3})
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
    assert "overlay.mp4" in webapp._download_links(job_id)
    (output / "overlay.mp4").write_bytes(b"changed")
    assert webapp._download_links(job_id) == {}


def test_a_second_web_submission_is_rejected_while_prediction_is_running(tmp_path, monkeypatch):
    import threading

    from fastapi.testclient import TestClient

    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    monkeypatch.setattr(webapp, "_job_config", lambda params, _input: params)
    entered = threading.Event()
    release = threading.Event()

    def predict(_config, **_kwargs):
        entered.set()
        assert release.wait(5)
        return {"frames_processed": 1}

    monkeypatch.setattr(webapp, "run_prediction", predict)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
    client = TestClient(webapp.create_app())
    responses = []

    def submit():
        responses.append(client.post("/jobs", files={"video_file": ("clip.mp4", b"video", "video/mp4")}))

    thread = threading.Thread(target=submit)
    thread.start()
    try:
        assert entered.wait(5)
        busy = client.post("/jobs", files={"video_file": ("other.mp4", b"video", "video/mp4")})
        assert busy.status_code == 409
        assert "Another prediction" in busy.json()["detail"]
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert responses[0].status_code == 200
    job_id = responses[0].json()["job_id"]
    assert client.get(f"/jobs/{job_id}").json()["status"] == "completed"


def test_manifest_write_failure_does_not_report_completed(tmp_path, monkeypatch):
    from segcraft import webapp

    job_id = "abcdef012347"
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp.JOBS[job_id] = {"id": job_id, "status": "queued", "output_dir": str(tmp_path), "_persistent": True}

    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(webapp, "_write_job_manifest", fail)
    webapp._run_job({"job_id": job_id, "input_path": "input.mp4", "youtube_url": None})
    job = webapp._get_job(job_id)
    assert job["status"] == "failed"
    assert "Could not save job state" in job["error"]


@pytest.mark.parametrize("terminal_status", ["failed", "canceled"])
def test_accepted_cancel_survives_final_state_storage_failure(tmp_path, monkeypatch, terminal_status):
    from fastapi.testclient import TestClient

    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    job_id = "abcdef012348"
    output = tmp_path / "jobs" / job_id / "output"
    output.mkdir(parents=True)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp._set_job(job_id, id=job_id, status="running", cancel_requested=False,
                        output_dir=str(output), _persistent=True)
    client = TestClient(webapp.create_app())
    assert client.post(f"/jobs/{job_id}/cancel").json()["status"] == "canceling"
    original_write = webapp._write_job_manifest

    def fail_write(*_args):
        raise OSError("synthetic-private-storage-detail")

    monkeypatch.setattr(webapp, "_write_job_manifest", fail_write)
    webapp._record_terminal_failure(job_id, terminal_status, "synthetic worker outcome")
    visible = client.get(f"/jobs/{job_id}").json()
    assert visible["status"] == "canceled"
    assert "could not save" in visible["error"].lower()
    assert "synthetic-private-storage-detail" not in visible["error"]
    assert visible["downloads"] == {}

    # A failed durable write cannot claim that the final state survived restart.
    monkeypatch.setattr(webapp, "_write_job_manifest", original_write)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
    recovered = webapp._get_job(job_id)
    assert recovered["status"] == "interrupted"


def test_cancel_observed_during_failed_terminal_write_is_not_overwritten(tmp_path, monkeypatch):
    from segcraft import webapp

    monkeypatch.setattr(webapp, "DEFAULT_WORK_DIR", tmp_path)
    job_id = "abcdef012349"
    output = tmp_path / "jobs" / job_id / "output"
    output.mkdir(parents=True)
    with webapp.JOBS_LOCK:
        webapp.JOBS.clear()
        webapp._set_job(job_id, id=job_id, status="running", cancel_requested=False,
                        output_dir=str(output), _persistent=True)
    original_write = webapp._write_job_manifest

    def cancel_then_fail(current_id, state):
        if state.get("status") == "failed":
            assert webapp._request_cancel(current_id) == "canceling"
            raise OSError("synthetic failure")
        original_write(current_id, state)

    monkeypatch.setattr(webapp, "_write_job_manifest", cancel_then_fail)
    webapp._record_terminal_failure(job_id, "failed", "worker failed")
    assert webapp._get_job(job_id)["status"] == "canceled"
    assert "could not save" in webapp._get_job(job_id)["error"].lower()


def test_web_help_prints_usage_and_does_not_start_a_server(monkeypatch, capsys):
    import pytest
    from segcraft import webapp

    started = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: started.append(kwargs))

    with pytest.raises(SystemExit) as exit_info:
        webapp.main(["--help"])

    assert exit_info.value.code == 0
    assert "--port" in capsys.readouterr().out
    assert started == []


def test_web_main_honours_port_and_no_browser_flags(monkeypatch):
    from segcraft import webapp

    started = []
    monkeypatch.delenv("SEGCRAFT_PORT", raising=False)
    monkeypatch.setattr(webapp, "port_in_use", lambda host, port: False)
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: started.append(kwargs))
    opened = []
    monkeypatch.setattr(webapp.webbrowser, "open", lambda url: opened.append(url))

    webapp.main(["--port", "8123", "--no-browser"])

    assert started == [{"factory": True, "host": "127.0.0.1", "port": 8123}]
    assert opened == []


def test_default_port_falls_back_to_the_next_free_one(monkeypatch, capsys):
    from segcraft import webapp

    monkeypatch.setattr(webapp, "port_in_use", lambda host, port: port in {8000, 8001})

    assert webapp.choose_port("127.0.0.1", 8000, explicit=False) == 8002
    assert "Port 8000 is already in use; using 8002" in capsys.readouterr().out


def test_explicit_busy_port_exits_with_a_clear_message(monkeypatch):
    import pytest
    from segcraft import webapp

    monkeypatch.setattr(webapp, "port_in_use", lambda host, port: True)

    with pytest.raises(SystemExit) as exit_info:
        webapp.choose_port("127.0.0.1", 8000, explicit=True)

    assert "Port 8000 is already in use" in str(exit_info.value)
    assert "--port 8001" in str(exit_info.value)
