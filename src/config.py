"""Central application configuration for Cocai.

Provides a single dataclass `AppConfig` that holds all settings so they can be:
  * Unit tested without patching os.environ everywhere.
  * Potentially surfaced in a future GUI for live configuration.

Configuration is split across two files:
  - config.toml  — non-secret settings (safe to commit to git)
  - .env         — API keys and secrets (git-ignored)

The `from_config()` classmethod reads both.  For tests, `from_dict()` accepts
a plain dict so no files are needed on disk.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from utils import FALSY_STRINGS, TRUTHY_STRINGS


def env_flag(name: str, default: bool = True) -> bool:
    """
    Read a boolean flag from environment variables with a forgiving parser.

    - Truthy values (case-insensitive): 1, true, yes, y, on, t
    - Falsy values (case-insensitive): 0, false, no, n, off, f
    - Any other non-empty value defaults to False, and missing env var returns
      the provided default.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if val in TRUTHY_STRINGS:
        return True
    if val in FALSY_STRINGS:
        return False
    return False


@dataclass(slots=True)
class AppConfig:
    # LLM
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""

    # Embedding
    embed_api_base: str = "https://api.openai.com/v1"
    embed_model: str = "text-embedding-3-small"
    embed_dims: int = 1536
    embed_api_key: str = ""

    # Vector store (ChromaDB)
    chroma_path: str = ".data/chroma"
    rag_collection: str = "game_module"
    mem_collection: str = "cocai"

    # Memory (Mem0)
    memory_enabled: bool = True
    mem0_api_key: str | None = None

    # Tracing (Arize Phoenix, optional)
    tracing_enabled: bool = False
    tracing_endpoint: str | None = None

    # Game module
    game_module_path: str = "game_modules/Clean-Up-Aisle-Four"
    should_preread_game_module: bool = False
    should_reuse_existing_index: bool = True

    # Image generation (OpenAI-compatible images/generations endpoint)
    image_gen_enabled: bool = False
    image_model: str = "bytedance-seed/seedream-4.5"
    image_api_key: str = ""

    # Auto-update panes
    enable_auto_history_update: bool = True
    enable_auto_scene_update: bool = False

    @classmethod
    def from_config(
        cls,
        toml_path: str | Path = "config.toml",
        env: Mapping[str, str] | None = None,
    ) -> AppConfig:
        """Load config.toml for non-secret settings, then overlay API keys from env/.env."""
        e = env if env is not None else os.environ
        toml_path = Path(toml_path)

        cfg: dict[str, Any] = {}
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                cfg = tomllib.load(f)

        llm = cfg.get("llm", {})
        emb = cfg.get("embedding", {})
        vs = cfg.get("vector_store", {})
        mem = cfg.get("memory", {})
        tr = cfg.get("tracing", {})
        gm = cfg.get("game_module", {})
        ig = cfg.get("image_generation", {})
        au = cfg.get("auto_update", {})

        return cls(
            llm_api_base=llm.get("api_base", "https://api.openai.com/v1"),
            llm_model=llm.get("model", "gpt-4o"),
            llm_api_key=e.get("LLM_API_KEY", ""),
            embed_api_base=emb.get("api_base", "https://api.openai.com/v1"),
            embed_model=emb.get("model", "text-embedding-3-small"),
            embed_dims=int(emb.get("dims", 1536)),
            embed_api_key=e.get("EMBED_API_KEY", e.get("LLM_API_KEY", "")),
            chroma_path=vs.get("path", ".data/chroma"),
            rag_collection=vs.get("rag_collection", "game_module"),
            mem_collection=vs.get("mem_collection", "cocai"),
            memory_enabled=bool(mem.get("enabled", True)),
            mem0_api_key=e.get("MEM0_API_KEY") or None,
            tracing_enabled=bool(tr.get("enabled", False)),
            tracing_endpoint=tr.get("endpoint") or None,
            game_module_path=gm.get("path", "game_modules/Clean-Up-Aisle-Four"),
            should_preread_game_module=bool(gm.get("preread", False)),
            should_reuse_existing_index=bool(gm.get("reuse_index", True)),
            image_gen_enabled=bool(ig.get("enabled", False)),
            image_model=ig.get("model", "bytedance-seed/seedream-4.5"),
            image_api_key=e.get("IMAGE_API_KEY", e.get("LLM_API_KEY", "")),
            enable_auto_history_update=bool(au.get("history", True)),
            enable_auto_scene_update=bool(au.get("scene", False)),
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AppConfig:
        """Construct directly from a plain dict — intended for tests only."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
