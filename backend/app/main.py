import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.db.lifespan import lifespan
from app.api.v1.router import api_router
from app.api.v1.endpoints.skybridge import router as skybridge_router
from app.core.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# 建立 FastAPI 應用
app = FastAPI(
    title="Sionna RT Simulation API",
    description="API for running Sionna RT simulations and managing devices.",
    version="0.1.0",
    lifespan=lifespan,
)

# 靜態目錄：渲染圖片和模型
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/rendered_images", StaticFiles(directory=OUTPUT_DIR), name="rendered_images")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# CORS 設定
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_router, prefix="/api/v1")
app.include_router(skybridge_router, prefix="/api/v1/skybridge", tags=["skybridge"])


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Sionna RT Simulation API"}
