from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf
from pydantic import BaseModel


class ColumnConfig(BaseModel):
    name: str
    role: str
    description: str
    alias: list[str]
    sync: bool


class TableConfig(BaseModel):
    name: str
    role: str
    description: str
    columns: list[ColumnConfig]


class MetricConfig(BaseModel):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class MetaConfig(BaseModel):
    tables: list[TableConfig] | None = None
    metrics: list[MetricConfig] | None = None


def load_config(config_file: Path) -> MetaConfig:
    loaded_cfg = OmegaConf.load(config_file)
    primitive_cfg = OmegaConf.to_container(loaded_cfg, resolve=True)
    return MetaConfig.model_validate(cast(dict[str, Any], primitive_cfg))
