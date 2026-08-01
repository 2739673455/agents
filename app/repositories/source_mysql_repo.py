"""业务数据访问"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SourceMySQLRepo:
    """业务数据存储"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化业务数据存储"""
        self._session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """获取表的字段类型"""
        sql = f"show columns from {table_name}"
        result = await self._session.execute(text(sql))
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(
        self, table_name: str, column_name: str, limit: int
    ) -> list:
        """获取字段的去重取值"""
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self._session.execute(text(sql))
        return list(result.scalars().fetchall())

    async def get_db_info(self) -> dict[str, str]:
        """获取数据库版本和方言信息"""
        result = await self._session.execute(text("select version()"))
        version = str(result.scalar())

        dialect = self._session.get_bind().dialect.name

        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql: str) -> None:
        """通过执行计划验证 SQL"""
        await self._session.execute(text(f"explain {sql}"))

    async def execute_sql(self, sql: str) -> list[dict]:
        """执行 SQL 并返回行数据"""
        result = await self._session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]
