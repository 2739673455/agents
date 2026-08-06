"""语义目录检索服务测试"""

import unittest
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from elasticsearch import AsyncElasticsearch

from app.clients.embedding_client_manager import EmbeddingClient
from app.entities.meta import ColumnInfo, MetricInfo, TableInfo, ValueInfo
from app.entities.semantic_search import SearchHit, SemanticSearchRequest
from app.repositories.column_es_repo import ColumnESRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_es_repo import MetricESRepo
from app.repositories.value_es_repo import ValueESRepo
from app.services.semantic_catalog_service import SemanticCatalogService


class SemanticCatalogServiceTest(unittest.IsolatedAsyncioTestCase):
    """验证多路召回融合和关系上下文补全"""

    def setUp(self) -> None:
        """准备语义目录测试数据"""
        self.tables = [
            TableInfo(
                name="orders",
                role="fact",
                primary_key_columns=["id"],
                description="订单事实表",
                meta_version=2,
            ),
            TableInfo(
                name="users",
                role="dim",
                primary_key_columns=["id"],
                description="用户维度表",
                meta_version=1,
            ),
        ]
        self.columns = [
            self._column("orders", "id", "订单主键"),
            self._column(
                "orders",
                "user_id",
                "用户主键",
                reference_t_name="users",
                reference_c_name="id",
            ),
            self._column(
                "orders",
                "amount",
                "订单实付金额",
                alias=["销售额"],
                examples=[99, 199],
                meta_version=2,
                index_version=1,
            ),
            self._column("users", "id", "用户主键"),
            self._column(
                "users",
                "region",
                "用户所属区域",
                alias=["地区"],
                index_values=True,
                value_index_synced_at=datetime(2026, 8, 5, tzinfo=UTC),
                value_index_sync_status="succeeded",
            ),
        ]
        self.metrics = [
            MetricInfo(
                name="GMV",
                description="支付成功订单金额",
                alias=["销售额"],
                relevant_columns=[{"t_name": "orders", "c_name": "amount"}],
                meta_version=3,
                index_version=3,
            )
        ]

    @staticmethod
    def _column(
        t_name: str,
        name: str,
        description: str,
        *,
        alias: list[str] | None = None,
        examples: list[object] | None = None,
        index_values: bool = False,
        reference_t_name: str | None = None,
        reference_c_name: str | None = None,
        meta_version: int = 1,
        index_version: int = 1,
        value_index_synced_at: datetime | None = None,
        value_index_sync_status: str | None = None,
    ) -> ColumnInfo:
        """创建字段测试实体"""
        return ColumnInfo(
            t_name=t_name,
            name=name,
            type="varchar(64)",
            description=description,
            examples=examples or [],
            alias=alias or [],
            index_values=index_values,
            reference_t_name=reference_t_name,
            reference_c_name=reference_c_name,
            meta_version=meta_version,
            index_version=index_version,
            value_index_synced_at=value_index_synced_at,
            value_index_sync_status=value_index_sync_status,
        )

    def _build_service(
        self,
        *,
        column_search: AsyncMock | None = None,
        metric_search: AsyncMock | None = None,
        column_text_search: AsyncMock | None = None,
        metric_text_search: AsyncMock | None = None,
        value_search: AsyncMock | None = None,
    ) -> SemanticCatalogService:
        """创建带模拟依赖的语义目录服务"""
        meta_repo = MagicMock(spec=MetaMySQLRepo)
        meta_repo.list_table_infos = AsyncMock(return_value=self.tables)
        meta_repo.list_column_infos = AsyncMock(return_value=self.columns)
        meta_repo.list_metric_infos = AsyncMock(return_value=self.metrics)

        embedding_client = MagicMock(spec=EmbeddingClient)
        embedding_client.aembed_documents = AsyncMock(
            side_effect=lambda texts: [[0.1, 0.2] for _ in texts]
        )

        column_repo = MagicMock(spec=ColumnESRepo)
        column_repo.search_vector_hits = column_search or AsyncMock(return_value=[])
        column_repo.search_text_hits = column_text_search or AsyncMock(return_value=[])
        metric_repo = MagicMock(spec=MetricESRepo)
        metric_repo.search_vector_hits = metric_search or AsyncMock(return_value=[])
        metric_repo.search_text_hits = metric_text_search or AsyncMock(return_value=[])
        value_repo = MagicMock(spec=ValueESRepo)
        value_repo.search_hits = value_search or AsyncMock(return_value=[])

        return SemanticCatalogService(
            embedding_client=cast(EmbeddingClient, embedding_client),
            column_repo=cast(ColumnESRepo, column_repo),
            metric_repo=cast(MetricESRepo, metric_repo),
            value_repo=cast(ValueESRepo, value_repo),
            meta_repo=cast(MetaMySQLRepo, meta_repo),
        )

    async def test_search_fuses_results_and_expands_relations(self) -> None:
        """融合语义结果并补充指标依赖和一层主外键"""
        indexed_amount = self._column(
            "orders",
            "amount",
            "索引中的旧描述",
            meta_version=1,
            index_version=1,
        )
        indexed_metric = MetricInfo(
            name="GMV",
            description="索引中的旧描述",
            alias=[],
        )
        column_search = AsyncMock(
            return_value=[SearchHit(item=indexed_amount, score=0.82)]
        )
        metric_search = AsyncMock(
            return_value=[SearchHit(item=indexed_metric, score=0.91)]
        )

        async def search_values(
            query: str,
            score_threshold: float = 0.6,
            limit: int = 5,
            table_names: list[str] | None = None,
        ) -> list[SearchHit[ValueInfo]]:
            del score_threshold, limit, table_names
            if "华东" not in query:
                return []
            return [
                SearchHit(
                    item=ValueInfo(value="华东", t_name="users", c_name="region"),
                    score=3.2,
                )
            ]

        service = self._build_service(
            column_search=column_search,
            metric_search=metric_search,
            value_search=AsyncMock(side_effect=search_values),
        )

        result = await service.search(
            SemanticSearchRequest(
                query="华东销售额下降",
                terms=["销售额", "华东"],
            )
        )

        self.assertEqual(result.status, "success")
        self.assertEqual([metric.name for metric in result.metrics], ["GMV"])
        self.assertEqual(result.metrics[0].index_status, "current")
        self.assertEqual([value.value for value in result.values], ["华东"])

        columns = {(column.t_name, column.name): column for column in result.columns}
        self.assertEqual(columns[("orders", "amount")].description, "订单实付金额")
        self.assertEqual(columns[("orders", "amount")].index_status, "stale")
        self.assertEqual(
            columns[("orders", "amount")].inclusion_reasons,
            ["direct_match", "metric_dependency"],
        )
        self.assertIn("value_owner", columns[("users", "region")].inclusion_reasons)
        self.assertIn("primary_key", columns[("orders", "id")].inclusion_reasons)
        self.assertIn("foreign_key", columns[("orders", "user_id")].inclusion_reasons)
        self.assertIn("reference_target", columns[("users", "id")].inclusion_reasons)
        self.assertEqual(
            [table.name for table in result.tables],
            ["orders", "users"],
        )
        self.assertEqual(len(result.relations), 1)
        self.assertEqual(result.relations[0].source_c_name, "user_id")
        self.assertIn(
            "Column semantic index is stale: orders.amount",
            result.warnings,
        )

    async def test_search_degrades_when_vector_backend_fails(self) -> None:
        """向量检索失败时保留 ES 全文检索结果"""
        metric_search = AsyncMock(side_effect=RuntimeError("ES unavailable"))
        metric_text_search = AsyncMock(
            return_value=[SearchHit(item=self.metrics[0], score=8.0)]
        )
        service = self._build_service(
            metric_search=metric_search,
            metric_text_search=metric_text_search,
        )

        result = await service.search(
            SemanticSearchRequest(
                query="销售额",
                resource_types=["metric"],
                include_relations=False,
            )
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual([metric.name for metric in result.metrics], ["GMV"])
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("Metric vector retrieval unavailable", result.warnings[0])
        self.assertEqual(
            [(column.t_name, column.name) for column in result.columns],
            [("orders", "amount")],
        )

    async def test_search_does_not_scan_mysql_metadata_for_candidates(self) -> None:
        """ES 未命中时不使用 MySQL 元数据执行检索"""
        service = self._build_service()

        result = await service.search(
            SemanticSearchRequest(
                query="销售额",
                resource_types=["column", "metric"],
                include_relations=False,
            )
        )

        self.assertEqual(result.columns, [])
        self.assertEqual(result.metrics, [])

    async def test_search_uses_elasticsearch_fulltext_candidates(self) -> None:
        """字段描述的全文命中可以进入融合结果"""
        column_text_search = AsyncMock(
            return_value=[
                SearchHit(
                    item=self._column("orders", "amount", "订单实付金额"),
                    score=4.2,
                )
            ]
        )
        service = self._build_service(column_text_search=column_text_search)

        result = await service.search(
            SemanticSearchRequest(
                query="订单实付金额",
                resource_types=["column"],
                include_relations=False,
            )
        )

        self.assertEqual(
            [(column.t_name, column.name) for column in result.columns],
            [("orders", "amount")],
        )
        self.assertIn(
            "fulltext:订单实付金额:4.2000",
            result.columns[0].match_reasons,
        )

    async def test_table_scope_filters_direct_and_expanded_resources(self) -> None:
        """表范围同时限制直接命中和关系扩展"""
        column_search = AsyncMock(
            return_value=[
                SearchHit(
                    item=self._column("orders", "amount", "订单实付金额"),
                    score=0.9,
                ),
                SearchHit(
                    item=self._column("users", "region", "用户所属区域"),
                    score=0.8,
                ),
            ]
        )
        service = self._build_service(column_search=column_search)

        result = await service.search(
            SemanticSearchRequest(
                query="销售额",
                resource_types=["column"],
                table_names=["orders"],
            )
        )

        self.assertTrue(result.columns)
        self.assertTrue(all(column.t_name == "orders" for column in result.columns))
        self.assertEqual([table.name for table in result.tables], ["orders"])
        self.assertEqual(result.relations, [])

    async def test_unknown_table_scope_does_not_fall_back_to_all_tables(self) -> None:
        """未知表范围不能意外扩大为全库检索"""
        service = self._build_service()

        result = await service.search(
            SemanticSearchRequest(
                query="销售额",
                table_names=["missing_table"],
            )
        )

        self.assertEqual(result.metrics, [])
        self.assertEqual(result.columns, [])
        self.assertEqual(result.values, [])
        self.assertEqual(result.tables, [])
        self.assertIn("Unknown table scopes: missing_table", result.warnings)


class SearchRepositoryScoreTest(unittest.IsolatedAsyncioTestCase):
    """验证索引仓库保留后端原始命中分数"""

    async def test_column_vector_search_returns_elasticsearch_score(self) -> None:
        """字段向量检索返回 Elasticsearch 分数"""
        column_info = ColumnInfo(
            t_name="orders",
            name="amount",
            type="decimal",
            description="订单金额",
            examples=[],
            alias=[],
            index_values=False,
        )
        client = MagicMock(spec=AsyncElasticsearch)
        client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "payload": ColumnESRepo._to_payload(column_info)
                            },
                            "_score": 0.87,
                        }
                    ]
                }
            }
        )
        repository = ColumnESRepo(cast(AsyncElasticsearch, client))

        hits = await repository.search_vector_hits([0.1, 0.2])

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].item.name, "amount")
        self.assertEqual(hits[0].score, 0.87)
        self.assertEqual(
            client.search.await_args.kwargs["index"],
            "data-agent-column",
        )
        self.assertNotIn("filter", client.search.await_args.kwargs["knn"])

    async def test_metric_vector_search_returns_elasticsearch_score(self) -> None:
        """指标向量检索返回 Elasticsearch 分数"""
        metric_info = MetricInfo(
            name="GMV",
            description="销售额",
            alias=[],
        )
        client = MagicMock(spec=AsyncElasticsearch)
        client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "payload": MetricESRepo._to_payload(metric_info)
                            },
                            "_score": 0.92,
                        }
                    ]
                }
            }
        )
        repository = MetricESRepo(cast(AsyncElasticsearch, client))

        hits = await repository.search_vector_hits([0.1, 0.2])

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].item.name, "GMV")
        self.assertEqual(hits[0].score, 0.92)
        self.assertEqual(
            client.search.await_args.kwargs["index"],
            "data-agent-metric",
        )
        self.assertNotIn("filter", client.search.await_args.kwargs["knn"])

    async def test_column_text_search_boosts_exact_text_types(self) -> None:
        """字段全文检索在 ES 中按文本类型设置精确匹配权重"""
        client = MagicMock(spec=AsyncElasticsearch)
        client.search = AsyncMock(return_value={"hits": {"hits": []}})
        repository = ColumnESRepo(cast(AsyncElasticsearch, client))

        await repository.search_text_hits("销售额")

        search_query = client.search.await_args.kwargs["query"]
        exact_queries = search_query["dis_max"]["queries"][:3]
        boosts = {
            item["bool"]["filter"][0]["term"]["text_type"]: item["bool"]["boost"]
            for item in exact_queries
        }
        self.assertEqual(
            boosts,
            {"name": 8.0, "alias": 6.0, "description": 4.0},
        )

    async def test_metric_text_search_boosts_exact_text_types(self) -> None:
        """指标全文检索在 ES 中按文本类型设置精确匹配权重"""
        client = MagicMock(spec=AsyncElasticsearch)
        client.search = AsyncMock(return_value={"hits": {"hits": []}})
        repository = MetricESRepo(cast(AsyncElasticsearch, client))

        await repository.search_text_hits("GMV")

        search_query = client.search.await_args.kwargs["query"]
        exact_queries = search_query["dis_max"]["queries"][:3]
        boosts = {
            item["bool"]["filter"][0]["term"]["text_type"]: item["bool"]["boost"]
            for item in exact_queries
        }
        self.assertEqual(
            boosts,
            {"name": 8.0, "alias": 6.0, "description": 4.0},
        )

    async def test_value_search_returns_elasticsearch_score(self) -> None:
        """字段值检索返回 Elasticsearch 分数"""
        client = MagicMock(spec=AsyncElasticsearch)
        client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "value": "华东",
                                "t_name": "users",
                                "c_name": "region",
                            },
                            "_score": 3.5,
                        }
                    ]
                }
            }
        )
        repository = ValueESRepo(cast(AsyncElasticsearch, client))

        hits = await repository.search_hits("华东")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].item.value, "华东")
        self.assertEqual(hits[0].score, 3.5)
