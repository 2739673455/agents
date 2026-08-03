"""业务数据访问"""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SourceMySQLRepo:
    """业务数据存储"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化业务数据存储"""
        self._session = session

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """校验并引用数据库标识符"""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", identifier):
            raise ValueError(f"Invalid database identifier: {identifier}")
        return f"`{identifier}`"

    async def table_exists(self, table_name: str) -> bool:
        """判断当前数据库中是否存在指定表"""
        result = await self._session.execute(
            text(
                """
                select exists(
                    select 1
                    from information_schema.tables
                    where table_schema = database()
                      and table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
        return bool(result.scalar())

    async def get_primary_key_columns(self, table_name: str) -> list[str]:
        """按定义顺序获取表的主键字段"""
        result = await self._session.execute(
            text(
                """
                select column_name
                from information_schema.key_column_usage
                where table_schema = database()
                  and table_name = :table_name
                  and constraint_name = 'PRIMARY'
                order by ordinal_position
                """
            ),
            {"table_name": table_name},
        )
        return list(result.scalars().fetchall())

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """获取表的字段类型"""
        table_identifier = self._quote_identifier(table_name)
        sql = f"show columns from {table_identifier}"
        result = await self._session.execute(text(sql))
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(
        self,
        table_name: str,
        column_name: str,
        limit: int | None = None,
    ) -> list:
        """获取字段的去重取值"""
        table_identifier = self._quote_identifier(table_name)
        column_identifier = self._quote_identifier(column_name)
        sql = f"select distinct {column_identifier} from {table_identifier}"
        if limit is not None:
            sql = f"{sql} limit {limit}"
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
