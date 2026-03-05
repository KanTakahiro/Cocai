## CoCai – AI agent working notes

Use this as the minimal, high-signal guide to be productive in this repo.

### Big picture

- Web app: `fastapi` app in `server.py` mounts Chainlit at `/chat` with `mount_chainlit(app, target="main.py", path="/chat")`.
- Chat brain: `main.py` wires a LlamaIndex `FunctionAgent` with tools and memory, and streams tokens to Chainlit.
- Memory: Mem0 short-term memory via ChromaDB (local, in-process). Fallback to LlamaIndex `Memory` if disabled or init fails.  Cloud Mem0 available via `MEM0_API_KEY`.
- Tracing: Optional Arize Phoenix via OpenTelemetry, enabled in `config.toml` (`[tracing] enabled = true`).
- Extras: Visual dice rolls via `/roll_dice` (Jinja template in `dice/`).

Data flow:

- User → Chainlit UI (/chat) → FunctionAgent → tools (`agentic_tools/`) → external APIs → responses stream back over Chainlit.

### Run/dev workflow

- `just serve` (uvicorn --reload at :8000). No Docker or Ollama required.
- URLs: Chat `http://localhost:8000/chat`, Play UI `http://localhost:8000/play`.
- Config: fill `config.toml` (endpoints, model names) and `.env` (API keys). See `.env.example`.
- Python deps via `uv`; no explicit venv creation needed. Format with `just format` (ruff).

### Key conventions and patterns

- Config: `AppConfig.from_config()` reads `config.toml` + `.env` (API keys). Called per chat session inside `@cl.on_chat_start`, not at module scope.
- LLM: `OpenAILike(model=..., api_base=..., api_key=...)` — works with any OpenAI-compatible endpoint (OpenAI, Together AI, Groq, vLLM, …).
- Embedding: `OpenAIEmbedding(model=..., api_base=..., api_key=...)` — same flexibility. Dims configured in `config.toml` (`[embedding] dims`).
- Vector store: ChromaDB `PersistentClient(path=chroma_path)` for both RAG (`rag_collection`) and Mem0 (`mem_collection`). No separate server process.
- File storage: `LocalStorageClient` stores Chainlit uploads under `.chainlit/files/`. No MinIO.
- System prompt: `prompts/system_prompt.md` + auto-generated module summary → final `system_prompt`.
- Module RAG: `ToolForConsultingTheModule` builds/loads ChromaDB collection from `game_module.path` (config.toml). Reuse controlled by `game_module.reuse_index`.
- Dice visual: `tools.roll_a_skill(ctx, ...)` saves `user_message_id`/`thread_id` in `Context` state (set in `main.handle_message_from_user`) and posts a `cl.Pdf` pointing to `/roll_dice?d10=...`.

### Adding a new tool (preferred pattern)

1. Implement a function (sync or async). If it needs Chainlit context, accept `Context` as first arg.
2. Define a pydantic model for inputs when helpful; then wrap with `FunctionTool.from_defaults(fn, fn_schema=YourModel)`.
3. Add to `self._tools` in `AgentContextAwareToolRetriever.__init__` in `src/agentic_tools/__init__.py`.
4. If the tool renders Chainlit elements replying to a user message, read `user_message_id` and `user_message_thread_id` from `ctx.store`.

Reference examples:
- Simple stateless tool: `roll_a_dice`.
- Contextful + UI element: `roll_a_skill(ctx, ...)`.
- RAG over module docs: `ToolForConsultingTheModule` (ChromaDB + SimpleDirectoryReader).

### Environment variables you will actually use

- Models: `LLM_API_KEY`, `EMBED_API_KEY`.
- Memory: `MEM0_API_KEY` (optional, for cloud Mem0).
- Tools: `TAVILY_API_KEY` (optional internet search).
- Chainlit: `CHAINLIT_AUTH_SECRET`.

### Gotchas and tips

- ChromaDB data lives in `.data/chroma/` (git-ignored). Delete it to force a fresh index rebuild.
- `env_flag()` in `config.py` is a shared boolean parser for env vars — used in tests.
- `config.toml` is committed; `.env` is git-ignored. Never put secrets in `config.toml`.

### Where to look

- Core runtime: `main.py` (agent, tools wiring, memory, callbacks), `server.py` (FastAPI + Chainlit mount).
- Tools: `src/agentic_tools/` (dice/skills, RAG module, character creation via `cochar`, clue recording).
- Config: `config.toml`, `src/config.py`, `.env.example`.
- Prompts: `prompts/`.
