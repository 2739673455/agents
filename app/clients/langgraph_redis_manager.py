"""LangGraph Redis 持久化客户端管理"""

from urllib.parse import quote

from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.store.redis.aio import AsyncRedisStore

from app.conf.app_config import RedisCfg, cfg


class LangGraphRedisManager:
    """LangGraph Redis Checkpointer 和 Store 生命周期管理器"""

    def __init__(self, redis_config: RedisCfg) -> None:
        """初始化 Redis 持久化配置"""
        self._redis_config = redis_config
        self._checkpointer: AsyncRedisSaver | None = None
        self._store: AsyncRedisStore | None = None

    @property
    def _url(self) -> str:
        """构造 Redis 连接 URL"""
        password = self._redis_config.password
        auth = f":{quote(password, safe='')}@" if password else ""
        return (
            f"redis://{auth}{self._redis_config.host}:"
            f"{self._redis_config.port}/{self._redis_config.db}"
        )

    async def init(self) -> None:
        """初始化 LangGraph Redis 持久化组件"""
        checkpointer = AsyncRedisSaver(
            redis_url=self._url,
            checkpoint_prefix="insight_checkpoint",
            checkpoint_write_prefix="insight_checkpoint_write",
        )
        store = AsyncRedisStore(
            redis_url=self._url,
            store_prefix="insight_store",
            vector_prefix="insight_store_vector",
        )

        await checkpointer.__aenter__()
        try:
            await store.__aenter__()
            await store.setup()
        except Exception:
            await store.__aexit__(None, None, None)
            await checkpointer.__aexit__(None, None, None)
            raise

        self._checkpointer = checkpointer
        self._store = store

    def get_checkpointer(self) -> AsyncRedisSaver:
        """获取已初始化的 Checkpointer"""
        if self._checkpointer is None:
            raise RuntimeError("LangGraph Redis manager is not initialized")
        return self._checkpointer

    def get_store(self) -> AsyncRedisStore:
        """获取已初始化的 Store"""
        if self._store is None:
            raise RuntimeError("LangGraph Redis manager is not initialized")
        return self._store

    async def delete_thread(self, thread_id: str) -> None:
        """删除会话线程的全部 Checkpoint"""
        await self.get_checkpointer().adelete_thread(thread_id)

    async def close(self) -> None:
        """关闭 LangGraph Redis 持久化组件"""
        if self._store is not None:
            await self._store.__aexit__(None, None, None)
        if self._checkpointer is not None:
            await self._checkpointer.__aexit__(None, None, None)
        self._store = None
        self._checkpointer = None


langgraph_redis_manager = LangGraphRedisManager(cfg.redis)
