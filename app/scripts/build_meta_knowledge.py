import asyncio
from argparse import ArgumentParser
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    meta_mysql_client_manager,
    source_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.repositories.value_es_repo import ValueESRepo
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):
    meta_mysql_client_manager.init()  # 初始化元数据MySQL客户端
    source_mysql_client_manager.init()  # 初始化业务数据客户端
    qdrant_client_manager.init()  # 初始化Qdrant客户端
    embedding_client_manager.init()  # 初始化Embedding客户端
    es_client_manager.init()  # 初始化Elasticsearch客户端

    async with (
        meta_mysql_client_manager.session() as meta_session,
        source_mysql_client_manager.session() as source_session,
    ):
        meta_mysql_repository = MetaMySQLRepo(meta_session)  # 创建元数据MySQLRepo实例
        dw_mysql_repository = SourceMySQLRepo(source_session)  # 创建业务数据Repo实例
        column_qdrant_repository = ColumnQdrantRepo(
            qdrant_client_manager.get_client()
        )  # 创建列QdrantRepo实例
        embedding_client = (
            embedding_client_manager.get_client()
        )  # 获取Embedding客户端实例
        value_es_repository = ValueESRepo(
            es_client_manager.get_client()
        )  # 创建值ElasticsearchRepo实例
        metric_qdrant_repository = MetricQdrantRepo(
            qdrant_client_manager.get_client()
        )  # 创建指标QdrantRepo实例

        mete_knowledge_service = MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_client,
            value_es_repository=value_es_repository,
            metric_qdrant_repository=metric_qdrant_repository,
        )  # 创建MetaKnowledgeService实例
        await mete_knowledge_service.build(config_path)  # 构建元知识库

    await meta_mysql_client_manager.close()  # 关闭元数据MySQL客户端
    await source_mysql_client_manager.close()  # 关闭业务数据客户端
    await qdrant_client_manager.close()  # 关闭Qdrant客户端
    await embedding_client_manager.close()  # 关闭Embedding客户端
    await es_client_manager.close()  # 关闭Elasticsearch客户端


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("-c", "--conf")  # option that takes a value

    args = parser.parse_args()

    config_path = Path(args.conf)

    asyncio.run(build(config_path))
