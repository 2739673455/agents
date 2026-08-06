"""Redis 会话目录数据访问测试"""

import unittest
from datetime import UTC, datetime
from typing import Any, cast

from langgraph.store.base import Item, SearchItem
from langgraph.store.redis.aio import AsyncRedisStore

from app.repositories.conversation_redis_repo import ConversationRedisRepo


class _FakeConversationStore:
    """内存会话目录存储"""

    def __init__(self) -> None:
        self.items: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}

    async def aput(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
        index: bool | None = None,
    ) -> None:
        self.items[(namespace, key)] = value

    async def aget(self, namespace: tuple[str, ...], key: str) -> Item | None:
        value = self.items.get((namespace, key))
        if value is None:
            return None
        now = datetime.now(UTC)
        return Item(
            namespace=namespace,
            key=key,
            value=value,
            created_at=now,
            updated_at=now,
        )

    async def asearch(
        self,
        namespace: tuple[str, ...],
        *,
        limit: int,
    ) -> list[SearchItem]:
        now = datetime.now(UTC)
        return [
            SearchItem(
                namespace=item_namespace,
                key=key,
                value=value,
                created_at=now,
                updated_at=now,
            )
            for (item_namespace, key), value in self.items.items()
            if item_namespace == namespace
        ][:limit]

    async def adelete(self, namespace: tuple[str, ...], key: str) -> None:
        self.items.pop((namespace, key), None)


class ConversationRedisRepoTest(unittest.IsolatedAsyncioTestCase):
    """验证 Redis 会话目录行为"""

    def setUp(self) -> None:
        store = cast(AsyncRedisStore, _FakeConversationStore())
        self.repo = ConversationRedisRepo(store)

    async def test_conversation_is_isolated_by_user(self) -> None:
        """会话只能从所属用户命名空间读取"""
        conversation = await self.repo.create(1, "新对话")

        self.assertEqual(await self.repo.get(1, conversation.id), conversation)
        self.assertIsNone(await self.repo.get(2, conversation.id))

    async def test_list_excludes_drafts_and_orders_by_update_time(self) -> None:
        """会话列表排除草稿并按最后活动时间倒序排列"""
        first = await self.repo.create(1, "对话一")
        second = await self.repo.create(1, "对话二")
        await self.repo.create(1, "草稿", is_draft=True)
        updated_first = await self.repo.update(first, title="已更新")

        conversations = await self.repo.list_by_user(1)

        self.assertEqual(
            [conversation.id for conversation in conversations],
            [updated_first.id, second.id],
        )
        self.assertEqual(conversations[0].title, "已更新")

    async def test_delete_removes_conversation(self) -> None:
        """删除后会话目录不再存在"""
        conversation = await self.repo.create(1, "待删除")

        await self.repo.delete(1, conversation.id)

        self.assertIsNone(await self.repo.get(1, conversation.id))
