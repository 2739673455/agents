"""元数据导入导出配置模型"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TableRole = Literal["fact", "dim"]


class MetaConfigModel(BaseModel):
    """元数据配置模型基类"""

    model_config = ConfigDict(extra="forbid")


class ColumnConfig(MetaConfigModel):
    """字段元数据配置"""

    name: str
    description: str
    alias: list[str] = Field(default_factory=list)
    index_values: bool
    reference_t_name: str | None = None
    reference_c_name: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "ColumnConfig":
        """校验字段引用必须同时包含表名和字段名"""
        if (self.reference_t_name is None) != (self.reference_c_name is None):
            raise ValueError(
                "Reference table name and column name must be provided together"
            )
        return self


class TableConfig(MetaConfigModel):
    """表元数据配置"""

    name: str
    role: TableRole
    primary_key_columns: list[str] = Field(default_factory=list)
    description: str
    columns: list[ColumnConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_primary_key_columns(self) -> "TableConfig":
        """校验表的主键字段"""
        if len(self.primary_key_columns) != len(set(self.primary_key_columns)):
            raise ValueError("Primary key columns cannot contain duplicates")
        column_names = {column.name for column in self.columns}
        missing_columns = set(self.primary_key_columns) - column_names
        if missing_columns:
            raise ValueError(
                "Primary key columns are missing from table columns: "
                f"{', '.join(sorted(missing_columns))}"
            )
        return self


class ColumnReferenceConfig(MetaConfigModel):
    """字段联合主键引用"""

    t_name: str
    c_name: str


class MetricConfig(MetaConfigModel):
    """指标元数据配置"""

    name: str
    description: str
    relevant_columns: list[ColumnReferenceConfig] = Field(default_factory=list)
    alias: list[str] = Field(default_factory=list)


class MetaConfig(MetaConfigModel):
    """元数据导入导出配置"""

    version: Literal[1] = 1
    tables: list[TableConfig] = Field(default_factory=list)
    metrics: list[MetricConfig] = Field(default_factory=list)
