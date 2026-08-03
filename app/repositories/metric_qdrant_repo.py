"""指标向量数据访问"""

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.conf.app_config import cfg
from app.entities.meta import MetricInfo


class MetricQdrantRepo:
    """指标向量存储"""

    _collection_name = "data-agent-metric"

    def __init__(self, client: AsyncQdrantClient) -> None:
        """初始化指标向量存储"""
        self._client = client

    @staticmethod
    def _to_payload(metric_info: MetricInfo) -> dict[str, Any]:
        """将指标 ORM 转换为向量载荷"""
        return {
            "name": metric_info.name,
            "description": metric_info.description,
            "relevant_columns": metric_info.relevant_columns,
            "alias": metric_info.alias,
            "meta_version": metric_info.meta_version,
            "index_version": metric_info.meta_version,
        }

    async def ensure_collection(self) -> None:
        """确保指标向量集合存在"""
        if not await self._client.collection_exists(self._collection_name):
            await self._client.create_collection(
                self._collection_name,
                vectors_config=VectorParams(
                    size=cfg.qdrant.embedding_size, distance=Distance.COSINE
                ),
            )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        payloads: list[MetricInfo],
        batch_size: int = 20,
    ) -> None:
        """批量写入指标向量"""
        zipped = list(zip(ids, embeddings, payloads))
        for i in range(0, len(zipped), batch_size):
            batch = zipped[i : i + batch_size]
            batch_points = [
                PointStruct(
                    id=id,
                    vector=embedding,
                    payload=self._to_payload(payload),
                )
                for id, embedding, payload in batch
            ]
            await self._client.upsert(
                collection_name=self._collection_name, points=batch_points
            )

    async def delete_by_name(self, metric_name: str) -> None:
        """删除指标对应的全部向量"""
        if not await self._client.collection_exists(self._collection_name):
            return
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="name", match=MatchValue(value=metric_name)),
                ]
            ),
        )

    async def search(
        self, embedding: list[float], score_threshold: float = 0.6, limit: int = 5
    ) -> list[MetricInfo]:
        """根据向量检索指标信息"""
        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=embedding,
            score_threshold=score_threshold,
            limit=limit,
        )
        metric_infos: list[MetricInfo] = []
        for point in result.points:
            payload: Any = point.payload
            if not isinstance(payload, dict):
                continue
            metric_infos.append(MetricInfo(**payload))
        return metric_infos
