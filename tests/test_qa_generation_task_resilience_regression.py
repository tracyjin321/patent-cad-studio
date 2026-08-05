"""Regression tests for the gear-shaft browser QA findings.

Regression: ISSUE-001/002 — exact local matches waited for Moonshot and dead
workers left generation tasks running forever.
Found by /qa on 2026-08-05.
Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-08-05.md
"""

import importlib
import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

main_module = importlib.import_module("app.main")


@pytest.mark.asyncio
async def test_exact_local_assembly_match_does_not_wait_for_model(monkeypatch):
    async def model_must_not_run(*_args, **_kwargs):
        raise AssertionError("精确本地匹配不应调用大模型")

    monkeypatch.setattr(main_module, "analyze_component_assembly", model_must_not_run)
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test") as client:
        response = await client.post("/api/component-recommendations", json={
            "description": "生成机械专利附图风格的齿轮轴组合，装配6004轴承和带键槽直齿轮。",
            "use_ai": True,
            "limit": 16,
        })

    assert response.status_code == 200
    assert response.json()["component_ids"] == ["gear-shaft-assembly-680-9-1-6"]
    assert response.json()["parser_detail"] == "本地图元规则精确命中，跳过大模型补充分析"


@pytest.mark.asyncio
async def test_polling_marks_a_dead_worker_task_as_recoverable_failure(monkeypatch, tmp_path):
    task_id = str(uuid4())
    task_path = tmp_path / f"{task_id}.json"
    task_path.write_text(json.dumps({
        "id": task_id, "status": "running", "progress": 87, "worker_pid": 424242,
    }), encoding="utf-8")

    def dead_worker(_pid, _signal):
        raise ProcessLookupError

    monkeypatch.setattr(main_module, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(main_module.os, "kill", dead_worker)
    async with AsyncClient(transport=ASGITransport(app=main_module.app), base_url="http://test") as client:
        response = await client.get(f"/api/generation-tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["recoverable"] is True
    assert "worker 异常退出" in response.json()["error"]
    assert json.loads(task_path.read_text(encoding="utf-8"))["status"] == "failed"
