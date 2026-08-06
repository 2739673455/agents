"""聊天接口依赖"""

from typing import Annotated

from fastapi import Depends

from app.clients.langgraph_redis_manager import langgraph_redis_manager
from app.repositories.conversation_redis_repo import ConversationRedisRepo


def get_conversation_repo() -> ConversationRedisRepo:
    """创建会话目录数据访问"""
    return ConversationRedisRepo(langgraph_redis_manager.get_store())


ConversationRepoDep = Annotated[
    ConversationRedisRepo,
    Depends(get_conversation_repo),
]
