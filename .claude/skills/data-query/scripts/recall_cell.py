import argparse
import asyncio
import json

import httpx
from config import CFG


async def recall_cell(db_code: str, extracted_cells: list[str]):
    """检索字段信息"""
    if not extracted_cells:
        return {"retrieved_cell_map": {}}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            CFG.meta_db.retrieve_cell_url,
            json={"db_code": db_code, "keywords": extracted_cells},
        )
    return {"retrieved_cell_map": response.json()}


async def main():
    usage = "python recall_cell.py [关键词列表]"
    parser = argparse.ArgumentParser(description="检索单元格", usage=usage)
    parser.add_argument("extracted_cells", type=json.loads, help="关键词列表")

    args = parser.parse_args()
    res = await recall_cell(CFG.use_db_code, args.extracted_cells)
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
