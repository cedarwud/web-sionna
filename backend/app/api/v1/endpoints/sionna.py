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
    generate_scene_with_paths_image,
    get_active_devices_from_db_efficient,
    add_to_scene_safe,
    generate_empty_scene_image,
    generate_cfr_plot,  # 新增: 導入剛添加的 CFR 繪圖函數
    generate_sinr_map,  # 新增: 導入 SINR 地圖生成函數
    generate_doppler_plots,  # 新增: 導入延遲多普勒圖生成函數
    generate_channel_response_plots,  # 新增: 導入通道響應圖生成函數
)
from app.core.config import (  # Import constants
    SCENE_WITH_PATHS_IMAGE_PATH,
    STATIC_IMAGES_DIR,
    MODELS_DIR,
    CFR_PLOT_IMAGE_PATH,  # 新增: 導入 CFR 圖片路徑
    SINR_MAP_IMAGE_PATH,  # 新增: 導入 SINR 地圖路徑
    UNSCALED_DOPPLER_IMAGE_PATH,  # 新增: 導入未縮放的延遲多普勒圖路徑
    POWER_SCALED_DOPPLER_IMAGE_PATH,  # 新增: 導入功率縮放的延遲多普勒圖路徑
    CHANNEL_RESPONSE_IMAGE_PATH,  # 新增: 導入通道響應圖路徑
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


@router.get("/scene-image-rt", tags=["Sionna Simulation"])
async def get_scene_image_rt_endpoint(session: AsyncSession = Depends(get_session)):
    """Generates and returns the Sionna scene image with RT paths using data from DB."""
    logger.info("--- API Request: /scene-image-rt ---")
    if await generate_scene_with_paths_image(SCENE_WITH_PATHS_IMAGE_PATH, session):
        if os.path.exists(SCENE_WITH_PATHS_IMAGE_PATH):
            file_size = os.path.getsize(SCENE_WITH_PATHS_IMAGE_PATH)
            logger.info(
                f"Returning image for {SCENE_WITH_PATHS_IMAGE_PATH} (Size: {file_size} bytes)"
            )

            # 使用StreamingResponse從文件流直接返回
            def iterfile():
                with open(SCENE_WITH_PATHS_IMAGE_PATH, "rb") as f:
                    # 每次讀取4KB
                    chunk = f.read(4096)
                    while chunk:
                        yield chunk
                        chunk = f.read(4096)

            return StreamingResponse(
                iterfile(),
                media_type="image/png",
                headers={
                    "Content-Disposition": f"attachment; filename=scene_with_paths.png"
                },
            )
        else:
            logger.error(
                f"File not found after generation: {SCENE_WITH_PATHS_IMAGE_PATH}"
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to find scene image with paths after rendering.",
            )
    else:
        logger.error("Failed to render scene with paths.")
        raise HTTPException(status_code=500, detail="Failed to render scene with paths")


@router.get("/scene-image-devices", tags=["Sionna Simulation"])
async def get_scene_image_devices_endpoint():
    """Generates and returns the Sionna scene image with only the base map (no devices)."""
    logger.info("--- API Request: /scene-image-devices (empty map only) ---")

    temp_image_path = STATIC_IMAGES_DIR / "scene_with_devices.png"

    # 只產生純地圖，不畫任何節點
    from app.services.sionna_simulation import generate_empty_scene_image

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


@router.post("/generate-scene-image", tags=["Sionna Scene Management"])
async def trigger_generate_scene_image(
    filename: str = Query(
        "empty_scene.png",
        description="儲存的圖片檔案名稱 (將存在於 static/images/)",
    )
):
    """
    觸發伺服器生成基於 GLB 的場景圖像並儲存。
    """
    logger.info(f"--- API Request: /generate-scene-image?filename={filename} ---")

    # **安全性**: 基本的檔名驗證，防止路徑遍歷
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="無效的檔案名稱。")

    # 構造完整的輸出路徑
    # 確保 STATIC_IMAGES_DIR 是 Path 對象
    if not isinstance(STATIC_IMAGES_DIR, Path):
        logger.error(f"STATIC_IMAGES_DIR 設定錯誤，不是 Path 對象: {STATIC_IMAGES_DIR}")
        raise HTTPException(
            status_code=500, detail="伺服器配置錯誤: 圖像儲存路徑無效。"
        )

    output_file_path = STATIC_IMAGES_DIR / filename
    output_path_str = str(output_file_path)

    logger.info(f"請求將渲染圖像儲存至伺服器路徑: {output_path_str}")

    try:
        # 使用 run_in_threadpool 執行同步函數，避免阻塞
        success = await run_in_threadpool(
            generate_empty_scene_image, output_path=output_path_str
        )
        if success:
            logger.info(f"圖像成功生成並儲存至: {output_path_str}")
            return {
                "message": "Scene image generated successfully.",
                "path": output_path_str,  # 回傳相對於伺服器的路徑可能更有用，或是一個可訪問的 URL
            }
        else:
            logger.error(f"伺服器端生成圖像失敗。目標路徑: {output_path_str}")
            raise HTTPException(status_code=500, detail="伺服器端生成圖像失敗。")
    except Exception as e:
        logger.exception(f"呼叫 generate_empty_scene_image 時發生未預期錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤: {str(e)}")


@router.get("/cfr-plot", tags=["Sionna Simulation"])
async def get_cfr_plot_endpoint(session: AsyncSession = Depends(get_session)):
    """生成並返回 Channel Frequency Response (CFR) 圖，基於 Sionna 的模擬。"""
    logger.info("--- API Request: /cfr-plot ---")

    # 修改：傳遞 session 參數給 generate_cfr_plot 函數
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
    生成並返回延遲多普勒圖，包括未縮放和功率縮放兩個版本。
    此端點會返回一個包含兩個圖像URL的JSON對象。
    """
    logger.info("--- API Request: /doppler-plots ---")

    # 生成延遲多普勒圖
    success = await generate_doppler_plots(
        session, str(UNSCALED_DOPPLER_IMAGE_PATH), str(POWER_SCALED_DOPPLER_IMAGE_PATH)
    )

    if not success:
        logger.error("延遲多普勒圖生成失敗")
        raise HTTPException(status_code=500, detail="延遲多普勒圖生成失敗")

    # 檢查兩個圖像是否都已生成
    if not os.path.exists(UNSCALED_DOPPLER_IMAGE_PATH) or not os.path.exists(
        POWER_SCALED_DOPPLER_IMAGE_PATH
    ):
        logger.error("延遲多普勒圖文件未生成或找不到")
        raise HTTPException(status_code=500, detail="延遲多普勒圖文件未生成或找不到")

    # 返回圖像URLs的JSON
    base_url = "/static/images"  # 前端訪問靜態文件的基礎URL
    return {
        "unscaled_plot_url": f"{base_url}/unscaled_delay_doppler.png",
        "power_scaled_plot_url": f"{base_url}/power_scaled_delay_doppler.png",
    }


@router.get("/unscaled-doppler-image", tags=["Sionna Simulation"])
async def get_unscaled_doppler_image(session: AsyncSession = Depends(get_session)):
    """
    返回未縮放的延遲多普勒圖圖像文件。
    會首先檢查圖像是否存在，如果不存在則會生成。
    """
    logger.info("--- API Request: /unscaled-doppler-image ---")

    # 檢查文件是否已經存在
    if (
        not os.path.exists(UNSCALED_DOPPLER_IMAGE_PATH)
        or os.path.getsize(UNSCALED_DOPPLER_IMAGE_PATH) == 0
    ):
        logger.info("未縮放的延遲多普勒圖不存在或為空，正在生成...")
        success = await generate_doppler_plots(
            session,
            str(UNSCALED_DOPPLER_IMAGE_PATH),
            str(POWER_SCALED_DOPPLER_IMAGE_PATH),
        )
        if not success:
            logger.error("生成延遲多普勒圖失敗")
            raise HTTPException(status_code=500, detail="生成延遲多普勒圖失敗")

    # 再次檢查文件是否存在
    if not os.path.exists(UNSCALED_DOPPLER_IMAGE_PATH):
        logger.error(f"文件生成後仍不存在: {UNSCALED_DOPPLER_IMAGE_PATH}")
        raise HTTPException(status_code=500, detail="未縮放的延遲多普勒圖生成失敗")

    # 使用StreamingResponse返回文件
    def iterfile():
        with open(UNSCALED_DOPPLER_IMAGE_PATH, "rb") as f:
            # 每次讀取4KB
            chunk = f.read(4096)
            while chunk:
                yield chunk
                chunk = f.read(4096)

    return StreamingResponse(
        iterfile(),
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=unscaled_delay_doppler.png"
        },
    )


@router.get("/power-scaled-doppler-image", tags=["Sionna Simulation"])
async def get_power_scaled_doppler_image(session: AsyncSession = Depends(get_session)):
    """
    返回功率縮放的延遲多普勒圖圖像文件。
    會首先檢查圖像是否存在，如果不存在則會生成。
    """
    logger.info("--- API Request: /power-scaled-doppler-image ---")

    # 檢查文件是否已經存在
    if (
        not os.path.exists(POWER_SCALED_DOPPLER_IMAGE_PATH)
        or os.path.getsize(POWER_SCALED_DOPPLER_IMAGE_PATH) == 0
    ):
        logger.info("功率縮放的延遲多普勒圖不存在或為空，正在生成...")
        success = await generate_doppler_plots(
            session,
            str(UNSCALED_DOPPLER_IMAGE_PATH),
            str(POWER_SCALED_DOPPLER_IMAGE_PATH),
        )
        if not success:
            logger.error("生成延遲多普勒圖失敗")
            raise HTTPException(status_code=500, detail="生成延遲多普勒圖失敗")

    # 再次檢查文件是否存在
    if not os.path.exists(POWER_SCALED_DOPPLER_IMAGE_PATH):
        logger.error(f"文件生成後仍不存在: {POWER_SCALED_DOPPLER_IMAGE_PATH}")
        raise HTTPException(status_code=500, detail="功率縮放的延遲多普勒圖生成失敗")

    # 使用StreamingResponse返回文件
    def iterfile():
        with open(POWER_SCALED_DOPPLER_IMAGE_PATH, "rb") as f:
            # 每次讀取4KB
            chunk = f.read(4096)
            while chunk:
                yield chunk
                chunk = f.read(4096)

    return StreamingResponse(
        iterfile(),
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=power_scaled_delay_doppler.png"
        },
    )


# 新增通道響應圖端點
@router.get("/channel-response-plots", tags=["Sionna Simulation"])
async def get_channel_response_plots(session: AsyncSession = Depends(get_session)):
    """
    生成並返回通道響應圖，顯示 H_des、H_jam 和 H_all 的三維圖。
    從資料庫中獲取發射器和接收器數據，必須有至少一個活動的發射器和接收器。
    """
    logger.info("--- API Request: /channel-response-plots ---")

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
