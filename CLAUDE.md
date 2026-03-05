# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just serve              # Dev server (uvicorn --reload at :8000)
just format             # Format with Ruff
just test               # Run pytest with coverage
uv run pytest tests/test_config.py::test_config_defaults  # Single test
```

**Service URLs:** Chat `http://localhost:8000/chat` · Play UI `http://localhost:8000/play`

**First-run setup:**
1. Copy `config.toml` and fill in your API endpoint/model settings
2. Create `.env` from `.env.example` and fill in API keys
3. Run `chainlit create-secret` and add the secret to `.env`
4. `just serve`

No external services (Docker, Ollama, etc.) are required.

## Configuration

Settings are split across two files:

| File | Purpose | Git status |
|------|---------|------------|
| `config.toml` | Non-secret settings (API base URLs, models, paths) | **committed** |
| `.env` | API keys and secrets | **git-ignored** |

`config.toml` sections: `[llm]`, `[embedding]`, `[vector_store]`, `[memory]`, `[tracing]`, `[game_module]`, `[auto_update]`.  
`AppConfig.from_config()` (`src/config.py`) reads both; loaded once per chat session inside `@cl.on_chat_start`.

Key env vars (`.env`): `LLM_API_KEY`, `EMBED_API_KEY` (falls back to `LLM_API_KEY`), `CHAINLIT_AUTH_SECRET`, `MEM0_API_KEY` (optional cloud Mem0), `TAVILY_API_KEY` (optional search).

## Architecture

CoCai is an AI-powered Call of Cthulhu game master. A FastAPI app (`server.py`) mounts Chainlit at `/chat`. On each session start (`main.py:factory()`), a LlamaIndex `FunctionAgent` is assembled with tools and Mem0 memory, then streams responses to the Chainlit UI.

### Key files

| File | Role |
|------|------|
| `src/main.py` | Agent wiring, Chainlit event handlers, session setup |
| `src/server.py` | FastAPI app, Chainlit mount, SSE `/api/events`, `/roll_dice` |
| `src/config.py` | `AppConfig` dataclass — reads `config.toml` + env for secrets |
| `src/state.py` | `GameState` / `Clue` dataclasses for the play UI panes |
| `src/events.py` | `Broadcaster` for SSE pub-sub to play UI |
| `src/utils.py` | `LocalStorageClient` (file storage), data layer setup, logging |
| `src/agentic_tools/` | One file per tool (dice, RAG, character, stats, clues) |
| `src/async_panes/` | Background pane update manager (history summary) |
| `public/play.html/js/css` | Three-pane play UI (history · illustration · character stats) |
| `prompts/system_prompt.md` | Base system prompt for the CoC Keeper role |

### LLM and embedding (`set_up_llama_index()`)

Both LLM and embedding use OpenAI-compatible API endpoints configured in `config.toml`:
- LLM: `OpenAILike(model=..., api_base=..., api_key=...)` — works with OpenAI, Together AI, Groq, vLLM, etc.
- Embedding: `OpenAIEmbedding(model=..., api_base=..., api_key=...)` — same flexibility.

**Important:** Initialize LLMs inside `@cl.on_chat_start` (not at import time) so Phoenix traces attach correctly to Agent Steps.

### Vector store (ChromaDB)

ChromaDB replaces Qdrant — it runs in-process with disk persistence, no separate server needed.

- RAG index (`rag_collection`): built from game module documents in `game_module_path`
- Mem0 memory (`mem_collection`): short-term episodic memory per user session
- Both stored under `chroma_path` (default `.data/chroma/`)

### Memory

Mem0 uses ChromaDB (local) by default. Set `MEM0_API_KEY` to switch to Mem0 Cloud. Set `[memory] enabled = false` to bypass Mem0 entirely (falls back to LlamaIndex in-process chat store).

### Async pane updates

After each user→agent exchange, `BackgroundPaneUpdateManager` (`async_panes/pane_update_manager.py`) schedules a non-blocking history summary task. Key behaviors:
- At most one task per pane ("history", "scene") runs at a time; scheduling cancels any prior task.
- A generation counter guards against stale results overwriting newer state.
- Pane update coroutines must re-raise `asyncio.CancelledError` and defer all UI mutations to the end.
- SSE status phases emitted to play UI: `evaluating → summarizing → updated/unchanged/cancelled/error`.

### Optional tracing (Arize Phoenix)

Set `[tracing] enabled = true` in `config.toml` and start Phoenix locally (no Docker):
```bash
uv run phoenix serve   # runs at http://localhost:6006 and OTEL at :4317
```

### File storage

`LocalStorageClient` (`src/utils.py`) stores Chainlit file uploads under `.chainlit/files/`. No MinIO or S3 required.

### Adding a new tool

1. Implement a function (sync or async); accept `Context` as first arg if it needs Chainlit context.
2. Wrap: `FunctionTool.from_defaults(fn, fn_schema=YourPydanticModel)`.
3. Add to `self._tools` in `AgentContextAwareToolRetriever.__init__` (`src/agentic_tools/__init__.py`).
4. To reply to the user's message from inside a tool, read `user_message_id` and `user_message_thread_id` from `ctx.store`.

Reference examples: stateless → `roll_a_dice`; context + UI → `roll_a_skill`; RAG → `ToolForConsultingTheModule`.

### README files

`README.md` is the English version; `README.zh-TW.md` is the Traditional Chinese version. **Both files must be updated together** — any change to one must be reflected in the other.

### Adding a new async pane

```python
gen = manager.advance_generation()  # already called once per message
manager.schedule("my_pane", gen, lambda: update_my_pane(...), timeout=45.0, debounce=0.15)
```
