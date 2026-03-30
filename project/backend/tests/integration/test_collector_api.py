"""Ингест /track, /logs/upload и смежные маршруты коллектора."""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_track_invalid_project_id(client):
    r = client.post(
        "/track",
        json={
            "project_id": "not-a-uuid",
            "action": "test",
            "timestamp": "2026-01-01T12:00:00Z",
            "context": {},
            "meta": {},
        },
    )
    assert r.status_code == 400


def test_track_unknown_project(client, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(uuid.uuid4())
    r = client.post(
        "/track",
        json={
            "project_id": pid,
            "action": "pytest_event",
            "timestamp": "2026-01-01T12:00:00Z",
            "context": {"platform": "python"},
            "meta": {"page_url": "https://example.com/x", "error_message": "boom"},
        },
    )
    assert r.status_code == 500 or r.status_code == 400
    # FK: проекта нет в БД — откат и 500
    assert r.status_code != 200


def test_track_ok_minimal(client, sample_project_id, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(sample_project_id)
    r = client.post(
        "/track",
        json={
            "project_id": pid,
            "action": "pytest_ok",
            "timestamp": "2026-03-30T12:00:00Z",
            "context": {},
            "meta": {},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data


def test_track_with_error_meta(client, sample_project_id, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(sample_project_id)
    r = client.post(
        "/track",
        json={
            "project_id": pid,
            "action": "pytest_error",
            "timestamp": "2026-03-30T12:01:00Z",
            "context": {"platform": "backend"},
            "meta": {
                "error_message": "ValueError: x",
                "error_stack": "Traceback...",
            },
        },
    )
    assert r.status_code == 200


def test_track_requires_api_key(client, sample_project_with_api_key):
    pid, raw = sample_project_with_api_key
    r = client.post(
        "/track",
        json={
            "project_id": str(pid),
            "action": "no_key",
            "timestamp": "2026-03-30T12:02:00Z",
            "context": {},
            "meta": {},
        },
    )
    assert r.status_code == 401


def test_track_with_x_api_key(client, sample_project_with_api_key):
    pid, raw = sample_project_with_api_key
    r = client.post(
        "/track",
        json={
            "project_id": str(pid),
            "action": "with_key",
            "timestamp": "2026-03-30T12:03:00Z",
            "context": {},
            "meta": {},
        },
        headers={"X-Api-Key": raw},
    )
    assert r.status_code == 200


def test_logs_upload_project_not_found(client, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(uuid.uuid4())
    r = client.post(
        "/logs/upload",
        json={
            "project_id": pid,
            "filename": "app.log",
            "content": "error: something failed\n",
            "lines_sent": 1,
            "total_lines": 100,
        },
    )
    assert r.status_code == 404


def test_logs_upload_ok(client, sample_project_id, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(sample_project_id)
    r = client.post(
        "/logs/upload",
        json={
            "project_id": pid,
            "filename": "worker.log",
            "content": "ERROR connection reset\nWARN slow\n",
            "lines_sent": 2,
            "total_lines": 50,
            "server_name": "test-srv",
            "service_name": "pytest",
        },
    )
    assert r.status_code == 200
    assert "id" in r.json()


def test_list_project_logs(client, sample_project_id, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "false")
    pid = str(sample_project_id)
    client.post(
        "/logs/upload",
        json={
            "project_id": pid,
            "filename": "a.log",
            "content": "line",
            "lines_sent": 1,
            "total_lines": 1,
        },
    )
    r = client.get(f"/projects/{pid}/logs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_stats_summary_reports_token(client, db_session_committed, monkeypatch):
    monkeypatch.setenv("REPORTS_API_TOKEN", "reports-secret")
    r = client.get("/stats/summary")
    assert r.status_code == 401
    r2 = client.get(
        "/stats/summary",
        headers={"Authorization": "Bearer reports-secret"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert "period" in body
    assert "events_with_errors" in body


def test_weekly_report_xlsx(client, monkeypatch):
    monkeypatch.setenv("REPORTS_API_TOKEN", "xlsx-token")
    r = client.get(
        "/reports/weekly.xlsx",
        headers={"X-Reports-Token": "xlsx-token"},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
