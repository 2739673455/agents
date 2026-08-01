"""字段向量数据访问"""

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
from app.entities.meta import ColumnInfo


class ColumnQdrantRepo:
    """字段向量存储"""

    _collection_name = "data-agent-column"

    def __init__(self, client: AsyncQdrantClient) -> None:
        """初始化字段向量存储"""
        self._client = client

    @staticmethod
    def _to_payload(column_info: ColumnInfo) -> dict[str, Any]:
        """将字段 ORM 转换为向量载荷"""
        return {
            "id": column_info.id,
            "name": column_info.name,
            "type": column_info.type,
            "examples": column_info.examples,
            "description": column_info.description,
            "alias": column_info.alias,
            "index_values": column_info.index_values,
            "reference_column_id": column_info.reference_column_id,
            "table_id": column_info.table_id,
        }

    async def ensure_collection(self) -> None:
        """确保字段向量集合存在"""
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
        payloads: list[ColumnInfo],
        batch_size: int = 20,
    ) -> None:
        """批量写入字段向量"""
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

    async def delete_by_id(self, column_id: str) -> None:
        """删除字段对应的全部向量"""
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="id", match=MatchValue(value=column_id)),
                ]
            ),
        )

    async def search(
        self, embedding: list[float], score_threshold: float = 0.6, limit: int = 5
    ) -> list[ColumnInfo]:
        """根据向量检索字段信息"""
        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=embedding,
            score_threshold=score_threshold,
            limit=limit,
        )
        column_infos: list[ColumnInfo] = []
        for point in result.points:
            payload: Any = point.payload
            if not isinstance(payload, dict):
                continue
            column_infos.append(ColumnInfo(**payload))
        return column_infos
