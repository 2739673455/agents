import asyncio
import json
import re

import util
from db_session import neo4j_session
from loguru import logger
from util import embed


async def get_tb_info_by_dbcode(db_code: str):
    """查找数据库下的所有表信息"""
    try:
        logger.info(f"query table by db_code: {db_code}")
        async with neo4j_session() as session:
            results = await session.run(
                "MATCH (tb:TABLE)-[]-(db:DATABASE {db_code: $db_code}) RETURN tb, db",
                db_code=db_code,
            )
            records = await results.data()
        return [
            {
                "db_code": db_code,
                "db_name": record["db"]["db_name"],
                "db_type": record["db"]["db_type"],
                "database": record["db"]["database"],
                "tb_code": record["tb"]["tb_code"],
                "tb_name": record["tb"]["tb_name"],
                "tb_meaning": record["tb"]["tb_meaning"],
            }
            for record in records
        ]
    except Exception as e:
        logger.exception(e)
        return []


async def get_col_by_dbcode_tbname_colname(
    db_code: str, tb_col_tuple_list: list[tuple[str, str]]
):
    """根据表名列名查找列信息"""
    try:
        logger.info(
            f"query column by db_code: {db_code}, tb_col_tuple_list: {tb_col_tuple_list}"
        )
        async with neo4j_session() as session:
            results = await session.run(
                """
            MATCH (db:DATABASE {db_code: $db_code})
            UNWIND $ls AS tb_col
            MATCH (col:COLUMN {col_name: tb_col[1]})-[:BELONG]->(tb:TABLE {tb_name: tb_col[0]})-[:BELONG]->(db)
            RETURN col, tb
            """,
                db_code=db_code,
                ls=tb_col_tuple_list,
            )
            records = await results.data()
        col_map: dict[str, dict[str, dict]] = {}  # {tb_code: {col_name: col}
        for record in records:
            tb_code = record["col"]["tb_code"]
            col_name = record["col"]["col_name"]
            col_data = dict(record["col"])
            if tb_code not in record:
                col_map[tb_code] = {}
            if col_name not in col_map[tb_code]:
                col_data["field_meaning"] = (
                    json.loads(record["col"]["field_meaning"])
                    if record["col"].get("field_meaning")
                    else None
                )
                col_map[tb_code][col_name] = col_data
        return col_map
    except Exception as e:
        logger.exception(e)
        return {}


async def retrieve_knowledge(db_code: str, query: str, keywords: list[str]):
    """混合检索知识"""
    try:
        logger.info(
            f"query knowledge by db_code: {db_code}, query: {query}, keywords: {keywords}"
        )
        # 子句切分,支持中英文标点
        sub_statements = re.split(r"[，。！？；,;!?\s]+", query)
        # 去掉太短的子句
        sub_statements = [s.strip() for s in sub_statements if len(s.strip()) >= 3]
        embeds = await embed(sub_statements)
        tsquery = " OR ".join(keywords)

        cypher = """
            CALL () {
                // 子句向量检索
                UNWIND $embeds AS vec
                CALL (vec) {
                    CALL db.index.vector.queryNodes('embed_kn_embed', $search_num_per_vec, vec)
                    YIELD node AS e_node, score AS v_score
                    WHERE v_score > $vec_search_threshold

                    // 关联到 KNOWLEDGE 并过滤库
                    MATCH (e_node)-[:BELONG]->(kn:KNOWLEDGE)-[:BELONG]->(db:DATABASE {db_code: $db_code})
                    RETURN kn, v_score, 0.0 AS f_score, 1 AS type
                }
                RETURN kn, v_score, f_score, type

                UNION ALL

                // 全文检索
                CALL db.index.fulltext.queryNodes('embed_kn_tscontent', $tsquery, {limit: $search_num_per_ft})
                YIELD node AS e_node, score AS f_score

                // 关联到 KNOWLEDGE 并过滤库
                MATCH (e_node)-[:BELONG]->(kn:KNOWLEDGE)-[:BELONG]->(db:DATABASE {db_code: $db_code})
                RETURN kn, 0.0 AS v_score, f_score, 2 AS type
            }

            // 取同一个 KNOWLEDGE 向量和全文的各自最高分
            WITH kn, max(v_score) AS mv, max(f_score) AS mf
            WITH collect({n: kn, v: mv, f: mf}) AS raw_data

            // 构造有序的 v_list (向量排名列表)
            UNWIND raw_data AS row
            WITH row, raw_data WHERE row.v > 0 
            ORDER BY row.v DESC
            WITH collect({node: row.n, score: row.v}) AS v_list, raw_data

            // 构造有序的 f_list (全文排名列表)
            UNWIND raw_data AS row
            WITH row, v_list WHERE row.f > 0 
            ORDER BY row.f DESC
            WITH collect({node: row.n, score: row.f}) AS f_list, v_list

            // RRF 融合重排序
            // 合并两个列表中的所有唯一节点
            WITH [x IN v_list | x.node] + [x IN f_list | x.node] AS all_nodes, v_list, f_list
            UNWIND all_nodes AS kn_node
            WITH DISTINCT kn_node, v_list, f_list

            // 分别计算向量排名分和全文排名
            WITH kn_node,
                [i IN range(0, size(v_list)-1) WHERE v_list[i].node = kn_node][0] AS v_rank,
                [i IN range(0, size(f_list)-1) WHERE f_list[i].node = kn_node][0] AS f_rank

            // 计算最终 RRF 得分：1/(60+rank)
            WITH kn_node,
                (CASE WHEN v_rank IS NOT NULL THEN 1.0/(60 + v_rank) ELSE 0 END) +
                (CASE WHEN f_rank IS NOT NULL THEN 1.0/(60 + f_rank) ELSE 0 END) AS rrf_score

            // 取 topk
            ORDER BY rrf_score DESC
            LIMIT $final_num

            // 递归查找子知识，从深度0开始
            OPTIONAL MATCH (kn_node)-[:CONTAIN*0..]->(kn:KNOWLEDGE)

            // 展平、去重并按 kn_code 排序
            WITH DISTINCT kn
            RETURN kn
            ORDER BY kn.kn_code ASC
        """

        async with neo4j_session() as session:
            results = await session.run(
                cypher,
                embeds=embeds,
                tsquery=tsquery,
                db_code=db_code,
                vec_search_threshold=0.7,
                search_num_per_vec=10,  # 每个子句向量检索的个数
                search_num_per_ft=20,  # 全文检索的个数
                final_num=5,  # 最终返回的个数
            )
            records = await results.data()
            kn_map = {record["kn"]["kn_code"]: record["kn"] for record in records}
        return kn_map
    except Exception as e:
        logger.exception(e)
        return {}


async def retrieve_column(db_code: str, keywords: list[str]):
    """向量检索字段"""
    try:
        logger.info(f"query column by db_code: {db_code}, keywords: {keywords}")
        embeds = await embed(keywords)
        cypher = """
            UNWIND $embeds AS vec
            CALL (vec) {
                // 向量检索
                CALL db.index.vector.queryNodes('embed_col_embed', $search_num_per_vec, vec)
                YIELD node AS e_node, score AS v_score
                WHERE v_score > $vec_search_threshold

                // 关联到 COLUMN TABLE 并过滤库
                MATCH (e_node)-[:BELONG]->(col:COLUMN)-[:BELONG]->(:TABLE)-[:BELONG]->(:DATABASE {db_code: $db_code})

                // 返回每个 COLUMN 的最高分
                RETURN col, max(v_score) AS v_score
            }
            WITH col, max(v_score) AS score
            ORDER BY score DESC
            RETURN col, score
        """

        async with neo4j_session() as session:
            results = await session.run(
                cypher,
                embeds=embeds,
                db_code=db_code,
                vec_search_threshold=0.7,
                search_num_per_vec=10,  # 每个向量检索的个数
            )
            records = await results.data()
        col_map: dict[str, dict[str, dict]] = {}  # {tb_code: {col_name: col}
        for record in records:
            tb_code = record["col"]["tb_code"]
            col_name = record["col"]["col_name"]
            col_data = dict(record["col"])
            if tb_code not in col_map:
                col_map[tb_code] = {}
            if col_name not in col_map[tb_code]:
                col_data["field_meaning"] = (
                    json.loads(record["col"]["field_meaning"])
                    if record["col"].get("field_meaning")
                    else None
                )
                col_data["score"] = record["score"]
                col_map[tb_code][col_name] = col_data
        return col_map
    except Exception as e:
        logger.exception(e)
        return {}


async def retrieve_cell(db_code: str, keywords: list[str]):
    """混合检索单元格"""
    try:
        logger.info(f"query cell by db_code: {db_code}, keywords: {keywords}")
        embeds = await embed(keywords)
        cypher = """
            // 成对处理每一组向量和关键词
            UNWIND range(0, size($embeds)-1) AS idx
            WITH $embeds[idx] AS vec, $texts[idx] AS keyword

            CALL (vec, keyword) {
                CALL (vec, keyword) {
                    // 向量检索
                    CALL db.index.vector.queryNodes('cell_embed', $search_num_per_vec, vec)
                    YIELD node AS cell, score AS v_score
                    WHERE v_score > $vec_search_threshold

                    // 关联到 COLUMN TABLE 并过滤库
                    MATCH (cell)-[:BELONG]->(:COLUMN)-[:BELONG]->(:TABLE)-[:BELONG]->(:DATABASE {db_code: $db_code})
                    RETURN cell, v_score, 0.0 AS f_score

                    UNION ALL

                    // 全文检索
                    CALL db.index.fulltext.queryNodes('cell_tscontent', keyword, {limit: $search_num_per_ft})
                    YIELD node AS cell, score AS f_score

                    MATCH (cell)-[:BELONG]-(:COLUMN)-[:BELONG]-(:TABLE)-[:BELONG]-(:DATABASE {db_code: $db_code})
                    RETURN cell, 0.0 AS v_score, f_score
                }

                // 每个 CELL 取两个维度的最高分
                WITH cell, max(v_score) AS mv, max(f_score) AS mf
                WITH collect({n: cell, v: mv, f: mf}) AS raw_data

                // 构造有序的 v_list (向量排名列表)
                UNWIND raw_data AS row
                WITH row, raw_data WHERE row.v > 0 
                ORDER BY row.v DESC
                WITH collect({node: row.n, score: row.v}) AS v_list, raw_data

                // 构造有序的 f_list (全文排名列表)
                UNWIND raw_data AS row
                WITH row, v_list WHERE row.f > 0 
                ORDER BY row.f DESC
                WITH collect({node: row.n, score: row.f}) AS f_list, v_list

                // RRF 融合重排序
                // 合并两个列表中的所有唯一节点
                WITH [x IN v_list | x.node] + [x IN f_list | x.node] AS all_nodes, v_list, f_list
                UNWIND all_nodes AS c_node
                WITH DISTINCT c_node, v_list, f_list

                // 分别计算向量排名分和全文排名
                WITH c_node,
                    [i IN range(0, size(v_list)-1) WHERE v_list[i].node = c_node][0] AS v_rank,
                    [i IN range(0, size(f_list)-1) WHERE f_list[i].node = c_node][0] AS f_rank

                // 计算最终 RRF 得分：1/(60+rank)
                WITH c_node,
                    (CASE WHEN v_rank IS NOT NULL THEN 1.0/(60 + v_rank) ELSE 0 END) +
                    (CASE WHEN f_rank IS NOT NULL THEN 1.0/(60 + f_rank) ELSE 0 END) AS rrf_score

                // 取 topk
                ORDER BY rrf_score DESC
                LIMIT $max_num_per_cell
                RETURN c_node, rrf_score
            }

            // 取每个 CELL 的最高 RRF 得分
            WITH c_node, max(rrf_score) AS max_rrf_score

            // 补充 COLUMN 信息
            MATCH (c_node)-[:BELONG]->(col:COLUMN)
            RETURN c_node { .*, embed: null, tscontent: null } AS cell, col, max_rrf_score*30 AS score
        """

        async with neo4j_session() as session:
            results = await session.run(
                cypher,
                embeds=embeds,
                texts=keywords,
                db_code=db_code,
                vec_search_threshold=0.7,
                search_num_per_vec=20,  # 每个向量检索的个数
                search_num_per_ft=20,  # 每个全文检索的个数
                max_num_per_cell=10,
            )
            records = await results.data()
        cell_map: dict[str, dict[str, dict]] = {}  # {tb_code: {col_name: col}
        for record in records:
            tb_code = record["col"]["tb_code"]
            col_name = record["col"]["col_name"]
            col_data = dict(record["col"])
            if tb_code not in cell_map:
                cell_map[tb_code] = {}
            if col_name not in cell_map[tb_code]:
                # 原本没有此 Column 则添加
                col_data["field_meaning"] = (
                    json.loads(record["col"]["field_meaning"])
                    if record["col"].get("field_meaning")
                    else None
                )
                col_data["score"] = record["score"]
                cell_map[tb_code][col_name] = {
                    **col_data,
                    "cells": [record["cell"]["content"]],
                }
            else:
                # 原本有此 Column 则更新
                _col = cell_map[tb_code][col_name]
                if _col.get("cells") and record["cell"]["content"] not in _col["cells"]:
                    _col["cells"].append(record["cell"]["content"])
                _col["score"] = max(record["score"], _col.get("score", 0.0))  # 取最高分
        return cell_map
    except Exception as e:
        logger.exception(e)
        return {}


if __name__ == "__main__":
    db_code = [
        "mysql_sales",
        "pg_archeology_scan",
        "pg_cold_chain_pharma_compliance",
    ][2]

    async def main():
        # 查找数据库下的所有表信息
        tbs = await get_tb_info_by_dbcode(db_code)
        for i in tbs:
            print(i)

        # 混合检索知识
        kns = await retrieve_knowledge(
            db_code,
            "温度精度影响因子",
            ["温度", "精度", "影响因子"],
        )
        for kn in kns.values():
            print(kn)

        # 向量检索字段
        col_map = await retrieve_column(db_code, ["销售数量"])
        for tb_code in col_map:
            for col_name in col_map[tb_code]:
                print(col_map[tb_code][col_name])

        # 混合检索单元格
        cell_map = await retrieve_cell(db_code, ["Validated"])
        for tb_code in cell_map:
            for col_name in cell_map[tb_code]:
                print(cell_map[tb_code][col_name])

        # 根据表名列名查找列信息
        kn_col_map = await get_col_by_dbcode_tbname_colname(
            db_code, [("insuranceclaims", "claimstat")]
        )
        for tb_code in kn_col_map:
            for col_name in kn_col_map[tb_code]:
                print(kn_col_map[tb_code][col_name])

    asyncio.run(main())
