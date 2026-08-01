"""元数据管理与索引同步路由"""

from collections.abc import AsyncGenerator
from typing import Annotated, NoReturn

import yaml
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from yaml import YAMLError

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    meta_mysql_client_manager,
    source_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.conf.meta_config import MetaConfig
from app.entities.meta import ColumnInfo, MetricInfo, TableInfo
from app.repositories.column_qdrant_repo import ColumnQdrantRepo
from app.repositories.meta_mysql_repo import MetaMySQLRepo
from app.repositories.metric_qdrant_repo import MetricQdrantRepo
from app.repositories.source_mysql_repo import SourceMySQLRepo
from app.repositories.value_es_repo import ValueESRepo
from app.routes.api.v1.meta import schemas
from app.services.index_service import IndexService
from app.services.meta_import_service import (
    ImportMode,
    MetaImportService,
    ResourceChanges,
)
from app.services.meta_service import MetaService

router = APIRouter(tags=["meta"])

_max_yaml_size = 2 * 1024 * 1024


async def get_meta_service() -> AsyncGenerator[MetaService]:
    """创建请求级元数据管理服务"""
    async with meta_mysql_client_manager.session() as meta_session:
        yield MetaService(meta_repo=MetaMySQLRepo(meta_session))


async def get_index_service() -> AsyncGenerator[IndexService]:
    """创建请求级索引同步服务"""
    async with (
        meta_mysql_client_manager.session() as meta_session,
        source_mysql_client_manager.session() as source_session,
    ):
        yield IndexService(
            meta_repo=MetaMySQLRepo(meta_session),
            source_repo=SourceMySQLRepo(source_session),
            column_repo=ColumnQdrantRepo(qdrant_client_manager.get_client()),
            embedding_client=embedding_client_manager.get_client(),
            value_repo=ValueESRepo(es_client_manager.get_client()),
            metric_repo=MetricQdrantRepo(qdrant_client_manager.get_client()),
        )


async def get_meta_import_service() -> AsyncGenerator[MetaImportService]:
    """创建请求级元数据导入服务"""
    async with (
        meta_mysql_client_manager.session() as meta_session,
        source_mysql_client_manager.session() as source_session,
    ):
        yield MetaImportService(
            meta_repo=MetaMySQLRepo(meta_session),
            source_repo=SourceMySQLRepo(source_session),
        )


MetaServiceDep = Annotated[MetaService, Depends(get_meta_service)]
IndexServiceDep = Annotated[IndexService, Depends(get_index_service)]
MetaImportServiceDep = Annotated[
    MetaImportService,
    Depends(get_meta_import_service),
]


def _raise_not_found(exc: ValueError) -> NoReturn:
    """将资源不存在错误转换为 HTTP 404"""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _to_import_changes(changes: ResourceChanges) -> schemas.ResourceImportChanges:
    """转换元数据导入变更响应"""
    return schemas.ResourceImportChanges(
        created_count=len(changes.created_ids),
        updated_count=len(changes.updated_ids),
        deleted_count=len(changes.deleted_ids),
        created_ids=changes.created_ids,
        updated_ids=changes.updated_ids,
        deleted_ids=changes.deleted_ids,
    )


async def _load_yaml(file: UploadFile) -> MetaConfig:
    """读取并校验上传的 YAML 元数据配置"""
    try:
        content = await file.read(_max_yaml_size + 1)
    finally:
        await file.close()
    if len(content) > _max_yaml_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Metadata YAML file exceeds the 2 MiB limit",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata YAML file cannot be empty",
        )

    try:
        raw_config = yaml.safe_load(content.decode("utf-8"))
        return MetaConfig.model_validate(raw_config)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata YAML file must use UTF-8 encoding",
        ) from exc
    except YAMLError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid metadata YAML: {exc}",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc


@router.post("/import", response_model=schemas.MetaImportResponse)
async def import_metadata(
    file: Annotated[UploadFile, File(description="元数据 YAML 文件")],
    service: MetaImportServiceDep,
    mode: Annotated[ImportMode, Query(description="导入模式")] = ImportMode.MERGE,
    dry_run: Annotated[bool, Query(description="仅预览变更")] = False,
    confirm: Annotated[bool, Query(description="确认执行替换")] = False,
) -> schemas.MetaImportResponse:
    """从 YAML 文件批量导入元数据"""
    if mode is ImportMode.REPLACE and not dry_run and not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Replace import requires confirm=true",
        )

    meta_config = await _load_yaml(file)
    try:
        result = await service.import_metadata(meta_config, mode, dry_run)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return schemas.MetaImportResponse(
        mode=result.mode,
        dry_run=result.dry_run,
        tables=_to_import_changes(result.tables),
        columns=_to_import_changes(result.columns),
        metrics=_to_import_changes(result.metrics),
        index_sync_required=result.index_sync_required,
    )


@router.get("/export", response_class=Response)
async def export_metadata(service: MetaServiceDep) -> Response:
    """以 YAML 格式导出全部元数据"""
    try:
        meta_config = await service.export_metadata()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    content = yaml.safe_dump(
        meta_config.model_dump(mode="json", exclude_none=True),
        allow_unicode=True,
        sort_keys=False,
    )
    return Response(
        content=content,
        media_type="application/yaml",
        headers={"Content-Disposition": 'attachment; filename="metadata.yaml"'},
    )


@router.put("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_table_info(
    table_id: str,
    body: schemas.TableInfoRequest,
    service: MetaServiceDep,
) -> None:
    """新增或更新表元数据"""
    await service.upsert_table_info(
        TableInfo(
            id=table_id,
            name=body.name,
            role=body.role,
            primary_key_columns=body.primary_key_columns,
            description=body.description,
        )
    )


@router.put("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_column_info(
    column_id: str,
    body: schemas.ColumnInfoRequest,
    service: MetaServiceDep,
) -> None:
    """新增或更新字段元数据"""
    try:
        await service.upsert_column_info(
            ColumnInfo(
                id=column_id,
                name=body.name,
                type=body.type,
                examples=body.examples,
                description=body.description,
                alias=body.alias,
                index_values=body.index_values,
                reference_column_id=body.reference_column_id,
                table_id=body.table_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.put("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_metric_info(
    metric_id: str,
    body: schemas.MetricInfoRequest,
    service: MetaServiceDep,
) -> None:
    """新增或更新指标元数据"""
    await service.upsert_metric_info(
        MetricInfo(
            id=metric_id,
            name=body.name,
            description=body.description,
            relevant_columns=body.relevant_columns,
            alias=body.alias,
        )
    )


@router.post("/columns/sync", response_model=schemas.BatchIndexSyncResponse)
async def sync_column_indexes(
    body: schemas.ColumnIndexSyncRequest,
    service: IndexServiceDep,
) -> schemas.BatchIndexSyncResponse:
    """同步多个字段的向量索引"""
    try:
        results = await service.sync_column_indexes(body.column_ids)
    except ValueError as exc:
        _raise_not_found(exc)
    return schemas.BatchIndexSyncResponse(
        results=[
            schemas.IndexSyncResponse(
                resource_id=column_id,
                indexed_count=indexed_count,
            )
            for column_id, indexed_count in results.items()
        ]
    )


@router.post(
    "/columns/{column_id}/sync-values",
    response_model=schemas.IndexSyncResponse,
)
async def sync_column_values(
    column_id: str,
    service: IndexServiceDep,
) -> schemas.IndexSyncResponse:
    """同步单个字段的全部取值索引"""
    try:
        indexed_count = await service.sync_column_values(column_id)
    except ValueError as exc:
        _raise_not_found(exc)
    return schemas.IndexSyncResponse(
        resource_id=column_id,
        indexed_count=indexed_count,
    )


@router.post("/metrics/{metric_id}/sync", response_model=schemas.IndexSyncResponse)
async def sync_metric_index(
    metric_id: str,
    service: IndexServiceDep,
) -> schemas.IndexSyncResponse:
    """同步单个指标的向量索引"""
    try:
        indexed_count = await service.sync_metric_index(metric_id)
    except ValueError as exc:
        _raise_not_found(exc)
    return schemas.IndexSyncResponse(
        resource_id=metric_id,
        indexed_count=indexed_count,
    )


@router.post("/tables/{table_id}/sync", response_model=schemas.TableSyncResponse)
async def sync_table(
    table_id: str,
    service: IndexServiceDep,
) -> schemas.TableSyncResponse:
    """同步表下全部字段向量和字段值索引"""
    try:
        result = await service.sync_table(table_id)
    except ValueError as exc:
        _raise_not_found(exc)
    return schemas.TableSyncResponse(table_id=table_id, **result)
