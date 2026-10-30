import sys
from pathlib import Path
import os
from contextlib import AsyncExitStack, asynccontextmanager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)

if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import chat
from app.api.v1 import oss
from app.common.logger import setup_logging
from app.agent.law import create_law_agent, model
from app.refagent.evidence_review import EvidenceReviewer
from app.common.path import DATABASE_PATH
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 初始化日志配置
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MCP tools and build the Agent once when the web app starts."""
    async with AsyncExitStack() as mcp_stack:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        app.state.checkpointer = await mcp_stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(str(DATABASE_PATH))
        )
        await app.state.checkpointer.setup()
        app.state.agent = await create_law_agent(mcp_stack, app.state.checkpointer)
        app.state.reviewer = EvidenceReviewer(model)
        yield

app = FastAPI(
    title="Personal Chief API",
    description="私厨",
    version="0.1.0",
    lifespan=lifespan,
)

# 同源托管前端和 API 时不需要 CORS。只有单独部署前端时才配置明确的可信域名。
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok"}

# 2.挂载路由
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(oss.router, prefix="/api/v1", tags=["申请上传签名url"])

# 3.挂载前端资源
static_dir = Path(__file__).resolve().parent / "static"

# 前端 fallback 路由 - 只处理非 API 请求
@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str):
    # 排除 API 路径
    if path.startswith("api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Not Found"}, status_code=404)
    # 如果请求的是静态文件，直接返回
    static_root = static_dir.resolve()
    file_path = (static_root / path).resolve()
    try:
        file_path.relative_to(static_root)
    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Not Found"}, status_code=404)
    if file_path.is_file():
        return FileResponse(file_path)
    # 否则返回 index.html（SPA fallback）
    index_path = static_root / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return {"message": "你的独家私厨上线了~", "status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # 启动命令：python -m app.main
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
