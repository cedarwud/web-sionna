import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session  # Import dependency
from app.services.sionna_simulation import (  # Import service functions
    generate_scene_with_paths_image,
    generate_constellation_plot,
    generate_empty_scene_image,
)
from app.core.config import (  # Import constants
    SCENE_WITH_PATHS_IMAGE_PATH,
    CONSTELLATION_IMAGE_PATH,
    EMPTY_SCENE_IMAGE_PATH,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scene-image-rt", tags=["Sionna Simulation"])
async def get_scene_image_rt_endpoint(session: AsyncSession = Depends(get_session)):
    """Generates and returns the Sionna scene image with RT paths using data from DB."""
    logger.info("--- API Request: /scene-image-rt ---")
    if await generate_scene_with_paths_image(SCENE_WITH_PATHS_IMAGE_PATH, session):
        if os.path.exists(SCENE_WITH_PATHS_IMAGE_PATH):
            file_size = os.path.getsize(SCENE_WITH_PATHS_IMAGE_PATH)
            logger.info(f"Returning image for {SCENE_WITH_PATHS_IMAGE_PATH} (Size: {file_size} bytes)")
            
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
                headers={"Content-Disposition": f"attachment; filename=scene_with_paths.png"}
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


@router.get("/constellation-diagram", tags=["Sionna Simulation"])
async def get_constellation_diagram_endpoint(
    session: AsyncSession = Depends(get_session),
):
    """Generates and returns the constellation diagram using data from DB."""
    logger.info("--- API Request: /constellation-diagram ---")
    # Add query parameters for jnr_db, ebno_db if needed later
    if await generate_constellation_plot(
        CONSTELLATION_IMAGE_PATH, session
    ):  # Pass session
        if os.path.exists(CONSTELLATION_IMAGE_PATH):
            file_size = os.path.getsize(CONSTELLATION_IMAGE_PATH)
            logger.info(f"Returning image for {CONSTELLATION_IMAGE_PATH} (Size: {file_size} bytes)")
            
            # 使用StreamingResponse從文件流直接返回
            def iterfile():
                with open(CONSTELLATION_IMAGE_PATH, "rb") as f:
                    # 每次讀取4KB
                    chunk = f.read(4096)
                    while chunk:
                        yield chunk
                        chunk = f.read(4096)
            
            return StreamingResponse(
                iterfile(), 
                media_type="image/png",
                headers={"Content-Disposition": f"attachment; filename=constellation_diagram.png"}
            )
        else:
            logger.error(f"File not found after generation: {CONSTELLATION_IMAGE_PATH}")
            raise HTTPException(
                status_code=500,
                detail="Failed to find constellation diagram after generation.",
            )
    else:
        logger.error("Failed to generate constellation diagram.")
        raise HTTPException(
            status_code=500, detail="Failed to generate constellation diagram"
        )


# 新增：檢查並生成空場景圖片的端點
@router.get("/check-empty-scene", tags=["Sionna Simulation"])
async def check_empty_scene_endpoint():
    """檢查是否有空場景圖片，如果沒有則生成"""
    logger.info("--- API Request: /check-empty-scene ---")

    if os.path.exists(EMPTY_SCENE_IMAGE_PATH):
        logger.info(f"空場景圖片已存在於 {EMPTY_SCENE_IMAGE_PATH}")
        return {
            "status": "success",
            "message": "空場景圖片已存在",
            "path": f"/rendered_images/empty_scene.png",
        }

    logger.info("空場景圖片不存在，開始生成")
    if generate_empty_scene_image(EMPTY_SCENE_IMAGE_PATH):
        logger.info(f"空場景圖片已生成於 {EMPTY_SCENE_IMAGE_PATH}")
        return {
            "status": "success",
            "message": "空場景圖片已生成",
            "path": f"/rendered_images/empty_scene.png",
        }
    else:
        logger.error("生成空場景圖片時發生錯誤")
        raise HTTPException(status_code=500, detail="生成空場景圖片時發生錯誤")
