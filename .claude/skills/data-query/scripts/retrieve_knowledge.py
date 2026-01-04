import argparse
import asyncio

from config import CONF


async def retrieve_knowledge(db_code: str, query: str, keywords: list[str]):
    """混合检索知识"""


async def main():
    usage = 'python retrieve_knowledge.py --query "查询文本" --keywords [关键词列表]'
    parser = argparse.ArgumentParser(description="检索知识", usage=usage)
    parser.add_argument("--query", type=str, help="查询文本")
    parser.add_argument("--keywords", type=list[str], help="关键词列表")

    try:
        args = parser.parse_args()
        kns = await retrieve_knowledge(
            CONF.use_db_code,
            args.query,
            args.keywords,
        )
        print(kns)
    except SystemExit:
        print(usage)
        raise


if __name__ == "__main__":
    asyncio.run(main())
