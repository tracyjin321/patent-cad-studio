"""Production-safe multi-process entry point for CAD generation."""

from __future__ import annotations

import os

import uvicorn


def worker_count() -> int:
    """Use two isolated CAD kernels by default; allow explicit capacity tuning."""
    raw = os.getenv("CAD_WORKERS", "5")
    try:
        workers = int(raw)
    except ValueError as exc:
        raise ValueError("CAD_WORKERS 必须是正整数") from exc
    if workers < 1:
        raise ValueError("CAD_WORKERS 必须是正整数")
    return workers


def main() -> None:
    os.environ["CAD_WORKERS"] = str(worker_count())
    uvicorn.run(
        "app.main:app",
        host=os.getenv("CAD_HOST", "127.0.0.1"),
        port=int(os.getenv("CAD_PORT", "8000")),
        workers=worker_count(),
        timeout_keep_alive=30,
    )


if __name__ == "__main__":
    main()
