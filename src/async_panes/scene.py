"""
Auto-detect significant scene changes.

Image generation has been removed; this module evaluates whether the scene
has changed but does not produce illustrations.  It is kept so the
BackgroundPaneUpdateManager scaffolding continues to work if scene updates
are re-enabled in config.toml ([auto_update] scene = true).
"""

from __future__ import annotations

import asyncio
import logging

from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from llama_index.memory.mem0 import Mem0Memory

from events import broadcaster

from .async_panes_utils import build_transcript, format_transcript, llm_complete_text


async def update_scene_if_needed(
    ctx: Context,
    memory: Memory | Mem0Memory,
    last_user_msg: str | None = None,
    last_agent_msg: str | None = None,
) -> None:
    logger = logging.getLogger("auto_scene_update")
    transcript = build_transcript(
        memory=memory, last_user_msg=last_user_msg, last_agent_msg=last_agent_msg
    )
    if not transcript:
        logger.debug("No transcript found for scene update.")
        return
    try:
        broadcaster.publish({"type": "scene_status", "phase": "evaluating"})
        should = await __should_update_scene(transcript)
        if not should:
            broadcaster.publish({"type": "scene_status", "phase": "unchanged"})
            return
        # Image generation is currently disabled; signal unchanged.
        broadcaster.publish({"type": "scene_status", "phase": "unchanged"})
    except asyncio.CancelledError:
        logger.info("auto_scene_update task cancelled")
        try:
            broadcaster.publish({"type": "scene_status", "phase": "cancelled"})
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error("Auto scene update failed.", exc_info=e)
        try:
            broadcaster.publish({"type": "scene_status", "phase": "error"})
        except Exception:
            pass


async def __should_update_scene(transcript: list[dict[str, str]]) -> bool:
    if not transcript:
        return False
    recent_text = format_transcript(transcript, last_k=8)
    prompt = (
        "You are monitoring a Call of Cthulhu session. Decide if the LATEST exchange significantly changes the scene/setting.\n"
        "Scene changes include: moving to a different location (inside/outside), entering a new room/building, time of day shifts, lighting/weather changes, a new set piece revealed, or a major shift in focus (e.g., basement to street, office to library).\n"
        "Do NOT trigger for rules clarifications, minor dialogue, or small detail tweaks.\n\n"
        "Conversation (most recent last):\n"
        f"{recent_text}\n\n"
        "Answer strictly with YES or NO."
    )
    decision = await llm_complete_text(prompt)
    try:
        return decision.lower().startswith("y")
    except Exception:
        return False
