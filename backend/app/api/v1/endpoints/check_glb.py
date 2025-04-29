from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
import tempfile, shutil, os
import trimesh
import logging
import numpy as np

# 導入必要的函數和變數
from app.api.v1.endpoints.sionna import build_gltf, XIN_GLB_PATH, GLB_PATH

logger = logging.getLogger(__name__)
router = APIRouter()
# 新增：GLB 模型文件路徑
STATIC_DIR = (
    Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    / "static"
)
MODELS_DIR = STATIC_DIR / "models"


@router.post("/check-glb-colors", tags=["GLB Validation"])
async def check_glb_colors(file_path: str = Form(None), file: UploadFile = File(None)):
    """
    檢查 GLB/GLTF 是否帶有頂點顏色：
    - has_colors: 是否至少一個網格有頂點色
    - color_coverage: 有顏色頂點 / 總頂點
    - mesh_count, colored_mesh_count
    """
    # 1) 确定要检查的文件路径
    temp_dir = None
    try:
        if file:
            temp_dir = Path(tempfile.mkdtemp())
            path_to_check = temp_dir / file.filename
            with open(path_to_check, "wb") as f:
                f.write(await file.read())
        elif file_path:
            path_to_check = Path(file_path)
            if not path_to_check.exists():
                # fallback 到 models 目录
                candidate = MODELS_DIR / path_to_check.name
                if candidate.exists():
                    path_to_check = candidate
                else:
                    raise HTTPException(
                        404,
                        f"File not found: {file_path}. 目录下可用: "
                        + ", ".join(p.name for p in MODELS_DIR.glob("*.glb")),
                    )
        else:
            path_to_check = Path(GLB_PATH)  # 你的默认路径
            if not path_to_check.exists():
                raise HTTPException(404, f"Default GLB not found at {GLB_PATH}")

        # 2) 文件后缀检查
        if path_to_check.suffix.lower() not in (".glb", ".gltf"):
            raise HTTPException(400, "只支持 .glb 或 .gltf")

        # 3) 用 trimesh.load(force="scene") 载入
        scene = trimesh.load(str(path_to_check), force="scene")
        meshes = scene.geometry  # dict of name->Trimesh

        # 4) 统计
        total_vertices = 0
        colored_vertices = 0
        mesh_count = 0
        colored_mesh_count = 0

        for name, mesh in meshes.items():
            mesh_count += 1
            vcount = mesh.vertices.shape[0]
            total_vertices += vcount

            vc = getattr(mesh.visual, "vertex_colors", None)
            # 只把形状正确、长度匹配的当作“有顶点色”
            if vc is not None and vc.shape[0] == vcount:
                # 这里假设 RGBA 全部 >0 就算有色
                nonzero = vc[:, :3].sum(axis=1) > 0
                ccount = int(nonzero.sum())
                if ccount > 0:
                    colored_mesh_count += 1
                    colored_vertices += ccount

        coverage = colored_vertices / total_vertices if total_vertices else 0.0

        result = {
            "has_colors": colored_vertices > 0,
            "color_coverage": round(coverage, 4),
            "vertex_count": total_vertices,
            "colored_vertex_count": colored_vertices,
            "mesh_count": mesh_count,
            "colored_mesh_count": colored_mesh_count,
            "file_used": str(path_to_check),
        }

        return JSONResponse(content=result)

    finally:
        # 清理临时上传文件
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)


@router.post("/bake-glb", tags=["Sionna Scene"])
async def bake_glb_to_models(filename: str = Form("scene.baked.glb")):
    """
    將 XIN.glb (或 fallback 的 scene.glb) 做頂點色淺灰化後
    export 成新的 GLB，並存到 MODELS_DIR/{filename}。
    
    範例：
      curl -X POST http://<host>/api/v1/check-glb/bake-glb \
           -d filename="my_baked.glb"
    """
    # 1) 確定要用哪個原始檔
    if XIN_GLB_PATH.exists() and XIN_GLB_PATH.stat().st_size > 0:
        src = XIN_GLB_PATH
    else:
        # fallback: 若 scene.glb 不存在就生成
        if not GLB_PATH.exists() or GLB_PATH.stat().st_size == 0:
            if not build_gltf():
                raise HTTPException(500, "無法生成 scene.glb")
        src = GLB_PATH

    # 2) 讀入並淺灰化頂點色
    try:
        scene = trimesh.load(str(src), force="scene")
    except Exception as e:
        raise HTTPException(500, f"載入 GLB 失敗: {e}")

    # 3) 合併所有子網格為單一 Mesh
    all_meshes = list(scene.geometry.values())
    if len(all_meshes) == 0:
        raise HTTPException(500, "場景中沒有任何幾何體")
    combined = trimesh.util.concatenate(all_meshes)

    # 4) 生成淺灰頂點色
    n_verts = combined.vertices.shape[0]
    gray = np.array([230, 230, 230, 255], dtype=np.uint8)
    combined.visual.vertex_colors = np.tile(gray, (n_verts, 1))

    # 5) 輸出
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELS_DIR / filename
    try:
        combined.export(str(out_path))
    except Exception as e:
        raise HTTPException(500, f"輸出 GLB 失敗: {e}")

    return JSONResponse(
        {
            "message": "Baked GLB 已儲存",
            "output_path": str(out_path),
            "vertex_count": n_verts,
        }
    )
