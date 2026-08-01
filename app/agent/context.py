from typing import TypedDict

from app.clients.embedding_client_manager import EmbeddingClient
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.repositories.value_es_repo import ValueESRepo


class DataAgentContext(TypedDict):
    embedding_client: EmbeddingClient
    column_qdrant_repository: ColumnQdrantRepo
    value_es_repository: ValueESRepo
    metric_qdrant_repository: MetricQdrantRepo
    meta_mysql_repository: MetaMySQLRepo
    dw_mysql_repository: SourceMySQLRepo
