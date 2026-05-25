from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine

from .routers import projects, tasks, attachments, process, project_contacts


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

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(attachments.router)
app.include_router(process.router)
app.include_router(project_contacts.router)


@app.get("/")
def root():
    return {"message": "TaskM API 运行中", "docs": "/docs"}


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "TaskM API"}
