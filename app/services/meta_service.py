"""元数据管理服务"""

from typing import cast

from app.conf.meta_config import (
    ColumnConfig,
    MetaConfig,
    MetricConfig,
    TableConfig,
    TableRole,
)
from app.entities.meta import ColumnInfo, MetricInfo, TableInfo
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
            reference_column_id = column_info.reference_column_id
            if reference_column_id:
                if reference_column_id == column_info.id:
                    raise meta_error.InvalidMetadataError(
                        detail=f"Column cannot reference itself: {column_info.id}"
                    )
                try:
                    await self._meta_repo.get_column_info_by_id(reference_column_id)
                except meta_error.MetadataNotFoundError as exc:
                    raise meta_error.InvalidMetadataError(
                        detail=f"Reference column not found: {reference_column_id}"
                    ) from exc
            await self._meta_repo.upsert_column_info(column_info)

    async def upsert_metric_info(self, metric_info: MetricInfo) -> None:
        """新增或更新指标元数据"""
        async with self._meta_repo.transaction():
            await self._meta_repo.upsert_metric_info(metric_info)

    async def export_metadata(self) -> MetaConfig:
        """导出可重新导入的元数据配置"""
        table_infos = await self._meta_repo.list_table_infos()
        column_infos = await self._meta_repo.list_column_infos()
        metric_infos = await self._meta_repo.list_metric_infos()

        columns_by_table: dict[str, list[ColumnInfo]] = {
            table_info.id: [] for table_info in table_infos
        }
        orphan_column_ids: list[str] = []
        for column_info in column_infos:
            if column_info.table_id not in columns_by_table:
                orphan_column_ids.append(column_info.id)
                continue
            columns_by_table[column_info.table_id].append(column_info)
        if orphan_column_ids:
            raise meta_error.MetadataConflictError(
                detail=(
                    "Columns reference missing tables: "
                    f"{', '.join(sorted(orphan_column_ids))}"
                )
            )

        return MetaConfig(
            version=1,
            tables=[
                TableConfig(
                    id=table_info.id,
                    name=table_info.name,
                    role=cast(TableRole, table_info.role),
                    primary_key_columns=table_info.primary_key_columns,
                    description=table_info.description,
                    columns=[
                        ColumnConfig(
                            id=column_info.id,
                            name=column_info.name,
                            description=column_info.description,
                            alias=column_info.alias,
                            index_values=column_info.index_values,
                            reference_column_id=column_info.reference_column_id,
                        )
                        for column_info in sorted(
                            columns_by_table[table_info.id],
                            key=lambda item: item.id,
                        )
                    ],
                )
                for table_info in table_infos
            ],
            metrics=[
                MetricConfig(
                    id=metric_info.id,
                    name=metric_info.name,
                    description=metric_info.description,
                    relevant_columns=metric_info.relevant_columns,
                    alias=metric_info.alias,
                )
                for metric_info in metric_infos
            ],
        )
