"""名称主键元数据集成测试"""

import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, ClassVar, cast
from unittest.mock import AsyncMock, MagicMock

import yaml
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.conf.meta_config import MetaConfig
from app.entities.meta import Base, ColumnInfo, ColumnMetric, MetricInfo, TableInfo
from app.errors.meta_error import InvalidMetadataError
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.services.meta_import_service import ImportMode, MetaImportService
from dbmock.core.entities.warehouse import Base as WarehouseBase


class _MetaRepo:
    """测试用内存元数据存储"""

    def __init__(self) -> None:
        self.tables: dict[str, TableInfo] = {}
        self.columns: dict[tuple[str, str], ColumnInfo] = {}
        self.metrics: dict[str, MetricInfo] = {}

    @asynccontextmanager
    async def transaction(self):
        yield

    async def list_table_infos(self) -> list[TableInfo]:
        return list(self.tables.values())

    async def list_column_infos(self) -> list[ColumnInfo]:
        return list(self.columns.values())

    async def list_metric_infos(self) -> list[MetricInfo]:
        return list(self.metrics.values())

    async def delete_metric_infos(self, metric_names: list[str]) -> None:
        for metric_name in metric_names:
            self.metrics.pop(metric_name, None)

    async def delete_column_infos(self, column_keys: list[tuple[str, str]]) -> None:
        for column_key in column_keys:
            self.columns.pop(column_key, None)

    async def delete_table_infos(self, table_names: list[str]) -> None:
        for t_name in table_names:
            self.tables.pop(t_name, None)

    async def upsert_table_info(
        self,
        table_info: TableInfo,
        *,
        force_version_increment: bool = False,
    ) -> None:
        self.tables[table_info.name] = table_info

    async def upsert_column_infos(
        self,
        column_infos: list[ColumnInfo],
        force_version_increment_keys: set[tuple[str, str]] | None = None,
    ) -> None:
        for column_info in column_infos:
            self.columns[(column_info.t_name, column_info.name)] = column_info

    async def upsert_metric_info(
        self,
        metric_info: MetricInfo,
        *,
        force_version_increment: bool = False,
    ) -> None:
        self.metrics[metric_info.name] = metric_info


class _SourceRepo:
    """测试用业务表结构存储"""

    _columns: ClassVar[dict[str, dict[str, str]]] = {
        "users": {"id": "int"},
        "orders": {"id": "int", "user_id": "int"},
    }

    async def get_column_types(self, t_name: str) -> dict[str, str]:
        return self._columns[t_name]

    async def get_column_values(
        self,
        t_name: str,
        c_name: str,
        limit: int | None = None,
    ) -> list[Any]:
        return [1]


class MetadataNameKeyTest(unittest.IsolatedAsyncioTestCase):
    """验证 YAML 导入使用名称主键"""

    async def test_import_uses_names_and_composite_column_keys(self) -> None:
        config = MetaConfig.model_validate(
            {
                "tables": [
                    {
                        "name": "users",
                        "role": "dim",
                        "primary_key_columns": ["id"],
                        "description": "用户",
                        "columns": [
                            {
                                "name": "id",
                                "description": "用户主键",
                                "index_values": False,
                            }
                        ],
                    },
                    {
                        "name": "orders",
                        "role": "fact",
                        "primary_key_columns": ["id"],
                        "description": "订单",
                        "columns": [
                            {
                                "name": "id",
                                "description": "订单主键",
                                "index_values": False,
                            },
                            {
                                "name": "user_id",
                                "description": "用户主键",
                                "index_values": False,
                                "reference_t_name": "users",
                                "reference_c_name": "id",
                            },
                        ],
                    },
                ],
                "metrics": [
                    {
                        "name": "订单数",
                        "description": "订单总数",
                        "relevant_columns": [{"t_name": "orders", "c_name": "id"}],
                    }
                ],
            }
        )
        meta_repo = _MetaRepo()
        service = MetaImportService(
            cast(MetaMySQLRepo, meta_repo),
            cast(SourceMySQLRepo, _SourceRepo()),
        )

        result = await service.import_metadata(config, ImportMode.MERGE, False)

        self.assertEqual(result.tables.created, ["orders", "users"])
        self.assertEqual(
            result.columns.created,
            [("orders", "id"), ("orders", "user_id"), ("users", "id")],
        )
        self.assertEqual(result.metrics.created, ["订单数"])
        self.assertEqual(
            meta_repo.columns[("orders", "user_id")].reference_t_name,
            "users",
        )
        self.assertFalse(hasattr(meta_repo.tables["orders"], "id"))
        self.assertFalse(hasattr(meta_repo.columns[("orders", "id")], "id"))
        self.assertFalse(hasattr(meta_repo.metrics["订单数"], "id"))

    async def test_duplicate_table_name_is_rejected(self) -> None:
        config = MetaConfig.model_validate(
            {
                "tables": [
                    {
                        "name": "users",
                        "role": "dim",
                        "description": "用户一",
                        "columns": [],
                    },
                    {
                        "name": "users",
                        "role": "dim",
                        "description": "用户二",
                        "columns": [],
                    },
                ]
            }
        )
        service = MetaImportService(
            cast(MetaMySQLRepo, _MetaRepo()),
            cast(SourceMySQLRepo, _SourceRepo()),
        )

        with self.assertRaisesRegex(InvalidMetadataError, "Duplicate table name"):
            await service.import_metadata(config, ImportMode.MERGE, True)

    async def test_metadata_versions_increment_only_when_content_changes(self) -> None:
        existing = ColumnInfo(
            t_name="users",
            name="id",
            type="int",
            description="用户主键",
            examples=[],
            alias=[],
            index_values=False,
            meta_version=3,
            index_version=2,
        )
        changed = ColumnInfo(
            t_name="users",
            name="id",
            type="bigint",
            description="用户主键",
            examples=[],
            alias=[],
            index_values=False,
        )
        unchanged = ColumnInfo(
            t_name="users",
            name="id",
            type="int",
            description="用户主键",
            examples=[],
            alias=[],
            index_values=False,
        )
        forced = ColumnInfo(
            t_name="users",
            name="id",
            type="int",
            description="用户主键",
            examples=[],
            alias=[],
            index_values=False,
        )
        session = MagicMock(spec=AsyncSession)
        session.get = AsyncMock(side_effect=[existing, existing, existing])
        session.merge = AsyncMock()
        repository = MetaMySQLRepo(cast(AsyncSession, session))

        await repository.upsert_column_info(changed)
        await repository.upsert_column_info(unchanged)
        await repository.upsert_column_info(forced, force_version_increment=True)

        self.assertEqual((changed.meta_version, changed.index_version), (4, 2))
        self.assertEqual((unchanged.meta_version, unchanged.index_version), (3, 2))
        self.assertEqual((forced.meta_version, forced.index_version), (4, 2))

    async def test_index_version_follows_synchronized_metadata_version(self) -> None:
        column_info = ColumnInfo(
            t_name="users",
            name="id",
            type="int",
            description="用户主键",
            examples=[],
            alias=[],
            index_values=False,
            meta_version=4,
            index_version=2,
        )
        metric_info = MetricInfo(
            name="用户数",
            description="用户总数",
            alias=[],
            meta_version=5,
            index_version=3,
        )

        column_payload = ColumnQdrantRepo._to_payload(column_info)
        metric_payload = MetricQdrantRepo._to_payload(metric_info)
        MetaMySQLRepo.mark_column_indexed(column_info)
        MetaMySQLRepo.mark_metric_indexed(metric_info)

        self.assertEqual(column_payload["index_version"], 4)
        self.assertEqual(metric_payload["index_version"], 5)
        self.assertEqual(column_info.index_version, column_info.meta_version)
        self.assertEqual(metric_info.index_version, metric_info.meta_version)


class MetadataSchemaTest(unittest.TestCase):
    """验证关系数据库名称主键结构"""

    def test_orm_schema_and_foreign_keys_are_executable(self) -> None:
        self.assertEqual(
            [column.name for column in TableInfo.__table__.primary_key],
            ["name"],
        )
        self.assertEqual(
            [column.name for column in ColumnInfo.__table__.primary_key],
            ["t_name", "name"],
        )
        self.assertEqual(
            [column.name for column in ColumnMetric.__table__.primary_key],
            ["t_name", "c_name", "metric_name"],
        )
        self.assertNotIn("relevant_columns", MetricInfo.__table__.columns)
        for model in (TableInfo, ColumnInfo, MetricInfo):
            self.assertIn("meta_version", model.__table__.columns)
            self.assertIn("index_version", model.__table__.columns)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                TableInfo(
                    name="users",
                    role="dim",
                    primary_key_columns=["id"],
                    description="用户",
                )
            )
            session.add_all(
                [
                    ColumnInfo(
                        t_name="users",
                        name="id",
                        type="int",
                        description="用户主键",
                        examples=[],
                        alias=[],
                        index_values=False,
                    ),
                    ColumnInfo(
                        t_name="users",
                        name="manager_id",
                        type="int",
                        description="上级用户",
                        examples=[],
                        alias=[],
                        index_values=False,
                        reference_t_name="users",
                        reference_c_name="id",
                    ),
                ]
            )
            session.add(MetricInfo(name="用户数", description="用户总数", alias=[]))
            session.add(
                ColumnMetric(
                    t_name="users",
                    c_name="id",
                    metric_name="用户数",
                )
            )
            session.commit()

            table_info = session.get(TableInfo, "users")
            column_info = session.get(ColumnInfo, ("users", "id"))
            metric_info = session.get(MetricInfo, "用户数")
            assert table_info is not None
            assert column_info is not None
            assert metric_info is not None
            self.assertEqual(
                (table_info.meta_version, table_info.index_version), (1, 0)
            )
            self.assertEqual(
                (column_info.meta_version, column_info.index_version),
                (1, 0),
            )
            self.assertEqual(
                (metric_info.meta_version, metric_info.index_version),
                (1, 0),
            )

    def test_example_yaml_uses_name_references(self) -> None:
        raw_config = yaml.safe_load(Path("conf/meta_config.yaml").read_text())
        config = MetaConfig.model_validate(raw_config)

        self.assertTrue(config.tables)
        self.assertTrue(config.metrics)
        self.assertNotIn("id", raw_config["tables"][0])
        source_tables = WarehouseBase.metadata.tables
        self.assertTrue(
            all(
                table.name in source_tables
                and all(
                    column.name in source_tables[table.name].columns
                    for column in table.columns
                )
                for table in config.tables
            )
        )
        column_keys = {
            (table.name, column.name)
            for table in config.tables
            for column in table.columns
        }
        self.assertTrue(
            all(
                column.reference_t_name is None
                or (
                    column.reference_t_name,
                    column.reference_c_name,
                )
                in column_keys
                for table in config.tables
                for column in table.columns
            )
        )
        self.assertTrue(
            all(
                (reference.t_name, reference.c_name) in column_keys
                for metric in config.metrics
                for reference in metric.relevant_columns
            )
        )


if __name__ == "__main__":
    unittest.main()
