"""Network-free API lifecycle tests using an injected graph generator."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from scinapse.api import create_app
from test_checker import _minimal_document

REQUEST = {"question": "Which methods study melanoma cells?", "seeds": ["https://doi.org/10.1126/science.aad0501"]}


def finished(client, job_id):
    for _ in range(100):
        status = client.get(f"/api/explorations/{job_id}").json()
        if status["status"] in ("completed", "failed"):
            return status
        time.sleep(.01)
    raise AssertionError("Test job did not finish")


def test_background_job_progress_graph_and_busy_limit(monkeypatch):
    monkeypatch.setenv("SCINAPSE_NO_LLM", "1")
    entered, release = threading.Event(), threading.Event()
    captured = {}

    def generate(cfg, *, no_llm, on_progress):
        captured.update(seeds=cfg.seeds, question=cfg.question, no_llm=no_llm)
        on_progress(4, "Enriching publication metadata")
        entered.set()
        assert release.wait(3)
        doc = _minimal_document()
        doc["research_question"] = cfg.question
        return doc

    with TestClient(create_app(generate)) as client:
        try:
            result = client.post("/api/explorations", json=REQUEST)
            assert result.status_code == 202
            job_id = result.json()["id"]
            assert entered.wait(2)
            status = client.get(f"/api/explorations/{job_id}").json()
            assert status["status"] == "running" and status["stage"] == 4
            assert "graph" not in status
            listed = client.get("/api/explorations?status=running").json()
            assert listed["total"] == 1
            assert listed["tasks"][0]["id"] == job_id
            assert listed["tasks"][0]["graph_url"] is None
            assert client.get(f"/api/explorations/{job_id}/graph").status_code == 409
            assert client.post("/api/explorations", json=REQUEST).status_code == 409
        finally:
            release.set()
        assert finished(client, job_id)["status"] == "completed"
        graph = client.get(f"/api/explorations/{job_id}/graph").json()
        assert graph["research_question"] == REQUEST["question"]
        assert graph["nodes"][0]["title"] == "Seed paper about melanoma single cells."
        assert captured == {"seeds": ("10.1126/science.aad0501",), "question": REQUEST["question"], "no_llm": True}


def test_request_validation_and_missing_sessions():
    with TestClient(create_app(lambda *a, **k: {})) as client:
        for payload in [{"question": "   ", "seeds": REQUEST["seeds"]}, {"question": "valid question", "seeds": []}, {"question": "valid question", "seeds": ["27124452"]}]:
            assert client.post("/api/explorations", json=payload).status_code == 422
        assert client.get("/api/explorations/missing").status_code == 404
        assert client.get("/api/explorations/missing/graph").status_code == 404
        assert client.get("/api/health").json()["status"] == "ok"


def test_worker_error_is_reported_without_exposing_exception():
    def fail(*args, **kwargs):
        raise RuntimeError("private provider details")
    with TestClient(create_app(fail)) as client:
        job_id = client.post("/api/explorations", json=REQUEST).json()["id"]
        status = finished(client, job_id)
        assert status["status"] == "failed"
        assert "private provider details" not in status["message"]
        assert client.get(f"/api/explorations/{job_id}/graph").status_code == 409
        # A failed worker frees the queue so the same input can be retried.
        assert client.post("/api/explorations", json=REQUEST).status_code == 202


def test_invalid_graph_is_never_published():
    with TestClient(create_app(lambda *a, **k: {"nodes": []} )) as client:
        job_id = client.post("/api/explorations", json=REQUEST).json()["id"]
        assert finished(client, job_id)["status"] == "failed"
        assert client.get(f"/api/explorations/{job_id}/graph").status_code == 409


def test_task_listing_filters_order_and_completed_graph_links():
    def generate(cfg, **kwargs):
        if cfg.question.startswith("Fail"):
            raise RuntimeError("test failure")
        return _minimal_document()

    with TestClient(create_app(generate)) as client:
        assert client.get("/api/explorations").json() == {"tasks": [], "total": 0}
        completed_id = client.post("/api/explorations", json=REQUEST).json()["id"]
        assert finished(client, completed_id)["status"] == "completed"
        failed_id = client.post("/api/explorations", json={**REQUEST, "question": "Fail this research"}).json()["id"]
        assert finished(client, failed_id)["status"] == "failed"
        listed = client.get("/api/explorations").json()
        assert listed["total"] == 2
        assert [task["id"] for task in listed["tasks"]] == [failed_id, completed_id]
        assert all("graph" not in task for task in listed["tasks"])
        assert listed["tasks"][0]["graph_url"] is None
        completed = client.get("/api/explorations?status=completed").json()
        assert completed["total"] == 1
        task = completed["tasks"][0]
        assert task["status_url"] == f"/api/explorations/{completed_id}"
        assert client.get(task["status_url"]).json()["status"] == "completed"
        assert client.get(task["graph_url"]).json()["nodes"]
        assert client.get("/api/explorations?status=invalid").status_code == 422
