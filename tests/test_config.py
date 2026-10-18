"""Config tests — dotenv resolution (network-free)."""

from __future__ import annotations

import os

import scinapse.config as C


def test_load_dotenv_falls_back_to_repo_root(tmp_path, monkeypatch):
    """Runs from subdirectories (no ./.env in cwd) still load the repo .env."""
    monkeypatch.chdir(tmp_path)  # cwd without a .env
    monkeypatch.delenv("SCINAPSE_TEST_DOTENV", raising=False)
    (tmp_path / ".env").write_text("SCINAPSE_TEST_DOTENV=loaded-from-fallback\n", encoding="utf-8")
    monkeypatch.setattr(C, "REPO_ROOT", tmp_path)
    C.load_dotenv()
    assert os.environ.get("SCINAPSE_TEST_DOTENV") == "loaded-from-fallback"


def test_load_dotenv_cwd_file_wins(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCINAPSE_TEST_DOTENV", raising=False)
    (tmp_path / ".env").write_text("SCINAPSE_TEST_DOTENV=from-cwd\n", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    (root / ".env").write_text("SCINAPSE_TEST_DOTENV=from-repo-root\n", encoding="utf-8")
    monkeypatch.setattr(C, "REPO_ROOT", root)
    C.load_dotenv()
    assert os.environ.get("SCINAPSE_TEST_DOTENV") == "from-cwd"
