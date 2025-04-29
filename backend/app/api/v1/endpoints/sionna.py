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
)
from app.core.config import (  # Import constants
    SCENE_WITH_PATHS_IMAGE_PATH,
    CONSTELLATION_IMAGE_PATH,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 新增：GLB 模型文件路徑
STATIC_DIR = (
    Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    / "static"
)
MODELS_DIR = STATIC_DIR / "models"
GLB_PATH = MODELS_DIR / "scene.glb"

# 確保目錄存在
MODELS_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Models directory path: {MODELS_DIR}")


# 新增：生成 GLB 模型的函數
# gltf.py or glb.py 中的 build_gltf()


def build_gltf() -> bool:
    """
    將 Sionna RT etoile 場景匯出為帶頂點色的 GLB 模型
    """
    try:
        # 一律重新生成（或先手動刪掉舊檔），不用跳過
        logger.info("Exporting etoile scene to GLB (Mitsuba+Trimesh route)...")

        # 確保目錄存在，清空 tmp
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp())

        # 1) Mitsuba 讀場景
        scene = rt.load_scene(rt.scene.etoile)
        mi_scene = scene._scene

        # 2) 把每個 shape 寫成 PLY
        import mitsuba as mi
        import trimesh as tm
        import numpy as np

        ply_shapes = []
        for i, shape in enumerate(mi_scene.shapes()):
            if isinstance(shape, mi.Mesh):
                ply_path = tmp_dir / f"mesh_{i}.ply"
                shape.write_ply(str(ply_path))  # default PLY
                ply_shapes.append((ply_path, shape))

        if not ply_shapes:
            logger.error("No Mitsuba meshes found")
            return False

        # 3) Trimesh 讀 PLY，並塞頂點色
        tm_meshes = []
        for ply_path, shape in ply_shapes:
            mesh: tm.Trimesh = tm.load(str(ply_path), force="mesh")

            # 從 Mitsuba BSDF 拿 base_color (float[3], 0~1)
            try:
                color_f = np.array(shape.bsdf.base_color)  # e.g. [0.8,0.7,0.6]
            except AttributeError:
                color_f = np.array([0.8, 0.8, 0.8])

            # 轉 0~255 uint8
            color_u = (np.clip(color_f, 0, 1) * 255).astype(np.uint8)
            # 複製到所有 vertex
            vert_count = mesh.vertices.shape[0]
            mesh.visual.vertex_colors = np.tile(color_u.reshape(1, 3), (vert_count, 1))

            tm_meshes.append(mesh)

        # 4) 建立一个 tm.Scene，把每个带顶点色的 Trimesh 加进去
        scene_tm = tm.Scene()
        # 4) 用 ColorVisuals 強制走 vertex color 流程，再一次性 export
        from trimesh.visual import ColorVisuals

        scene_tm = tm.Scene()
        for idx, mesh in enumerate(tm_meshes):
            # 把可能的 TextureVisuals 換成只用 vertex_colors 的 ColorVisuals
            mesh.visual = ColorVisuals(
                mesh=mesh, vertex_colors=mesh.visual.vertex_colors
            )
            scene_tm.add_geometry(mesh, node_name=f"mesh_{idx}")

        # ❗️ 一定要在 loop 外，只呼叫一次 export
        scene_tm.export(str(GLB_PATH))

        shutil.rmtree(tmp_dir)

        if GLB_PATH.exists() and GLB_PATH.stat().st_size > 0:
            logger.info(f"GLB created at {GLB_PATH}")
            return True
        else:
            logger.error("GLB file creation failed")
            return False

    except Exception as e:
        logger.exception(f"Error generating GLB file: {e}")
        return False


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
