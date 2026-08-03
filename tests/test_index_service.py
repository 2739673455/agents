"""检索索引批量同步测试"""

import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, call

from elasticsearch import AsyncElasticsearch

from app.clients.embedding_client_manager import EmbeddingClient
from app.entities.meta import ColumnInfo, MetricInfo, ValueInfo
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.repositories.value_es_repo import ValueESRepo
from app.services.index_service import IndexService


class BatchIndexSyncTest(unittest.IsolatedAsyncioTestCase):
    """验证批量索引同步与请求去重"""

    @staticmethod
    def _build_service(
        meta_repo: MagicMock,
        source_repo: MagicMock,
        column_repo: MagicMock,
        embedding_client: MagicMock,
        value_repo: MagicMock,
        metric_repo: MagicMock,
    ) -> IndexService:
        return IndexService(
            meta_repo=cast(MetaMySQLRepo, meta_repo),
            source_repo=cast(SourceMySQLRepo, source_repo),
            column_repo=cast(ColumnQdrantRepo, column_repo),
            embedding_client=cast(EmbeddingClient, embedding_client),
            value_repo=cast(ValueESRepo, value_repo),
            metric_repo=cast(MetricQdrantRepo, metric_repo),
        )

    async def test_sync_column_values_deduplicates_columns(self) -> None:
        enabled_column = ColumnInfo(
            t_name="users",
            name="name",
            type="varchar(64)",
            description="用户名",
            examples=[],
            alias=[],
            index_values=True,
            meta_version=1,
        )
        disabled_column = ColumnInfo(
            t_name="users",
            name="status",
            type="tinyint",
            description="状态",
            examples=[],
            alias=[],
            index_values=False,
            meta_version=1,
        )
        columns = {
            ("users", "name"): enabled_column,
            ("users", "status"): disabled_column,
        }
        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.get_column_info = AsyncMock(
            side_effect=lambda t_name, c_name: columns[(t_name, c_name)]
        )

        @asynccontextmanager
        async def transaction():
            yield

        meta_repo.transaction.side_effect = transaction
        meta_repo.mark_column_values_syncing = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_syncing
        )
        meta_repo.mark_column_values_succeeded = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_succeeded
        )
        meta_repo.mark_column_values_failed = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_failed
        )
        source_repo = MagicMock(spec=SourceMySQLRepo)

        async def iter_column_value_batches(
            t_name: str,
            c_name: str,
            batch_size: int = 1000,
        ):
            yield ["Alice", None]
            yield ["Bob"]

        source_repo.iter_column_value_batches = iter_column_value_batches
        value_repo = MagicMock(spec=ValueESRepo)
        value_repo.ensure_index = AsyncMock()
        value_repo.delete_by_column = AsyncMock()
        value_repo.index = AsyncMock()
        value_repo.refresh = AsyncMock()
        service = self._build_service(
            meta_repo,
            source_repo,
            MagicMock(spec=ColumnQdrantRepo),
            MagicMock(spec=EmbeddingClient),
            value_repo,
            MagicMock(spec=MetricQdrantRepo),
        )

        results = await service.sync_column_values(
            [("users", "name"), ("users", "status"), ("users", "name")]
        )

        self.assertEqual(
            results,
            {("users", "name"): 2, ("users", "status"): 0},
        )
        self.assertEqual(meta_repo.get_column_info.await_count, 2)
        value_repo.delete_by_column.assert_has_awaits(
            [call("users", "name"), call("users", "status")]
        )
        self.assertEqual(value_repo.index.await_count, 2)
        value_repo.refresh.assert_awaited_once()
        self.assertEqual(enabled_column.value_index_sync_status, "succeeded")
        self.assertEqual(disabled_column.value_index_sync_status, "succeeded")
        self.assertIsInstance(enabled_column.value_index_synced_at, datetime)
        self.assertIsInstance(disabled_column.value_index_synced_at, datetime)

    async def test_sync_column_values_records_failure(self) -> None:
        previous_synced_at = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        column_info = ColumnInfo(
            t_name="users",
            name="name",
            type="varchar(64)",
            description="用户名",
            examples=[],
            alias=[],
            index_values=True,
            value_index_synced_at=previous_synced_at,
            value_index_sync_status="succeeded",
        )
        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.get_column_info = AsyncMock(return_value=column_info)

        @asynccontextmanager
        async def transaction():
            yield

        meta_repo.transaction.side_effect = transaction
        meta_repo.mark_column_values_syncing = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_syncing
        )
        meta_repo.mark_column_values_succeeded = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_succeeded
        )
        meta_repo.mark_column_values_failed = MagicMock(
            side_effect=MetaMySQLRepo.mark_column_values_failed
        )
        source_repo = MagicMock(spec=SourceMySQLRepo)

        async def iter_column_value_batches(t_name: str, c_name: str):
            yield ["Alice"]

        source_repo.iter_column_value_batches = iter_column_value_batches
        value_repo = MagicMock(spec=ValueESRepo)
        value_repo.ensure_index = AsyncMock()
        value_repo.delete_by_column = AsyncMock()
        value_repo.index = AsyncMock(side_effect=RuntimeError("ES unavailable"))
        service = self._build_service(
            meta_repo,
            source_repo,
            MagicMock(spec=ColumnQdrantRepo),
            MagicMock(spec=EmbeddingClient),
            value_repo,
            MagicMock(spec=MetricQdrantRepo),
        )

        with self.assertRaisesRegex(RuntimeError, "ES unavailable"):
            await service.sync_column_values([("users", "name")])

        self.assertEqual(column_info.value_index_sync_status, "failed")
        self.assertEqual(column_info.value_index_synced_at, previous_synced_at)
        meta_repo.mark_column_values_succeeded.assert_not_called()

    async def test_sync_metric_indexes_deduplicates_metrics(self) -> None:
        metrics = {
            "用户数": MetricInfo(
                name="用户数",
                description="用户总数",
                alias=["客户数"],
                meta_version=1,
                index_version=0,
            ),
            "订单数": MetricInfo(
                name="订单数",
                description="订单总数",
                alias=[],
                meta_version=1,
                index_version=0,
            ),
        }

        @asynccontextmanager
        async def transaction():
            yield

        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.transaction.side_effect = transaction
        meta_repo.mark_metric_indexed = MagicMock(
            side_effect=MetaMySQLRepo.mark_metric_indexed
        )
        meta_repo.get_metric_info = AsyncMock(
            side_effect=lambda metric_name: metrics[metric_name]
        )
        embedding_client = MagicMock(spec=EmbeddingClient)
        embedding_client.aembed_documents = AsyncMock(
            side_effect=lambda texts: [[0.1] for _ in texts]
        )
        metric_repo = MagicMock(spec=MetricQdrantRepo)
        metric_repo.ensure_collection = AsyncMock()
        metric_repo.delete_by_name = AsyncMock()
        metric_repo.upsert = AsyncMock()
        service = self._build_service(
            meta_repo,
            MagicMock(spec=SourceMySQLRepo),
            MagicMock(spec=ColumnQdrantRepo),
            embedding_client,
            MagicMock(spec=ValueESRepo),
            metric_repo,
        )

        results = await service.sync_metric_indexes(["用户数", "订单数", "用户数"])

        self.assertEqual(results, {"用户数": 3, "订单数": 2})
        self.assertEqual(meta_repo.get_metric_info.await_count, 2)
        metric_repo.delete_by_name.assert_has_awaits([call("用户数"), call("订单数")])
        self.assertEqual(metric_repo.upsert.await_count, 2)
        self.assertEqual(metrics["用户数"].index_version, 1)
        self.assertEqual(metrics["订单数"].index_version, 1)

    async def test_delete_indexes_deduplicates_resources(self) -> None:
        column_repo = MagicMock(spec=ColumnQdrantRepo)
        column_repo.delete = AsyncMock()
        value_repo = MagicMock(spec=ValueESRepo)
        value_repo.delete_by_column = AsyncMock()
        metric_repo = MagicMock(spec=MetricQdrantRepo)
        metric_repo.delete_by_name = AsyncMock()
        service = self._build_service(
            MagicMock(spec=MetaMySQLRepo),
            MagicMock(spec=SourceMySQLRepo),
            column_repo,
            MagicMock(spec=EmbeddingClient),
            value_repo,
            metric_repo,
        )

        await service.delete_column_indexes(
            [("users", "name"), ("users", "name"), ("orders", "id")]
        )
        await service.delete_metric_indexes(["用户数", "用户数", "订单数"])

        column_repo.delete.assert_has_awaits(
            [call("users", "name"), call("orders", "id")]
        )
        value_repo.delete_by_column.assert_has_awaits(
            [call("users", "name"), call("orders", "id")]
        )
        metric_repo.delete_by_name.assert_has_awaits([call("用户数"), call("订单数")])


class ValueESRepoTest(unittest.IsolatedAsyncioTestCase):
    """验证字段值批量写入结果"""

    async def test_bulk_write_does_not_refresh_each_batch(self) -> None:
        client = MagicMock(spec=AsyncElasticsearch)
        client.bulk = AsyncMock(return_value={"errors": False})
        repository = ValueESRepo(cast(AsyncElasticsearch, client))

        await repository.index(
            [
                ValueInfo(value="1", t_name="users", c_name="id"),
                ValueInfo(value="2", t_name="users", c_name="id"),
            ],
            batch_size=1,
        )

        self.assertEqual(client.bulk.await_count, 2)
        self.assertTrue(
            all(
                call_item.kwargs["refresh"] is False
                for call_item in client.bulk.await_args_list
            )
        )

    async def test_bulk_item_failure_is_reported(self) -> None:
        client = MagicMock(spec=AsyncElasticsearch)
        client.bulk = AsyncMock(return_value={"errors": True})
        repository = ValueESRepo(cast(AsyncElasticsearch, client))

        with self.assertRaisesRegex(RuntimeError, "contains failed items"):
            await repository.index([ValueInfo(value="1", t_name="users", c_name="id")])


if __name__ == "__main__":
    unittest.main()
