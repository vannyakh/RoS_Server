"""Shared by every gateway compatibility test."""

import sys

import pytest


@pytest.fixture(autouse=True)
def _match_results_in_tmp(tmp_path, monkeypatch):
    """results.py saves unlinked matches to match_results.jsonl; keep test runs out of the repo."""
    path = str(tmp_path / "match_results.jsonl")
    monkeypatch.setenv("MATCH_RESULTS_FILE", path)
    module = sys.modules.get("match_results")
    if module is not None:
        monkeypatch.setattr(module, "PATH", path)
