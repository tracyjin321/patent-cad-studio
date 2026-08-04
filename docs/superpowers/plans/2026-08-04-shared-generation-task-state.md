# Shared Generation Task State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generation-task polling reliable across all five Uvicorn workers without changing the frontend API or reducing CAD concurrency.

**Architecture:** Keep the executing worker's in-memory state for its runtime `asyncio.Task`, while making the existing `generated/tasks/<uuid>.json` record authoritative for status reads. Persist state transitions with atomic file replacement so another worker never observes partial JSON.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn multi-process workers, pytest, httpx ASGI transport, JSON files.

## Global Constraints

- Preserve the existing five-worker CAD concurrency.
- Keep the current generation-task API response shape and frontend polling behavior.
- Keep HTTP 404 for task IDs that genuinely do not exist.
- Add no database, Redis, or other dependency.
- Do not redesign distributed cancellation or task scheduling.
- Preserve all pre-existing uncommitted user changes in the main checkout.

---

### Task 1: Shared persisted status records

**Files:**
- Modify: `tests/test_api.py` near the generation-task endpoint tests
- Modify: `app/main.py` near `TASKS_DIR`, `_persist_task`, and `get_generation_task`

**Interfaces:**
- Consumes: `TASKS_DIR: pathlib.Path` and task records shaped as `dict[str, object]` with an `id` field.
- Produces: `_task_path(task_id: str) -> Path | None`, `_read_persisted_task(task_id: str) -> dict[str, object] | None`, and atomic `_persist_task(task_id: str) -> None` behavior.
- Preserves: `GET /api/generation-tasks/{task_id}` response body and 404 detail.

- [ ] **Step 1: Write the failing cross-worker regression test**

Add imports if absent:

```python
import json
from uuid import uuid4
```

Add this test beside the existing generation-task tests:

```python
@pytest.mark.asyncio
async def test_generation_task_status_reads_latest_persisted_record_across_workers(monkeypatch, tmp_path):
    task_id = str(uuid4())
    task_path = tmp_path / f"{task_id}.json"
    task_path.write_text(
        json.dumps({"id": task_id, "status": "queued", "progress": 0}),
        encoding="utf-8",
    )
    monkeypatch.setattr(main_module, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(main_module, "GENERATION_TASKS", {})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        queued = await client.get(f"/api/generation-tasks/{task_id}")
        task_path.write_text(
            json.dumps({"id": task_id, "status": "completed", "progress": 100, "result": {"id": "model-1"}}),
            encoding="utf-8",
        )
        completed = await client.get(f"/api/generation-tasks/{task_id}")

    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
```

This reproduces both failure modes: a worker with an empty in-memory mapping and a worker that must not return a cached stale record.

- [ ] **Step 2: Run the regression test and verify RED**

Run:

```bash
./.venv/bin/pytest -q tests/test_api.py::test_generation_task_status_reads_latest_persisted_record_across_workers
```

Expected: FAIL because the first GET returns HTTP 404 while `GENERATION_TASKS` is empty.

- [ ] **Step 3: Implement validated task paths and persisted reads**

Change the UUID import in `app/main.py` to:

```python
from uuid import UUID, uuid4
```

Add these helpers above `_persist_task`:

```python
def _task_path(task_id: str) -> Path | None:
    try:
        if str(UUID(task_id)) != task_id:
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    return TASKS_DIR / f"{task_id}.json"


def _read_persisted_task(task_id: str) -> dict[str, object] | None:
    path = _task_path(task_id)
    if path is None:
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("id") != task_id:
            return None
        return record
    except (OSError, ValueError, TypeError):
        return None
```

Update `get_generation_task` to read the shared record on every request:

```python
@app.get("/api/generation-tasks/{task_id}")
def get_generation_task(task_id: str) -> dict[str, object]:
    record = _read_persisted_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return record
```

Do not cache this deserialized record back into `GENERATION_TASKS`. The owning
worker's running coroutine retains a reference to its in-memory record; replacing
that mapping entry during a GET could cause the final state transition to persist
an older object.

- [ ] **Step 4: Make task writes atomic**

Replace `_persist_task` with:

```python
def _persist_task(task_id: str) -> None:
    path = _task_path(task_id)
    if path is None:
        raise ValueError("生成任务 ID 无效")
    record = {key: value for key, value in GENERATION_TASKS[task_id].items() if key != "runtime_task"}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
```

This uses the existing process ID and task UUID to avoid temporary-file collisions and keeps temporary files outside the `*.json` recovery scan.

- [ ] **Step 5: Add and run invalid/unknown-ID coverage**

Add:

```python
@pytest.mark.asyncio
async def test_generation_task_status_rejects_invalid_or_unknown_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "TASKS_DIR", tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.get("/api/generation-tasks/not-a-uuid")
        unknown = await client.get(f"/api/generation-tasks/{uuid4()}")
    assert invalid.status_code == 404
    assert unknown.status_code == 404
```

Run:

```bash
./.venv/bin/pytest -q \
  tests/test_api.py::test_generation_task_status_reads_latest_persisted_record_across_workers \
  tests/test_api.py::test_generation_task_status_rejects_invalid_or_unknown_ids
```

Expected: 2 passed.

- [ ] **Step 6: Run all task API regression tests**

Run:

```bash
./.venv/bin/pytest -q tests/test_api.py -k generation_task
```

Expected: all selected generation-task tests pass.

- [ ] **Step 7: Commit the isolated implementation**

Stage only the implementation and test changes:

```bash
git add app/main.py tests/test_api.py
git commit -m "fix: share generation task status across workers"
```

---

### Task 2: Full verification and five-worker runtime check

**Files:**
- Verify: `app/main.py`
- Verify: `tests/test_api.py`
- Verify: `app/server.py`

**Interfaces:**
- Consumes: the shared persisted task status behavior from Task 1.
- Produces: a five-worker service on `http://127.0.0.1:8000` whose valid task URL never intermittently returns 404.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
./.venv/bin/pytest -q
```

Expected: all tests pass; the existing Pillow deprecation warning may remain.

- [ ] **Step 2: Integrate while preserving the dirty main checkout**

Stop the local server, save all pre-existing tracked and untracked main-checkout changes in a named stash, fast-forward the reviewed fix branch into `main`, then restore the named stash. Resolve only overlapping hunks in `app/main.py` or `tests/test_api.py`, preserving both the user's patent-check changes and the shared-task fix. Verify `git status --short` still lists the same pre-existing user files.

- [ ] **Step 3: Restart the configured five-worker service**

Run from the main checkout:

```bash
./.venv/bin/python -m app.server
```

Expected startup log: Uvicorn listens on `http://127.0.0.1:8000` and five server processes complete application startup.

- [ ] **Step 4: Verify real multi-worker polling**

Run repeated HTTP requests against the live service:

```bash
./.venv/bin/python -c 'import httpx,time; client=httpx.Client(base_url="http://127.0.0.1:8000"); created=client.post("/api/generation-tasks",json={"description":"生成测试轴","part_type":"shaft","use_ai":False}); created.raise_for_status(); url=created.json()["status_url"]; codes=[]; states=[]; [(time.sleep(.1), codes.append((response:=client.get(url)).status_code), states.append(response.json().get("status") if response.status_code==200 else None)) for _ in range(30)]; print({"codes":codes,"states":states}); assert codes==[200]*30'
```

Expected: every status code is 200; states progress through `queued`/`running` to a terminal state without 404.

- [ ] **Step 5: Verify the browser-facing page**

Run:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/
```

Expected: `200`.

- [ ] **Step 6: Report the result**

Report the focused test count, complete test count, live 30-poll result, current local commit, and whether anything was pushed. Keep the service running for the user.
