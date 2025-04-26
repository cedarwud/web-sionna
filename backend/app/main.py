import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Import lifespan manager and API router from their new locations
from app.db.lifespan import lifespan
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)

# Create FastAPI app instance using the lifespan manager
app = FastAPI(
    title="Sionna RT Simulation API",
    description="API for running Sionna RT simulations and managing devices.",
    version="0.1.0",
    lifespan=lifespan,  # Use the imported lifespan context manager
)

# --- Static Files Mount ---
# 獲取 backend 目錄的絕對路徑
backend_dir = os.path.dirname(os.path.abspath(__file__))
# 構建相對於 backend 目錄的靜態文件夾路徑
static_files_dir = os.path.join(
    backend_dir, "..", "frontend", "public", "rendered_images"
)

# 檢查目錄是否存在，如果不存在則建立 (雖然 lifespan 中可能已經建立，但這裡多一層保障)
os.makedirs(static_files_dir, exist_ok=True)
logger.info(f"Static files directory set to: {static_files_dir}")

# 掛載靜態文件目錄到 /rendered_images URL 路徑
# 注意：name="static" 只是 FastAPI 內部的名稱，URL 路徑由第一個參數決定
app.mount(
    "/rendered_images", StaticFiles(directory=static_files_dir), name="rendered_images"
)
logger.info(
    f"Mounted static files directory '{static_files_dir}' at '/rendered_images'."
)

# --- CORS Middleware ---
# 允許特定域名的跨域請求，包括生產環境中的IP地址
origins = [
    "http://localhost",
    "http://localhost:5173",  # 本地開發環境
    "http://127.0.0.1:5173",
    "http://120.126.151.101",
    "http://120.126.151.101:5173",  # 生產環境 IP 地址
    # 添加任何其他需要的域名
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 使用明確的域名列表而不是 ["*"]
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法
    allow_headers=["*"],  # 允許所有頭部
)
logger.info("CORS middleware added with specific origins.")

# --- Include API Routers ---
# Include the router for API version 1
app.include_router(api_router, prefix="/api/v1")  # Add a /api/v1 prefix
logger.info("Included API router v1 at /api/v1.")


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a basic welcome message."""
    logger.info("--- Root endpoint '/' requested ---")
    return {"message": "Welcome to the Sionna RT Simulation API"}


# --- Uvicorn Entry Point (for direct run, if needed) ---
# Note: Running directly might skip lifespan events unless using uvicorn programmatically
if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting Uvicorn server directly (use 'docker-compose up' for full setup)..."
    )
    # This won't properly run the lifespan events like DB init unless configured differently.
    # Recommended to run via Docker Compose or `uvicorn app.main:app --reload` from the backend directory.
    uvicorn.run(app, host="0.0.0.0", port=8000)

logger.info(
    "FastAPI application setup complete. Ready for Uvicorn via external command."
)
