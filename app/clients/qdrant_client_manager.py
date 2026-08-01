"""Qdrant 客户端管理"""

from qdrant_client import AsyncQdrantClient

from app.conf.app_config import QdrantConfig, cfg


class QdrantClientManager:
    """Qdrant 客户端管理器"""

    def __init__(self, qdrant_config: QdrantConfig) -> None:
        """初始化 Qdrant 客户端管理器"""
        self._qdrant_config = qdrant_config
        self._client: AsyncQdrantClient | None = None

    @property
    def _url(self) -> str:
        """获取 Qdrant 连接 URL"""
        return f"http://{self._qdrant_config.host}:{self._qdrant_config.port}"

    def init(self) -> None:
        """初始化 Qdrant 客户端"""
        self._client = AsyncQdrantClient(url=self._url)

    def get_client(self) -> AsyncQdrantClient:
        """获取 Qdrant 客户端"""
        if self._client is None:
            raise RuntimeError("Qdrant client manager is not initialized")
        return self._client

    async def close(self) -> None:
        """关闭 Qdrant 客户端并释放资源"""
        if self._client is not None:
            await self._client.close()
        self._client = None


qdrant_client_manager = QdrantClientManager(cfg.qdrant)

if __name__ == "__main__":
    import asyncio
    import random

    from qdrant_client import models

    qdrant_client_manager.init()

    async def test() -> None:
        try:
            client = qdrant_client_manager.get_client()
            if not await client.collection_exists("my_collection"):
                await client.create_collection(
                    collection_name="my_collection",
                    vectors_config=models.VectorParams(
                        size=10,
                        distance=models.Distance.COSINE,
                    ),
                )

            await client.upsert(
                collection_name="my_collection",
                points=[
                    models.PointStruct(
                        id=i,
                        vector=[random.random() for _ in range(10)],
                    )
                    for i in range(100)
                ],
            )

            res = await client.query_points(
                collection_name="my_collection",
                query=[random.random() for _ in range(10)],
                limit=10,
                score_threshold=0.8,
            )

            print(res)
        finally:
            await qdrant_client_manager.close()

    asyncio.run(test())
