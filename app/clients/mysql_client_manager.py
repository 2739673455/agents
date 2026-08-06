"""MySQL 协议数据库客户端管理"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.app_config import DBConfig, cfg


class MysqlClientManager:
    """MySQL 客户端管理器"""

    def __init__(self, db_config: DBConfig) -> None:
        """初始化 MySQL 客户端管理器"""
        self._db_config = db_config
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    @property
    def _url(self) -> str:
        """获取异步数据库连接 URL"""
        return (
            f"mysql+asyncmy://{self._db_config.user}:{self._db_config.password}@"
            f"{self._db_config.host}:{self._db_config.port}/{self._db_config.database}"
        )

    def init(self) -> None:
        """初始化数据库引擎和会话工厂"""
        self._engine = create_async_engine(
            self._url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
        )
        self._session_maker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """获取数据库会话工厂"""
        if self._session_maker is None:
            raise RuntimeError("MySQL client manager is not initialized")
        return self._session_maker

    def session(self) -> AsyncSession:
        """创建数据库会话"""
        return self._get_session_maker()()

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """获取 FastAPI 请求级数据库会话"""
        async with self.session() as db_session:
            yield db_session

    async def close(self) -> None:
        """关闭数据库引擎并释放资源"""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._session_maker = None


meta_mysql_client_manager = MysqlClientManager(cfg.db_meta)

if __name__ == "__main__":
    import asyncio

    from sqlalchemy import text

    meta_mysql_client_manager.init()

    async def test() -> None:
        try:
            async with meta_mysql_client_manager.session() as session:
                result = await session.execute(
                    text("select * from table_info limit 10")
                )
                rows = result.fetchall()
                print(rows)
        finally:
            await meta_mysql_client_manager.close()

    asyncio.run(test())
