import pytest

from app import server


worker_count = server.worker_count


def test_worker_count_defaults_to_parallel_capacity(monkeypatch):
    monkeypatch.delenv("CAD_WORKERS", raising=False)
    assert worker_count() == 5


def test_worker_count_is_configurable(monkeypatch):
    monkeypatch.setenv("CAD_WORKERS", "4")
    assert worker_count() == 4


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_worker_count_rejects_invalid_capacity(monkeypatch, value):
    monkeypatch.setenv("CAD_WORKERS", value)
    with pytest.raises(ValueError, match="正整数"):
        worker_count()


def test_main_recovers_tasks_before_starting_worker_pool(monkeypatch):
    events = []
    monkeypatch.delenv("CAD_WORKERS", raising=False)
    monkeypatch.setattr(
        server,
        "recover_generation_tasks",
        lambda: events.append("recover"),
        raising=False,
    )
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda *args, **kwargs: events.append(("run", kwargs["workers"])),
    )

    server.main()

    assert events == ["recover", ("run", 5)]
