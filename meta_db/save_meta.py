"""
导入元数据

每个库的表信息批量存储
每个库的知识信息批量存储
每个库的字段信息批量存储
每个表的单元格信息批量存储
"""

import asyncio
import json
from typing import LiteralString, cast

import jieba.analyse
from config import DB_CFG, DBCfg, TableCfg
from db_session import get_asession, neo4j_session
from loguru import logger
from neo4j import AsyncSession
from sqlalchemy import column, inspect, select, table, text
from util import embed


def is_numeric(s) -> bool:
    """判断字符串是否为数值"""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


async def get_keywords(texts: list[str]) -> list[list[str]]:
    """获取关键词"""

    def sync_jieba() -> list[list[str]]:
        allow_pos = (
            "n",  # 名词: 数据、服务器、表格
            "nr",  # 人名: 张三、李四
            "ns",  # 地名: 北京、上海
            "nt",  # 机构团体名: 政府、学校、某公司
            "nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
            "v",  # 动词: 运行、开发
            "vn",  # 名动词: 工作、研究
            "a",  # 形容词: 美丽、快速
            "an",  # 名形词: 难度、合法性、复杂度
            "eng",  # 英文
            "i",  # 成语
            "l",  # 常用固定短语
        )
        keywords = [
            jieba.analyse.extract_tags(t, withWeight=False, allowPOS=allow_pos)
            for t in texts
        ]
        return keywords

    return await asyncio.to_thread(sync_jieba)


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
        return fewshot
    except Exception:
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


async def _get_column(db_cfg: DBCfg, tb_code: str, logger=None) -> list[dict]:
    """整合 表信息、字段属性、字段示例数据"""
    try:
        if not db_cfg.table:
            return []
        tb_cfg = db_cfg.table[tb_code]
        columns = []
        async with get_asession(db_cfg) as session:
            # 获取表的字段属性
            columns = await _get_column_attr(session, tb_code, tb_cfg, logger)
            # 获取字段示例数据
            fewshot = await _get_fewshot(session, tb_code, tb_cfg, logger)
        if not columns:
            return []

        col_info_map = tb_cfg.column or {}
        # # 初始化表字段信息列表
        cols: list[dict] = []
        # 遍历所有表字段
        for c in columns:
            col_info = col_info_map.get(c["name"])
            _column = {
                "tb_code": tb_code,  # 表编号
                "col_name": c["name"],  # 字段名称
                "col_type": str(c["data_type"]),  # 数据类型
                "col_comment": c["comment"],  # 字段注释
                "fewshot": list(fewshot.get(c["name"], set()))
                if fewshot
                else None,  # 示例数据
                "col_meaning": col_info.col_meaning if col_info else None,  # 字段含义
                "field_meaning": json.dumps(col_info.field_meaning, ensure_ascii=False)
                if col_info and col_info.field_meaning
                else None,  # JSONB字段含义
                "col_alias": col_info.col_alias if col_info else None,  # 字段别名
                "rel_col": col_info.rel_col
                if col_info and col_info.rel_col
                else c["relation"],  # 关联关系，优先使用配置中的关联关系
            }
            cols.append(_column)
        return cols
    except Exception as e:
        if logger:
            logger.exception(f"{tb_code} merge column error: {e}")
        return []


async def save_db(session: AsyncSession, db_cfg: DBCfg, save: dict | None, logger=None):
    """写入库信息"""
    if (save is not None) and (db_cfg.db_code not in save):
        return

    # 收集数据库信息
    db_dict: dict[str, str] = {
        "db_code": db_cfg.db_code,
        "db_name": db_cfg.db_name,
        "db_type": db_cfg.db_type,
        "database": db_cfg.database,
    }
    try:
        # DATABASE db_code 唯一约束
        await session.run(
            "CREATE CONSTRAINT database_db_code IF NOT EXISTS FOR (d:DATABASE) REQUIRE d.db_code IS UNIQUE"
        )
        # 创建 DATABASE 节点
        await session.run(
            """
            MERGE (n:DATABASE {db_code: $db_dict.db_code})
            SET n += $db_dict
            """,
            db_dict=db_dict,
        )
        if logger:
            logger.info(f"save database {db_cfg.db_code}")
    except Exception as e:
        if logger:
            logger.exception(f"save database error: {e}")


async def save_tb_col(
    session: AsyncSession, db_cfg: DBCfg, save: dict | None, logger=None
):
    """写入表与字段信息"""
    if not db_cfg.table:
        return
    if (save is not None) and (
        (db_cfg.db_code not in save) or ("table" not in save[db_cfg.db_code])
    ):
        return

    tbs: list[dict] = []
    cols: list[dict] = []
    col_col_rels: list[tuple] = []  # (tb_code, col_name, rel_tb_name,rel_col_name)
    for tb_code, tb_cfg in db_cfg.table.items():
        if (save is not None) and (tb_code not in save[db_cfg.db_code]["table"]):
            continue
        # 收集表信息
        tbs.append(
            {
                "tb_code": tb_code,
                "tb_name": tb_cfg.tb_name,
                "tb_meaning": tb_cfg.tb_meaning,
                "rel_db_code": db_cfg.db_code,
            }
        )
        # 收集字段信息
        columns = await _get_column(db_cfg, tb_code, logger)
        cols.extend(columns)
        # 收集字段关联信息
        for c in columns:
            if c["rel_col"]:
                rel_tb_name, rel_col_name = c["rel_col"].split(".")
                col_col_rels.append((tb_code, c["col_name"], rel_tb_name, rel_col_name))
    # 写入表信息
    try:
        # TABLE tb_code 唯一约束
        await session.run(
            "CREATE CONSTRAINT table_tb_code IF NOT EXISTS FOR (t:TABLE) REQUIRE t.tb_code IS UNIQUE"
        )
        # 创建 TABLE 节点，创建 TABLE-[:BELONG]->DATABASE 关系
        await session.run(
            """
            UNWIND $tbs AS tb
            MERGE (n:TABLE {tb_code: tb.tb_code})
            SET n += tb
            WITH tb.tb_code AS tb_code, tb.rel_db_code AS rel_db_code
            MATCH (db:DATABASE {db_code: rel_db_code})
            MATCH (t:TABLE {tb_code: tb_code})
            MERGE (t)-[:BELONG]->(db)
            """,
            tbs=tbs,
        )
        if logger:
            logger.info(f"save table ({len(tbs)})")
            logger.info(f"save table-belong->database ({len(tbs)})")
    except Exception as e:
        if logger:
            logger.exception(f"save table info error: {e}")
    # 写入字段信息
    try:
        # COLUMN (tb_code, col_name) 唯一约束
        await session.run(
            "CREATE CONSTRAINT column_tb_code_col_name IF NOT EXISTS FOR (c:COLUMN) REQUIRE (c.tb_code, c.col_name) IS UNIQUE"
        )
        # 创建 COLUMN 节点
        await session.run(
            """
            UNWIND $cols AS col
            MERGE (n:COLUMN {tb_code: col.tb_code, col_name: col.col_name})
            SET n += col
            WITH col.tb_code AS tb_code, col.col_name AS col_name, col.rel_col AS rel_col
            MATCH (tb:TABLE {tb_code: tb_code})
            MATCH (col:COLUMN {tb_code: tb_code, col_name: col_name})
            MERGE (col)-[:BELONG]->(tb)
            WITH 1 AS dummy
            UNWIND $col_col_rels AS rel
            MATCH (col:COLUMN {tb_code: rel[0], col_name: rel[1]})-[]-(:TABLE)-[]-(:DATABASE)-[]-(:TABLE {tb_name: rel[2]})-[]-(rel_col:COLUMN {col_name: rel[3]})
            MERGE (col)-[:REL]->(rel_col)
            """,
            cols=cols,
            col_col_rels=col_col_rels,
        )
        if logger:
            logger.info(f"save column ({len(cols)})")
            logger.info(f"save column-belong->table ({len(cols)})")
            logger.info(f"save column-rel->column ({len(col_col_rels)})")
        return cols
    except Exception as e:
        if logger:
            logger.exception(f"save column info error: {e}")
        return None


async def save_col_embed(session: AsyncSession, cols: list[dict], logger=None):
    """写入字段向量化信息"""

    def flatten_dict_values(d: dict) -> list:
        """递归展平嵌套字典，获取所有叶子节点的值"""
        return sum(
            [
                flatten_dict_values(v) if isinstance(v, dict) else [v]
                for v in d.values()
            ],
            [],
        )

    col_contents: list[dict] = []
    for col in cols:
        col_dict = {"tb_code": col["tb_code"], "col_name": col["col_name"]}
        # 收集字段名
        col_contents.append({**col_dict, "content": col["col_name"], "col": "col_name"})
        # 收集字段注释
        if col["col_comment"] is not None:
            col_contents.append(
                {**col_dict, "content": col["col_comment"], "col": "col_comment"}
            )
        # 收集字段示例
        if col["fewshot"] is not None:
            col_contents.extend(
                [
                    {**col_dict, "content": i, "col": "fewshot"}
                    for i in col["fewshot"]
                    if not is_numeric(i)
                ]
            )
        # 收集字段含义
        if col["col_meaning"] is not None:
            col_contents.append(
                {**col_dict, "content": col["col_meaning"], "col": "col_meaning"}
            )
        # 收集字段JSON字段含义（展平嵌套字典的所有值）
        if col["field_meaning"] is not None:
            col_contents.extend(
                [
                    {**col_dict, "content": i, "col": "field_meaning"}
                    for i in flatten_dict_values(json.loads(col["field_meaning"]))
                ]
            )
        # 收集字段别名
        if col["col_alias"] is not None:
            col_contents.extend(
                [
                    {**col_dict, "content": i, "col": "col_alias"}
                    for i in col["col_alias"]
                ]
            )
    try:
        # EMBED_COL (content) 唯一约束
        await session.run(
            "CREATE CONSTRAINT embed_col IF NOT EXISTS FOR (e:EMBED_COL) REQUIRE (e.content) IS UNIQUE"
        )
        # EMBED_COL embed 向量索引
        await session.run(
            """
            CREATE VECTOR INDEX embed_col_embed IF NOT EXISTS FOR (e:EMBED_COL) ON e.embed
            OPTIONS { indexConfig: {`vector.dimensions`: 1024,`vector.similarity_function`: 'cosine'} }
            """
        )
        embeds = await embed([item["content"] for item in col_contents])
        flatten_embeds = [vec for batch in embeds for vec in batch]
        for col_dict, vec in zip(col_contents, flatten_embeds):
            col_dict["embed"] = vec

        # 创建 EMBED_COL 节点，创建 EMBED_COL-[:BELONG]->COLUMN 关系
        await session.run(
            """
            UNWIND $col_info_list AS col_item
            MERGE (ec:EMBED_COL {content: col_item.content})
            ON CREATE SET ec.embed = col_item.embed
            WITH ec, col_item
            MATCH (col:COLUMN {tb_code: col_item.tb_code, col_name: col_item.col_name})
            MERGE (ec)-[:BELONG]->(col)
            """,
            col_info_list=col_contents,
        )
        if logger:
            logger.info(f"save embed_col ({len(col_contents)})")
            logger.info(f"save embed_col->belong->column ({len(col_contents)})")
    except Exception as e:
        if logger:
            logger.exception(f"save embed_col error: {e}")


async def save_kn(
    session: AsyncSession, db_cfg: DBCfg, save: dict | None, logger=None
) -> list[dict] | None:
    """写入知识信息"""
    if not db_cfg.knowledge:
        return None
    if (save is not None) and (
        (db_cfg.db_code not in save) or ("knowledge" not in save[db_cfg.db_code])
    ):
        return

    kns: list[dict] = []
    kn_kn_rels: list[tuple] = []  # (db_code, kn_code, rel_kn_code)
    kn_col_rels: list[tuple] = []  # (db_code, kn_code, rel_tb_name, rel_col_name)
    for kn_code, kn in db_cfg.knowledge.items():
        if (save is not None) and (kn_code not in save[db_cfg.db_code]["knowledge"]):
            continue
        kns.append(
            {
                "db_code": db_cfg.db_code,
                "kn_code": kn_code,
                **kn.model_dump(),
                "rel_db_code": db_cfg.db_code,
            }
        )
        # 收集知识与知识的关系
        if kn.rel_kn:
            for rel_kn_code in kn.rel_kn:
                kn_kn_rels.append((db_cfg.db_code, kn_code, rel_kn_code))
        # 收集知识与字段的关系
        if kn.rel_col:
            for rel_col in kn.rel_col:
                rel_tb_name, rel_col_name = rel_col.split(".")
                kn_col_rels.append((db_cfg.db_code, kn_code, rel_tb_name, rel_col_name))
    try:
        # 创建约束
        await session.run(
            "CREATE CONSTRAINT knowledge_db_code_kn_code IF NOT EXISTS FOR (k:KNOWLEDGE) REQUIRE (k.db_code, k.kn_code) IS UNIQUE"
        )
        # 创建 KNOWLEDGE 节点及所有关系
        await session.run(
            """
            UNWIND $kns AS kn
            MERGE (n:KNOWLEDGE {db_code: kn.db_code, kn_code: kn.kn_code})
            SET n += kn
            WITH n, kn.db_code AS db_code, kn.kn_code AS kn_code, kn.rel_db_code AS rel_db_code
            MATCH (db:DATABASE {db_code: rel_db_code})
            MATCH (k:KNOWLEDGE {db_code: db_code, kn_code: kn_code})
            MERGE (k)-[:BELONG]->(db)
            WITH 1 AS dummy
            UNWIND $kn_kn_rels AS rel
            MATCH (kn:KNOWLEDGE {db_code: rel[0], kn_code: rel[1]})
            MATCH (rel_kn:KNOWLEDGE {db_code: rel[0], kn_code: rel[2]})
            MERGE (kn)-[:CONTAIN]->(rel_kn)
            WITH 1 AS dummy
            UNWIND $kn_col_rels AS rel
            MATCH (kn:KNOWLEDGE {db_code: rel[0], kn_code: rel[1]})-[]-(:DATABASE)-[]-(:TABLE)-[]-(rel_col:COLUMN {tb_name: rel[2], col_name: rel[3]})
            MERGE (kn)-[:REL]->(rel_col)
            """,
            kns=kns,
            kn_kn_rels=kn_kn_rels,
            kn_col_rels=kn_col_rels,
        )
        if logger:
            logger.info(f"save knowledge ({len(kns)})")
            logger.info(f"save knowledge-belong->database ({len(kns)})")
            logger.info(f"save knowledge-contain->knowledge ({len(kn_kn_rels)})")
            logger.info(f"save knowledge-rel->column ({len(kn_col_rels)})")
        return kns
    except Exception as e:
        if logger:
            logger.exception(f"save knowledge error: {e}")
        return None


async def save_kn_embed(session: AsyncSession, kns: list[dict], logger=None):
    """写入知识向量化信息"""
    kn_contents: list[dict] = []
    for kn in kns:
        kn_dict = {"db_code": kn["db_code"], "kn_code": kn["kn_code"]}
        # 收集知识名称
        kn_contents.append({**kn_dict, "content": kn["kn_name"], "col": "kn_name"})
        # 收集知识描述
        kn_contents.append({**kn_dict, "content": kn["kn_desc"], "col": "kn_desc"})
        # 收集知识别名
        if kn["kn_alias"] is not None:
            kn_contents.extend(
                [{**kn_dict, "content": i, "col": "kn_alias"} for i in kn["kn_alias"]]
            )
    try:
        # EMBED_KN (content) 唯一约束
        await session.run(
            "CREATE CONSTRAINT embed_kn IF NOT EXISTS FOR (e:EMBED_KN) REQUIRE (e.content) IS UNIQUE"
        )
        # EMBED_KN embed 向量索引
        await session.run(
            """
            CREATE VECTOR INDEX embed_kn_embed IF NOT EXISTS FOR (e:EMBED_KN) ON e.embed
            OPTIONS { indexConfig: {`vector.dimensions`: 1024,`vector.similarity_function`: 'cosine'} }
            """
        )
        # EMBED_KN tscontent 全文索引
        await session.run(
            "CREATE FULLTEXT INDEX embed_kn_tscontent IF NOT EXISTS FOR (e:EMBED_KN) ON EACH [e.tscontent]"
        )

        # 嵌入与分词
        contents = [kn["content"] for kn in kn_contents]
        embeds, tscontents = await asyncio.gather(
            embed(contents), get_keywords(contents)
        )
        for i, e, t in zip(kn_contents, embeds, tscontents):
            i["embed"] = e
            i["tscontent"] = t

        # 创建 EMBED_KN 节点，创建 EMBED_KN-[:BELONG]->KNOWLEDGE 关系
        await session.run(
            """
            UNWIND $kn_contents AS kn_item
            MERGE (ek:EMBED_KN {content: kn_item.content})
            ON CREATE SET ek.embed = kn_item.embed, ek.tscontent = kn_item.tscontent
            WITH ek, kn_item
            MATCH (kn:KNOWLEDGE {db_code: kn_item.db_code, kn_code: kn_item.kn_code})
            MERGE (ek)-[:BELONG]->(kn)
            """,
            kn_contents=kn_contents,
        )
        if logger:
            logger.info(f"save embed_kn ({len(kn_contents)})")
            logger.info(f"save embed_kn->belong->kn ({len(kn_contents)})")
    except Exception as e:
        if logger:
            logger.exception(f"save embed_kn error: {e}")


async def save_cell(
    session: AsyncSession, db_cfg: DBCfg, save: dict | None, logger=None
):
    """写入单元格信息"""

    async def handle_batch(batch: list[dict]):
        """处理批次"""
        if not batch:
            return []
        try:
            cell_batch = [i["content"] for i in batch]
            embed_batch, tscontent_batch = await asyncio.gather(
                embed(cell_batch), get_keywords(cell_batch)
            )
            for i, e, t in zip(batch, embed_batch, tscontent_batch):
                i["embed"] = e
                i["tscontent"] = t
            return batch
        except Exception as e:
            if logger:
                logger.exception(f"process {tb_code} cell error: {e}")
            return []

    async def save_to_neo4j(batch: list[dict]):
        """写入 neo4j"""
        # 创建 CELL 节点，创建 CELL-[:BELONG]->COLUMN 关系
        await session.run(
            """
            UNWIND $batch AS cell
            MERGE (c:CELL {content: cell.content})
            ON CREATE SET c.embed = cell.embed, c.tscontent = cell.tscontent
            WITH c, cell
            MATCH (col:COLUMN {tb_code: cell.tb_code, col_name: cell.col_name})
            MERGE (c)-[:BELONG]->(col)
            """,
            batch=batch,
        )
        if logger:
            logger.info(f"save cell ({len(batch)})")
            logger.info(f"save cell-belong->column ({len(batch)})")

    if not db_cfg.table:
        return
    if (save is not None) and (
        (db_cfg.db_code not in save) or ("cell" not in save[db_cfg.db_code])
    ):
        return

    SELECT_BATCH_SIZE = 5000

    try:
        # CELL (content) 唯一约束
        await session.run(
            "CREATE CONSTRAINT cell IF NOT EXISTS FOR (c:CELL) REQUIRE (c.content) IS UNIQUE"
        )
        # CELL embed 向量索引
        await session.run(
            """
            CREATE VECTOR INDEX cell_embed IF NOT EXISTS FOR (c:CELL) ON c.embed
            OPTIONS { indexConfig: {`vector.dimensions`: 1024,`vector.similarity_function`: 'cosine'} }
            """
        )
        # CELL tscontent 全文索引
        await session.run(
            "CREATE FULLTEXT INDEX cell_tscontent IF NOT EXISTS FOR (c:CELL) ON EACH [c.tscontent]"
        )

        for tb_code, tb_cfg in db_cfg.table.items():
            if (save is not None) and (tb_code not in save[db_cfg.db_code]["cell"]):
                continue
            sync_col_names: list[str] = []
            # 获取表的字段属性
            async with get_asession(db_cfg) as db_session:
                columns = await _get_column_attr(db_session, tb_code, tb_cfg, logger)
            if not columns:
                continue
            # 收集需要同步的字段
            for c in columns:
                if (
                    (any(i in str(c["data_type"]).lower() for i in ["varchar", "text"]))
                    and (
                        tb_cfg.sync_col is None or c["name"] in tb_cfg.sync_col
                    )  # 如果同步字段为空，则所有字段都需要同步；如果字段在同步字段里则同步
                    and (
                        tb_cfg.no_sync_col is None
                        or c["name"] not in tb_cfg.no_sync_col
                    )  # 如果字段在同步字段里，且不在不同步字段里，则同步
                ):
                    sync_col_names.append(c["name"])
            if not sync_col_names:
                continue

            # 查询字段值
            async with get_asession(db_cfg) as db_session:
                stmt = select(*[column(c) for c in sync_col_names]).select_from(
                    table(tb_cfg.tb_name)
                )
                if logger:
                    logger.info(f"execute sql statement:\n{stmt}")
                result = await db_session.stream(
                    stmt.execution_options(yield_per=SELECT_BATCH_SIZE)
                )
                async for batch in result.partitions(SELECT_BATCH_SIZE):
                    # 构造 col_name->[cell] 映射
                    # 解包->转置->转换为集合->关联列名->转换为字典
                    col_map = dict(zip(sync_col_names, map(set, zip(*batch))))
                    _batch: list[dict] = []
                    for col_name, cells in col_map.items():
                        _batch.extend(
                            [
                                {"tb_code": tb_code, "col_name": col_name, "content": i}
                                for i in cells
                                if (i) and (i.strip() != "") and (not is_numeric(i))
                            ]
                        )
                    if logger:
                        logger.info(f"process {tb_code} cell ({len(_batch)})")
                    handled_batch = await handle_batch(_batch)
                    await save_to_neo4j(handled_batch)
    except Exception as e:
        if logger:
            logger.exception(f"save cell error: {e}")
        raise


async def save_meta(save: dict | None = None):
    """
    保存元数据

    save = {
        db_code:{
            'table':[tb_code]
            'knowledge':[kn_code]
            'cell':[tb_code]
        }
    }
    None 视为全选
    """
    async with neo4j_session() as session:
        for db_cfg in DB_CFG.values():
            # 保存库信息
            await save_db(session, db_cfg, save, logger)
            # 保存表与字段信息
            cols = await save_tb_col(session, db_cfg, save, logger)
            # 保存字段向量化信息
            if cols:
                await save_col_embed(session, cols, logger)
            # 保存知识
            kns = await save_kn(session, db_cfg, save, logger)
            if kns:
                # 保存知识向量化信息
                await save_kn_embed(session, kns, logger)
            # 保存字段值信息
            await save_cell(session, db_cfg, save, logger)


async def clear_meta():
    """清空元数据"""
    async with neo4j_session() as session:
        # 删除所有数据
        await session.run("MATCH (n) DETACH DELETE n")

        # 删除所有约束
        result = await session.run("SHOW CONSTRAINTS")
        records = await result.data()
        for record in records:
            query_str = f"DROP CONSTRAINT {record['name']}"
            await session.run(cast(LiteralString, query_str))

        # 删除所有索引
        result = await session.run("SHOW INDEXES")
        records = await result.data()
        for record in records:
            query_str = f"DROP INDEX {record['name']}"
            await session.run(cast(LiteralString, query_str))
    logger.info("clear metadata")


if __name__ == "__main__":

    async def main():
        await clear_meta()
        await save_meta()

    asyncio.run(main())
