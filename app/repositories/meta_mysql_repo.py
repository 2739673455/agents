"""元数据访问"""

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from app.entities.meta import ColumnInfo, ColumnMetric, MetricInfo, TableInfo
from app.errors import meta_error


class MetaMySQLRepo:
    """元数据存储"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化元数据存储"""
        self._session = session

    def transaction(self) -> AsyncSessionTransaction:
        """创建事务上下文"""
        return self._session.begin()

    async def upsert_table_info(self, table_info: TableInfo) -> None:
        """新增或更新表信息"""
        await self._session.merge(table_info)

    async def upsert_column_info(self, column_info: ColumnInfo) -> None:
        """新增或更新字段信息"""
        await self._session.merge(column_info)

    async def upsert_metric_info(self, metric_info: MetricInfo) -> None:
        """新增或更新指标信息及字段关联"""
        await self._session.merge(metric_info)
        await self._session.execute(
            delete(ColumnMetric).where(ColumnMetric.metric_id == metric_info.id)
        )
        self._session.add_all(
            [
                ColumnMetric(column_id=column_id, metric_id=metric_info.id)
                for column_id in dict.fromkeys(metric_info.relevant_columns)
            ]
        )

    async def list_table_infos(self) -> list[TableInfo]:
        """获取全部表信息"""
        result = await self._session.scalars(select(TableInfo).order_by(TableInfo.id))
        return list(result.all())

    async def list_column_infos(self) -> list[ColumnInfo]:
        """获取全部字段信息"""
        result = await self._session.scalars(select(ColumnInfo).order_by(ColumnInfo.id))
        return list(result.all())

    async def list_metric_infos(self) -> list[MetricInfo]:
        """获取全部指标信息"""
        result = await self._session.scalars(select(MetricInfo).order_by(MetricInfo.id))
        return list(result.all())

    async def delete_metric_infos(self, metric_ids: list[str]) -> None:
        """删除指标信息及字段关联"""
        if not metric_ids:
            return
        await self._session.execute(
            delete(ColumnMetric).where(ColumnMetric.metric_id.in_(metric_ids))
        )
        await self._session.execute(
            delete(MetricInfo).where(MetricInfo.id.in_(metric_ids))
        )

    async def delete_column_infos(self, column_ids: list[str]) -> None:
        """删除字段信息及指标关联"""
        if not column_ids:
            return
        await self._session.execute(
            delete(ColumnMetric).where(ColumnMetric.column_id.in_(column_ids))
        )
        await self._session.execute(
            delete(ColumnInfo).where(ColumnInfo.id.in_(column_ids))
        )

    async def delete_table_infos(self, table_ids: list[str]) -> None:
        """删除表信息"""
        if not table_ids:
            return
        await self._session.execute(
            delete(TableInfo).where(TableInfo.id.in_(table_ids))
        )

    async def get_column_info_by_id(self, column_id: str) -> ColumnInfo:
        """根据编号获取字段信息"""
        result = await self._session.get(ColumnInfo, column_id)
        if result:
            return result
        raise meta_error.MetadataNotFoundError(
            detail=f"Column info not found: {column_id}"
        )

    async def get_table_info_by_id(self, table_id: str) -> TableInfo:
        """根据编号获取表信息"""
        result = await self._session.get(TableInfo, table_id)
        if result:
            return result
        raise meta_error.MetadataNotFoundError(
            detail=f"Table info not found: {table_id}"
        )

    async def get_metric_info_by_id(self, metric_id: str) -> MetricInfo:
        """根据编号获取指标信息"""
        result = await self._session.get(MetricInfo, metric_id)
        if result:
            return result
        raise meta_error.MetadataNotFoundError(
            detail=f"Metric info not found: {metric_id}"
        )

    async def get_columns_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        """获取表的全部字段信息"""
        result = await self._session.scalars(
            select(ColumnInfo).where(ColumnInfo.table_id == table_id)
        )
        return list(result.all())

    async def get_key_columns_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        """获取表的主键和外键字段"""
        table_info = await self.get_table_info_by_id(table_id)
        result = await self._session.scalars(
            select(ColumnInfo).where(
                ColumnInfo.table_id == table_id,
                or_(
                    ColumnInfo.name.in_(table_info.primary_key_columns),
                    ColumnInfo.reference_column_id.is_not(None),
                ),
            )
        )
        return list(result.all())
