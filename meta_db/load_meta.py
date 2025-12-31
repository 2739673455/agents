import asyncio
from dataclasses import dataclass

from db_pool import get_session
from loguru import logger
from sqlalchemy import inspect, text

from ..config import DB_CONF, DBCfg, KnowledgeCfg, TableCfg


@dataclass
class ColumnInfo:
    """字段信息"""

    name: str  # 字段名
    data_type: str  # 数据类型
    comment: str | None  # 注释
    relation: str | None  # 关联关系


async def load_meta():
    """加载元数据"""
    tb_info_list: list[dict] = []
    tb_col_list: list[dict] = []
    kn_list: list[dict] = []
    for db_code, db_conf in DB_CONF.items():
        if db_conf.table:
            # 加载表配置
            for tb_code, tb_conf in db_conf.table.items():
                # 获取表信息
                try:
                    tb_info = await get_tb_info(db_conf, tb_code, tb_conf)
                    logger.info(f"{db_conf.db_code}.{tb_code} load table info")
                except Exception as e:
                    logger.exception(f"{db_code}.{tb_code} load table info error: {e}")
                    continue
                # 获取字段示例数据
                try:
                    fewshot = await get_fewshot(db_conf, tb_conf)
                    logger.info(f"{db_conf.db_code}.{tb_code} load fewshot")
                except Exception as e:
                    logger.exception(f"{db_code}.{tb_code} load fewshot error: {e}")
                    continue
                # 获取表的字段属性
                try:
                    columns = await get_column(db_conf, tb_code, tb_conf)
                    logger.info(
                        f"{db_conf.db_code}.{tb_code} load column ({len(columns)})"
                    )
                except Exception as e:
                    logger.exception(f"{db_code}.{tb_code} load column error: {e}")
                    continue
                # 合并字段信息
                try:
                    tb_cols = await merge_tb_col(tb_code, tb_conf, columns, fewshot)
                except Exception as e:
                    logger.exception(f"{db_code}.{tb_code} merge column error: {e}")
                    continue

                tb_info_list.append(tb_info)
                tb_col_list.extend(tb_cols)

        if db_conf.knowledge:
            # 获取指标知识
            try:
                knowledges = await get_knowledge(db_conf, db_conf.knowledge)
                logger.info(f"{db_conf.db_code} load knowledge ({len(knowledges)})")
                kn_list.extend(knowledges)
            except Exception as e:
                logger.exception(f"{db_code} load knowledge error: {e}")
    return tb_info_list, tb_col_list, kn_list


async def get_tb_info(db_conf: DBCfg, tb_code: str, tb_conf: TableCfg) -> dict:
    """获取表信息"""
    return {
        "db_code": db_conf.db_code,  # 数据库编号
        "db_name": db_conf.db_name,  # 数据库名称
        "db_type": db_conf.db_type,  # 数据库类型
        "database": db_conf.database,  # 数据库
        "tb_code": tb_code,  # 表编号
        "tb_name": tb_conf.tb_name,  # 表名
        "tb_meaning": tb_conf.tb_meaning,  # 表含义
    }


async def get_fewshot(db_conf: DBCfg, tb_info: TableCfg) -> dict[str, set[str]]:
    """查询字段示例数据，返回字段名到示例值的映射"""
    fewshot_sql = "SELECT * FROM %s LIMIT 10000" % tb_info.tb_name
    async with get_session(db_conf) as session:
        result = await session.execute(text(fewshot_sql))  # 执行查询获取示例数据
        column_names = result.keys()  # 获取所有列名
        # 构建列名到示例值的映射 {"column1": ("value1", "value2", ...)}
        column_value_map = {col: set() for col in column_names}
        pending_cols = set(column_names)  # 记录未收集满 5 个值的列
        for row in result.mappings():  # 遍历每一行数据，收集各列的示例值
            for col in list(pending_cols):  # 遍历每一列
                cell = row[col]
                # 跳过 NULL 和空字符串
                if cell is None or (isinstance(cell, str) and not cell.strip()):
                    continue
                # 统一转换为字符串格式存储，截取前 300 个字符，添加到示例值集合
                column_value_map[col].add(str(cell)[:300])
                # 剔除已收集满 5 个值的列
                if len(column_value_map[col]) >= 5:
                    pending_cols.remove(col)
            # 如果所有列都已收集满 5 个值，结束
            if not pending_cols:
                break
    return column_value_map


async def get_column(db_conf: DBCfg, tb_code: str, tb_info: TableCfg) -> list[dict]:
    """获取字段属性"""

    def get_info_sync(sync_session):
        inspector = inspect(sync_session.bind)
        cols = inspector.get_columns(tb_info.tb_name)  # 获取所有列
        fks = inspector.get_foreign_keys(tb_info.tb_name)  # 获取所有外键
        return cols, fks

    async with get_session(db_conf) as session:
        cols, fks = await session.run_sync(get_info_sync)
        # 创建 col_name->column 映射
        name_column_map = {
            c["name"]: {
                "name": c["name"],  # 字段名
                "data_type": c["type"],  # 数据类型
                "comment": c["comment"],  # 字段注释
                "relation": None,  # 关联关系
            }
            for c in cols
        }
        # 添加关联关系
        for fk in fks:
            for col_name, ref_name in zip(
                fk["constrained_columns"], fk["referred_columns"]
            ):
                rel_col = f"{fk['referred_table']}.{ref_name}"
                name_column_map[col_name]["relation"] = rel_col

        columns = list(name_column_map.values())
    return columns


async def merge_tb_col(
    tb_code: str, tb_info: TableCfg, columns: list[dict], fewshot: dict[str, set[str]]
) -> list[dict]:
    """整合 表信息、字段属性、字段示例数据"""
    col_info_map = tb_info.col_info or {}
    # 初始化表字段信息列表
    tb_cols: list[dict] = []
    # 遍历所有表字段
    for column in columns:
        col_info = col_info_map.get(column["name"])
        column = {
            "tb_code": tb_code,  # 表编号
            "col_name": column["name"],  # 字段名称
            "col_type": str(column["data_type"]),  # 数据类型
            "col_comment": column["comment"],  # 字段注释
            "fewshot": list(fewshot.get(column["name"], set())),  # 示例数据
            "col_meaning": col_info.col_meaning if col_info else None,  # 字段含义
            "field_meaning": col_info.field_meaning
            if col_info
            else None,  # JSONB字段含义
            "col_alias": col_info.col_alias if col_info else None,  # 字段别名
            "rel_col": (col_info.rel_col if col_info else None)
            or column["relation"],  # 关联关系，优先使用配置中的关联关系
        }
        tb_cols.append(column)
    return tb_cols


async def get_knowledge(db_conf: DBCfg, kn_map: dict[int, KnowledgeCfg]):
    """获取知识信息"""
    return [
        {
            **kn.__dict__,
            "db_code": db_conf.db_code,
            "kn_code": kn_code,
        }
        for kn_code, kn in kn_map.items()
    ]


if __name__ == "__main__":
    asyncio.run(load_meta())
