from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from query_meta import (
    get_col_by_dbcode_tbname_colname,
    get_tb_info_by_dbcode,
    retrieve_cell,
    retrieve_column,
    retrieve_knowledge,
)
from save_meta import clear_meta, save_meta

ALL_SCOPES = {
    "health_check": "服务健康检查",
    "save_metadata": "写入元数据",
    "clear_metadata": "清空元数据",
    "get_table": "获取表信息",
    "get_column": "获取字段信息",
    "retrieve_knowledge": "检索知识",
    "retrieve_column": "检索字段",
    "retrieve_cell": "检索单元格",
}
SECRET_KEY = "d6a5d730ec247d487f17419df966aec9d4c2a09d2efc9699d09757cf94c68b01"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
GROUP_DB = {
    "root": {"allowed_scopes": list(ALL_SCOPES.keys())},
}
USER_DB = {
    "root": {
        "group": "root",
        "username": "root",
        "email": "root@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",
    }
}

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scopes=ALL_SCOPES)
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
    return 200


@metadata_router.post("/save_metadata")
async def api_save_meta(req: SaveMetaRequest):
    await save_meta(req.save)


@metadata_router.post("/clear_metadata")
async def api_clear_meta():
    await clear_meta()


@metadata_router.post("/get_table")
async def api_get_table(req: GetTableRequest):
    return await get_tb_info_by_dbcode(req.db_code)


@metadata_router.post("/get_column")
async def api_get_column(req: GetColumnRequest):
    return await get_col_by_dbcode_tbname_colname(req.db_code, req.tb_col_tuple_list)


@metadata_router.post("/retrieve_knowledge")
async def api_retrieve_knowledge(req: RetrieveKnowledgeRequest):
    return await retrieve_knowledge(req.db_code, req.query, req.keywords)


@metadata_router.post("/retrieve_column")
async def api_retrieve_column(req: RetrieveColumnRequest):
    return await retrieve_column(req.db_code, req.keywords)


@metadata_router.post("/retrieve_cell")
async def api_retrieve_cell(req: RetrieveCellRequest):
    return await retrieve_cell(req.db_code, req.keywords)


@api_router.post("/token")
async def login(req: Annotated[OAuth2PasswordRequestForm, Depends()]):
    username = req.username
    password = req.password
    scopes = req.scopes

    group = USER_DB[username]["group"]
    allowed_scopes = GROUP_DB[group]["allowed_scopes"]

    if not (
        username in USER_DB
        and password_hash.verify(password, USER_DB[username]["password"])
    ):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": f"username:{username}", "scope": " ".join(scopes), "exp": expire}
    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}


api_router.include_router(metadata_router, prefix="/metadata")
