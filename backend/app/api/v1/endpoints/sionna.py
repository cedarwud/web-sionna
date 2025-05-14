import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import sionna.rt as rt
from pathlib import Path
from typing import List

import numpy as np
from pydantic import BaseModel

from app.api.deps import get_session  # Import dependency
from app.services.sionna_simulation import (  # Import service functions
    generate_empty_scene_image,
    generate_cfr_plot,  # 新增: 導入剛添加的 CFR 繪圖函數
    generate_sinr_map,  # 新增: 導入 SINR 地圖生成函數
    generate_doppler_plots,  # 新增: 導入延遲多普勒圖生成函數
    generate_channel_response_plots,  # 新增: 導入通道響應圖生成函數
)
from app.core.config import (  # Import constants
    STATIC_IMAGES_DIR,
    MODELS_DIR,
    CFR_PLOT_IMAGE_PATH,  # 新增: 導入 CFR 圖片路徑
    SINR_MAP_IMAGE_PATH,  # 新增: 導入 SINR 地圖路徑
    CHANNEL_RESPONSE_IMAGE_PATH,  # 新增: 導入通道響應圖路徑
    DOPPLER_IMAGE_PATH,  # 新增: 導入新的延遲多普勒圖路徑
)
from app.crud import crud_device  # 新增: 導入 crud_device 以獲取設備資料
from app.db.models import DeviceRole  # 新增: 導入 DeviceRole 枚舉

# 新增: 導入 run_in_threadpool
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/models/{model_name}", tags=["Models"])
async def get_model_glb(model_name: str):
    """
    提供指定名稱的 3D 模型 GLB 檔案。
    """
    # **安全性**: 基本的檔名驗證，防止路徑遍歷
    if ".." in model_name or "/" in model_name or "\\" in model_name:
        logger.warning(f"請求了無效的模型名稱: {model_name}")
        raise HTTPException(status_code=400, detail="無效的模型檔案名稱。")

    # 確保 MODELS_DIR 是 Path 對象 (通常在 config.py 中定義)
    if not isinstance(MODELS_DIR, Path):
        logger.error(f"MODELS_DIR 設定錯誤，不是 Path 對象: {MODELS_DIR}")
        raise HTTPException(
            status_code=500, detail="伺服器配置錯誤: 模型儲存路徑無效。"
        )

    model_path = MODELS_DIR / f"{model_name}.glb"  # 假設所有模型都是 .glb

    logger.info(f"請求模型檔案: {model_path}")

    if not model_path.is_file():
        logger.error(f"模型檔案不存在: {model_path}")
        raise HTTPException(status_code=404, detail=f"找不到模型檔案: {model_name}.glb")

    return FileResponse(
        path=str(model_path),
        media_type="model/gltf-binary",
        filename=f"{model_name}.glb",
    )


@router.get("/scene-image-devices", tags=["Sionna Simulation"])
async def get_scene_image_devices_endpoint():
    """Generates and returns the Sionna scene image with only the base map (no devices)."""
    logger.info("--- API Request: /scene-image-devices (empty map only) ---")

    temp_image_path = STATIC_IMAGES_DIR / "scene_with_devices.png"

    # 刪除舊的圖檔 (如果存在)
    if os.path.exists(temp_image_path):
        logger.info(f"刪除舊的空場景圖檔: {temp_image_path}")
        os.remove(temp_image_path)

    success = await run_in_threadpool(
        generate_empty_scene_image, output_path=str(temp_image_path)
    )
    if success and os.path.exists(temp_image_path):
        file_size = os.path.getsize(temp_image_path)
        logger.info(f"Returning image for {temp_image_path} (Size: {file_size} bytes)")

        def iterfile():
            with open(temp_image_path, "rb") as f:
                chunk = f.read(4096)
                while chunk:
                    yield chunk
                    chunk = f.read(4096)

        return StreamingResponse(
            iterfile(),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=scene_with_devices.png"
            },
        )
    else:
        logger.error(f"File not found or failed to generate: {temp_image_path}")
        raise HTTPException(
            status_code=500, detail="Failed to render empty scene image."
        )


@router.get("/cfr-plot", tags=["Sionna Simulation"])
async def get_cfr_plot_endpoint(session: AsyncSession = Depends(get_session)):
    """生成並返回 Channel Frequency Response (CFR) 圖，基於 Sionna 的模擬。"""
    logger.info("--- API Request: /cfr-plot ---")

    # 確保對應服務函數會刪除舊的圖檔
    if await generate_cfr_plot(session=session, output_path=str(CFR_PLOT_IMAGE_PATH)):
        if os.path.exists(CFR_PLOT_IMAGE_PATH):
            file_size = os.path.getsize(CFR_PLOT_IMAGE_PATH)
            logger.info(
                f"返回 CFR 圖像，文件路徑: {CFR_PLOT_IMAGE_PATH} (大小: {file_size} 字節)"
            )

            # 使用 StreamingResponse 從文件流直接返回
            def iterfile():
                with open(CFR_PLOT_IMAGE_PATH, "rb") as f:
                    # 每次讀取 4KB
                    chunk = f.read(4096)
                    while chunk:
                        yield chunk
                        chunk = f.read(4096)

            return StreamingResponse(
                iterfile(),
                media_type="image/png",
                headers={"Content-Disposition": f"attachment; filename=cfr_plot.png"},
            )
        else:
            logger.error(f"生成後找不到文件: {CFR_PLOT_IMAGE_PATH}")
            raise HTTPException(
                status_code=500,
                detail="生成 CFR 圖後找不到文件。",
            )
    else:
        logger.error("生成 CFR 圖失敗。")
        raise HTTPException(status_code=500, detail="生成 CFR 圖失敗。")


@router.get("/sinr-map", tags=["Sionna Simulation"])
async def get_sinr_map_endpoint(
    session: AsyncSession = Depends(get_session),
    sinr_vmin: float = Query(-40.0, description="SINR 最小值 (dB)"),
    sinr_vmax: float = Query(0.0, description="SINR 最大值 (dB)"),
    cell_size: float = Query(1.0, description="Radio map 網格大小 (m)"),
    samples_per_tx: int = Query(10**7, description="每個發射器的採樣數量"),
):
    """生成並返回 SINR (Signal-to-Interference-plus-Noise Ratio) 地圖。"""
    logger.info(
        f"--- API Request: /sinr-map?sinr_vmin={sinr_vmin}&sinr_vmax={sinr_vmax}&cell_size={cell_size}&samples_per_tx={samples_per_tx} ---"
    )

    # 確保對應服務函數會刪除舊的圖檔
    if await generate_sinr_map(
        session=session,
        output_path=str(SINR_MAP_IMAGE_PATH),
        sinr_vmin=sinr_vmin,
        sinr_vmax=sinr_vmax,
        cell_size=cell_size,
        samples_per_tx=samples_per_tx,
    ):
        if os.path.exists(SINR_MAP_IMAGE_PATH):
            file_size = os.path.getsize(SINR_MAP_IMAGE_PATH)
            logger.info(
                f"返回 SINR 地圖，文件路徑: {SINR_MAP_IMAGE_PATH} (大小: {file_size} 字節)"
            )

            # 使用 StreamingResponse 從文件流直接返回
            def iterfile():
                with open(SINR_MAP_IMAGE_PATH, "rb") as f:
                    # 每次讀取 4KB
                    chunk = f.read(4096)
                    while chunk:
                        yield chunk
                        chunk = f.read(4096)

            return StreamingResponse(
                iterfile(),
                media_type="image/png",
                headers={"Content-Disposition": f"attachment; filename=sinr_map.png"},
            )
        else:
            logger.error(f"生成後找不到文件: {SINR_MAP_IMAGE_PATH}")
            raise HTTPException(
                status_code=500,
                detail="生成 SINR 地圖後找不到文件。",
            )
    else:
        logger.error("生成 SINR 地圖失敗。")
        raise HTTPException(status_code=500, detail="生成 SINR 地圖失敗。")


@router.get("/doppler-plots", tags=["Sionna Simulation"])
async def get_doppler_plots_endpoint(session: AsyncSession = Depends(get_session)):
    """
    生成並返回延遲多普勒圖，顯示每個發射器和組合後的延遲多普勒域圖。
    從資料庫中獲取發射器和接收器數據，必須有至少一個活動的發射器和接收器。
    """
    logger.info("--- API Request: /doppler-plots ---")

    # 刪除舊的圖檔 (如果存在)
    if os.path.exists(DOPPLER_IMAGE_PATH):
        logger.info(f"刪除舊的延遲多普勒圖檔: {DOPPLER_IMAGE_PATH}")
        os.remove(DOPPLER_IMAGE_PATH)

    # 生成延遲多普勒圖
    success = await generate_doppler_plots(session, str(DOPPLER_IMAGE_PATH))

    if not success:
        logger.error("延遲多普勒圖生成失敗")
        raise HTTPException(status_code=500, detail="延遲多普勒圖生成失敗")

    # 檢查圖像是否已生成
    if not os.path.exists(DOPPLER_IMAGE_PATH):
        logger.error("延遲多普勒圖文件未生成或找不到")
        raise HTTPException(status_code=500, detail="延遲多普勒圖文件未生成或找不到")

    # 直接返回圖像流
    def iterfile():
        with open(DOPPLER_IMAGE_PATH, "rb") as f:
            # 每次讀取4KB
            chunk = f.read(4096)
            while chunk:
                yield chunk
                chunk = f.read(4096)

    return StreamingResponse(
        iterfile(),
        media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename=delay_doppler.png"},
    )


# 新增通道響應圖端點
@router.get("/channel-response-plots", tags=["Sionna Simulation"])
async def get_channel_response_plots(session: AsyncSession = Depends(get_session)):
    """
    生成並返回通道響應圖，顯示 H_des、H_jam 和 H_all 的三維圖。
    從資料庫中獲取發射器和接收器數據，必須有至少一個活動的發射器和接收器。
    """
    logger.info("--- API Request: /channel-response-plots ---")

    # 刪除舊的圖檔 (如果存在)
    if os.path.exists(CHANNEL_RESPONSE_IMAGE_PATH):
        logger.info(f"刪除舊的通道響應圖檔: {CHANNEL_RESPONSE_IMAGE_PATH}")
        os.remove(CHANNEL_RESPONSE_IMAGE_PATH)

    # 檢查資料庫中是否有足夠的設備
    active_desired = await crud_device.get_devices_by_role(
        db=session, role=DeviceRole.DESIRED.value, active_only=True
    )
    active_receivers = await crud_device.get_devices_by_role(
        db=session, role=DeviceRole.RECEIVER.value, active_only=True
    )

    if not active_desired:
        logger.error("沒有活動的發射器")
        raise HTTPException(
            status_code=400,
            detail="需要至少一個活動的發射器才能生成通道響應圖。請在資料庫中添加並啟用發射器。",
        )

    if not active_receivers:
        logger.error("沒有活動的接收器")
        raise HTTPException(
            status_code=400,
            detail="需要至少一個活動的接收器才能生成通道響應圖。請在資料庫中添加並啟用接收器。",
        )

    # 檢查文件是否已經存在
    if (
        not os.path.exists(CHANNEL_RESPONSE_IMAGE_PATH)
        or os.path.getsize(CHANNEL_RESPONSE_IMAGE_PATH) == 0
    ):
        logger.info("通道響應圖不存在或為空，正在生成...")
        success = await generate_channel_response_plots(
            session,
            str(CHANNEL_RESPONSE_IMAGE_PATH),
        )
        if not success:
            logger.error("生成通道響應圖失敗")
            raise HTTPException(status_code=500, detail="生成通道響應圖失敗")

    # 再次檢查文件是否存在
    if not os.path.exists(CHANNEL_RESPONSE_IMAGE_PATH):
        logger.error(f"文件生成後仍不存在: {CHANNEL_RESPONSE_IMAGE_PATH}")
        raise HTTPException(status_code=500, detail="通道響應圖生成失敗")

    # 使用StreamingResponse返回文件
    def iterfile():
        with open(CHANNEL_RESPONSE_IMAGE_PATH, "rb") as f:
            # 每次讀取4KB
            chunk = f.read(4096)
            while chunk:
                yield chunk
                chunk = f.read(4096)

    return StreamingResponse(
        iterfile(),
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=channel_response_plots.png"
        },
    )
