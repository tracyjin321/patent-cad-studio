# Shared Generation Task State Design

## Context

The application runs five Uvicorn worker processes. A generation task is created
in one worker and stored in that worker's `GENERATION_TASKS` dictionary. Browser
polling can be routed to a different worker, where the task is absent, so the
same task URL intermittently changes from HTTP 200 to HTTP 404.

Task records are already persisted under `generated/tasks/`, but the query
endpoint only reads process-local memory.

## Goals

- Preserve the existing five-worker CAD concurrency.
- Make task status polling independent of which worker receives the request.
- Keep the current API response shape and frontend polling behavior.
- Preserve HTTP 404 for task IDs that genuinely do not exist.

## Design

The persisted JSON record becomes the shared read source for generation-task
status. Task creation and state transitions continue updating the in-memory
record owned by the executing worker, then persist each transition.

The status endpoint reads the task's persisted record on every request instead
of relying on a worker-local dictionary. This prevents both missing-task 404s
and stale `queued` or `running` states in workers that previously read an older
record.

Task record writes use an atomic replace operation. Readers therefore see either
the previous complete JSON document or the next complete JSON document, never a
partially written file.

Task IDs are validated before constructing a filesystem path. A missing,
invalid, or unreadable record is treated as an unknown task and returns the
existing `生成任务不存在` 404 response.

Cancellation behavior is not redesigned in this change. Cross-worker
cancellation coordination is a separate concern; this fix is limited to the
observed status-query failure.

## Data Flow

1. Any worker accepts `POST /api/generation-tasks` and atomically persists the
   initial `queued` record.
2. The owning worker persists `running`, then `completed`, `failed`, or
   `cancelled` state transitions.
3. Any worker handling `GET /api/generation-tasks/{id}` reads the latest complete
   record from `generated/tasks/{id}.json` and returns it.
4. If no valid record exists, the endpoint returns HTTP 404.

## Testing

- Create a persisted task record while the querying worker's in-memory mapping
  is empty; GET must return HTTP 200 and the record.
- Replace a persisted `queued` record with `completed`; repeated GET requests
  must return the newer state rather than a cached copy.
- Unknown or invalid task IDs must still return HTTP 404.
- Run the task API tests and the complete test suite.
- Restart the five-worker service and verify repeated polling never changes from
  HTTP 200 to HTTP 404 for a valid task.

## Non-goals

- No database or Redis dependency.
- No frontend API changes.
- No reduction in worker count.
- No redesign of distributed cancellation or task scheduling.
