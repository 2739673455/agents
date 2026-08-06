from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.clients.doris_client_manager import source_doris_client_manager
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    chat_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.redis_client_manager import redis_client_manager
from app.conf.app_config import cfg
from app.core.middlewares import trace
from app.errors.exc_handlers import register_exception_handlers
from app.routes import api


@asynccontextmanager
async def lifespan(app: FastAPI):
    # FastAPI 应用启动前执行
    embedding_client_manager.init()
    es_client_manager.init()
    redis_client_manager.init()
    meta_mysql_client_manager.init()
    source_doris_client_manager.init()
    chat_mysql_client_manager.init()

    yield

    # FastAPI 应用结束前执行
    await embedding_client_manager.close()
    await es_client_manager.close()
    await redis_client_manager.close()
    await meta_mysql_client_manager.close()
    await source_doris_client_manager.close()
    await chat_mysql_client_manager.close()


def register_routes(app: FastAPI) -> None:
    """注册接口"""
    app.include_router(api.v1.chat.router, prefix="/api/v1/chat")
    app.include_router(
        api.v1.attachment.router,
        prefix="/api/v1/chat/attachment",
    )
    app.include_router(api.v1.meta.router, prefix="/api/v1/meta")


def register_middlewares(app: FastAPI) -> None:
    """注册中间件"""
    app.middleware("http")(trace.middleware)


def create_app() -> FastAPI:
    """创建并组装 FastAPI 应用"""
    app = FastAPI(lifespan=lifespan)
    register_middlewares(app)
    register_exception_handlers(app)
    register_routes(app)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=cfg.port)
