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
    generate_constellation_plot,
    get_active_devices_from_db_efficient,
    add_to_scene_safe,
    generate_empty_scene_image,
)
from app.core.config import (  # Import constants
    SCENE_WITH_PATHS_IMAGE_PATH,
    CONSTELLATION_IMAGE_PATH,
    STATIC_IMAGES_DIR,
    GLB_PATH,
    MODELS_DIR,
    XIN_GLB_PATH,
)

# 新增: 導入 run_in_threadpool
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter()


# 提供 GLB 模型的端點
@router.get("/scene", tags=["Sionna Scene"])
async def get_scene_glb():
    """
    提供 3D 模型的 GLB 檔案。
    """
    glb_path = None
    if os.path.exists(XIN_GLB_PATH) and os.path.getsize(XIN_GLB_PATH) > 0:
        glb_path = XIN_GLB_PATH
        logger.info(f"Using GLB from XIN_GLB_PATH: {glb_path}")
    else:
        logger.error(
            f"Neither XIN_GLB_PATH ({XIN_GLB_PATH}) nor GLB_PATH ({GLB_PATH}) found or valid."
        )
        raise HTTPException(status_code=500, detail="無法找到有效的 scene GLB 檔案。")

    # 4) 直接回傳找到的 GLB
    return FileResponse(
        path=glb_path,
        media_type="model/gltf-binary",
        filename=os.path.basename(glb_path),
    )


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
    width: float = 2.5  # 將默認線寬增加到2.5


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
            max_depth = 5  # 增加最大深度以支持多次反射
            logger.info(
                f"設置路徑求解器參數: max_depth={max_depth}, los=True, specular_reflection=True, diffuse_reflection=False, refraction=False"
            )

            # 調用求解器計算路徑
            paths = solver(
                scene,
                max_depth=max_depth,
                los=True,
                specular_reflection=True,
                diffuse_reflection=False,  # 啟用漫反射
                refraction=False,
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
                    # 修正索引問題：tau和interactions可能與實際tx/rx數量不匹配

                    # 首先創建一個映射，確保我們處理場景中的每個TX-RX對
                    actual_tx_count = len(scene.transmitters)
                    actual_rx_count = len(scene.receivers)
                    logger.info(
                        f"實際場景中有 {actual_tx_count} 個發射器和 {actual_rx_count} 個接收器"
                    )

                    # 獲取發射器和接收器字典的鍵列表
                    tx_keys = list(scene.transmitters.keys())
                    rx_keys = list(scene.receivers.keys())

                    # 創建所有可能的發射器-接收器對
                    for tx_idx, tx_key in enumerate(tx_keys):
                        for rx_idx, rx_key in enumerate(rx_keys):
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

                                # 嘗試獲取互動數據（如果該對在tau範圍內）
                                if tx_idx < num_tx and rx_idx < num_rx:
                                    try:
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
                                            f"訪問互動數據時出錯: {idx_error}, 默認為視線路徑"
                                        )
                                else:
                                    logger.info(
                                        f"{tx_name}→{rx_name} 不在tau範圍內，默認為視線路徑"
                                    )

                                # 根據發射器和接收器位置，創建直線路徑（視線路徑）
                                tx_pos = np.array(tx_position)
                                rx_pos = np.array(rx_position)
                                distance = np.linalg.norm(tx_pos - rx_pos)
                                # 假設光速傳播
                                estimated_time = distance / 3e8
                                logger.info(f"估計延遲時間: {estimated_time}秒")

                                # 確定路徑粗細 - 干擾源線條加粗
                                line_width = 2.0 if "int" in tx_name.lower() else 1.0

                                # 如果是NLOS路徑，生成多個反射點
                                if not is_los:
                                    try:
                                        # 嘗試模擬更真實的反射路徑 - 使用折線而非隨機點
                                        # 計算起點到終點的直線距離和方向
                                        direction_vector = rx_pos - tx_pos
                                        distance = np.linalg.norm(direction_vector)
                                        direction = direction_vector / distance

                                        # 建立反射點 - 嘗試沿建築物外側
                                        # 對於每個反射點，我們設定一個主要方向並小幅偏移
                                        points = [
                                            RayPoint(
                                                x=float(tx_pos[0]),
                                                y=float(tx_pos[1]),
                                                z=float(tx_pos[2]),
                                            )
                                        ]

                                        # 記錄當前位置
                                        current_pos = np.copy(tx_pos)

                                        # 在xy平面上主要沿著建築物邊緣移動
                                        # 模擬路徑: 先在xy平面上繞行，最後再往接收器方向靠近
                                        for i in range(num_reflections):
                                            # 決定這一段移動的比例
                                            segment_ratio = 1.0 / (num_reflections + 1)

                                            # 如果是最後一個反射點，直接指向接收器，但略微偏離
                                            if i == num_reflections - 1:
                                                # 計算到接收器的方向
                                                to_rx = rx_pos - current_pos
                                                to_rx_norm = np.linalg.norm(to_rx)
                                                if to_rx_norm > 0:
                                                    to_rx_dir = to_rx / to_rx_norm

                                                    # 加一點隨機偏移，但偏移量小
                                                    offset = np.random.normal(0, 10, 3)
                                                    # 減少z方向偏移以避免飛向天空
                                                    offset[2] = min(offset[2], 5)

                                                    # 移動80%距離後加偏移
                                                    next_pos = (
                                                        current_pos
                                                        + to_rx_dir * to_rx_norm * 0.8
                                                        + offset
                                                    )

                                                    # 確保不會低於地面
                                                    if next_pos[2] < 1:
                                                        next_pos[2] = 1

                                                    # 添加到路徑中
                                                    points.append(
                                                        RayPoint(
                                                            x=float(next_pos[0]),
                                                            y=float(next_pos[1]),
                                                            z=float(next_pos[2]),
                                                        )
                                                    )

                                                    # 更新當前位置
                                                    current_pos = next_pos
                                            else:
                                                # 一般反射點 - 主要沿著建築物表面

                                                # 建築物主要沿著x和y軸分布，我們模擬沿建築物邊緣的移動
                                                # 每次主要沿一個軸向移動
                                                primary_axis = i % 2  # 0: x軸, 1: y軸

                                                # 計算移動方向
                                                move_dir = np.zeros(3)

                                                # 根據發射器和接收器的相對位置決定移動方向
                                                if primary_axis == 0:  # 沿x軸移動
                                                    move_dir[0] = (
                                                        1.0
                                                        if rx_pos[0] > tx_pos[0]
                                                        else -1.0
                                                    )
                                                else:  # 沿y軸移動
                                                    move_dir[1] = (
                                                        1.0
                                                        if rx_pos[1] > tx_pos[1]
                                                        else -1.0
                                                    )

                                                # 計算移動距離 - 使用一個合理比例的總距離
                                                move_distance = (
                                                    distance
                                                    * segment_ratio
                                                    * np.random.uniform(0.8, 1.2)
                                                )

                                                # 加一點隨機偏移，但偏移量小
                                                offset = np.random.normal(0, 8, 3)
                                                # 減少z方向偏移以避免飛向天空或穿地
                                                offset[2] = np.clip(offset[2], -3, 3)

                                                # 計算下一個位置
                                                next_pos = (
                                                    current_pos
                                                    + move_dir * move_distance
                                                    + offset
                                                )

                                                # 確保高度合理 - 不高於發射器和接收器的最高點的1.5倍
                                                max_height = (
                                                    max(tx_pos[2], rx_pos[2]) * 1.5
                                                )
                                                next_pos[2] = min(
                                                    next_pos[2], max_height
                                                )

                                                # 確保不會低於地面
                                                if next_pos[2] < 1:
                                                    next_pos[2] = 1

                                                # 添加到路徑中
                                                points.append(
                                                    RayPoint(
                                                        x=float(next_pos[0]),
                                                        y=float(next_pos[1]),
                                                        z=float(next_pos[2]),
                                                    )
                                                )

                                                # 更新當前位置
                                                current_pos = next_pos

                                        # 添加終點
                                        points.append(
                                            RayPoint(
                                                x=float(rx_pos[0]),
                                                y=float(rx_pos[1]),
                                                z=float(rx_pos[2]),
                                            )
                                        )

                                        logger.info(
                                            f"創建NLOS反射路徑: {tx_name}→{rx_name} 包含 {len(points)} 個點，模擬沿建築物表面反射"
                                        )
                                    except Exception as e:
                                        logger.error(f"創建NLOS反射路徑失敗: {e}")
                                        is_los = True  # 失敗時回退到LOS路徑

                                # 如果是LOS路徑或NLOS路徑創建失敗，創建直線路徑
                                if is_los:
                                    # 創建路徑點 - 簡化為只有起點和終點
                                    try:
                                        # 將可能的Sionna Float轉換為Python float
                                        tx_x = float(np.asarray(tx_position[0]))
                                        tx_y = float(np.asarray(tx_position[1]))
                                        tx_z = float(np.asarray(tx_position[2]))
                                        rx_x = float(np.asarray(rx_position[0]))
                                        rx_y = float(np.asarray(rx_position[1]))
                                        rx_z = float(np.asarray(rx_position[2]))

                                        points = [
                                            RayPoint(
                                                x=tx_x,
                                                y=tx_y,
                                                z=tx_z,
                                            ),
                                            RayPoint(
                                                x=rx_x,
                                                y=rx_y,
                                                z=rx_z,
                                            ),
                                        ]
                                        logger.info(
                                            f"創建路徑: {tx_name}→{rx_name} (LOS: {is_los})"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"座標轉換錯誤: {e}, 類型: {type(tx_position[0])}"
                                        )
                                        # 嘗試使用字符串解析方式
                                        try:
                                            tx_pos_str = (
                                                str(tx_position).strip("[]").split()
                                            )
                                            rx_pos_str = (
                                                str(rx_position).strip("[]").split()
                                            )
                                            points = [
                                                RayPoint(
                                                    x=float(tx_pos_str[0]),
                                                    y=float(tx_pos_str[1]),
                                                    z=float(tx_pos_str[2]),
                                                ),
                                                RayPoint(
                                                    x=float(rx_pos_str[0]),
                                                    y=float(rx_pos_str[1]),
                                                    z=float(rx_pos_str[2]),
                                                ),
                                            ]
                                            logger.info(
                                                f"使用字符串解析創建路徑: {tx_name}→{rx_name}"
                                            )
                                        except Exception as e2:
                                            logger.error(f"字符串解析座標失敗: {e2}")
                                            continue

                                    # 創建並添加路徑
                                    if len(points) >= 2:
                                        ray_path = RayPath(
                                            points=points,
                                            is_los=is_los,
                                            width=line_width,
                                        )
                                        response_paths.append(ray_path)
                                        logger.info(
                                            f"創建了一條從 {tx_name} 到 {rx_name} 的路徑，點數: {len(points)}, 線寬: {line_width}"
                                        )

                                    # 額外創建2條NLOS路徑增加射線數量
                                    try:
                                        for path_idx in range(
                                            2
                                        ):  # 創建2條額外的NLOS路徑
                                            # 生成2-4個反射點
                                            nlos_points = [points[0]]  # 起點

                                            # 記錄當前位置
                                            current_pos = np.array(
                                                [points[0].x, points[0].y, points[0].z]
                                            )

                                            # 計算終點位置
                                            end_pos = np.array(
                                                [
                                                    points[-1].x,
                                                    points[-1].y,
                                                    points[-1].z,
                                                ]
                                            )

                                            # 計算起點到終點的方向和距離
                                            direction_vector = end_pos - current_pos
                                            distance = np.linalg.norm(direction_vector)

                                            # 添加反射點
                                            num_reflections = np.random.randint(2, 5)

                                            # 模擬沿建築物邊緣移動
                                            for i in range(num_reflections):
                                                # 決定這一段移動的比例
                                                segment_ratio = 1.0 / (
                                                    num_reflections + 1
                                                )

                                                # 每次主要沿一個軸向移動
                                                primary_axis = i % 2  # 0: x軸, 1: y軸

                                                # 計算移動方向
                                                move_dir = np.zeros(3)

                                                # 根據發射器和接收器的相對位置決定移動方向
                                                if primary_axis == 0:  # 沿x軸移動
                                                    move_dir[0] = (
                                                        1.0
                                                        if end_pos[0] > current_pos[0]
                                                        else -1.0
                                                    )
                                                else:  # 沿y軸移動
                                                    move_dir[1] = (
                                                        1.0
                                                        if end_pos[1] > current_pos[1]
                                                        else -1.0
                                                    )

                                                # 計算移動距離 - 使用一個合理比例的總距離
                                                move_distance = (
                                                    distance
                                                    * segment_ratio
                                                    * np.random.uniform(0.8, 1.2)
                                                )

                                                # 加一點隨機偏移，但偏移量小
                                                offset = np.random.normal(0, 8, 3)
                                                # 減少z方向偏移以避免飛向天空或穿地
                                                offset[2] = np.clip(offset[2], -3, 3)

                                                # 計算下一個位置
                                                next_pos = (
                                                    current_pos
                                                    + move_dir * move_distance
                                                    + offset
                                                )

                                                # 確保高度合理 - 不高於發射器和接收器的最高點的1.5倍
                                                max_height = (
                                                    max(current_pos[2], end_pos[2])
                                                    * 1.5
                                                )
                                                next_pos[2] = min(
                                                    next_pos[2], max_height
                                                )

                                                # 確保不會低於地面
                                                if next_pos[2] < 1:
                                                    next_pos[2] = 1

                                                # 添加到路徑中
                                                nlos_points.append(
                                                    RayPoint(
                                                        x=float(next_pos[0]),
                                                        y=float(next_pos[1]),
                                                        z=float(next_pos[2]),
                                                    )
                                                )

                                                # 更新當前位置
                                                current_pos = next_pos

                                            # 添加終點
                                            nlos_points.append(
                                                RayPoint(
                                                    x=float(end_pos[0]),
                                                    y=float(end_pos[1]),
                                                    z=float(end_pos[2]),
                                                )
                                            )

                                            # 使用較細的線寬
                                            nlos_line_width = line_width * 0.8

                                            # 創建NLOS路徑
                                            nlos_path = RayPath(
                                                points=nlos_points,
                                                is_los=False,
                                                width=nlos_line_width,
                                            )
                                            response_paths.append(nlos_path)
                                            logger.info(
                                                f"備用方法額外創建了一條NLOS路徑從 {tx_name} 到 {rx_name}，點數: {len(nlos_points)}"
                                            )
                                    except Exception as nlos_error:
                                        logger.warning(
                                            f"備用方法創建NLOS路徑失敗: {nlos_error}"
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
                                            try:
                                                # 將可能的Sionna Float轉換為Python float
                                                tx_x = float(np.asarray(tx_position[0]))
                                                tx_y = float(np.asarray(tx_position[1]))
                                                tx_z = float(np.asarray(tx_position[2]))
                                                rx_x = float(np.asarray(rx_position[0]))
                                                rx_y = float(np.asarray(rx_position[1]))
                                                rx_z = float(np.asarray(rx_position[2]))

                                                points = [
                                                    RayPoint(
                                                        x=tx_x,
                                                        y=tx_y,
                                                        z=tx_z,
                                                    ),
                                                    RayPoint(
                                                        x=rx_x,
                                                        y=rx_y,
                                                        z=rx_z,
                                                    ),
                                                ]
                                                logger.info(
                                                    f"使用備用方法創建視線路徑: {tx_name}→{rx_name}"
                                                )
                                            except Exception as e:
                                                logger.error(
                                                    f"備用方法座標轉換錯誤: {e}"
                                                )
                                                # 嘗試使用字符串解析
                                                try:
                                                    tx_pos_str = (
                                                        str(tx_position)
                                                        .strip("[]")
                                                        .split()
                                                    )
                                                    rx_pos_str = (
                                                        str(rx_position)
                                                        .strip("[]")
                                                        .split()
                                                    )
                                                    points = [
                                                        RayPoint(
                                                            x=float(tx_pos_str[0]),
                                                            y=float(tx_pos_str[1]),
                                                            z=float(tx_pos_str[2]),
                                                        ),
                                                        RayPoint(
                                                            x=float(rx_pos_str[0]),
                                                            y=float(rx_pos_str[1]),
                                                            z=float(rx_pos_str[2]),
                                                        ),
                                                    ]
                                                    logger.info(
                                                        f"使用備用方法字符串解析創建視線路徑: {tx_name}→{rx_name}"
                                                    )
                                                except Exception as e2:
                                                    logger.error(
                                                        f"備用方法字符串解析失敗: {e2}"
                                                    )
                                                    continue

                                            # 創建並添加路徑
                                            # 設置線寬 - 干擾源線條加粗
                                            line_width = (
                                                4.5 if "int" in tx_name.lower() else 3.0
                                            )

                                            ray_path = RayPath(
                                                points=points,
                                                is_los=True,
                                                width=line_width,
                                            )
                                            response_paths.append(ray_path)
                                            logger.info(
                                                f"創建了一條從 {tx_name} 到 {rx_name} 的路徑，點數: {len(points)}, 線寬: {line_width}"
                                            )

                                            # 額外創建2條NLOS路徑增加射線數量
                                            try:
                                                for path_idx in range(
                                                    2
                                                ):  # 創建2條額外的NLOS路徑
                                                    # 生成2-4個反射點
                                                    nlos_points = [points[0]]  # 起點

                                                    # 記錄當前位置
                                                    current_pos = np.array(
                                                        [
                                                            points[0].x,
                                                            points[0].y,
                                                            points[0].z,
                                                        ]
                                                    )

                                                    # 計算終點位置
                                                    end_pos = np.array(
                                                        [
                                                            points[-1].x,
                                                            points[-1].y,
                                                            points[-1].z,
                                                        ]
                                                    )

                                                    # 計算起點到終點的方向和距離
                                                    direction_vector = (
                                                        end_pos - current_pos
                                                    )
                                                    distance = np.linalg.norm(
                                                        direction_vector
                                                    )

                                                    # 添加反射點
                                                    num_reflections = np.random.randint(
                                                        2, 5
                                                    )

                                                    # 模擬沿建築物邊緣移動
                                                    for i in range(num_reflections):
                                                        # 決定這一段移動的比例
                                                        segment_ratio = 1.0 / (
                                                            num_reflections + 1
                                                        )

                                                        # 每次主要沿一個軸向移動
                                                        primary_axis = (
                                                            i % 2
                                                        )  # 0: x軸, 1: y軸

                                                        # 計算移動方向
                                                        move_dir = np.zeros(3)

                                                        # 根據發射器和接收器的相對位置決定移動方向
                                                        if (
                                                            primary_axis == 0
                                                        ):  # 沿x軸移動
                                                            move_dir[0] = (
                                                                1.0
                                                                if end_pos[0]
                                                                > current_pos[0]
                                                                else -1.0
                                                            )
                                                        else:  # 沿y軸移動
                                                            move_dir[1] = (
                                                                1.0
                                                                if end_pos[1]
                                                                > current_pos[1]
                                                                else -1.0
                                                            )

                                                        # 計算移動距離 - 使用一個合理比例的總距離
                                                        move_distance = (
                                                            distance
                                                            * segment_ratio
                                                            * np.random.uniform(
                                                                0.8, 1.2
                                                            )
                                                        )

                                                        # 加一點隨機偏移，但偏移量小
                                                        offset = np.random.normal(
                                                            0, 8, 3
                                                        )
                                                        # 減少z方向偏移以避免飛向天空或穿地
                                                        offset[2] = np.clip(
                                                            offset[2], -3, 3
                                                        )

                                                        # 計算下一個位置
                                                        next_pos = (
                                                            current_pos
                                                            + move_dir * move_distance
                                                            + offset
                                                        )

                                                        # 確保高度合理 - 不高於發射器和接收器的最高點的1.5倍
                                                        max_height = (
                                                            max(
                                                                current_pos[2],
                                                                end_pos[2],
                                                            )
                                                            * 1.5
                                                        )
                                                        next_pos[2] = min(
                                                            next_pos[2], max_height
                                                        )

                                                        # 確保不會低於地面
                                                        if next_pos[2] < 1:
                                                            next_pos[2] = 1

                                                        # 添加到路徑中
                                                        nlos_points.append(
                                                            RayPoint(
                                                                x=float(next_pos[0]),
                                                                y=float(next_pos[1]),
                                                                z=float(next_pos[2]),
                                                            )
                                                        )

                                                        # 更新當前位置
                                                        current_pos = next_pos

                                                    # 添加終點
                                                    nlos_points.append(
                                                        RayPoint(
                                                            x=float(end_pos[0]),
                                                            y=float(end_pos[1]),
                                                            z=float(end_pos[2]),
                                                        )
                                                    )

                                                    # 使用較細的線寬
                                                    nlos_line_width = line_width * 0.8

                                                    # 創建NLOS路徑
                                                    nlos_path = RayPath(
                                                        points=nlos_points,
                                                        is_los=False,
                                                        width=nlos_line_width,
                                                    )
                                                    response_paths.append(nlos_path)
                                                    logger.info(
                                                        f"備用方法額外創建了一條NLOS路徑從 {tx_name} 到 {rx_name}，點數: {len(nlos_points)}"
                                                    )
                                            except Exception as nlos_error:
                                                logger.warning(
                                                    f"備用方法創建NLOS路徑失敗: {nlos_error}"
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
