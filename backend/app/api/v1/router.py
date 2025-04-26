# backend/app/api/v1/router.py
from fastapi import APIRouter
# 從 endpoints 目錄導入 sionna 和 新的 interferers 路由
from app.api.v1.endpoints import sionna, interferers # <--- 新增 import

api_router = APIRouter()

# 包含現有的 sionna 路由
api_router.include_router(sionna.router, prefix="/sionna", tags=["Sionna Simulation"])

# --- 新增 ---
# 包含新的 interferers 路由
api_router.include_router(interferers.router, prefix="/interferers", tags=["Interferers"])
# --- 結束新增 ---

# Add other endpoint routers here later, e.g., for device CRUD
# api_router.include_router(devices.router, prefix="/devices", tags=["Devices"])