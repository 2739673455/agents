import argparse
import asyncio
from typing import Callable

import httpx
from config import CFG
from state_manage import read_callback, write_callback


async def recall_knowledge(
    r_callback: Callable | None = None,
    w_callback: Callable | None = None,
):
    """混合检索知识"""
    state = await r_callback() if r_callback else {}
    db_code: str = state["db_code"]
    query: str = state["query"]
    keywords: list[str] = state["keywords"]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            CFG.meta_db.retrieve_knowledge_url,
            json={"db_code": db_code, "query": query, "keywords": keywords},
        )
    if w_callback:
        await w_callback({"kn_map": response.json()})


async def main():
    usage = "python recall_knowledge.py"
    argparse.ArgumentParser(description="检索知识", usage=usage)

    await recall_knowledge(read_callback, write_callback)


if __name__ == "__main__":
    asyncio.run(main())
