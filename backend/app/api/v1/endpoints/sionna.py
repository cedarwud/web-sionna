import logging
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import sionna.rt as rt
import tempfile
import shutil
from pathlib import Path
import trimesh

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
XIN_GLB_PATH = MODELS_DIR / "XIN.glb"  # 優先使用的 GLB 檔案
GLB_PATH = MODELS_DIR / "scene.glb"  # 備用 GLB 檔案

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
    提供 3D 模型的 GLB 檔案。優先使用 XIN.glb，如果找不到則使用或生成 scene.glb
    """
    logger.info("--- API Request: /sionna/scene ---")

    # 優先檢查 XIN.glb 是否存在
    if XIN_GLB_PATH.exists() and os.path.getsize(XIN_GLB_PATH) > 0:
        logger.info(f"Using existing XIN.glb file from {XIN_GLB_PATH}")
        return FileResponse(
            path=str(XIN_GLB_PATH),
            media_type="model/gltf-binary",
            filename="scene.glb",  # 保持檔案名稱一致，以避免前端需要修改
        )
    else:
        logger.info("XIN.glb not found or empty, falling back to scene.glb")

        # 檢查 scene.glb 是否存在，如果不存在則生成
        if not GLB_PATH.exists() or os.path.getsize(GLB_PATH) == 0:
            logger.info("scene.glb file not found or empty, generating...")
            success = build_gltf()
            if not success:
                logger.error("Failed to generate scene.glb file")
                raise HTTPException(
                    status_code=500, detail="Failed to generate scene model"
                )

        # 再次檢查 scene.glb 文件是否存在
        if not GLB_PATH.exists():
            logger.error(f"scene.glb file not found at {GLB_PATH}")
            raise HTTPException(status_code=404, detail="Scene model not found")

        # 返回 scene.glb 文件
        logger.info(f"Serving scene.glb file from {GLB_PATH}")
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


# 新增：檢查 GLB 文件是否包含頂點顏色的端點
@router.post("/check-glb-colors", tags=["GLB Validation"])
async def check_glb_colors(file_path: str = Form(None), file: UploadFile = File(None)):
    """
    檢查 GLB 檔案是否包含完整的頂點顏色資料。
    可以通過兩種方式提供 GLB 檔案：
    1. 上傳檔案
    2. 提供檔案路徑

    範例：
    使用 curl 上傳檔案檢查:
    ```
    curl -X POST http://localhost:8000/api/v1/sionna/check-glb-colors -F file=@path/to/your/file.glb
    ```

    使用 curl 提供檔案路徑檢查:
    ```
    curl -X POST http://localhost:8000/api/v1/sionna/check-glb-colors -F file_path="/path/to/your/file.glb"
    ```

    回傳結果：
    - has_colors: 是否有頂點顏色 (布爾值)
    - color_coverage: 帶有顏色的頂點百分比 (0.0~1.0)
    - vertex_count: 總頂點數
    - colored_vertex_count: 帶有顏色的頂點數
    - mesh_count: 3D 網格數量
    - colored_mesh_count: 帶有顏色的網格數量
    """
    logger.info("--- API Request: /sionna/check-glb-colors ---")

    # 判斷是使用上傳檔案還是檔案路徑
    temp_file = None
    path_to_check = None

    try:
        if file:
            # 使用者上傳了檔案
            temp_dir = tempfile.mkdtemp()
            temp_file = Path(temp_dir) / file.filename

            # 寫入臨時檔案
            with open(temp_file, "wb") as f:
                contents = await file.read()
                f.write(contents)

            path_to_check = temp_file
            logger.info(f"Using uploaded file: {file.filename}")

        elif file_path:
            # 使用者提供了檔案路徑
            # 檢查是否為容器內路徑，並做路徑轉換
            host_path = file_path

            # 嘗試轉換主機路徑到容器內路徑
            if "/home/" in file_path:
                # 確認是否在 Docker 環境中
                if os.path.exists("/.dockerenv"):
                    # 嘗試直接訪問檔案名而不是完整路徑
                    container_path = (
                        f"/app/app/static/models/{os.path.basename(file_path)}"
                    )
                    if os.path.exists(container_path):
                        host_path = container_path
                        logger.info(
                            f"Converted host path to container path: {host_path}"
                        )

            path_to_check = Path(host_path)
            logger.info(f"Using provided file path: {host_path}")

            if not path_to_check.exists():
                # 嘗試使用預設模型目錄
                model_name = os.path.basename(file_path)
                default_path = MODELS_DIR / model_name

                if default_path.exists():
                    path_to_check = default_path
                    logger.info(
                        f"Using file from default models directory: {path_to_check}"
                    )
                else:
                    available_models = ", ".join(
                        [f.name for f in MODELS_DIR.glob("*.glb")]
                    )
                    raise HTTPException(
                        status_code=404,
                        detail=f"File not found at path: {host_path}. Available models: {available_models}",
                    )
        else:
            # 如果既沒有上傳檔案也沒有提供路徑，則使用預設的 GLB 檔案
            path_to_check = GLB_PATH
            logger.info(f"No file provided, using default GLB file: {GLB_PATH}")

            if not path_to_check.exists():
                raise HTTPException(
                    status_code=404, detail=f"Default GLB file not found at: {GLB_PATH}"
                )

        # 檢查檔案是否為 GLB 格式
        if path_to_check.suffix.lower() not in [".glb", ".gltf"]:
            raise HTTPException(
                status_code=400, detail="Provided file is not a GLB/GLTF file"
            )

        # 使用 trimesh 載入 GLB 模型並檢查頂點顏色
        try:
            scene = trimesh.load(str(path_to_check))

            # 初始化計數器
            total_vertices = 0
            colored_vertices = 0
            total_meshes = 0
            colored_meshes = 0

            # 遍歷場景中的所有網格
            for mesh_name, mesh in scene.geometry.items():
                if isinstance(mesh, trimesh.Trimesh):
                    total_meshes += 1
                    total_vertices += len(mesh.vertices)

                    # 檢查是否有頂點顏色
                    has_colors = (
                        hasattr(mesh.visual, "vertex_colors")
                        and mesh.visual.vertex_colors is not None
                    )
                    if has_colors and len(mesh.visual.vertex_colors) > 0:
                        colored_meshes += 1
                        colored_vertices += len(mesh.visual.vertex_colors)

            # 計算有顏色的頂點比例
            color_coverage = (
                colored_vertices / total_vertices if total_vertices > 0 else 0
            )

            result = {
                "has_colors": colored_vertices > 0,
                "color_coverage": color_coverage,
                "vertex_count": total_vertices,
                "colored_vertex_count": colored_vertices,
                "mesh_count": total_meshes,
                "colored_mesh_count": colored_meshes,
                "file_path": str(path_to_check),  # 新增實際使用的檔案路徑
            }

            logger.info(f"GLB analysis complete: {result}")

            # 使用自訂回應，添加額外的換行
            from fastapi.responses import Response
            import json

            # 先將結果轉為漂亮格式化的 JSON 字串，確保有適當的縮排和換行
            json_content = json.dumps(result, ensure_ascii=False, indent=2)

            # 回應內容加上額外的換行符，確保 curl 輸出後有換行
            json_content = json_content + "\n"

            return Response(
                content=json_content,
                media_type="application/json",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        except Exception as e:
            logger.error(f"Error analyzing GLB file: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error analyzing GLB file: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Error in check_glb_colors: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )
    finally:
        # 清理臨時檔案
        if temp_file and Path(temp_file).exists():
            try:
                shutil.rmtree(Path(temp_file).parent)
                logger.info(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"Error cleaning temporary file: {e}")
