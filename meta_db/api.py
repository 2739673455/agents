from typing import Annotated

from auth import (
    authentication,
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
)
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


@api_router.get("/health")
async def health():
    return "live"


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


class GetTableRequest(BaseModel):
    db_code: str = Field(description="数据库编号")


@metadata_router.post(
    "/get_table",
    dependencies=[Security(authentication, scopes=["get_table"])],
)
async def api_get_table(req: GetTableRequest):
    return await get_tb_info_by_dbcode(req.db_code)


class GetColumnRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    tb_col_tuple_list: list[tuple[str, str]] = Field(
        description="(tb_name, col_name) 的列表",
        examples=[[("tb_name", "col_name")]],
    )


@metadata_router.post(
    "/get_column",
    dependencies=[Security(authentication, scopes=["get_column"])],
)
async def api_get_column(req: GetColumnRequest):
    return await get_col_by_dbcode_tbname_colname(req.db_code, req.tb_col_tuple_list)


class RetrieveKnowledgeRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    query: str = Field(description="查询")
    keywords: list[str] = Field(description="关键词列表")


@metadata_router.post(
    "/retrieve_knowledge",
    dependencies=[Security(authentication, scopes=["retrieve_knowledge"])],
)
async def api_retrieve_knowledge(req: RetrieveKnowledgeRequest):
    return await retrieve_knowledge(req.db_code, req.query, req.keywords)


class RetrieveColumnRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    keywords: list[str] = Field(description="关键词列表")


@metadata_router.post(
    "/retrieve_column",
    dependencies=[Security(authentication, scopes=["retrieve_column"])],
)
async def api_retrieve_column(req: RetrieveColumnRequest):
    return await retrieve_column(req.db_code, req.keywords)


class RetrieveCellRequest(BaseModel):
    db_code: str = Field(description="数据库编号")
    keywords: list[str] = Field(description="关键词列表")


@metadata_router.post(
    "/retrieve_cell",
    dependencies=[Security(authentication, scopes=["retrieve_cell"])],
)
async def api_retrieve_cell(req: RetrieveCellRequest):
    return await retrieve_cell(req.db_code, req.keywords)


@api_router.post("/auth/login")
async def login(
    req: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """用户名密码登录，返回 access_token 和 refresh_token"""
    client_ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = getattr(req.client, "host", "unknown")
    username = form_data.username
    password = form_data.password
    return await create_refresh_token(username, password, client_ip)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(description="刷新令牌")
    scopes: list[str] = Field(default=[], description="请求的权限范围列表")


@api_router.post("/auth/refresh")
async def refresh(req: Request, body: RefreshTokenRequest):
    """使用 refresh_token 换取新的 access_token"""
    client_ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = getattr(req.client, "host", "unknown")
    return await create_access_token(body.refresh_token, body.scopes, client_ip)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(description="刷新令牌")


@api_router.post("/auth/logout")
async def logout(req: Request, body: LogoutRequest):
    """撤销 refresh_token"""
    client_ip = req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = getattr(req.client, "host", "unknown")
    return await revoke_refresh_token(body.refresh_token, client_ip)


api_router.include_router(metadata_router, prefix="/metadata")
