from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ColumnInfo(Base):
    __tablename__ = "column_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="列编号")
    name: Mapped[Optional[str]] = mapped_column(String(256), comment="列名称")
    type: Mapped[Optional[str]] = mapped_column(String(256), comment="数据类型")
    role: Mapped[Optional[str]] = mapped_column(
        String(256), comment="列类型(primary_key,foreign_key,measure,dimension)"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, comment="列描述")
    examples: Mapped[Optional[dict]] = mapped_column(JSON, comment="数据示例")
    alias: Mapped[Optional[dict]] = mapped_column(JSON, comment="列别名")
    table_id: Mapped[Optional[str]] = mapped_column(String(256), comment="所属表编号")


class ColumnMetric(Base):
    __tablename__ = "column_metric"

    metric_id: Mapped[str] = mapped_column(
        String(256), primary_key=True, comment="指标编号"
    )
    column_id: Mapped[str] = mapped_column(
        String(256), primary_key=True, comment="列编号"
    )


class MetricInfo(Base):
    __tablename__ = "metric_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="指标编码")
    name: Mapped[Optional[str]] = mapped_column(String(256), comment="指标名称")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="指标描述")
    relevant_columns: Mapped[Optional[dict]] = mapped_column(JSON, comment="关联的列")
    alias: Mapped[Optional[dict]] = mapped_column(JSON, comment="指标别名")


class TableInfo(Base):
    __tablename__ = "table_info"

    id: Mapped[str] = mapped_column(String(256), primary_key=True, comment="表编号")
    name: Mapped[Optional[str]] = mapped_column(String(256), comment="表名称")
    role: Mapped[Optional[str]] = mapped_column(String(256), comment="表类型(fact/dim)")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="表描述")
