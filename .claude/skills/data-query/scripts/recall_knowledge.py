import argparse
import asyncio
import json

import httpx
from config import CFG


async def recall_knowledge(db_code: str, query: str, keywords: list[str]):
    """混合检索知识"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            CFG.meta_db.retrieve_knowledge_url,
            json={"db_code": db_code, "query": query, "keywords": keywords},
        )
    return {"kn_map": response.json()}


async def main():
    usage = 'python recall_knowledge.py --query "查询文本" --keywords [关键词列表]'
    parser = argparse.ArgumentParser(description="检索知识", usage=usage)
    parser.add_argument("--query", type=str, help="查询文本")
    parser.add_argument("--keywords", type=json.loads, help="关键词列表")

    args = parser.parse_args()
    res = await recall_knowledge(CFG.use_db_code, args.query, args.keywords)
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
