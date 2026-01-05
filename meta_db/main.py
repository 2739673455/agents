from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from query_meta import (
    get_col_by_dbcode_tbname_colname,
    get_tb_info_by_dbcode,
    retrieve_cell,
    retrieve_column,
    retrieve_knowledge,
)
from save_meta import clear_meta, save_meta


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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
metadata_router = APIRouter()


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


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(metadata_router, prefix="/metadata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 服务启动时的初始化操作

    # 应用运行期间
    yield

    # 服务关闭时的清理操作


# 创建 FastAPI 应用
app = FastAPI(lifespan=lifespan)

# 添加 CORS(Cross-Origin Resource Sharing，跨域资源共享) 中间件，允许前端应用从不同域名访问API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有头部
)

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=12321, reload=True)
