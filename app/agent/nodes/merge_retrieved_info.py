from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import (
    ColumnInfoState,
    DataAgentState,
    MetricInfoState,
    TableInfoState,
)
from app.core.log import logger
from app.entities.meta import ColumnInfo, TableInfo


async def merge_retrieved_info(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})

    # 已召回信息
    retrieved_columns = state["retrieved_columns"]
    retrieved_values = state["retrieved_values"]
    retrieved_metrics = state["retrieved_metrics"]

    # 获取所需依赖
    meta_mysql_repository = runtime.context["meta_mysql_repository"]

    retrieved_columns_map: dict[tuple[str, str], ColumnInfo] = {
        (retrieved_column.t_name, retrieved_column.name): retrieved_column
        for retrieved_column in retrieved_columns
    }

    # 合并表格信息
    table_infos: list[TableInfoState] = []

    try:
        # 将指标信息的相关字段加入字段信息列表
        for retrieved_metric in retrieved_metrics:
            relevant_columns = retrieved_metric.relevant_columns
            for relevant_column in relevant_columns:
                column_key = (
                    relevant_column["t_name"],
                    relevant_column["c_name"],
                )
                if column_key not in retrieved_columns_map:
                    column_info = await meta_mysql_repository.get_column_info(
                        *column_key
                    )
                    retrieved_columns_map[column_key] = column_info

        # 将字段取值合并到字段信息列表
        for retrieved_value in retrieved_values:
            column_key = (
                retrieved_value.t_name,
                retrieved_value.c_name,
            )
            column_value = retrieved_value.value
            if column_key not in retrieved_columns_map:
                column_info = await meta_mysql_repository.get_column_info(*column_key)
                retrieved_columns_map[column_key] = column_info
            if column_value not in retrieved_columns_map[column_key].examples:
                retrieved_columns_map[column_key].examples.append(column_value)

        # 按照字段所属的表名进行分组
        table_to_columns_map: dict[str, list[ColumnInfo]] = {}
        for column in retrieved_columns_map.values():
            table_to_columns_map.setdefault(column.t_name, []).append(column)

        # 显式的添加每个表的主外键
        for t_name, columns in table_to_columns_map.items():
            # 查询主外键字段
            key_columns: list[
                ColumnInfo
            ] = await meta_mysql_repository.get_key_columns_by_table_name(t_name)

            # 当前表已有的所有字段联合主键
            column_keys = {(column.t_name, column.name) for column in columns}

            for key_column in key_columns:
                if (key_column.t_name, key_column.name) not in column_keys:
                    columns.append(key_column)

        # 补充外键引用的目标字段及其所属表
        known_column_keys = {
            (column.t_name, column.name)
            for columns in table_to_columns_map.values()
            for column in columns
        }
        reference_column_keys = {
            (column.reference_t_name, column.reference_c_name)
            for columns in table_to_columns_map.values()
            for column in columns
            if column.reference_t_name and column.reference_c_name
        }
        for reference_column_key in sorted(reference_column_keys - known_column_keys):
            reference_column = await meta_mysql_repository.get_column_info(
                *reference_column_key
            )
            table_to_columns_map.setdefault(reference_column.t_name, []).append(
                reference_column
            )

        # 将表名和字段映射转换为表信息列表
        for t_name, columns in table_to_columns_map.items():
            table: TableInfo = await meta_mysql_repository.get_table_info(t_name)
            columns = [
                ColumnInfoState(
                    name=column.name,
                    type=column.type,
                    examples=column.examples,
                    description=column.description,
                    alias=column.alias,
                    reference_t_name=column.reference_t_name,
                    reference_c_name=column.reference_c_name,
                )
                for column in columns
            ]
            table_info_state = TableInfoState(
                name=table.name,
                role=table.role,
                primary_key_columns=table.primary_key_columns,
                description=table.description,
                columns=columns,
            )
            table_infos.append(table_info_state)

        # 处理指标信息
        metric_infos: list[MetricInfoState] = [
            MetricInfoState(
                name=metric_info.name,
                description=metric_info.description,
                relevant_columns=metric_info.relevant_columns,
                alias=metric_info.alias,
            )
            for metric_info in retrieved_metrics
        ]

        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        logger.info(
            f"合并召回信息: 表信息-{[table_info['name'] for table_info in table_infos]},指标信息-{[metric_info['name'] for metric_info in metric_infos]}"
        )

        return {"table_infos": table_infos, "metric_infos": metric_infos}
    except Exception as e:
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        logger.error(f"合并召回信息失败: {e!s}")
        raise
