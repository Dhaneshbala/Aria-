"""Snapshot tests — API response shapes pinned against regressions.

Syrupy stores accepted payloads in __snapshots__/. If an endpoint's shape
changes, the test fails and forces an intentional `--snapshot-update`.
Timestamps/counts are excluded (volatile by nature).
"""

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _scrub_health(body: dict) -> dict:
    return {
        k: ("…" if k in ("disk_free_gb", "data_dir") else v)
        for k, v in sorted(body.items())
    }


def test_health_shape_snapshot(snapshot):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert snapshot == _scrub_health(r.json())


def test_todos_shape_snapshot(snapshot):
    r = client.get("/api/todos")
    assert r.status_code == 200
    body = r.json()
    assert snapshot == {
        "keys": sorted(body.keys()),
        "todo_keys": sorted(body["todos"][0].keys()) if body.get("todos") else [],
    }
