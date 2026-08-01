"""WebSocket 临时令牌数据访问"""

from pydantic import BaseModel
from redis.asyncio import Redis


class WebSocketTokenData(BaseModel):
    """WebSocket 临时令牌数据"""

    user_id: int


class WebSocketTokenRedisRepo:
    """WebSocket 临时令牌存储"""

    _key_pattern = "ws_token:{token}"

    def __init__(self, client: Redis) -> None:
        """初始化 WebSocket 临时令牌存储"""
        self._client = client

    def _make_key(self, token: str) -> str:
        """构造 WebSocket 临时令牌键"""
        return self._key_pattern.format(token=token)

    async def create(self, token: str, user_id: int, expire_seconds: int) -> None:
        """创建 WebSocket 临时令牌"""
        key = self._make_key(token)
        data = WebSocketTokenData(user_id=user_id)
        await self._client.setex(key, expire_seconds, data.model_dump_json())

    async def consume(self, token: str) -> WebSocketTokenData | None:
        """消费 WebSocket 临时令牌"""
        data = await self._client.getdel(self._make_key(token))
        if data is None:
            return None
        return WebSocketTokenData.model_validate_json(data)
