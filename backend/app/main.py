from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
from .database import Base, engine, UPLOAD_DIR
from .settings_manager import get_port

from .routers import projects, tasks, attachments, process, project_contacts, export as export_router, requirements, backup, attendance_export
from .routers import categories as categories_router
from .routers import salary as salary_router
from .routers import leave


# ── 从配置读取端口（用于 CORS 白名单） ──
_BACKEND_PORT = get_port("backend_port", 8000)
_FRONTEND_PORT = get_port("frontend_port", 5173)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ── 启动迁移：补齐 projects.category 列（必须在任何查询前执行） ──
    try:
        from .database import _ensure_project_category_column
        _ensure_project_category_column()
    except Exception as e:
        print(f"[lifespan] 数据库迁移失败: {e}", flush=True)

    # ── 启动迁移：补齐 checkin_projects.man_days 列（多项目按项目分配人天） ──
    try:
        from .database import _ensure_checkin_project_mandays_column
        _ensure_checkin_project_mandays_column()
    except Exception as e:
        print(f"[lifespan] checkin_projects 迁移失败: {e}", flush=True)

    # ── 启动时 ──
    try:
        from .process_manager import on_startup
        on_startup()
    except Exception as e:
        print(f"[lifespan] on_startup failed: {e}", flush=True)

    # ── 启动后尝试重新应用自启动（无沙箱限制时生效） ──
    try:
        from .settings_manager import load_settings
        from .routers.process import _enable_autostart, AUTOSTART_SETTINGS_KEY
        saved = load_settings().get(AUTOSTART_SETTINGS_KEY, {})
        saved_mode = saved.get("mode", "off")
        if saved_mode != "off":
            _enable_autostart()
            print(f"[lifespan] 已更新自启动脚本", flush=True)
    except Exception as e:
        print(f"[lifespan] 应用自启动失败: {e}", flush=True)

    # 启动备份调度线程
    try:
        from .backup_service import start_background_scheduler
        start_background_scheduler()
    except Exception as e:
        print(f"[lifespan] 备份调度线程启动失败: {e}", flush=True)

    # 预取并缓存节假日数据（后台线程，不阻塞启动；用户打开工作记录前已就绪）
    try:
        from .holiday_service import prefetch_on_startup
        prefetch_on_startup()
        print("[lifespan] 节假日缓存预取已启动", flush=True)
    except Exception as e:
        print(f"[lifespan] 节假日预取启动失败: {e}", flush=True)

    yield

    # ── 关闭时 ──
    try:
        from .process_manager import on_shutdown
        on_shutdown()
    except Exception:
        pass
    # 停止备份调度线程
    try:
        from .backup_service import stop_background_scheduler
        stop_background_scheduler()
    except Exception:
        pass


Base.metadata.create_all(bind=engine)

# 幂等迁移：为已存在的 salary_items 表补充 base/rate 列（全新库由 create_all 直接带出）
from .database import ensure_salary_item_columns, ensure_salary_record_columns, ensure_salary_item_tax_deductible, ensure_salary_item_taxable, ensure_tax_adjustment_table, ensure_communication_subject_column, ensure_communication_protected_fake_column, ensure_salary_slip_table, ensure_salary_slip_multi, ensure_salary_config_template_table, ensure_salary_config_template_drop_effective_from, migrate_salary_config_from_settings
ensure_salary_item_columns(engine)
ensure_salary_record_columns(engine)
ensure_salary_item_tax_deductible(engine)
ensure_salary_item_taxable(engine)
ensure_tax_adjustment_table(engine)
ensure_communication_subject_column(engine)
ensure_communication_protected_fake_column(engine)
ensure_salary_slip_table(engine)
ensure_salary_slip_multi(engine)
ensure_salary_config_template_table(engine)
ensure_salary_config_template_drop_effective_from(engine)
migrate_salary_config_from_settings()

app = FastAPI(title="TaskM API", version="1.0.0", lifespan=lifespan, debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{_FRONTEND_PORT}", "http://localhost:3000"],
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
app.include_router(backup.router, prefix="/api")
app.include_router(attendance_export.router, prefix="/api")
app.include_router(categories_router.router, prefix="/api")
app.include_router(salary_router.router, prefix="/api")
app.include_router(leave.router, prefix="/api/leave")

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
