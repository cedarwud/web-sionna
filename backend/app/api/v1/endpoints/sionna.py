import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session # Import dependency
from app.services.sionna_simulation import ( # Import service functions
    generate_scene_original_image,
    generate_scene_with_paths_image,
    generate_constellation_plot
)
from app.core.config import ( # Import constants
    SCENE_ORIGINAL_IMAGE_PATH,
    SCENE_WITH_PATHS_IMAGE_PATH,
    CONSTELLATION_IMAGE_PATH
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/scene-image-original", tags=["Sionna Simulation"])
async def get_scene_image_original_endpoint():
    """Generates and returns the original Sionna scene image."""
    logger.info("--- API Request: /scene-image-original ---")
    # This function doesn't need DB access currently
    if generate_scene_original_image(SCENE_ORIGINAL_IMAGE_PATH):
        if os.path.exists(SCENE_ORIGINAL_IMAGE_PATH):
            logger.info(f"Returning FileResponse for {SCENE_ORIGINAL_IMAGE_PATH}")
            return FileResponse(SCENE_ORIGINAL_IMAGE_PATH, media_type="image/png")
        else:
            logger.error(f"File not found after generation: {SCENE_ORIGINAL_IMAGE_PATH}")
            raise HTTPException(status_code=500, detail="Failed to find original scene image after generation.")
    else:
        logger.error("Failed to render original scene.")
        raise HTTPException(status_code=500, detail="Failed to render original scene")

@router.get("/scene-image-rt", tags=["Sionna Simulation"])
async def get_scene_image_rt_endpoint(session: AsyncSession = Depends(get_session)):
    """Generates and returns the Sionna scene image with RT paths using data from DB."""
    logger.info("--- API Request: /scene-image-rt ---")
    if await generate_scene_with_paths_image(SCENE_WITH_PATHS_IMAGE_PATH, session):
        if os.path.exists(SCENE_WITH_PATHS_IMAGE_PATH):
            logger.info(f"Returning FileResponse for {SCENE_WITH_PATHS_IMAGE_PATH}")
            return FileResponse(SCENE_WITH_PATHS_IMAGE_PATH, media_type="image/png")
        else:
            logger.error(f"File not found after generation: {SCENE_WITH_PATHS_IMAGE_PATH}")
            raise HTTPException(status_code=500, detail="Failed to find scene image with paths after rendering.")
    else:
        logger.error("Failed to render scene with paths.")
        raise HTTPException(status_code=500, detail="Failed to render scene with paths")

@router.get("/constellation-diagram", tags=["Sionna Simulation"])
async def get_constellation_diagram_endpoint(session: AsyncSession = Depends(get_session)):
    """Generates and returns the constellation diagram using data from DB."""
    logger.info("--- API Request: /constellation-diagram ---")
    # Add query parameters for jnr_db, ebno_db if needed later
    if await generate_constellation_plot(CONSTELLATION_IMAGE_PATH, session): # Pass session
        if os.path.exists(CONSTELLATION_IMAGE_PATH):
             logger.info(f"Returning FileResponse for {CONSTELLATION_IMAGE_PATH}")
             return FileResponse(CONSTELLATION_IMAGE_PATH, media_type="image/png")
        else:
             logger.error(f"File not found after generation: {CONSTELLATION_IMAGE_PATH}")
             raise HTTPException(status_code=500, detail="Failed to find constellation diagram after generation.")
    else:
        logger.error("Failed to generate constellation diagram.")
        raise HTTPException(status_code=500, detail="Failed to generate constellation diagram")