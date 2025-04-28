import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import sionna.rt as rt
import tempfile, shutil
from pathlib import Path

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

# 新增：GLB 模型文件路徑
STATIC_DIR = (
    Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    / "static"
)
MODELS_DIR = STATIC_DIR / "scenes"
GLB_PATH = MODELS_DIR / "scene.glb"

# 確保目錄存在
MODELS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Models directory path: {MODELS_DIR}")


# 新增：生成 GLB 模型的函數
def build_gltf() -> bool:
    """
    將 Sionna RT 內建的 etoile 場景匯出為 GLB 模型文件
    """
    try:
        # 如果文件已存在且大小不為0，則跳過生成
        if GLB_PATH.exists() and os.path.getsize(GLB_PATH) > 0:
            logger.info(f"GLB file already exists at {GLB_PATH}")
            return True

        logger.info("Exporting etoile scene to GLB...")

        # 確保目錄存在
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        # 加載 Sionna RT 場景
        scene = rt.load_scene(rt.scene.etoile)
        mi_scene = scene._scene  # 低階 Mitsuba Scene
        tmp_dir = Path(tempfile.mkdtemp())

        import mitsuba as mi
        import trimesh as tm

        ply_paths = []

        # 遍歷場景中的所有形狀並導出為 PLY
        for i, shape in enumerate(mi_scene.shapes()):
            if isinstance(shape, mi.Mesh):
                ply = tmp_dir / f"mesh_{i}.ply"
                shape.write_ply(str(ply))
                ply_paths.append(ply)

        logger.info(f"Exported {len(ply_paths)} meshes to PLY")

        if not ply_paths:
            logger.error("No meshes found in scene")
            return False

        # 加載 PLY 文件並合併
        meshes = [tm.load(str(p), force="mesh") for p in ply_paths]

        combined = tm.util.concatenate(meshes)

        # 導出為 GLB
        combined.export(str(GLB_PATH))

        # 清理臨時文件
        shutil.rmtree(tmp_dir)

        if GLB_PATH.exists() and os.path.getsize(GLB_PATH) > 0:
            logger.info(f"Successfully created GLB file at {GLB_PATH}")
            return True
        else:
            logger.error("GLB file creation failed")
            return False
    except Exception as e:
        logger.exception(f"Error generating GLB file: {e}")
        return False


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
            logger.info(
                f"Returning image for {CONSTELLATION_IMAGE_PATH} (Size: {file_size} bytes)"
            )

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
                headers={
                    "Content-Disposition": f"attachment; filename=constellation_diagram.png"
                },
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


# 新增：提供 GLB 模型的端點
@router.get("/scene", tags=["Sionna Scene"])
async def get_scene_glb():
    """
    提供 Sionna RT etoile 場景的 GLB 模型文件
    """
    logger.info("--- API Request: /sionna/scene ---")

    # 檢查 GLB 文件是否存在，如果不存在則生成
    if not GLB_PATH.exists() or os.path.getsize(GLB_PATH) == 0:
        logger.info("GLB file not found or empty, generating...")
        success = build_gltf()
        if not success:
            logger.error("Failed to generate GLB file")
            raise HTTPException(
                status_code=500, detail="Failed to generate scene model"
            )

    # 檢查文件是否存在
    if not GLB_PATH.exists():
        logger.error(f"GLB file not found at {GLB_PATH}")
        raise HTTPException(status_code=404, detail="Scene model not found")

    # 返回 GLB 文件
    logger.info(f"Serving GLB file from {GLB_PATH}")
    return FileResponse(
        path=str(GLB_PATH), media_type="model/gltf-binary", filename="scene.glb"
    )
