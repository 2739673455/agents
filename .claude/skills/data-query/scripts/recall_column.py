import argparse
import asyncio
from typing import Callable

import httpx
from config import CFG
from state_manage import read_callback, write_callback


async def recall_column(
    r_callback: Callable | None = None,
    w_callback: Callable | None = None,
):
    """检索字段信息"""
    state = await r_callback() if r_callback else {}
    db_code: str = state["db_code"]
    keywords: list[str] = state.get("extracted_columns") or state["keywords"]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            CFG.meta_db.retrieve_column_url,
            json={"db_code": db_code, "keywords": keywords},
        )
    if w_callback:
        await w_callback({"retrieved_col_map": response.json()})


async def main():
    usage = "python recall_column.py"
    argparse.ArgumentParser(description="检索字段", usage=usage)

    await recall_column(read_callback, write_callback)


if __name__ == "__main__":
    asyncio.run(main())
