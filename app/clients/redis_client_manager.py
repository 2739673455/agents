"""Redis 客户端管理"""

from redis.asyncio import Redis

from app.conf.app_config import RedisCfg, cfg


class RedisClientManager:
    """Redis 客户端管理器"""

    def __init__(self, redis_config: RedisCfg) -> None:
        """初始化 Redis 客户端管理器"""
        self._redis_config = redis_config
        self._client: Redis | None = None

    def init(self) -> None:
        """初始化 Redis 客户端"""
        self._client = Redis(
            host=self._redis_config.host,
            port=self._redis_config.port,
            password=self._redis_config.password or None,
            db=self._redis_config.db,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=10,
            socket_keepalive=True,
        )

    def get_client(self) -> Redis:
        """获取 Redis 客户端"""
        if self._client is None:
            raise RuntimeError("Redis client manager is not initialized")
        return self._client

    async def close(self) -> None:
        """关闭 Redis 客户端并释放资源"""
        if self._client is not None:
            await self._client.aclose()
        self._client = None


redis_client_manager = RedisClientManager(cfg.redis)

if __name__ == "__main__":
    import asyncio

    redis_client_manager.init()

    async def test() -> None:
        try:
            client = redis_client_manager.get_client()
            result = await client.ping()
            print(result)
        finally:
            await redis_client_manager.close()

    asyncio.run(test())
