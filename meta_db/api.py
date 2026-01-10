from typing import Annotated

from auth import authentication, create_access_token, create_refresh_token
from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from query_meta import (
    get_col_by_dbcode_tbname_colname,
    get_tb_info_by_dbcode,
    retrieve_cell,
    retrieve_column,
    retrieve_knowledge,
)
from save_meta import clear_meta, save_meta

api_router = APIRouter(prefix="/api/v1")
metadata_router = APIRouter()


class SaveMetaRequest(BaseModel):
    save: dict[str, dict[str, list | None] | None] | None = Field(
        description="数据库元数据保存配置",
        examples=[
            {
                "db_code": {
                    "table": ["tb_code"],
                    "knowledge": ["kn_code"],
                    "cell": ["tb_code"],
                }
            }
        ],
    )


class GetTableRequest(BaseModel):
    db_code: str = Field(description="数据库编号")


class GetColumnRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    tb_col_tuple_list: list[tuple[str, str]] = Field(
        description="(tb_name, col_name) 的列表",
        examples=[[("tb_name", "col_name")]],
    )


class RetrieveKnowledgeRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    query: str = Field(description="查询")
    keywords: list[str] = Field(description="关键词列表")


class RetrieveColumnRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    keywords: list[str] = Field(description="关键词列表")


class RetrieveCellRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    keywords: list[str] = Field(description="关键词列表")


@metadata_router.get("/health")
async def health():
    return "live"


@metadata_router.post(
    "/save_metadata",
    dependencies=[Security(authentication, scopes=["save_metadata"])],
)
async def api_save_meta(req: SaveMetaRequest):
    await save_meta(req.save)


@metadata_router.post(
    "/clear_metadata",
    dependencies=[Security(authentication, scopes=["clear_metadata"])],
)
async def api_clear_meta():
    await clear_meta()


@metadata_router.post(
    "/get_table",
    dependencies=[Security(authentication, scopes=["get_table"])],
)
async def api_get_table(req: GetTableRequest):
    return await get_tb_info_by_dbcode(req.db_code)


@metadata_router.post(
    "/get_column",
    dependencies=[Security(authentication, scopes=["get_column"])],
)
async def api_get_column(req: GetColumnRequest):
    return await get_col_by_dbcode_tbname_colname(req.db_code, req.tb_col_tuple_list)


@metadata_router.post(
    "/retrieve_knowledge",
    dependencies=[Security(authentication, scopes=["retrieve_knowledge"])],
)
async def api_retrieve_knowledge(req: RetrieveKnowledgeRequest):
    return await retrieve_knowledge(req.db_code, req.query, req.keywords)


@metadata_router.post(
    "/retrieve_column",
    dependencies=[Security(authentication, scopes=["retrieve_column"])],
)
async def api_retrieve_column(req: RetrieveColumnRequest):
    return await retrieve_column(req.db_code, req.keywords)


@metadata_router.post(
    "/retrieve_cell",
    dependencies=[Security(authentication, scopes=["retrieve_cell"])],
)
async def api_retrieve_cell(req: RetrieveCellRequest):
    return await retrieve_cell(req.db_code, req.keywords)


@api_router.post("/refresh_token")
async def login_refresh_token(
    req: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    client_ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = getattr(req.client, "host", "unknown")
    username = form_data.username
    password = form_data.password
    return await create_refresh_token(username, password, client_ip)


@api_router.post("/access_token")
async def refresh_access_token(
    req: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    client_ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = getattr(req.client, "host", "unknown")
    refresh_token = form_data.refresh_token
    scopes = form_data.scopes
    return await create_access_token(refresh_token, scopes, client_ip)


api_router.include_router(metadata_router, prefix="/metadata")
