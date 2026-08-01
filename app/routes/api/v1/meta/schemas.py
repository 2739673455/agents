"""元数据管理接口模型"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableInfoRequest(BaseModel):
    """表元数据写入请求"""

    name: str
    role: str
    primary_key_columns: list[str] = Field(default_factory=list)
    description: str


class ColumnInfoRequest(BaseModel):
    """字段元数据写入请求"""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    examples: list[Any] = Field(default_factory=list)
    description: str
    alias: list[str] = Field(default_factory=list)
    index_values: bool
    reference_column_id: str | None = None
    table_id: str


class MetricInfoRequest(BaseModel):
    """指标元数据写入请求"""

    name: str
    description: str
    relevant_columns: list[str] = Field(default_factory=list)
    alias: list[str] = Field(default_factory=list)


class ColumnIndexSyncRequest(BaseModel):
    """批量字段索引同步请求"""

    column_ids: list[str] = Field(min_length=1)


class IndexSyncResponse(BaseModel):
    """单项索引同步响应"""

    resource_id: str
    indexed_count: int


class BatchIndexSyncResponse(BaseModel):
    """批量索引同步响应"""

    results: list[IndexSyncResponse]


class TableSyncResponse(BaseModel):
    """整表索引同步响应"""

    table_id: str
    column_count: int
    column_vector_count: int
    value_column_count: int
    value_count: int


class ResourceImportChanges(BaseModel):
    """单类元数据导入变更"""

    created_count: int
    updated_count: int
    deleted_count: int
    created_ids: list[str]
    updated_ids: list[str]
    deleted_ids: list[str]


class MetaImportResponse(BaseModel):
    """元数据导入响应"""

    mode: str
    dry_run: bool
    tables: ResourceImportChanges
    columns: ResourceImportChanges
    metrics: ResourceImportChanges
    index_sync_required: bool
