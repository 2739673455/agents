from typing import cast

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.types import ExceptionHandler

from app.conf.app_config import cfg
from app.core.exceptions import base, exc_handlers
from app.core.lifespan import lifespan
from app.core.middlewares import trace
from app.routes import api


def register_routes(app: FastAPI) -> None:
    """注册接口"""
    app.include_router(api.v1.chat.router, prefix="/api/v1/chat")
    app.include_router(
        api.v1.attachment.router,
        prefix="/api/v1/chat/attachment",
    )


def register_middlewares(app: FastAPI) -> None:
    """注册中间件"""
    app.middleware("http")(trace.middleware)


def register_exception_handlers(app: FastAPI) -> None:
    """注册异常处理器"""
    app.add_exception_handler(
        base.ProblemError,
        cast(ExceptionHandler, exc_handlers.problem_error_handler),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, exc_handlers.validation_error_handler),
    )
    app.add_exception_handler(
        HTTPException,
        cast(ExceptionHandler, exc_handlers.http_exception_handler),
    )
    app.add_exception_handler(
        Exception,
        cast(ExceptionHandler, exc_handlers.unhandled_exception_handler),
    )


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
