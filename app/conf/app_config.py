from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import dotenv
from omegaconf import OmegaConf
from pydantic import BaseModel, Field

# 路径常量
ROOT_DIR = Path(__file__).parents[2]
CONFIG_DIR = ROOT_DIR / "conf"
CONFIG_FILE = CONFIG_DIR / "app_config.yaml"


class LogCfg(BaseModel):
    level: str
    rotation: str


class DBConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str


class RedisCfg(BaseModel):
    host: str
    port: int
    password: str
    db: int


class QdrantConfig(BaseModel):
    host: str
    port: int
    embedding_size: int


class ESConfig(BaseModel):
    host: str
    port: int
    index_name: str


class EmbeddingConfig(BaseModel):
    base_url: str
    api_key: str | None
    model: str
    timeout: float


class SSEMCPCfg(BaseModel):
    transport: Literal["sse"]
    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None
    sse_read_timeout: float | None = None
    session_kwargs: dict[str, Any] | None = None


class StdioMCPCfg(BaseModel):
    transport: Literal["stdio"]
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    encoding: str | None = None
    encoding_error_handler: Literal["strict", "ignore", "replace"] | None = None
    session_kwargs: dict[str, Any] | None = None


class WebsocketMCPCfg(BaseModel):
    transport: Literal["websocket"]
    url: str
    session_kwargs: dict[str, Any] | None = None


class StreamableHttpMCPCfg(BaseModel):
    transport: Literal["streamable_http"]
    url: str
    headers: dict[str, str] | None = None
    timeout: timedelta | None = None
    sse_read_timeout: timedelta | None = None
    terminate_on_close: bool | None = None
    session_kwargs: dict[str, Any] | None = None


MCPCfg = Annotated[
    SSEMCPCfg | StdioMCPCfg | WebsocketMCPCfg | StreamableHttpMCPCfg,
    Field(discriminator="transport"),
]


class ModelCfg(BaseModel):
    model: str
    base_url: str
    api_key: str
    params: dict[str, Any]
    profile: dict[str, Any]


class LMConfigCfg(BaseModel):
    active: str
    models: dict[str, ModelCfg]


class Cfg(BaseModel):
    log: LogCfg
    db_source: DBConfig
    db_meta: DBConfig
    redis: RedisCfg
    qdrant: QdrantConfig
    elasticsearch: ESConfig
    embedding: EmbeddingConfig
    lm_config: LMConfigCfg
    mcp: dict[str, MCPCfg]
    cors_origins: list[str]
    port: int


def _load_config() -> Cfg:
    """从 .env 和 app_config.yaml 加载配置"""
    dotenv.load_dotenv(CONFIG_DIR / ".env")
    loaded_cfg = OmegaConf.load(CONFIG_FILE)
    primitive_cfg = OmegaConf.to_container(loaded_cfg, resolve=True)
    return Cfg.model_validate(cast(dict[str, Any], primitive_cfg))


def reload_config() -> None:
    """重新加载配置"""
    global cfg
    cfg = _load_config()


cfg = _load_config()
