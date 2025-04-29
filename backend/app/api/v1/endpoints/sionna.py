import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import sionna.rt as rt
import tempfile, shutil
from pathlib import Path
import trimesh
from typing import List, Optional, Dict, Any

import io
import pyrender
import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.api.deps import get_session  # Import dependency
from app.services.sionna_simulation import (  # Import service functions
    generate_scene_with_paths_image,
    generate_constellation_plot,
    get_active_devices_from_db_efficient,
    add_to_scene_safe,
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
async def get_scene_glb(render: bool = Query(False)):
    """
    提供 3D 模型的 GLB 檔案；如果帶上 `?render=true`，
    則在後端對地面塗上淺灰，並回傳渲染後的 PNG 圖像。
    """
    # 1) 選擇要用的原始 GLB
    if os.path.exists(XIN_GLB_PATH) and os.path.getsize(XIN_GLB_PATH) > 0:
        glb_path = XIN_GLB_PATH
    else:
        if not os.path.exists(GLB_PATH) or os.path.getsize(GLB_PATH) == 0:
            if not build_gltf():
                raise HTTPException(500, "無法生成 scene.glb")
        glb_path = GLB_PATH

    # 2) 如果需要 render，後端 Offscreen 渲染
    if render:
        # 2.1 讀入場景
        scene = trimesh.load(glb_path, force="scene")

        # 2.2 找出 ground mesh（按面積最大者判定）
        areas = {name: mesh.area for name, mesh in scene.geometry.items()}
        if not areas:
            raise HTTPException(500, "場景中沒有網格可渲染")
        ground_name = max(areas, key=areas.get)

        # 2.3 建立 pyrender.Scene，設定淺灰背景 + 中度環境光
        pr_scene = pyrender.Scene(
            bg_color=[0.8, 0.8, 0.8, 1.0], ambient_light=[0.6, 0.6, 0.6]
        )

        # 2.4 把每個子網格加入場景，只有地面 override 顏色
        for name, geom in scene.geometry.items():
            # 確保法線存在
            if not geom.has_vertex_normals:
                geom.compute_vertex_normals()
            # 如果是地面，用淺灰頂點色覆蓋
            if name == ground_name:
                n = geom.vertices.shape[0]
                gray = np.tile([180, 180, 170, 255], (n, 1))  # R/G/B/A
                geom.visual.vertex_colors = gray
            # 其他網格保留原貼圖／材質
            mesh = pyrender.Mesh.from_trimesh(geom, smooth=False)
            pr_scene.add(mesh)

        # 2.5 加光源：一盞主光 + 一盞補光
        key = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
        fill = pyrender.DirectionalLight(color=np.ones(3), intensity=1.5)
        pr_scene.add(key, pose=np.eye(4))
        pr_scene.add(fill, pose=np.diag([-1, -1, -1, 1]))

        # 2.6 設置相機（對應 notebook 角度）
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)
        cam_pose = np.array(
            [
                [1, 0, 0, 0],
                [0, 0, 1, -1500],
                [0, -1, 0, 0],
                [0, 0, 0, 1],
            ]
        )
        pr_scene.add(camera, pose=cam_pose)

        # 2.7 Offscreen render → PNG
        renderer = pyrender.OffscreenRenderer(1200, 800)
        color, _ = renderer.render(pr_scene)
        renderer.delete()

        buf = io.BytesIO()
        Image.fromarray(color).save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    # 3) 否則直接回傳原始 GLB
    return FileResponse(
        path=glb_path,
        media_type="model/gltf-binary",
        filename=os.path.basename(glb_path),
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


# 新增：射線路徑端點所需的資料模型
class RayPoint(BaseModel):
    x: float
    y: float
    z: float


class RayPath(BaseModel):
    points: List[RayPoint]
    is_los: bool = False


class RayPathsResponse(BaseModel):
    paths: List[RayPath]


@router.get("/ray-paths", response_model=RayPathsResponse, tags=["Sionna Simulation"])
async def get_ray_paths(session: AsyncSession = Depends(get_session)):
    """計算並回傳所有發射器到接收器的射線路徑資料，用於在3D場景中渲染"""
    logger.info("--- API Request: /ray-paths ---")

    try:
        # 1. 從資料庫獲取活動設備
        logger.info("正在從資料庫獲取活動設備...")
        transmitters_data, receivers_data = await get_active_devices_from_db_efficient(
            session
        )

        logger.info(
            f"獲取到 {len(transmitters_data)} 個發射器和 {len(receivers_data)} 個接收器"
        )

        # 檢查設備數量
        if not transmitters_data or not receivers_data:
            logger.error("沒有有效的發射器或接收器數據")
            raise HTTPException(status_code=404, detail="沒有有效的發射器或接收器數據")

        # 2. 設置 Sionna 場景
        logger.info("設置 Sionna RT 場景...")
        try:
            # 檢查 rt.scene.etoile 是否存在
            if not hasattr(rt.scene, "etoile"):
                logger.error("rt.scene.etoile 不存在！檢查 Sionna 的配置")
                available_scenes = [
                    attr for attr in dir(rt.scene) if not attr.startswith("_")
                ]
                logger.info(f"可用場景: {available_scenes}")
                # 嘗試使用第一個可用場景
                if available_scenes:
                    scene_name = available_scenes[0]
                    logger.info(f"嘗試使用替代場景: {scene_name}")
                    scene = rt.load_scene(getattr(rt.scene, scene_name))
                else:
                    raise ValueError("無法找到可用的 Sionna 場景")
            else:
                scene = rt.load_scene(rt.scene.etoile)
                logger.info("成功加載 Etoile 場景")

            # 記錄場景信息
            logger.info(f"場景類型: {type(scene)}")
            logger.info(f"場景屬性: {dir(scene)[:10]}...")

            # 設置天線陣列
            iso = rt.PlanarArray(
                num_rows=1, num_cols=1, pattern="iso", polarization="V"
            )
            scene.tx_array = iso
            scene.rx_array = iso
            logger.info("成功設置天線陣列")
        except Exception as e:
            logger.exception(f"設置場景時發生錯誤: {e}")
            raise HTTPException(
                status_code=500, detail=f"設置 Sionna 場景時發生錯誤: {str(e)}"
            )

        # 3. 添加發射器
        logger.info("正在添加發射器...")
        sionna_txs = []
        for i, tx_data in enumerate(transmitters_data):
            try:
                if tx_data.position_list:
                    logger.info(
                        f"處理發射器 {i+1}/{len(transmitters_data)}: {tx_data.device_model.name}, 位置: {tx_data.position_list}"
                    )
                    color_param = {}
                    if (
                        tx_data.transmitter_type
                        and tx_data.transmitter_type.value == "interferer"
                    ):
                        color_param = {"color": [0, 0, 0]}
                    sionna_tx = rt.Transmitter(
                        tx_data.device_model.name,
                        position=tx_data.position_list,
                        **color_param,
                    )
                    sionna_txs.append(sionna_tx)
                    add_to_scene_safe(scene, sionna_tx)
                    logger.info(f"成功添加發射器: {tx_data.device_model.name}")
                else:
                    logger.warning(
                        f"發射器 {tx_data.device_model.name} 沒有位置數據，跳過"
                    )
            except Exception as e:
                logger.warning(f"添加發射器 {tx_data.device_model.name} 時出錯: {e}")

        # 4. 添加接收器
        logger.info("正在添加接收器...")
        sionna_rxs = []
        for i, rx_data in enumerate(receivers_data):
            try:
                if rx_data.position_list:
                    logger.info(
                        f"處理接收器 {i+1}/{len(receivers_data)}: {rx_data.device_model.name}, 位置: {rx_data.position_list}"
                    )
                    sionna_rx = rt.Receiver(
                        rx_data.device_model.name, position=rx_data.position_list
                    )
                    sionna_rxs.append(sionna_rx)
                    add_to_scene_safe(scene, sionna_rx)
                    logger.info(f"成功添加接收器: {rx_data.device_model.name}")
                else:
                    logger.warning(
                        f"接收器 {rx_data.device_model.name} 沒有位置數據，跳過"
                    )
            except Exception as e:
                logger.warning(f"添加接收器 {rx_data.device_model.name} 時出錯: {e}")

        # 檢查場景中是否有有效的發射器和接收器
        if not scene.transmitters or not scene.receivers:
            logger.error("沒有有效的發射器或接收器被添加到場景中")
            raise HTTPException(status_code=400, detail="沒有有效的發射器或接收器")

        logger.info(
            f"場景中有 {len(scene.transmitters)} 個發射器和 {len(scene.receivers)} 個接收器"
        )

        # 5. 計算路徑 - 簡化版本
        logger.info("開始計算射線路徑...")
        try:
            solver = rt.PathSolver()
            logger.info("PathSolver 實例化成功")

            # 記錄參數
            max_depth = 4  # 降低路徑深度，可能提高性能
            logger.info(
                f"設置路徑求解器參數: max_depth={max_depth}, los=True, specular_reflection=True, diffuse_reflection=False, refraction=True"
            )

            # 調用求解器計算路徑
            paths = solver(
                scene,
                max_depth=max_depth,
                los=True,
                specular_reflection=True,
                diffuse_reflection=False,
                refraction=True,
            )
            logger.info(f"路徑計算完成: {type(paths)}")

            # 記錄路徑數據結構詳情
            logger.info(f"Paths 對象類型: {type(paths)}")
            logger.info(f"Paths 對象屬性: {dir(paths)}")
            logger.info(f"Paths 對象字符串表示: {str(paths)[:200]}...")

            # 嘗試獲取一些基本信息
            if hasattr(paths, "shape"):
                logger.info(f"Paths shape: {paths.shape}")
            if hasattr(paths, "__len__"):
                logger.info(f"Paths 長度: {len(paths)}")
        except Exception as e:
            logger.exception(f"計算路徑時發生錯誤: {e}")
            raise HTTPException(
                status_code=500, detail=f"計算射線路徑時發生錯誤: {str(e)}"
            )

        # 6. 構建響應數據 - 使用簡化邏輯
        logger.info("構建響應數據...")
        response_paths = []

        # 嘗試直接從Paths對象獲取數據
        try:
            # 檢查paths對象是否有基本屬性
            logger.info("嘗試直接從Paths對象獲取數據...")

            # 嘗試使用tau、interactions等屬性探索內部結構
            if hasattr(paths, "tau") and hasattr(paths, "interactions"):
                logger.info("使用tau和interactions屬性構建詳細路徑")
                tau = paths.tau
                interactions = paths.interactions

                logger.info(f"Tau形狀: {getattr(tau, 'shape', '未知')}")
                logger.info(
                    f"Interactions形狀: {getattr(interactions, 'shape', '未知')}"
                )

                # 檢查tau屬性，它通常是一個多維數組，表示不同發射器和接收器之間的路徑延遲
                if hasattr(tau, "shape") and len(tau.shape) >= 2:
                    num_tx = tau.shape[0]
                    num_rx = tau.shape[1]
                    logger.info(
                        f"發現路徑數據結構: {num_tx}個發射器 x {num_rx}個接收器"
                    )

                    # 獲取場景中放置的對象位置來構建反射點
                    scene_vertices = []
                    scene_objects = []

                    # 嘗試獲取場景物體
                    if hasattr(paths, "objects"):
                        scene_objects = paths.objects
                        logger.info(
                            f"場景物體數量: {len(scene_objects) if hasattr(scene_objects, '__len__') else '未知'}"
                        )

                    # 嘗試獲取場景頂點
                    if hasattr(paths, "vertices"):
                        scene_vertices = paths.vertices
                        logger.info(
                            f"場景頂點數量: {len(scene_vertices) if hasattr(scene_vertices, '__len__') else '未知'}"
                        )

                    # 為每對發射器-接收器嘗試構建詳細路徑
                    for tx_idx in range(num_tx):
                        for rx_idx in range(num_rx):
                            # 1. 使用場景中的發射器和接收器獲取實際位置
                            if tx_idx < len(scene.transmitters) and rx_idx < len(
                                scene.receivers
                            ):
                                # 獲取發射器和接收器字典的鍵列表
                                tx_keys = list(scene.transmitters.keys())
                                rx_keys = list(scene.receivers.keys())

                                # 使用列表索引獲取相應的鍵
                                tx_key = tx_keys[tx_idx]
                                rx_key = rx_keys[rx_idx]

                                # 使用鍵訪問字典
                                tx = scene.transmitters[tx_key]
                                rx = scene.receivers[rx_key]

                                tx_name = (
                                    tx
                                    if isinstance(tx, str)
                                    else getattr(tx, "name", f"TX-{tx_idx}")
                                )
                                rx_name = (
                                    rx
                                    if isinstance(rx, str)
                                    else getattr(rx, "name", f"RX-{rx_idx}")
                                )

                                # 獲取發射器和接收器位置
                                tx_position = getattr(tx, "position", None)
                                rx_position = getattr(rx, "position", None)

                                if tx_position is None or rx_position is None:
                                    logger.warning(
                                        f"無法獲取 {tx_name} 或 {rx_name} 的位置"
                                    )
                                    continue

                                # 2. 檢查該對的互動數據來確定反射次數
                                try:
                                    # 預設為視線路徑（Line of Sight）
                                    is_los = True

                                    # 訪問特定發射器-接收器對的互動數據
                                    # 修改索引方式以適應 drjit 張量
                                    try:
                                        # 嘗試使用減少索引維度的方式
                                        # 根據 Tau形狀: (1, 2, 7) 和 Interactions形狀: (4, 1, 2, 7)
                                        path_interactions = interactions[
                                            :, 0, tx_idx, rx_idx
                                        ]
                                        path_tau = tau[0, tx_idx, rx_idx]

                                        logger.info(
                                            f"{tx_name}→{rx_name} 互動: {path_interactions}, 延遲: {path_tau}"
                                        )

                                        # 根據互動數據判斷是否為視線路徑
                                        # 如果互動都是0，通常表示視線路徑
                                        if (
                                            hasattr(path_interactions, "__iter__")
                                            and sum(path_interactions) > 0
                                        ):
                                            is_los = False
                                            logger.info(
                                                f"{tx_name}→{rx_name}檢測為非視線路徑(NLOS)"
                                            )
                                        else:
                                            logger.info(
                                                f"{tx_name}→{rx_name}檢測為視線路徑(LOS)"
                                            )

                                    except Exception as idx_error:
                                        logger.warning(
                                            f"訪問互動數據時出錯: {idx_error}"
                                        )
                                        # 嘗試備用方法 - 模擬路徑
                                        # 根據發射器和接收器位置，創建直線路徑（視線路徑）
                                        tx_pos = np.array(tx_position)
                                        rx_pos = np.array(rx_position)
                                        distance = np.linalg.norm(tx_pos - rx_pos)
                                        # 假設光速傳播
                                        estimated_time = distance / 3e8
                                        logger.info(
                                            f"估計延遲時間: {estimated_time}秒，假設為視線路徑"
                                        )
                                        # 默認已設為LOS路徑

                                    # 根據路徑類型構建點
                                    if is_los:
                                        # 直線路徑 - 只有起點和終點
                                        points = [
                                            RayPoint(
                                                x=float(tx_position[0]),
                                                y=float(tx_position[1]),
                                                z=float(tx_position[2]),
                                            ),
                                            RayPoint(
                                                x=float(rx_position[0]),
                                                y=float(rx_position[1]),
                                                z=float(rx_position[2]),
                                            ),
                                        ]
                                        logger.info(f"創建LOS路徑: {tx_name}→{rx_name}")
                                    else:
                                        # 嘗試創建反射路徑
                                        logger.info(
                                            f"嘗試創建NLOS路徑: {tx_name}→{rx_name}"
                                        )

                                        # 開始和結束點
                                        points = [
                                            RayPoint(
                                                x=float(tx_position[0]),
                                                y=float(tx_position[1]),
                                                z=float(tx_position[2]),
                                            )
                                        ]

                                        # 根據互動信息嘗試添加反射點
                                        has_reflection_points = False

                                        # 方法1: 如果primitives屬性可用，直接使用它獲取反射面
                                        if hasattr(paths, "primitives"):
                                            primitives = None
                                            try:
                                                # 嘗試使用與interactions相同的索引方式
                                                primitives = paths.primitives[
                                                    :, 0, tx_idx, rx_idx
                                                ]
                                                logger.info(
                                                    f"從primitives獲取到反射面: {primitives}"
                                                )
                                            except Exception as e1:
                                                logger.warning(
                                                    f"使用第一種索引方式訪問primitives失敗: {e1}"
                                                )
                                                try:
                                                    # 嘗試備用索引方式
                                                    primitives = paths.primitives[
                                                        0, tx_idx, rx_idx
                                                    ]
                                                    logger.info(
                                                        "使用備用索引方式獲取反射面成功"
                                                    )
                                                except Exception as e2:
                                                    logger.warning(
                                                        f"使用備用索引方式訪問primitives也失敗: {e2}"
                                                    )

                                            # 如果獲取到反射面，嘗試估計反射點
                                            if (
                                                primitives is not None
                                                and hasattr(primitives, "__len__")
                                                and len(primitives) > 0
                                            ):
                                                try:
                                                    # 這裡需要根據Sionna API理解如何從primitives獲取反射點
                                                    # 簡單估計: 取反射面的中心點
                                                    for p in primitives:
                                                        if hasattr(p, "center"):
                                                            center = p.center
                                                            points.append(
                                                                RayPoint(
                                                                    x=float(center[0]),
                                                                    y=float(center[1]),
                                                                    z=float(center[2]),
                                                                )
                                                            )
                                                            has_reflection_points = True
                                                    logger.info(
                                                        f"從反射面成功創建了 {has_reflection_points} 個反射點"
                                                    )
                                                except Exception as e3:
                                                    logger.warning(
                                                        f"從primitives創建反射點失敗: {e3}"
                                                    )

                                        # 方法2: 如果場景頂點可用，使用它們估計反射點
                                        if (
                                            not has_reflection_points
                                            and scene_vertices
                                            and hasattr(scene_vertices, "__len__")
                                        ):
                                            # 簡化邏輯: 從場景頂點中隨機選擇一個點作為反射點
                                            # 在實際應用中，應該使用更複雜的算法來確定真實的反射點
                                            try:
                                                # 估計反射點數量
                                                num_reflections = 0
                                                # 檢查path_interactions是否在當前作用域中存在
                                                if (
                                                    "path_interactions" in locals()
                                                    and path_interactions is not None
                                                ):
                                                    try:
                                                        num_reflections = sum(
                                                            1
                                                            for i in path_interactions
                                                            if i > 1
                                                        )
                                                    except Exception:
                                                        # 如果無法從path_interactions獲取，則使用默認值
                                                        num_reflections = (
                                                            1  # 默認添加一個反射點
                                                        )
                                                else:
                                                    # 如果沒有互動數據，則默認添加一個反射點
                                                    num_reflections = 1

                                                if num_reflections > 0:
                                                    # 簡單示例: 在發射器和接收器之間創建反射點
                                                    tx_pos = np.array(
                                                        [
                                                            tx_position[0],
                                                            tx_position[1],
                                                            tx_position[2],
                                                        ]
                                                    )
                                                    rx_pos = np.array(
                                                        [
                                                            rx_position[0],
                                                            rx_position[1],
                                                            rx_position[2],
                                                        ]
                                                    )

                                                    # 添加一些簡單的反射點，實際應該根據物理模型計算
                                                    for i in range(num_reflections):
                                                        # 在起點和終點之間插入點
                                                        t = (i + 1) / (
                                                            num_reflections + 1
                                                        )
                                                        mid_point = (
                                                            tx_pos * (1 - t)
                                                            + rx_pos * t
                                                        )

                                                        # 添加一些偏移使路徑看起來更自然
                                                        # (這只是視覺效果，實際反射應該基於物理模型)
                                                        offset = np.random.normal(
                                                            0, 10, 3
                                                        )  # 隨機偏移
                                                        mid_point += offset

                                                        points.append(
                                                            RayPoint(
                                                                x=float(mid_point[0]),
                                                                y=float(mid_point[1]),
                                                                z=float(mid_point[2]),
                                                            )
                                                        )
                                                        has_reflection_points = True
                                            except Exception as e:
                                                logger.warning(f"創建反射點失敗: {e}")

                                        # 添加終點
                                        points.append(
                                            RayPoint(
                                                x=float(rx_position[0]),
                                                y=float(rx_position[1]),
                                                z=float(rx_position[2]),
                                            )
                                        )

                                    # 4. 創建並添加路徑
                                    if len(points) >= 2:
                                        ray_path = RayPath(points=points, is_los=is_los)
                                        response_paths.append(ray_path)
                                        logger.info(
                                            f"創建了一條從 {tx_name} 到 {rx_name} 的路徑，點數: {len(points)}"
                                        )

                                except Exception as e:
                                    logger.warning(
                                        f"為 {tx_name}→{rx_name} 創建詳細路徑失敗: {e}"
                                    )

                    if len(response_paths) > 0:
                        logger.info(f"成功創建了 {len(response_paths)} 條詳細路徑")
                        return RayPathsResponse(paths=response_paths)

            # 如果失敗，嘗試其他方法...
            # 現有的代碼繼續執行
        except Exception as e:
            logger.exception(f"嘗試獲取路徑數據時出錯: {e}")
            # 不中斷程序，嘗試使用原來的方法

        # 如果上面的方法都失敗，繼續使用原來的方法嘗試
        if len(response_paths) == 0:
            logger.info("嘗試其他方法獲取路徑...")
            try:
                for tx_idx, tx in enumerate(scene.transmitters):
                    for rx_idx, rx in enumerate(scene.receivers):
                        # 檢查tx和rx是否為字符串類型
                        tx_name = (
                            tx
                            if isinstance(tx, str)
                            else getattr(tx, "name", f"TX-{tx_idx}")
                        )
                        rx_name = (
                            rx
                            if isinstance(rx, str)
                            else getattr(rx, "name", f"RX-{rx_idx}")
                        )

                        logger.info(
                            f"處理 TX{tx_idx} ({tx_name}) 到 RX{rx_idx} ({rx_name}) 的路徑"
                        )

                        # 嘗試不同的方法獲取路徑
                        try:
                            # 嘗試使用不同的方法獲取路徑數據
                            if hasattr(paths, "path"):
                                logger.info("嘗試使用path屬性")
                                pair_paths = paths.path(tx_idx, rx_idx)
                                logger.info(f"成功獲取路徑: {type(pair_paths)}")
                            elif hasattr(paths, "__call__"):
                                logger.info("嘗試使用__call__方法")
                                pair_paths = paths(tx_idx, rx_idx)
                                logger.info(f"成功獲取路徑: {type(pair_paths)}")
                            else:
                                # 嘗試直接使用索引，可能會失敗
                                logger.warning("嘗試直接索引，可能會失敗")
                                try:
                                    pair_paths = paths[tx_idx, rx_idx]
                                    logger.info(f"成功獲取路徑: {type(pair_paths)}")
                                except Exception as idx_error:
                                    logger.warning(
                                        f"獲取TX-RX對路徑時出錯: {idx_error}"
                                    )
                                    # 如果無法獲取路徑，嘗試直接創建一條直線路徑
                                    try:
                                        # 獲取發射器和接收器位置
                                        tx_position = getattr(tx, "position", None)
                                        rx_position = getattr(rx, "position", None)

                                        if (
                                            tx_position is not None
                                            and rx_position is not None
                                        ):
                                            # 創建一條簡單的視線路徑
                                            points = [
                                                RayPoint(
                                                    x=float(tx_position[0]),
                                                    y=float(tx_position[1]),
                                                    z=float(tx_position[2]),
                                                ),
                                                RayPoint(
                                                    x=float(rx_position[0]),
                                                    y=float(rx_position[1]),
                                                    z=float(rx_position[2]),
                                                ),
                                            ]

                                            ray_path = RayPath(
                                                points=points, is_los=True
                                            )
                                            response_paths.append(ray_path)
                                            logger.info(
                                                f"為 {tx_name}→{rx_name} 創建了一條簡單視線路徑"
                                            )
                                    except Exception as path_error:
                                        logger.warning(
                                            f"創建簡單視線路徑時出錯: {path_error}"
                                        )
                        except Exception as pair_error:
                            logger.warning(f"獲取TX-RX對路徑時出錯: {pair_error}")
            except Exception as e:
                logger.exception(f"構建路徑數據時發生錯誤: {e}")

        # 7. 返回響應
        logger.info(f"最終構建了 {len(response_paths)} 條路徑，準備返回")
        return RayPathsResponse(paths=response_paths)

    except Exception as e:
        logger.exception(f"計算射線路徑時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"計算射線路徑時發生錯誤: {str(e)}")
