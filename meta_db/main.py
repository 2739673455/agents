from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from save_meta import clear_meta, save_meta

metadata_router = APIRouter()


@metadata_router.get("/health")
async def health():
    return 200


@metadata_router.post("/save_metadata")
async def save_metadata(save):
    await save_meta(save)


@metadata_router.post("/clear_metadata")
async def clear_metadata():
    await clear_meta()


api_router = APIRouter(prefix="/api")
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
