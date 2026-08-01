from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    chat_mysql_client_manager,
    meta_mysql_client_manager,
    source_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.clients.redis_client_manager import redis_client_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # FastAPI 应用启动前执行
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    redis_client_manager.init()
    meta_mysql_client_manager.init()
    source_mysql_client_manager.init()
    chat_mysql_client_manager.init()

    yield

    # FastAPI 应用结束前执行
    await embedding_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await redis_client_manager.close()
    await meta_mysql_client_manager.close()
    await source_mysql_client_manager.close()
    await chat_mysql_client_manager.close()
