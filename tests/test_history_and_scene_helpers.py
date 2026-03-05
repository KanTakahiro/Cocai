import asyncio
from types import SimpleNamespace

import pytest

from async_panes import history


def _future_with(value: str):
    fut: asyncio.Future[str] = asyncio.Future()
    fut.set_result(value)
    return fut


@pytest.mark.asyncio
async def test_should_update_history_yes(monkeypatch):
    monkeypatch.setattr(
        history, "llm_complete_text", lambda prompt: _future_with("YES")
    )
    assert await history.__should_update_history([{"role": "user", "content": "hi"}])  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_should_update_history_no(monkeypatch):
    monkeypatch.setattr(history, "llm_complete_text", lambda prompt: _future_with("NO"))
    assert not await history.__should_update_history(
        [{"role": "user", "content": "hi"}]
    )  # type: ignore[attr-defined]
