# Application Configuration (AppConfig)

Runtime settings are centralized in `src/config.py` via the `AppConfig` dataclass.  Configuration is split across two files so that API keys never enter version control:

| File | Content | Git |
|------|---------|-----|
| `config.toml` | Non-secret settings (endpoints, model names, paths, feature flags) | **committed** |
| `.env` | Secrets (`LLM_API_KEY`, `EMBED_API_KEY`, `CHAINLIT_AUTH_SECRET`, …) | git-ignored |

## Key Fields

| Section | Fields |
|---------|--------|
| `[llm]` | `api_base`, `model` |
| `[embedding]` | `api_base`, `model`, `dims` |
| `[vector_store]` | `path` (ChromaDB dir), `rag_collection`, `mem_collection` |
| `[memory]` | `enabled` |
| `[tracing]` | `enabled`, `endpoint` |
| `[game_module]` | `path`, `preread`, `reuse_index` |
| `[auto_update]` | `history`, `scene` |

API keys read from `.env`: `LLM_API_KEY`, `EMBED_API_KEY` (falls back to `LLM_API_KEY`), `MEM0_API_KEY` (optional), `TAVILY_API_KEY` (optional).

## Usage in `main.py`

```python
from config import AppConfig

cfg = AppConfig.from_config()          # reads config.toml + .env
system_prompt = set_up_llama_index(cfg)
memory = __prepare_memory(key, cfg)
```

`from_config()` is called once per chat session inside `@cl.on_chat_start` — not at import time — so every session picks up the latest config without a server restart.

## Adding a New Config Value

1. Add a field to `config.toml` (non-secret) or note it as a `.env` key (secret).
2. Add the corresponding field to `AppConfig` in `src/config.py` with a sensible default.
3. Read it in `AppConfig.from_config()`.
4. Add or update a test in `tests/test_config.py`.

## Testing

`AppConfig.from_config(toml_path=..., env={...})` accepts explicit arguments so tests never need files on disk or real env vars.  `AppConfig.from_dict(...)` lets tests construct a config from a plain dict directly.
