"""元数据批量导入服务"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.conf.meta_config import MetaConfig
from app.entities.meta import ColumnInfo, MetricInfo, TableInfo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo


class ImportMode(StrEnum):
    """元数据导入模式"""

    MERGE = "merge"
    REPLACE = "replace"


@dataclass(frozen=True)
class ResourceChanges:
    """单类元数据变更"""

    created_ids: list[str]
    updated_ids: list[str]
    deleted_ids: list[str]


@dataclass(frozen=True)
class MetaImportResult:
    """元数据导入结果"""

    mode: ImportMode
    dry_run: bool
    tables: ResourceChanges
    columns: ResourceChanges
    metrics: ResourceChanges

    @property
    def index_sync_required(self) -> bool:
        """判断导入后是否需要处理检索索引"""
        changes = (self.tables, self.columns, self.metrics)
        return any(
            change.created_ids or change.updated_ids or change.deleted_ids
            for change in changes
        )


class MetaImportService:
    """从配置批量导入元数据"""

    def __init__(self, meta_repo: MetaMySQLRepo, source_repo: SourceMySQLRepo) -> None:
        """初始化元数据批量导入服务"""
        self._meta_repo = meta_repo
        self._source_repo = source_repo

    async def import_metadata(
        self,
        meta_config: MetaConfig,
        mode: ImportMode,
        dry_run: bool,
    ) -> MetaImportResult:
        """校验并批量导入元数据"""
        if not meta_config.tables and not meta_config.metrics:
            raise ValueError("Metadata import document cannot be empty")

        async with self._meta_repo.transaction():
            existing_tables = {
                table_info.id: table_info
                for table_info in await self._meta_repo.list_table_infos()
            }
            existing_columns = {
                column_info.id: column_info
                for column_info in await self._meta_repo.list_column_infos()
            }
            existing_metrics = {
                metric_info.id: metric_info
                for metric_info in await self._meta_repo.list_metric_infos()
            }

            table_infos, column_infos, metric_infos = await self._build_metadata(
                meta_config
            )
            imported_tables = self._index_by_id(table_infos, "table")
            imported_columns = self._index_by_id(column_infos, "column")
            imported_metrics = self._index_by_id(metric_infos, "metric")

            available_column_ids = set(imported_columns)
            if mode is ImportMode.MERGE:
                available_column_ids.update(existing_columns)
            self._validate_column_references(column_infos, available_column_ids)
            self._validate_metric_columns(metric_infos, available_column_ids)

            table_changes = self._get_changes(
                self._table_snapshots(existing_tables),
                self._table_snapshots(imported_tables),
                mode,
            )
            column_changes = self._get_changes(
                self._column_snapshots(existing_columns),
                self._column_snapshots(imported_columns),
                mode,
            )
            metric_changes = self._get_changes(
                self._metric_snapshots(existing_metrics),
                self._metric_snapshots(imported_metrics),
                mode,
            )

            result = MetaImportResult(
                mode=mode,
                dry_run=dry_run,
                tables=table_changes,
                columns=column_changes,
                metrics=metric_changes,
            )
            if dry_run:
                return result

            if mode is ImportMode.REPLACE:
                await self._meta_repo.delete_metric_infos(metric_changes.deleted_ids)
                await self._meta_repo.delete_column_infos(column_changes.deleted_ids)
                await self._meta_repo.delete_table_infos(table_changes.deleted_ids)

            for table_id in table_changes.created_ids + table_changes.updated_ids:
                await self._meta_repo.upsert_table_info(imported_tables[table_id])
            for column_id in column_changes.created_ids + column_changes.updated_ids:
                await self._meta_repo.upsert_column_info(imported_columns[column_id])
            for metric_id in metric_changes.created_ids + metric_changes.updated_ids:
                await self._meta_repo.upsert_metric_info(imported_metrics[metric_id])

            return result

    async def _build_metadata(
        self,
        meta_config: MetaConfig,
    ) -> tuple[list[TableInfo], list[ColumnInfo], list[MetricInfo]]:
        """校验业务数据并构造元数据实体"""
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []

        source_columns: set[tuple[str, str]] = set()
        for table_config in meta_config.tables:
            table_id = table_config.id or table_config.name
            table_infos.append(
                TableInfo(
                    id=table_id,
                    name=table_config.name,
                    role=table_config.role,
                    primary_key_columns=table_config.primary_key_columns,
                    description=table_config.description,
                )
            )

            column_types = await self._source_repo.get_column_types(table_config.name)
            for column_config in table_config.columns:
                source_column = (table_config.name, column_config.name)
                if source_column in source_columns:
                    raise ValueError(
                        "Duplicate source column in metadata import: "
                        f"{table_config.name}.{column_config.name}"
                    )
                source_columns.add(source_column)

                if column_config.name not in column_types:
                    raise ValueError(
                        "Column not found in source table: "
                        f"{table_config.name}.{column_config.name}"
                    )
                column_values = await self._source_repo.get_column_values(
                    table_config.name,
                    column_config.name,
                    10,
                )
                column_infos.append(
                    ColumnInfo(
                        id=column_config.id or f"{table_id}.{column_config.name}",
                        name=column_config.name,
                        type=column_types[column_config.name],
                        examples=self._serialize_examples(column_values),
                        description=column_config.description,
                        alias=list(dict.fromkeys(column_config.alias)),
                        index_values=column_config.index_values,
                        reference_column_id=column_config.reference_column_id,
                        table_id=table_id,
                    )
                )

        metric_infos = [
            MetricInfo(
                id=metric_config.id or metric_config.name,
                name=metric_config.name,
                description=metric_config.description,
                relevant_columns=list(dict.fromkeys(metric_config.relevant_columns)),
                alias=list(dict.fromkeys(metric_config.alias)),
            )
            for metric_config in meta_config.metrics
        ]
        return table_infos, column_infos, metric_infos

    @staticmethod
    def _index_by_id[T](items: list[T], resource: str) -> dict[str, T]:
        """按编号索引实体并校验重复编号"""
        indexed: dict[str, T] = {}
        for item in items:
            item_id = getattr(item, "id", None)
            if not isinstance(item_id, str):
                raise TypeError(f"{resource.title()} metadata is missing an id")
            if item_id in indexed:
                raise ValueError(
                    f"Duplicate {resource} id in metadata import: {item_id}"
                )
            indexed[item_id] = item
        return indexed

    @staticmethod
    def _validate_metric_columns(
        metric_infos: list[MetricInfo],
        available_column_ids: set[str],
    ) -> None:
        """校验指标关联的字段编号"""
        for metric_info in metric_infos:
            missing_column_ids = sorted(
                set(metric_info.relevant_columns) - available_column_ids
            )
            if missing_column_ids:
                raise ValueError(
                    f"Metric {metric_info.id} references missing columns: "
                    f"{', '.join(missing_column_ids)}"
                )

    @staticmethod
    def _validate_column_references(
        column_infos: list[ColumnInfo],
        available_column_ids: set[str],
    ) -> None:
        """校验外键字段引用的目标字段"""
        for column_info in column_infos:
            reference_column_id = column_info.reference_column_id
            if not reference_column_id:
                continue
            if reference_column_id == column_info.id:
                raise ValueError(f"Column cannot reference itself: {column_info.id}")
            if reference_column_id not in available_column_ids:
                raise ValueError(
                    f"Column {column_info.id} references missing column: "
                    f"{reference_column_id}"
                )

    @staticmethod
    def _get_changes(
        existing: dict[str, tuple[Any, ...]],
        imported: dict[str, tuple[Any, ...]],
        mode: ImportMode,
    ) -> ResourceChanges:
        """计算单类元数据的新增、更新和删除编号"""
        existing_ids = set(existing)
        imported_ids = set(imported)
        return ResourceChanges(
            created_ids=sorted(imported_ids - existing_ids),
            updated_ids=sorted(
                item_id
                for item_id in existing_ids & imported_ids
                if existing[item_id] != imported[item_id]
            ),
            deleted_ids=(
                sorted(existing_ids - imported_ids)
                if mode is ImportMode.REPLACE
                else []
            ),
        )

    @staticmethod
    def _table_snapshots(
        table_infos: dict[str, TableInfo],
    ) -> dict[str, tuple[Any, ...]]:
        """生成表元数据比较快照"""
        return {
            item_id: (
                item.name,
                item.role,
                item.primary_key_columns,
                item.description,
            )
            for item_id, item in table_infos.items()
        }

    @staticmethod
    def _column_snapshots(
        column_infos: dict[str, ColumnInfo],
    ) -> dict[str, tuple[Any, ...]]:
        """生成字段元数据比较快照"""
        return {
            item_id: (
                item.name,
                item.type,
                item.description,
                item.examples,
                item.alias,
                item.index_values,
                item.reference_column_id,
                item.table_id,
            )
            for item_id, item in column_infos.items()
        }

    @staticmethod
    def _metric_snapshots(
        metric_infos: dict[str, MetricInfo],
    ) -> dict[str, tuple[Any, ...]]:
        """生成指标元数据比较快照"""
        return {
            item_id: (
                item.name,
                item.description,
                item.relevant_columns,
                item.alias,
            )
            for item_id, item in metric_infos.items()
        }

    @staticmethod
    def _serialize_examples(examples: list[Any]) -> list[Any]:
        """将字段示例转换为可序列化值"""
        serialized: list[Any] = []
        for value in examples:
            if isinstance(value, (datetime, date)):
                serialized.append(value.isoformat())
            elif isinstance(value, Decimal):
                serialized.append(float(value))
            else:
                serialized.append(value)
        return sorted(serialized, key=lambda value: str(value))
