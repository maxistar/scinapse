"""Local HTTP API for background research graph builds; CLI remains independent."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .checker import check
from .config import BuildConfig, load_dotenv, nebius_api_key, normalize_doi

log = logging.getLogger(__name__)


class ExplorationInput(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    seeds: list[str] = Field(min_length=1, max_length=10)

    @field_validator("question")
    @classmethod
    def question_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter a research question (at least 3 characters).")
        return value

    @field_validator("seeds")
    @classmethod
    def seed_dois(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            doi = normalize_doi(value)
            if len(doi) > 500 or not re.fullmatch(r"10\.\d{4,9}/[^\s]+", doi, re.I):
                raise ValueError("Use seed DOIs or https://doi.org/ links.")
            if doi.casefold() not in {item.casefold() for item in result}:
                result.append(doi)
        return result


def create_app(runner=None) -> FastAPI:
    """One pipeline worker avoids overlapping shared API rate limits and cache writes."""
    lock = threading.Lock()
    jobs: dict[str, dict] = {}
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scinapse-build")

    @asynccontextmanager
    async def lifespan(app):
        load_dotenv()
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Scinapse API", lifespan=lifespan)

    def public(job):
        return {**{key: value for key, value in job.items() if key != "graph"},
                "status_url": f"/api/explorations/{job['id']}",
                "graph_url": f"/api/explorations/{job['id']}/graph" if job["status"] == "completed" else None}

    def build(job_id: str, request: ExplorationInput, smoke: bool, no_llm: bool):
        def progress(stage: int, message: str):
            with lock:
                jobs[job_id].update(status="running", stage=stage, message=message)
        try:
            if runner is None:
                from .pipeline import run
                generate = run
            else:
                generate = runner
            cfg = BuildConfig(seeds=tuple(request.seeds), question=request.question)
            if smoke:
                cfg = cfg.smoke()
            progress(0, "Starting research")
            graph = generate(cfg, no_llm=no_llm, on_progress=progress)
            errors = check(graph)
            if errors or not graph.get("nodes"):
                log.error("Graph validation failed for %s: %s", job_id, errors)
                raise ValueError("No valid graph was produced")
            with lock:
                jobs[job_id].update(status="completed", stage=10, message="Research ready", graph=graph)
        except Exception:
            log.exception("Research job %s failed", job_id)
            with lock:
                jobs[job_id].update(status="failed", message="Research could not be completed. Check the backend logs and retry.")
        finally:
            with lock:
                jobs[job_id]["finished_at"] = time.time()

    @app.get("/api/health")
    def health():
        return {"status": "ok", "assessments_enabled": bool(nebius_api_key()) and os.getenv("SCINAPSE_NO_LLM") != "1",
                "profile": "standard" if os.getenv("SCINAPSE_SMOKE", "1") == "0" else "smoke"}

    @app.post("/api/explorations", status_code=202)
    def start(request: ExplorationInput):
        smoke = os.getenv("SCINAPSE_SMOKE", "1") != "0"
        no_llm = os.getenv("SCINAPSE_NO_LLM") == "1" or not nebius_api_key()
        with lock:
            if any(job["status"] in ("queued", "running") for job in jobs.values()):
                raise HTTPException(409, "Another research job is running. Please wait for it to finish.")
            # Keep memory bounded for this single-process local server.
            while len(jobs) >= 20:
                del jobs[next(iter(jobs))]
            job_id = uuid.uuid4().hex
            jobs[job_id] = {"id": job_id, "status": "queued", "stage": 0, "total_stages": 10,
                            "message": "Waiting to start", "question": request.question,
                            "profile": "smoke" if smoke else "standard", "assessments_enabled": not no_llm,
                            "created_at": time.time(), "finished_at": None, "graph": None}
            result = public(jobs[job_id])
        executor.submit(build, job_id, request, smoke, no_llm)
        return result

    @app.get("/api/explorations")
    def list_tasks(status_filter: Literal["queued", "running", "completed", "failed"] | None = Query(None, alias="status")):
        """List retained tasks, newest first, without embedding large graph documents."""
        with lock:
            tasks = [public(job) for job in reversed(list(jobs.values()))
                     if status_filter is None or job["status"] == status_filter]
            return {"tasks": tasks, "total": len(tasks)}

    @app.get("/api/explorations/{job_id}")
    def status(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "Research session expired or the backend restarted. Start the search again.")
            return public(jobs[job_id])

    @app.get("/api/explorations/{job_id}/graph")
    def graph(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "Research session not found.")
            if jobs[job_id]["status"] != "completed":
                raise HTTPException(409, "The graph is not ready.")
            return jobs[job_id]["graph"]

    return app


app = create_app()
