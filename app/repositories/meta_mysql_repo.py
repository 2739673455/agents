"""元数据访问"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.mappers.column_info_mapper import ColumnInfoMapper
from app.mappers.column_metric_mapper import ColumnMetricMapper
from app.mappers.metric_info_mapper import MetricInfoMapper
from app.mappers.table_info_mapper import TableInfoMapper
from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.table_info_mysql import TableInfoMySQL


class MetaMySQLRepo:
    """元数据存储"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化元数据存储"""
        self._session = session

    def transaction(self) -> AsyncSessionTransaction:
        """创建事务上下文"""
        return self._session.begin()

    async def save_table_infos(self, table_infos: list[TableInfo]) -> None:
        """保存表信息"""
        models = [TableInfoMapper.to_model(table_info) for table_info in table_infos]
        self._session.add_all(models)

    async def save_column_infos(self, columns_info: list[ColumnInfo]) -> None:
        """保存字段信息"""
        models = [
            ColumnInfoMapper.to_model(column_info) for column_info in columns_info
        ]
        self._session.add_all(models)

    async def save_metric_infos(self, metric_infos: list[MetricInfo]) -> None:
        """保存指标信息"""
        self._session.add_all(
            [MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos]
        )

    async def save_column_metrics(self, column_metrics: list[ColumnMetric]) -> None:
        """保存字段与指标的关联关系"""
        self._session.add_all(
            [
                ColumnMetricMapper.to_model(column_metric)
                for column_metric in column_metrics
            ]
        )

    async def get_column_info_by_id(self, column_id: str) -> ColumnInfo:
        """根据编号获取字段信息"""
        result: ColumnInfoMySQL | None = await self._session.get(
            ColumnInfoMySQL, column_id
        )
        if result:
            return ColumnInfoMapper.to_entity(result)
        raise ValueError(f"Column info not found: {column_id}")

    async def get_table_info_by_id(self, table_id: str) -> TableInfo:
        """根据编号获取表信息"""
        result: TableInfoMySQL | None = await self._session.get(
            TableInfoMySQL, table_id
        )
        if result:
            return TableInfoMapper.to_entity(result)
        raise ValueError(f"Table info not found: {table_id}")

    async def get_key_columns_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        """获取表的主键和外键字段"""
        sql = """
            select *
            from column_info
            where table_id = :table_id
            and role in ('primary_key', 'foreign_key')
        """
        result = await self._session.execute(text(sql), {"table_id": table_id})
        return [ColumnInfo(**row) for row in result.mappings().fetchall()]
