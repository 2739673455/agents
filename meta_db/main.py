from contextlib import asynccontextmanager

from api import api_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

    uvicorn.run("main:app", host="0.0.0.0", port=12321)
