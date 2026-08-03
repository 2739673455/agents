"""元数据管理服务"""

from typing import cast

from app.conf.meta_config import (
    ColumnConfig,
    ColumnReferenceConfig,
    MetaConfig,
    MetricConfig,
    TableConfig,
    TableRole,
)
from app.entities.meta import ColumnInfo, ColumnReference, MetricInfo, TableInfo
from app.errors import meta_error
from app.repositories.meta_mysql_repo import MetaMySQLRepo


class MetaService:
    """管理表、字段和指标元数据"""

    def __init__(self, meta_repo: MetaMySQLRepo) -> None:
        """初始化元数据管理服务"""
        self._meta_repo = meta_repo

    async def upsert_table_info(self, table_info: TableInfo) -> None:
        """新增或更新表元数据"""
        async with self._meta_repo.transaction():
            await self._meta_repo.upsert_table_info(table_info)

    async def upsert_column_info(self, column_info: ColumnInfo) -> None:
        """新增或更新字段元数据"""
        async with self._meta_repo.transaction():
            try:
                await self._meta_repo.get_table_info(column_info.t_name)
            except meta_error.MetadataNotFoundError as exc:
                raise meta_error.InvalidMetadataError(
                    detail=(
                        "Table info not found for column: "
                        f"{column_info.t_name}.{column_info.name}"
                    )
                ) from exc

            reference_t_name = column_info.reference_t_name
            reference_c_name = column_info.reference_c_name
            if (reference_t_name is None) != (reference_c_name is None):
                raise meta_error.InvalidMetadataError(
                    detail=(
                        "Reference table name and column name must be provided together"
                    )
                )
            if reference_t_name and reference_c_name:
                if (reference_t_name, reference_c_name) == (
                    column_info.t_name,
                    column_info.name,
                ):
                    raise meta_error.InvalidMetadataError(
                        detail=(
                            "Column cannot reference itself: "
                            f"{column_info.t_name}.{column_info.name}"
                        )
                    )
                try:
                    await self._meta_repo.get_column_info(
                        reference_t_name,
                        reference_c_name,
                    )
                except meta_error.MetadataNotFoundError as exc:
                    raise meta_error.InvalidMetadataError(
                        detail=(
                            "Reference column not found: "
                            f"{reference_t_name}.{reference_c_name}"
                        )
                    ) from exc
            await self._meta_repo.upsert_column_info(column_info)

    async def upsert_metric_info(self, metric_info: MetricInfo) -> None:
        """新增或更新指标元数据"""
        async with self._meta_repo.transaction():
            relevant_column_keys = sorted(
                dict.fromkeys(
                    (
                        reference["t_name"],
                        reference["c_name"],
                    )
                    for reference in metric_info.relevant_columns
                )
            )
            for t_name, c_name in relevant_column_keys:
                try:
                    await self._meta_repo.get_column_info(t_name, c_name)
                except meta_error.MetadataNotFoundError as exc:
                    raise meta_error.InvalidMetadataError(
                        detail=f"Relevant column not found: {t_name}.{c_name}"
                    ) from exc
            metric_info.relevant_columns = [
                ColumnReference(t_name=t_name, c_name=c_name)
                for t_name, c_name in relevant_column_keys
            ]
            await self._meta_repo.upsert_metric_info(metric_info)

    async def export_metadata(self) -> MetaConfig:
        """导出可重新导入的元数据配置"""
        table_infos = await self._meta_repo.list_table_infos()
        column_infos = await self._meta_repo.list_column_infos()
        metric_infos = await self._meta_repo.list_metric_infos()

        columns_by_table: dict[str, list[ColumnInfo]] = {
            table_info.name: [] for table_info in table_infos
        }
        for column_info in column_infos:
            columns_by_table[column_info.t_name].append(column_info)

        return MetaConfig(
            version=1,
            tables=[
                TableConfig(
                    name=table_info.name,
                    role=cast(TableRole, table_info.role),
                    description=table_info.description,
                    columns=[
                        ColumnConfig(
                            name=column_info.name,
                            description=column_info.description,
                            alias=column_info.alias,
                            index_values=column_info.index_values,
                            reference_t_name=column_info.reference_t_name,
                            reference_c_name=column_info.reference_c_name,
                        )
                        for column_info in sorted(
                            columns_by_table[table_info.name],
                            key=lambda item: item.name,
                        )
                    ],
                )
                for table_info in table_infos
            ],
            metrics=[
                MetricConfig(
                    name=metric_info.name,
                    description=metric_info.description,
                    relevant_columns=[
                        ColumnReferenceConfig(**reference)
                        for reference in metric_info.relevant_columns
                    ],
                    alias=metric_info.alias,
                )
                for metric_info in metric_infos
            ],
        )
