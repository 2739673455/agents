import asyncio
from typing import Callable

import httpx
from config import CFG
from state_manage import read_callback, write_callback


async def add_kn_col(
    r_callback: Callable | None = None,
    w_callback: Callable | None = None,
):
    """获取知识相关字段，并与之前检索出的字段合并"""
    state = await r_callback() if r_callback else {}
    db_code: str = state["db_code"]
    col_map: dict[str, dict[str, dict]] = state["col_map"]
    kn_map: dict[str, dict] = state["kn_map"]
    retrieve_cell_url = CFG.meta_db.retrieve_cell_url
    if not kn_map or all(not kn.get("rel_col") for kn in kn_map.values()):
        return

    # 获取知识的相关字段
    tb_col_tuple_set: set[tuple[str, str]] = set()
    for kn in kn_map.values():
        if kn["rel_col"]:
            for tb_col in kn["rel_col"]:
                tb_name, col_name = tb_col.split(".")
                tb_col_tuple_set.add((tb_name, col_name))
    async with httpx.AsyncClient() as client:
        response = await client.post(
            retrieve_cell_url,
            json={"db_code": db_code, "tb_col_tuple_list": list(tb_col_tuple_set)},
        )
        kn_rel_col_map = response.json()

    # 将知识的相关字段与召回的字段合并
    for tb_code, n_c_map in kn_rel_col_map.items():
        col_map.setdefault(tb_code, {}).update(n_c_map)

    if w_callback:
        await w_callback({"col_map": col_map})


if __name__ == "__main__":
    asyncio.run(add_kn_col(read_callback, write_callback))
