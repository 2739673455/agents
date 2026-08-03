"""检索索引批量同步测试"""

import unittest
from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import AsyncMock, MagicMock, call

from app.clients.embedding_client_manager import EmbeddingClient
from app.entities.meta import ColumnInfo, MetricInfo
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
        )
        disabled_column = ColumnInfo(
            t_name="users",
            name="status",
            type="tinyint",
            description="状态",
            examples=[],
            alias=[],
            index_values=False,
        )
        columns = {
            ("users", "name"): enabled_column,
            ("users", "status"): disabled_column,
        }
        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.get_column_info = AsyncMock(
            side_effect=lambda t_name, c_name: columns[(t_name, c_name)]
        )
        source_repo = MagicMock(spec=SourceMySQLRepo)
        source_repo.get_column_values = AsyncMock(return_value=["Alice", None, "Bob"])
        value_repo = MagicMock(spec=ValueESRepo)
        value_repo.ensure_index = AsyncMock()
        value_repo.delete_by_column = AsyncMock()
        value_repo.index = AsyncMock()
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
        value_repo.index.assert_awaited_once()

    async def test_sync_metric_indexes_deduplicates_metrics(self) -> None:
        metrics = {
            "用户数": MetricInfo(
                name="用户数",
                description="用户总数",
                alias=["客户数"],
            ),
            "订单数": MetricInfo(
                name="订单数",
                description="订单总数",
                alias=[],
            ),
        }

        @asynccontextmanager
        async def transaction():
            yield

        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.transaction.return_value = transaction()
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


if __name__ == "__main__":
    unittest.main()
