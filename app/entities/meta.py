"""元数据实体"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """元数据 ORM 基类"""


class TableInfo(Base):
    """表信息"""

    __tablename__ = "table_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="表编号")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="表名称")
    role: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="表类型(fact/dim)"
    )
    primary_key_columns: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, comment="主键字段"
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="表描述")


class ColumnInfo(Base):
    """字段信息"""

    __tablename__ = "column_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="列编号")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="列名称")
    type: Mapped[str] = mapped_column(String(256), nullable=False, comment="数据类型")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="列描述")
    examples: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, comment="数据示例"
    )
    alias: Mapped[list[str]] = mapped_column(JSON, nullable=False, comment="列别名")
    index_values: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="是否索引字段值",
    )
    reference_column_id: Mapped[str | None] = mapped_column(
        String(256), comment="引用字段编号"
    )
    table_id: Mapped[str] = mapped_column(
        String(256),
        ForeignKey("table_info.id"),
        nullable=False,
        comment="所属表编号",
    )


@dataclass
class ValueInfo:
    """字段取值信息"""

    id: str
    value: str
    column_id: str


class MetricInfo(Base):
    """指标信息"""

    __tablename__ = "metric_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="指标编码")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="指标名称")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="指标描述")
    relevant_columns: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, comment="关联的列"
    )
    alias: Mapped[list[str]] = mapped_column(JSON, nullable=False, comment="指标别名")


class ColumnMetric(Base):
    """字段与指标关联"""

    __tablename__ = "column_metric"

    metric_id: Mapped[str] = mapped_column(
        String(256),
        ForeignKey("metric_info.id"),
        primary_key=True,
        comment="指标编号",
    )
    column_id: Mapped[str] = mapped_column(
        String(256),
        ForeignKey("column_info.id"),
        primary_key=True,
        comment="列编号",
    )
