"""FastAPI app của Harness Agent Call Center (bước 17).

Chạy máy chủ (từ thư mục Code/, MỘT worker — pipeline, khóa lượt và kho phiên nằm trong tiến trình):
    uvicorn api.app:app --host 127.0.0.1 --port 8000
Tài liệu tương tác: http://127.0.0.1:8000/docs . Biến môi trường: IDLE_TIMEOUT_S (mặc định 1800, bộ quét nền chốt cuộc bỏ dở), API_TRACE_FILE (mặc định runs/api_session.jsonl).
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from monitoring.metrics import Registry

from .routes import router
from .sessions import SessionStore


def _build_pipeline():
    from pipeline import CallCenterHarnessPipeline
    p = CallCenterHarnessPipeline(trace_file=os.environ.get("API_TRACE_FILE") or "runs/api_session.jsonl")
    cap = (os.environ.get("API_MAX_COST_VND") or "").strip()
    if cap:                                                          # trần chi phí cứng cho cả máy chủ (demo): client kiểm trước MỖI lần gọi API
        p.llm_client.cost_tracker.set_hard_cap(float(cap))
    p.start_idle_sweeper(idle_seconds=float(os.environ.get("IDLE_TIMEOUT_S") or 1800))
    return p


def create_app(pipeline=None) -> FastAPI:
    """`pipeline=None` → dựng pipeline thật lúc khởi động (và đóng lúc tắt); truyền pipeline vào (test) → API dùng nó và không đóng hộ."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = app.state.pipeline is None
        if owned:
            app.state.pipeline = await asyncio.to_thread(_build_pipeline)     # dựng pipeline mở tiến trình MCP — không chạy trên vòng lặp sự kiện
        yield
        if owned:
            await asyncio.to_thread(app.state.pipeline.close)

    app = FastAPI(title="Harness Agent Call Center API", lifespan=lifespan)
    app.state.pipeline = pipeline
    app.state.sessions = SessionStore()
    app.state.metrics = Registry()
    app.include_router(router)
    ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")      # giao diện bước 18: cùng origin với API nên không cần CORS
    if os.path.isdir(ui_dir):
        app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

        @app.get("/", include_in_schema=False)
        def root():
            return RedirectResponse("/ui/")
    return app


app = create_app()
