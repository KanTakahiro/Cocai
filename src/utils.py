import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

import chainlit.data as cl_data
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.data.storage_clients.base import BaseStorageClient
from chainlit.logger import logger

# If Python's builtin readline module is previously loaded, elaborate line editing and history features will be available.
# https://rich.readthedocs.io/en/stable/console.html#input
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install
from sqlalchemy import create_engine, text

# ---- Environment flags -------------------------------------------------------

TRUTHY_STRINGS = {"1", "true", "yes", "y", "on", "t"}
FALSY_STRINGS = {"0", "false", "no", "n", "off", "f"}


class OpenAICompatibleEmbedding(BaseEmbedding):
    """
    OpenAI-compatible embedding that accepts any model name without enum validation.

    Use instead of OpenAIEmbedding when the model is not an official OpenAI model
    (e.g. models served via OpenRouter, Together AI, or local vLLM).
    """

    _async_client: Any = PrivateAttr()
    _sync_client: Any = PrivateAttr()

    def __init__(self, model: str, api_base: str, api_key: str, embed_batch_size: int = 10, **kwargs):
        super().__init__(model_name=model, embed_batch_size=embed_batch_size, **kwargs)
        from openai import AsyncOpenAI, OpenAI
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=api_base)
        self._sync_client = OpenAI(api_key=api_key, base_url=api_base)

    @classmethod
    def class_name(cls) -> str:
        return "OpenAICompatibleEmbedding"

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._sync_client.embeddings.create(
            model=self.model_name, input=[query]
        ).data[0].embedding

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._sync_client.embeddings.create(
            model=self.model_name, input=[text]
        ).data[0].embedding

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        response = self._sync_client.embeddings.create(model=self.model_name, input=texts)
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        response = await self._async_client.embeddings.create(
            model=self.model_name, input=[query]
        )
        return response.data[0].embedding

    async def _aget_text_embedding(self, text: str) -> List[float]:
        response = await self._async_client.embeddings.create(
            model=self.model_name, input=[text]
        )
        return response.data[0].embedding

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        response = await self._async_client.embeddings.create(model=self.model_name, input=texts)
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


class LocalStorageClient(BaseStorageClient):
    """
    Simple local-filesystem storage client for Chainlit file uploads.

    Files are stored under `storage_path` and served via the `/files/` route
    that Chainlit or FastAPI can expose.  No external services required.
    """

    def __init__(self, storage_path: str = ".chainlit/files"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageClient initialised at %s", self.storage_path)

    async def upload_file(
        self,
        object_key: str,
        data: Union[bytes, str],
        mime: str = "application/octet-stream",
        overwrite: bool = True,
        content_disposition: str | None = None,
    ) -> Dict[str, Any]:
        try:
            dest = self.storage_path / object_key
            dest.parent.mkdir(parents=True, exist_ok=True)
            mode = "wb" if isinstance(data, bytes) else "w"
            with open(dest, mode) as f:
                f.write(data)
            return {"object_key": object_key, "url": f"/files/{object_key}"}
        except Exception as e:
            logger.warning("LocalStorageClient upload_file error: %s", e)
            return {}

    async def delete_file(self, object_key: str) -> bool:
        try:
            dest = self.storage_path / object_key
            if dest.exists():
                dest.unlink()
            return True
        except Exception as e:
            logger.warning("LocalStorageClient delete_file error: %s", e)
            return False

    async def close(self) -> None:
        pass

    async def get_read_url(self, object_key: str) -> str:
        return f"/files/{object_key}"


def set_up_data_layer(sqlite_file_path: str = ".chainlit/data.db"):
    engine = create_engine(f"sqlite:///{sqlite_file_path}")
    with open(".chainlit/schema.sql") as f:
        schema_sql = f.read()
    sql_statements = schema_sql.strip().split(";")
    with engine.connect() as conn:
        for statement in sql_statements:
            if statement.strip():
                conn.execute(text(statement))

    storage_client = LocalStorageClient(storage_path=".chainlit/files")
    cl_data._data_layer = SQLAlchemyDataLayer(
        conninfo=f"sqlite+aiosqlite:///{sqlite_file_path}",
        storage_provider=storage_client,
    )


def set_up_logging(should_use_rich: bool = True):
    console = Console()
    # https://rich.readthedocs.io/en/latest/logging.html#handle-exceptions
    logging.basicConfig(
        # This can get really verbose if set to `logging.DEBUG`.
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            (
                RichHandler(rich_tracebacks=True, console=console)
                if should_use_rich
                else logging.StreamHandler()
            )
        ],
        # This function does nothing if the root logger already has handlers configured,
        # unless the keyword argument force is set to True.
        # https://docs.python.org/3/library/logging.html#logging.basicConfig
        force=True,
    )
    logger = logging.getLogger(__name__)

    if should_use_rich:
        # https://rich.readthedocs.io/en/stable/traceback.html#traceback-handler
        logger.debug("Installing rich traceback handler.")
        old_traceback_handler = install(show_locals=True, console=console)
        logger.debug(
            f"The global traceback handler has been swapped from {old_traceback_handler} to {sys.excepthook}."
        )
