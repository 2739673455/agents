"""字段向量数据访问"""

from dataclasses import asdict
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.conf.app_config import cfg
from app.entities.column_info import ColumnInfo


class ColumnQdrantRepo:
    """字段向量存储"""

    _collection_name = "data-agent-column"

    def __init__(self, client: AsyncQdrantClient) -> None:
        """初始化字段向量存储"""
        self._client = client

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
                PointStruct(id=id, vector=embedding, payload=asdict(payload))
                for id, embedding, payload in batch
            ]
            await self._client.upsert(
                collection_name=self._collection_name, points=batch_points
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
