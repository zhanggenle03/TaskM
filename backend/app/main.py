from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
from .database import Base, engine, UPLOAD_DIR

from .routers import projects, tasks, attachments, process, project_contacts, export as export_router, requirements


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ── 启动时 ──
    try:
        from .process_manager import on_startup
        on_startup()
    except Exception as e:
        print(f"[lifespan] on_startup failed: {e}", flush=True)

    yield

    # ── 关闭时 ──
    try:
        from .process_manager import on_shutdown
        on_shutdown()
    except Exception:
        pass


Base.metadata.create_all(bind=engine)

app = FastAPI(title="TaskM API", version="1.0.0", lifespan=lifespan, debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(attachments.router, prefix="/api")
app.include_router(process.router, prefix="/api")
app.include_router(project_contacts.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
app.include_router(requirements.router, prefix="/api")

# 挂载上传目录为静态文件（供富文本图片等访问）
import os
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ── 生产模式：前端静态文件服务（通过环境变量 TASKM_FRONTEND_DIST 控制） ──
_FRONTEND_DIST = os.environ.get("TASKM_FRONTEND_DIST", "")

if _FRONTEND_DIST and os.path.isdir(_FRONTEND_DIST):
    # 挂载前端静态资源目录（JS/CSS/字体等）
    assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend_assets")

    # 覆写根路由为前端首页
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"), media_type="text/html")

    # SPA fallback：非 API/非文件路由返回 index.html
    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        path = request.url.path
        if not path.startswith("/api") and not path.startswith("/uploads"):
            return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"), media_type="text/html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)
else:
    # ── 开发模式：API 运行状态（由 Vite 代理代理 /api） ──
    @app.get("/")
    def root():
        return {"message": "TaskM API 运行中", "docs": "/docs"}


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "TaskM API"}
