"""数据库管理 — 引擎、会话工厂、FastAPI 依赖、上下文管理器"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import MySQLCfg, cfg

ENGINE_KWARGS_MAP: dict[str, object] = {
    "echo": False,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    "pool_timeout": 30,
}


class DatabaseManager:
    """数据库管理器"""

    def __init__(self) -> None:
        self._url: str | None = None
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    def _get_engine(self, db_url: str, db_driver: str) -> AsyncEngine:
        """获取或创建数据库引擎"""
        if self._engine is None:
            self._engine = create_async_engine(db_url, **ENGINE_KWARGS_MAP)
        return self._engine

    def _get_session_maker(
        self, db_url: str, db_driver: str
    ) -> async_sessionmaker[AsyncSession]:
        """获取或创建会话工厂"""
        if self._session_maker is None:
            engine = self._get_engine(db_url, db_driver)
            self._session_maker = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_maker

    @asynccontextmanager
    async def session(
        self, db_url: str, db_driver: str
    ) -> AsyncGenerator[AsyncSession]:
        """创建数据库会话上下文"""
        session_maker = self._get_session_maker(db_url, db_driver)
        async with session_maker() as db_session:
            yield db_session

    async def close_all(self) -> None:
        """关闭所有数据库引擎"""
        for engine in self._engine.values():
            await engine.dispose()
        self._engine.clear()
        self._session_maker.clear()


def _get_db_url(db_cfg: MySQLCfg) -> str:
    """获取数据库连接 URL"""
    return (
        f"mysql+asyncmy://{db_cfg.user}:{db_cfg.password}@"
        f"{db_cfg.host}:{db_cfg.port}/{db_cfg.database}"
    )


_db_manager = DatabaseManager()

_db_cfg = cfg.db.configs[cfg.db.driver]
_db_driver = cfg.db.driver
_db_url = _get_db_url(_db_cfg, _db_driver)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖 — 请求级数据库会话，自动关闭"""
    async with _db_manager.session(_db_url, _db_driver) as db_session:
        yield db_session


def get_db_session():
    """获取数据库会话上下文 — 用于后台任务等非请求场景"""
    return _db_manager.session(_db_url, _db_driver)


async def close_db() -> None:
    """关闭所有数据库引擎"""
    await _db_manager.close_all()
