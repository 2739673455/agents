import asyncio

import util
from config import DB_CFG, DBCfg, TableCfg
from db_session import get_session
from loguru import logger
from sqlalchemy import inspect, text


async def load_meta(db_codes: list[str], tb_codes: list[str]):
    """加载元数据"""
    db_info = dict[str,]
    tbs: list[dict] = []
    cols: list[dict] = []
    kns: list[dict] = []
    for db_cfg in DB_CFG.values():
        if db_cfg.table:
            # 加载表配置
            for tb_code in db_cfg.table:
                # 获取表信息
                tb_info = await get_tb_info(db_cfg, tb_code, logger)
                # 获取字段信息
                columns = await get_column(db_cfg, tb_code, logger)
                if tb_info:
                    tbs.append(tb_info)
                if columns:
                    cols.extend(columns)

        if db_cfg.knowledge:
            # 获取指标知识
            knowledges = await get_knowledge(db_cfg, logger)
            if knowledges:
                kns.extend(knowledges)
    return tbs, cols, kns


async def get_tb_info(db_conf: DBCfg, tb_code: str, logger=None) -> dict | None:
    """获取表信息"""
    try:
        if not db_conf.table:
            return None
        tb_conf = db_conf.table[tb_code]
        tb_info = {
            "db_code": db_conf.db_code,  # 数据库编号
            "db_name": db_conf.db_name,  # 数据库名称
            "db_type": db_conf.db_type,  # 数据库类型
            "database": db_conf.database,  # 数据库
            "tb_code": tb_code,  # 表编号
            "tb_name": tb_conf.tb_name,  # 表名
            "tb_meaning": tb_conf.tb_meaning,  # 表含义
            "sync_col": tb_conf.sync_col,  # 同步字段
            "no_sync_col": tb_conf.no_sync_col,  # 不同步字段
        }
        if logger:
            logger.info(f"{tb_code} load table info")
        return tb_info
    except Exception as e:
        if logger:
            logger.exception(f"{tb_code} load table info error: {e}")
        return None


async def _get_fewshot(
    session, tb_code: str, tb_cfg: TableCfg, logger=None
) -> dict[str, set[str]] | None:
    """查询字段示例数据，返回字段名到示例值的映射"""
    try:
        fewshot_sql = "SELECT * FROM %s LIMIT 10000" % tb_cfg.tb_name
        result = await session.execute(text(fewshot_sql))  # 执行查询获取示例数据
        pending_cols = set(result.keys())  # 记录未收集满 5 个值的列
        # 构建列名到示例值的映射 {"column1": ("value1", "value2", ...)}
        fewshot = {col: set() for col in pending_cols}
        for row in result.mappings():  # 遍历每一行数据，收集各列的示例值
            for col in list(pending_cols):  # 遍历每一列
                cell = row[col]
                # 跳过 NULL 和空字符串
                if cell is None or (isinstance(cell, str) and not cell.strip()):
                    continue
                # 统一转换为字符串格式存储，截取前 300 个字符，添加到示例值集合
                fewshot[col].add(str(cell)[:300])
                # 剔除已收集满 5 个值的列
                if len(fewshot[col]) >= 5:
                    pending_cols.remove(col)
            # 如果所有列都已收集满 5 个值，结束
            if not pending_cols:
                break
        if logger:
            logger.info(f"{tb_code} load fewshot")
        return fewshot
    except Exception as e:
        if logger:
            logger.exception(f"{tb_code} load fewshot error: {e}")
        return None


async def _get_column_attr(
    session, tb_code: str, tb_cfg: TableCfg, logger=None
) -> list[dict] | None:
    """获取字段属性"""

    def get_info_sync(sync_session):
        inspector = inspect(sync_session.bind)
        cols = inspector.get_columns(tb_cfg.tb_name)  # 获取所有列
        fks = inspector.get_foreign_keys(tb_cfg.tb_name)  # 获取所有外键
        return cols, fks

    try:
        cols, fks = await session.run_sync(get_info_sync)
        column_map = {
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
                column_map[col_name]["relation"] = rel_col
        columns = list(column_map.values())
        if logger:
            logger.info(f"{tb_code} load column ({len(columns)})")
        return columns
    except Exception as e:
        if logger:
            logger.exception(f"{tb_code} load column error: {e}")
        return None


async def get_column(db_cfg: DBCfg, tb_code: str, logger=None) -> list[dict] | None:
    """整合 表信息、字段属性、字段示例数据"""
    try:
        if not db_cfg.table:
            return None
        tb_cfg = db_cfg.table[tb_code]
        columns = None
        async with get_session(db_cfg) as session:
            # 获取表的字段属性
            columns = await _get_column_attr(session, tb_code, tb_cfg, logger)
            # 获取字段示例数据
            fewshot = await _get_fewshot(session, tb_code, tb_cfg, logger)
        if not columns:
            return None

        col_info_map = tb_cfg.col_info or {}
        # # 初始化表字段信息列表
        cols: list[dict] = []
        # 遍历所有表字段
        for column in columns:
            col_info = col_info_map.get(column["name"])
            _column = {
                "tb_code": tb_code,  # 表编号
                "col_name": column["name"],  # 字段名称
                "col_type": str(column["data_type"]),  # 数据类型
                "col_comment": column["comment"],  # 字段注释
                "fewshot": list(fewshot.get(column["name"], set()))
                if fewshot
                else None,  # 示例数据
                "col_meaning": col_info.col_meaning if col_info else None,  # 字段含义
                "field_meaning": col_info.field_meaning
                if col_info
                else None,  # JSONB字段含义
                "col_alias": col_info.col_alias if col_info else None,  # 字段别名
                "rel_col": (col_info.rel_col if col_info else None)
                or column["relation"],  # 关联关系，优先使用配置中的关联关系
            }
            cols.append(_column)
        return cols
    except Exception as e:
        if logger:
            logger.exception(f"{tb_code} merge column error: {e}")
        return None


async def get_knowledge(db_conf: DBCfg, logger=None) -> list[dict] | None:
    """获取知识信息"""
    try:
        if not db_conf.knowledge:
            return None
        kn = [
            {
                "db_code": db_conf.db_code,
                "kn_code": kn_code,
                "kn_name": kn.kn_name,
                "kn_desc": kn.kn_desc,
                "kn_def": kn.kn_def,
                "kn_alias": kn.kn_alias,
                "rel_kn": kn.rel_kn,
                "rel_col": kn.rel_col,
            }
            for kn_code, kn in db_conf.knowledge.items()
        ]
        if logger:
            logger.info(f"{db_conf.db_code} load knowledge ({len(kn)})")
        return kn
    except Exception as e:
        if logger:
            logger.exception(f"{db_conf.db_code} load knowledge error: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(load_meta())
