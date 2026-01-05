import argparse
import asyncio
import json

import httpx
from config import CFG


async def recall_column(db_code: str, extracted_columns: list[str]):
    """检索字段信息"""
    if not extracted_columns:
        return {"retrieved_col_map": {}}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            CFG.meta_db.retrieve_column_url,
            json={"db_code": db_code, "keywords": extracted_columns},
        )
    return {"retrieved_col_map": response.json()}


async def main():
    usage = "python recall_column.py [关键词列表]"
    parser = argparse.ArgumentParser(description="检索字段", usage=usage)
    parser.add_argument("extracted_columns", type=json.loads, help="关键词列表")

    args = parser.parse_args()
    res = await recall_column(CFG.use_db_code, args.extracted_columns)
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
