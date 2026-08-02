import pytest

from app.server import worker_count


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
