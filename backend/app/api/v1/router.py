# backend/app/api/v1/router.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from .api import api_router_v1
import os

# 導入領域特定的 API 路由器
from app.domains.device.api.device_api import router as device_router
from app.domains.coordinates.api.coordinate_api import router as coordinate_router
from app.domains.simulation.api.simulation_api import router as simulation_router

# 創建主要的 API 路由器
api_router = APIRouter()

# Sionna 模型相關路由器
sionna_router = APIRouter()

@sionna_router.get("/models/{model_name}")
async def get_sionna_model(model_name: str):
    """獲取Sionna模型文件（tower, jam, uav, sat）"""
    model_path = f"/app/app/static/models/{model_name}.glb"
    
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
    
    return FileResponse(
        path=model_path,
        media_type="model/gltf-binary",
        filename=f"{model_name}.glb"
    )

# 包含子路由器
api_router.include_router(api_router_v1, tags=["API v1"])

# 包含領域特定的路由器
api_router.include_router(device_router, prefix="/devices", tags=["Devices"])
api_router.include_router(coordinate_router, prefix="/coordinates", tags=["Coordinates"])
api_router.include_router(simulation_router, prefix="/simulations", tags=["Simulations"])

# 包含Sionna相關路由器
api_router.include_router(sionna_router, prefix="/sionna", tags=["Sionna Models"])
