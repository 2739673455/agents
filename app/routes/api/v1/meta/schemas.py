"""元数据管理接口模型"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TableInfoRequest(BaseModel):
    """表元数据写入请求"""

    role: str
    primary_key_columns: list[str] = Field(default_factory=list)
    description: str


class ColumnInfoRequest(BaseModel):
    """字段元数据写入请求"""

    model_config = ConfigDict(extra="forbid")

    type: str
    examples: list[Any] = Field(default_factory=list)
    description: str
    alias: list[str] = Field(default_factory=list)
    index_values: bool
    reference_t_name: str | None = None
    reference_c_name: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "ColumnInfoRequest":
        """校验字段引用必须同时包含表名和字段名"""
        if (self.reference_t_name is None) != (self.reference_c_name is None):
            raise ValueError(
                "Reference table name and column name must be provided together"
            )
        return self


class ColumnReference(BaseModel):
    """字段联合主键引用"""

    t_name: str
    c_name: str


class MetricInfoRequest(BaseModel):
    """指标元数据写入请求"""

    description: str
    relevant_columns: list[ColumnReference] = Field(default_factory=list)
    alias: list[str] = Field(default_factory=list)


class ColumnIndexSyncRequest(BaseModel):
    """批量字段索引同步请求"""

    columns: list[ColumnReference] = Field(min_length=1)


class MetricIndexSyncRequest(BaseModel):
    """批量指标索引同步请求"""

    metrics: list[str] = Field(min_length=1)


class ColumnIndexSyncResponse(BaseModel):
    """字段索引同步响应"""

    t_name: str
    c_name: str
    indexed_count: int


class MetricIndexSyncResponse(BaseModel):
    """指标索引同步响应"""

    metric_name: str
    indexed_count: int


class BatchIndexSyncResponse(BaseModel):
    """批量索引同步响应"""

    results: list[ColumnIndexSyncResponse]


class BatchMetricIndexSyncResponse(BaseModel):
    """批量指标索引同步响应"""

    results: list[MetricIndexSyncResponse]


class TableSyncResponse(BaseModel):
    """整表索引同步响应"""

    t_name: str
    column_count: int
    column_vector_count: int
    value_column_count: int
    value_count: int


class ResourceImportChanges(BaseModel):
    """单类元数据导入变更"""

    created_count: int
    updated_count: int
    deleted_count: int
    created_keys: list[str]
    updated_keys: list[str]
    deleted_keys: list[str]


class MetaImportResponse(BaseModel):
    """元数据导入响应"""

    mode: str
    dry_run: bool
    tables: ResourceImportChanges
    columns: ResourceImportChanges
    metrics: ResourceImportChanges
