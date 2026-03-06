"""
Integration tests that call the real LLM configured in config.toml.

These tests are skipped automatically when LLM_API_KEY is not set in the
environment (or in .env loaded by conftest.py).

Run individually:
    uv run pytest tests/test_llm_integration.py -v
"""
import pytest
from llama_index.core import Settings
from llama_index.llms.openai_like import OpenAILike

from async_panes import history
from async_panes.async_panes_utils import llm_complete_text
from config import AppConfig


# ---------------------------------------------------------------------------
# Session-scoped fixture: load config, skip if no key, init LLM once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def llm_setup():
    cfg = AppConfig.from_config()
    if not cfg.llm_api_key:
        pytest.skip("LLM_API_KEY not set — skipping LLM integration tests")
    llm = OpenAILike(
        model=cfg.llm_model,
        api_base=cfg.llm_api_base,
        api_key=cfg.llm_api_key,
        is_function_calling_model=True,
        is_chat_model=True,
    )
    # Probe the endpoint before running any test; skip cleanly on auth/network errors.
    try:
        llm.complete("hi")
    except Exception as e:
        pytest.skip(f"LLM endpoint unreachable or key invalid: {e}")
    Settings.llm = llm


# ---------------------------------------------------------------------------
# llm_complete_text
# ---------------------------------------------------------------------------


async def test_llm_complete_text_returns_nonempty_string():
    result = await llm_complete_text("Reply with exactly the word OK and nothing else.")
    assert isinstance(result, str)
    assert len(result) > 0


async def test_llm_complete_text_returns_empty_string_on_bad_prompt():
    """Passing an empty prompt should still return a string (possibly empty), not raise."""
    result = await llm_complete_text("")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# __should_update_history — YES / NO scenarios
# ---------------------------------------------------------------------------


async def test_should_update_history_yes_for_story_event():
    transcript = [
        {
            "role": "user",
            "content": "I push open the heavy oak door and step inside.",
        },
        {
            "role": "agent",
            "content": (
                "The door swings open with a groan. Inside the old library you find "
                "Professor Armitage slumped over his desk, a look of sheer terror "
                "frozen on his face. A crumpled note lies nearby — it reads: "
                "'They have found the Necronomicon.'"
            ),
        },
    ]
    result = await history.__should_update_history(transcript)  # type: ignore[attr-defined]
    assert result is True


async def test_should_update_history_no_for_rules_question():
    transcript = [
        {
            "role": "user",
            "content": "What is the difference between a Hard success and an Extreme success?",
        },
        {
            "role": "agent",
            "content": (
                "A Hard success requires rolling equal to or less than half your skill value. "
                "An Extreme success requires rolling equal to or less than one fifth of your skill value."
            ),
        },
    ]
    result = await history.__should_update_history(transcript)  # type: ignore[attr-defined]
    assert result is False
