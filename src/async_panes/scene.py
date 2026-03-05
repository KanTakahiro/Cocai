"""
Auto-detect significant scene changes and generate an illustration.

Pipeline per exchange:
  1. Evaluate  — LLM decides if the scene/setting changed meaningfully.
  2. Describe  — LLM writes a concise image-generation prompt.
  3. Image     — OpenRouter chat completions with modalities=["image"] produces the art.
  4. Publish   — SSE broadcasts the base64 data-URL to the play UI centre pane.

OpenRouter does NOT expose /images/generations.  Image-capable models are reached
via POST /chat/completions with ``extra_body={"modalities": ["image"]}``.  The
generated PNG is returned as a base64 data-URL inside
``choices[0].message.images[0].image_url.url``.

If image generation is disabled in config (`[image_generation] enabled = false`),
the module only evaluates scene changes and signals "unchanged" — keeping the
BackgroundPaneUpdateManager scaffolding functional with zero cost.
"""

from __future__ import annotations

import asyncio
import logging

from llama_index.core.memory import Memory
from llama_index.core.workflow import Context
from llama_index.memory.mem0 import Mem0Memory

from config import AppConfig
from events import broadcaster

from .async_panes_utils import build_transcript, format_transcript, llm_complete_text


async def update_scene_if_needed(
    ctx: Context,
    memory: Memory | Mem0Memory,
    app_config: AppConfig,
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

        if not app_config.image_gen_enabled:
            # Scene changed but image generation is disabled — nothing to display.
            broadcaster.publish({"type": "scene_status", "phase": "unchanged"})
            return

        broadcaster.publish({"type": "scene_status", "phase": "describing"})
        description = await __describe_visual_scene(transcript)
        if not description:
            broadcaster.publish({"type": "scene_status", "phase": "unchanged"})
            return

        broadcaster.publish({"type": "scene_status", "phase": "imaging"})
        url = await __generate_scene_image(description, app_config)
        if not url:
            broadcaster.publish({"type": "scene_status", "phase": "error"})
            return

        broadcaster.publish({"type": "illustration", "url": url})
        broadcaster.publish({"type": "scene_status", "phase": "updated"})
        logger.info("Scene illustration updated.")

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
        "Scene changes include: moving to a different location (inside/outside), entering a new room/building, "
        "time of day shifts, lighting/weather changes, a new set piece revealed, or a major shift in focus "
        "(e.g., basement to street, office to library).\n"
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


async def __describe_visual_scene(transcript: list[dict[str, str]]) -> str:
    """Ask the LLM to write a concise image-generation prompt for the current scene."""
    recent_text = format_transcript(transcript, last_k=10)
    prompt = (
        "You are writing an image-generation prompt for a Call of Cthulhu scene illustration.\n"
        "Based on the conversation below, describe the CURRENT SCENE visually in 50-80 words.\n"
        "Focus on: location, architecture/environment, lighting, time of day, atmosphere, and key objects.\n"
        "Style directive to append: dark atmospheric illustration, 1920s Lovecraftian horror, detailed oil painting.\n"
        "Do NOT include character dialogue, game mechanics, dice rolls, or story outcomes — only what can be SEEN.\n\n"
        f"Recent conversation (most recent last):\n{recent_text}\n\n"
        "Write ONLY the image prompt, no preamble."
    )
    try:
        description = await llm_complete_text(prompt)
        return description.strip()
    except asyncio.CancelledError:
        raise
    except Exception:
        return ""


async def __generate_scene_image(description: str, app_config: AppConfig) -> str:
    """Call OpenRouter's chat completions endpoint to generate a scene image.

    OpenRouter routes image-capable models through the standard chat completions
    path with a non-standard ``modalities`` body parameter rather than through
    the OpenAI ``/images/generations`` endpoint (which it does not expose).
    The generated image is returned as a base64 PNG data-URL embedded inside
    ``choices[0].message.images[0].image_url.url``.
    """
    logger = logging.getLogger("auto_scene_update")
    try:
        from openai import AsyncOpenAI

        image_base = app_config.image_api_base or app_config.llm_api_base
        client = AsyncOpenAI(
            api_key=app_config.image_api_key,
            base_url=image_base,
        )
        response = await client.chat.completions.create(
            model=app_config.image_model,
            messages=[{"role": "user", "content": description}],
            extra_body={"modalities": ["image"]},
        )
        # OpenRouter embeds the image under a non-standard `images` key that is
        # absent from the openai-python schema, so parse from the raw dict.
        raw = response.model_dump()
        choices = raw.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        images = message.get("images") or []
        if images:
            data_url: str = (images[0].get("image_url") or {}).get("url", "")
            if data_url:
                logger.info(
                    "Scene image generated (data URL, %d chars)", len(data_url)
                )
                return data_url

        logger.warning("Image generation returned no image data in response.")
        return ""
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        return ""
