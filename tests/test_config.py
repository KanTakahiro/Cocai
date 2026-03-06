from pathlib import Path

from config import AppConfig, env_flag


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_config_defaults():
    cfg = AppConfig()
    assert cfg.llm_api_base == "https://api.openai.com/v1"
    assert cfg.llm_model == "gpt-4o"
    assert cfg.embed_model == "text-embedding-3-small"
    assert cfg.embed_dims == 1536
    assert cfg.chroma_path == ".data/chroma"
    assert cfg.rag_collection == "game_module"
    assert cfg.mem_collection == "cocai"
    assert cfg.memory_enabled is True
    assert cfg.tracing_enabled is False
    assert cfg.game_module_path.endswith("Clean-Up-Aisle-Four")
    assert cfg.should_preread_game_module is False
    assert cfg.enable_auto_history_update is True
    assert cfg.enable_auto_scene_update is False


def test_config_from_dict_overrides():
    cfg = AppConfig.from_dict(
        {
            "llm_model": "gpt-4-turbo",
            "embed_dims": 3072,
            "memory_enabled": False,
        }
    )
    assert cfg.llm_model == "gpt-4-turbo"
    assert cfg.embed_dims == 3072
    assert cfg.memory_enabled is False
    assert cfg.tracing_enabled is False  # unspecified -> default


# ---------------------------------------------------------------------------
# from_config -- reads a real TOML file
# ---------------------------------------------------------------------------


def test_from_config_reads_toml(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        """
[llm]
api_base = "https://api.together.xyz/v1"
model = "meta-llama/Llama-3-70b-chat-hf"

[embedding]
api_base = "https://api.together.xyz/v1"
model = "togethercomputer/m2-bert-80M-8k-retrieval"
dims = 768

[vector_store]
path = "/tmp/chroma"
rag_collection = "my_module"
mem_collection = "my_mem"

[memory]
enabled = false

[tracing]
enabled = true
endpoint = "http://localhost:4317"

[game_module]
path = "game_modules/Other"
preread = true
reuse_index = false

[auto_update]
history = false
scene = false
"""
    )
    env = {"LLM_API_KEY": "sk-llm", "EMBED_API_KEY": "sk-emb"}
    cfg = AppConfig.from_config(toml_path=toml, env=env)

    assert cfg.llm_api_base == "https://api.together.xyz/v1"
    assert cfg.llm_model == "meta-llama/Llama-3-70b-chat-hf"
    assert cfg.llm_api_key == "sk-llm"
    assert cfg.embed_dims == 768
    assert cfg.embed_api_key == "sk-emb"
    assert cfg.chroma_path == "/tmp/chroma"
    assert cfg.rag_collection == "my_module"
    assert cfg.mem_collection == "my_mem"
    assert cfg.memory_enabled is False
    assert cfg.tracing_enabled is True
    assert cfg.tracing_endpoint == "http://localhost:4317"
    assert cfg.game_module_path == "game_modules/Other"
    assert cfg.should_preread_game_module is True
    assert cfg.should_reuse_existing_index is False
    assert cfg.enable_auto_history_update is False


def test_from_config_embed_key_falls_back_to_llm_key(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("")  # empty -> all defaults
    env = {"LLM_API_KEY": "sk-shared"}
    cfg = AppConfig.from_config(toml_path=toml, env=env)
    assert cfg.llm_api_key == "sk-shared"
    assert cfg.embed_api_key == "sk-shared"


def test_from_config_missing_toml_uses_defaults(tmp_path):
    cfg = AppConfig.from_config(toml_path=tmp_path / "nonexistent.toml", env={})
    assert cfg.llm_model == "gpt-4o"
    assert cfg.embed_dims == 1536


def test_from_config_mem0_cloud_key(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("")
    env = {"LLM_API_KEY": "sk-x", "MEM0_API_KEY": "m0-cloud"}
    cfg = AppConfig.from_config(toml_path=toml, env=env)
    assert cfg.mem0_api_key == "m0-cloud"


def test_config_defaults_image_and_server():
    cfg = AppConfig()
    assert cfg.image_gen_enabled is False
    assert cfg.image_api_base == ""
    assert cfg.image_model == "bytedance-seed/seedream-4.5"
    assert cfg.server_base_url == "http://127.0.0.1:8000"


def test_from_config_image_generation_section(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        """
[image_generation]
enabled = true
api_base = "https://openrouter.ai/api/v1"
model = "openai/gpt-image-1"
"""
    )
    env = {"LLM_API_KEY": "sk-llm", "IMAGE_API_KEY": "sk-img"}
    cfg = AppConfig.from_config(toml_path=toml, env=env)
    assert cfg.image_gen_enabled is True
    assert cfg.image_api_base == "https://openrouter.ai/api/v1"
    assert cfg.image_model == "openai/gpt-image-1"
    assert cfg.image_api_key == "sk-img"


def test_from_config_image_key_falls_back_to_llm_key(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text("")
    env = {"LLM_API_KEY": "sk-shared"}
    cfg = AppConfig.from_config(toml_path=toml, env=env)
    assert cfg.image_api_key == "sk-shared"


def test_from_config_server_base_url(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(
        """
[server]
base_url = "https://example.com"
"""
    )
    cfg = AppConfig.from_config(toml_path=toml, env={})
    assert cfg.server_base_url == "https://example.com"


# ---------------------------------------------------------------------------
# env_flag helper
# ---------------------------------------------------------------------------


def test_env_bool_helper_true(monkeypatch):
    monkeypatch.setenv("SOME_FLAG", "1")
    assert env_flag("SOME_FLAG") is True
    monkeypatch.setenv("SOME_FLAG", "true")
    assert env_flag("SOME_FLAG") is True
    monkeypatch.setenv("SOME_FLAG", "on")
    assert env_flag("SOME_FLAG") is True


def test_env_bool_helper_false(monkeypatch):
    monkeypatch.setenv("SOME_FLAG", "0")
    assert env_flag("SOME_FLAG") is False
    monkeypatch.setenv("SOME_FLAG", "false")
    assert env_flag("SOME_FLAG") is False
    monkeypatch.setenv("SOME_FLAG", "off")
    assert env_flag("SOME_FLAG") is False
