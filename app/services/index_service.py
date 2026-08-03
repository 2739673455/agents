"""检索索引同步服务"""

import uuid
from datetime import date, datetime
from typing import Any

from app.clients.embedding_client_manager import EmbeddingClient
from app.entities.meta import ColumnInfo, ColumnKey, MetricInfo, ValueInfo
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.repositories.value_es_repo import ValueESRepo


class IndexService:
    """同步字段、字段值和指标检索索引"""

    _embedding_batch_size = 64

    def __init__(
        self,
        meta_repo: MetaMySQLRepo,
        source_repo: SourceMySQLRepo,
        column_repo: ColumnQdrantRepo,
        embedding_client: EmbeddingClient,
        value_repo: ValueESRepo,
        metric_repo: MetricQdrantRepo,
    ) -> None:
        """初始化检索索引同步服务"""
        self._meta_repo = meta_repo
        self._source_repo = source_repo
        self._column_repo = column_repo
        self._embedding_client = embedding_client
        self._value_repo = value_repo
        self._metric_repo = metric_repo

    async def sync_column_indexes(
        self, column_keys: list[ColumnKey]
    ) -> dict[ColumnKey, int]:
        """同步多个字段的向量索引"""
        async with self._meta_repo.transaction():
            unique_column_keys = list(dict.fromkeys(column_keys))
            column_infos = [
                await self._meta_repo.get_column_info(*column_key)
                for column_key in unique_column_keys
            ]
            return {
                (column_info.t_name, column_info.name): await self._sync_column_index(
                    column_info
                )
                for column_info in column_infos
            }

    async def sync_column_values(
        self, column_keys: list[ColumnKey]
    ) -> dict[ColumnKey, int]:
        """同步多个字段的取值索引"""
        unique_column_keys = list(dict.fromkeys(column_keys))
        column_infos = [
            await self._meta_repo.get_column_info(*column_key)
            for column_key in unique_column_keys
        ]
        results: dict[ColumnKey, int] = {}
        for column_info in column_infos:
            column_key = (column_info.t_name, column_info.name)
            if column_info.index_values:
                results[column_key] = await self._sync_column_values(column_info)
            else:
                await self._clear_column_values(*column_key)
                results[column_key] = 0
        return results

    async def sync_metric_indexes(self, metric_names: list[str]) -> dict[str, int]:
        """同步多个指标的向量索引"""
        async with self._meta_repo.transaction():
            unique_metric_names = list(dict.fromkeys(metric_names))
            metric_infos = [
                await self._meta_repo.get_metric_info(metric_name)
                for metric_name in unique_metric_names
            ]
            return {
                metric_info.name: await self._sync_metric_index(metric_info)
                for metric_info in metric_infos
            }

    async def sync_table(self, t_name: str) -> dict[str, int]:
        """同步表下全部字段向量及字段值索引"""
        async with self._meta_repo.transaction():
            table_info = await self._meta_repo.get_table_info(t_name)
            column_infos = await self._meta_repo.get_columns_by_table_name(t_name)
            column_vector_count = 0
            for column_info in column_infos:
                column_vector_count += await self._sync_column_index(column_info)
            self._meta_repo.mark_table_indexed(table_info)

        value_column_count = 0
        value_count = 0
        for column_info in column_infos:
            if column_info.index_values:
                value_column_count += 1
                value_count += await self._sync_column_values(column_info)
            else:
                await self._clear_column_values(
                    column_info.t_name,
                    column_info.name,
                )

        return {
            "column_count": len(column_infos),
            "column_vector_count": column_vector_count,
            "value_column_count": value_column_count,
            "value_count": value_count,
        }

    async def _sync_column_index(self, column_info: ColumnInfo) -> int:
        """替换字段的全部向量索引"""
        await self._column_repo.ensure_collection()
        texts = self._get_index_texts(
            column_info.name,
            column_info.description,
            column_info.alias,
        )
        embeddings = await self._embed_texts(texts)
        resource_key = f"{column_info.t_name}.{column_info.name}"
        point_ids = self._get_point_ids("column", resource_key, texts)

        await self._column_repo.delete(column_info.t_name, column_info.name)
        await self._column_repo.upsert(
            point_ids,
            embeddings,
            [column_info] * len(point_ids),
        )
        self._meta_repo.mark_column_indexed(column_info)
        return len(point_ids)

    async def _sync_metric_index(self, metric_info: MetricInfo) -> int:
        """替换指标的全部向量索引"""
        await self._metric_repo.ensure_collection()
        texts = self._get_index_texts(
            metric_info.name,
            metric_info.description,
            metric_info.alias,
        )
        embeddings = await self._embed_texts(texts)
        point_ids = self._get_point_ids("metric", metric_info.name, texts)

        await self._metric_repo.delete_by_name(metric_info.name)
        await self._metric_repo.upsert(
            point_ids,
            embeddings,
            [metric_info] * len(point_ids),
        )
        self._meta_repo.mark_metric_indexed(metric_info)
        return len(point_ids)

    async def _sync_column_values(
        self,
        column_info: ColumnInfo,
    ) -> int:
        """替换字段的全部取值索引"""
        await self._value_repo.ensure_index()
        values = await self._source_repo.get_column_values(
            column_info.t_name,
            column_info.name,
        )
        value_infos = [
            ValueInfo(
                value=self._serialize_value(value),
                t_name=column_info.t_name,
                c_name=column_info.name,
            )
            for value in values
            if value is not None
        ]

        await self._value_repo.delete_by_column(
            column_info.t_name,
            column_info.name,
        )
        if value_infos:
            await self._value_repo.index(value_infos)
        return len(value_infos)

    async def _clear_column_values(self, t_name: str, c_name: str) -> None:
        """清理未启用字段的取值索引"""
        await self._value_repo.ensure_index()
        await self._value_repo.delete_by_column(t_name, c_name)

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """分批生成文本向量"""
        embeddings: list[list[float]] = []
        for index in range(0, len(texts), self._embedding_batch_size):
            batch = texts[index : index + self._embedding_batch_size]
            embeddings.extend(await self._embedding_client.aembed_documents(batch))
        return embeddings

    @staticmethod
    def _get_index_texts(name: str, description: str, aliases: list[str]) -> list[str]:
        """获取去重后的索引文本"""
        return list(
            dict.fromkeys(text for text in [name, description, *aliases] if text)
        )

    @staticmethod
    def _get_point_ids(resource: str, resource_key: str, texts: list[str]) -> list[str]:
        """生成稳定的向量点编号"""
        return [
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{resource}:{resource_key}:{index}:{text}",
                )
            )
            for index, text in enumerate(texts)
        ]

    @staticmethod
    def _serialize_value(value: Any) -> str:
        """将字段取值转换为索引文本"""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)
