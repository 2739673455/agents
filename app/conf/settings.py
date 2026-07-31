from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import dotenv
from omegaconf import OmegaConf
from pydantic import BaseModel, Field

# 路径常量
CURRENT_DIR = Path(__file__).parent  # core
ROOT_DIR = CURRENT_DIR.parent.parent  # 项目根目录
CONFIG_DIR = ROOT_DIR / "configs"  # 配置文件目录


# 数据库
class MySQLCfg(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str


class DBCfg(BaseModel):
    driver: str
    configs: dict[str, MySQLCfg]


# Redis 配置
class RedisCfg(BaseModel):
    host: str
    port: int
    password: str
    db: int


# 日志
class LogCfg(BaseModel):
    level: str
    max_file_size: str


# MCP 工具配置
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


# 模型配置
class ModelCfg(BaseModel):
    model: str
    base_url: str
    api_key: str
    params: dict
    profile: dict


class LMConfigCfg(BaseModel):
    active: str
    models: dict[str, ModelCfg]


class DataAgentCfg(BaseModel):
    base_url: str
    query: str


class Cfg(BaseModel):
    db: DBCfg
    redis: RedisCfg
    log: LogCfg
    mcp: dict[str, MCPCfg]
    lm_config: LMConfigCfg
    data_agent: DataAgentCfg
    cors_origins: list[str]
    port: int


def _load_config() -> Cfg:
    """从 .env 和 config.yml 加载配置"""
    dotenv.load_dotenv(CONFIG_DIR / ".env")
    raw_cfg = OmegaConf.to_container(
        OmegaConf.load(CONFIG_DIR / "config.yml"), resolve=True
    )
    return Cfg.model_validate(raw_cfg)


def reload_config() -> None:
    """热更新：重新加载 .env 和 config.yml 到当前进程"""
    global cfg
    cfg = _load_config()


cfg = _load_config()
