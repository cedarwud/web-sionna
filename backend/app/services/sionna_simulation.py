# backend/app/services/sionna_simulation.py
import logging
import os
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Optional
from pydantic import BaseModel, Field as PydanticField  # Use Pydantic BaseModel
import sionna.rt
from sionna.rt import (
    load_scene,
    Camera,
    Transmitter as SionnaTransmitter,
    Receiver as SionnaReceiver,
    PlanarArray,
    PathSolver,
    subcarrier_frequencies,
    RadioMapSolver,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import collections.abc  # Import for checking iterable

# Import models and config from their new locations
from app.db.models import Device, DeviceRole
from app.core.config import (
    OUTPUT_DIR,
    NYCU_XML_PATH,
    CFR_PLOT_IMAGE_PATH,
    UNSCALED_DOPPLER_IMAGE_PATH,
    POWER_SCALED_DOPPLER_IMAGE_PATH,
)
from app.crud import crud_device  # 導入整合後的 crud_device 模塊

# 新增導入 for GLB rendering
import trimesh
import pyrender
from PIL import Image
import io
import tensorflow as tf

# 從 config 導入
from app.core.config import NYCU_GLB_PATH, OUTPUT_DIR  # 確保導入 NYCU_GLB_PATH

logger = logging.getLogger(__name__)

# --- 新增：場景背景顏色常數 ---
SCENE_BACKGROUND_COLOR_RGB = [0.5, 0.5, 0.5]
# --- End Constant ---

# Ensure output directory exists (could also be done on app startup)
# Note: OUTPUT_DIR is now defined in config.py as STATIC_IMAGES_DIR
# The directory creation is also handled in config.py
# os.makedirs(OUTPUT_DIR, exist_ok=True) # Can be removed if config.py handles it

# # 新增：GLB 模型文件路徑 (REMOVED - Defined in config.py)
# STATIC_DIR = (
#     Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
#     / "static"
# )
# MODELS_DIR = STATIC_DIR / "models"
# NYCU_GLB_PATH = MODELS_DIR / "NYCU.glb"  # 優先使用的 GLB 檔案


# --- 定義新的資料容器 ---
class DeviceData(BaseModel):
    """用於傳遞設備模型和其處理後的位置列表"""

    device_model: Device = PydanticField(...)  # Store the original SQLModel object
    position_list: List[float] = None  # Store the position as a list [x, y, z]
    orientation_list: List[float] = None  # Store the orientation as a list [x, y, z]
    transmitter_role: Optional[DeviceRole] = (
        None  # Store transmitter type if applicable
    )

    class Config:
        arbitrary_types_allowed = True  # Allow complex types like SQLModel objects


# --- Helper Function ---
def add_to_scene_safe(scene, device):
    """Safely adds a device to the Sionna scene, warns if it exists."""
    try:
        scene.add(device)
        logger.info(f"Added '{device.name}' to the scene.")
    except ValueError:
        logger.warning(f"Device '{device.name}' might already exist in the scene.")
        pass


# --- 更高效率版本的 get_active_devices_from_db 函數 ---
async def get_active_devices_from_db_efficient(
    session: AsyncSession,
) -> tuple[List[DeviceData], List[DeviceData]]:
    """獲取活動的發射器和接收器設備資料 (使用單次查詢，效率更高)"""
    logger.info("Fetching active devices from database (efficient version)...")

    # 為特定需求獲取發射器
    signal_txs = await get_transmitters_by_type(
        db=session, transmitter_role=DeviceRole.DESIRED, active_only=True
    )
    jammer_txs = await get_transmitters_by_type(
        db=session, transmitter_role=DeviceRole.JAMMER, active_only=True
    )

    # 獲取接收器
    receivers_query = select(Device).where(
        Device.active == True, Device.role == DeviceRole.RECEIVER.value
    )
    receivers_result = await session.execute(receivers_query)
    receivers = receivers_result.scalars().all()

    # 處理發射器數據
    transmitters_data: List[DeviceData] = []

    # 處理信號發射器
    for dev_model in signal_txs:
        pos_list = [dev_model.position_x, dev_model.position_y, dev_model.position_z]
        ori_list = [
            dev_model.orientation_x,
            dev_model.orientation_y,
            dev_model.orientation_z,
        ]
        device_data = DeviceData(
            device_model=dev_model,
            position_list=pos_list,
            orientation_list=ori_list,
            transmitter_role=DeviceRole.DESIRED,
        )
        transmitters_data.append(device_data)
        logger.info(
            f"Processed Active Signal Transmitter: {dev_model.name}, Position: {pos_list}, Orientation: {ori_list}"
        )

    # 處理干擾源發射器
    for dev_model in jammer_txs:
        pos_list = [dev_model.position_x, dev_model.position_y, dev_model.position_z]
        ori_list = [
            dev_model.orientation_x,
            dev_model.orientation_y,
            dev_model.orientation_z,
        ]
        device_data = DeviceData(
            device_model=dev_model,
            position_list=pos_list,
            orientation_list=ori_list,
            transmitter_role=DeviceRole.JAMMER,
        )
        transmitters_data.append(device_data)
        logger.info(
            f"Processed Active Jammer: {dev_model.name}, Position: {pos_list}, Orientation: {ori_list}"
        )

    # 處理接收器數據
    receivers_data: List[DeviceData] = []
    for dev_model in receivers:
        pos_list = [dev_model.position_x, dev_model.position_y, dev_model.position_z]
        ori_list = [
            dev_model.orientation_x,
            dev_model.orientation_y,
            dev_model.orientation_z,
        ]
        device_data = DeviceData(
            device_model=dev_model, position_list=pos_list, orientation_list=ori_list
        )
        receivers_data.append(device_data)
        logger.info(
            f"Processed Active Receiver: {dev_model.name}, Position: {pos_list}, Orientation: {ori_list}"
        )

    return transmitters_data, receivers_data


# 本地實現get_transmitters_by_type函數
async def get_transmitters_by_type(
    db: AsyncSession,
    *,
    transmitter_role: DeviceRole,
    active_only: bool = False,
) -> List[Device]:
    """
    根據發射器角色（DESIRED或JAMMER）獲取設備。
    """
    logger.debug(f"Fetching transmitters with role: {transmitter_role}")
    # 使用role值進行查詢
    query = select(Device).where(Device.role == transmitter_role.value)

    if active_only:
        query = query.where(Device.active == True)

    result = await db.execute(query)
    return result.scalars().all()


# --- Helper Function for Pyrender Scene Setup ---
def _setup_pyrender_scene_from_glb() -> Optional[pyrender.Scene]:
    """Loads GLB, sets up pyrender scene, lights, camera. Returns Scene or None on error."""
    logger.info(f"Setting up base pyrender scene from GLB: {NYCU_GLB_PATH}")
    try:
        # 1. Load GLB
        if not os.path.exists(NYCU_GLB_PATH) or os.path.getsize(NYCU_GLB_PATH) == 0:
            logger.error(f"GLB file not found or empty: {NYCU_GLB_PATH}")
            return None
        scene_tm = trimesh.load(NYCU_GLB_PATH, force="scene")
        logger.info("GLB file loaded.")

        # 2. Create pyrender scene with background and ambient light
        pr_scene = pyrender.Scene(
            bg_color=[*SCENE_BACKGROUND_COLOR_RGB, 1.0],
            ambient_light=[0.6, 0.6, 0.6],
        )

        # 3. Add GLB geometry
        logger.info("Adding GLB geometry...")
        for name, geom in scene_tm.geometry.items():
            if geom.vertices is not None and len(geom.vertices) > 0:
                if (
                    not hasattr(geom, "vertex_normals")
                    or geom.vertex_normals is None
                    or len(geom.vertex_normals) != len(geom.vertices)
                ):
                    if (
                        hasattr(geom, "faces")
                        and geom.faces is not None
                        and len(geom.faces) > 0
                    ):
                        try:
                            geom.compute_vertex_normals()
                        except Exception as norm_err:
                            logger.error(
                                f"Failed compute normals for '{name}': {norm_err}",
                                exc_info=True,
                            )
                            continue
                    else:
                        logger.warning(f"Mesh '{name}' has no faces. Skipping.")
                        continue
                if not hasattr(geom, "visual") or (
                    not hasattr(geom.visual, "vertex_colors")
                    and not hasattr(geom.visual, "material")
                ):
                    geom.visual = trimesh.visual.ColorVisuals(
                        mesh=geom, vertex_colors=[255, 255, 255, 255]
                    )
                try:
                    mesh = pyrender.Mesh.from_trimesh(geom, smooth=False)
                    pr_scene.add(mesh)
                except Exception as mesh_err:
                    logger.error(
                        f"Failed convert mesh '{name}': {mesh_err}", exc_info=True
                    )
            else:
                logger.warning(f"Skipping empty mesh '{name}'.")
        logger.info("GLB geometry added.")

        # 4. Add lights
        warm_white = np.array([1.0, 0.98, 0.9])
        main_light = pyrender.DirectionalLight(color=warm_white, intensity=3.0)
        pr_scene.add(main_light, pose=np.eye(4))
        logger.info("Lights added.")

        # 5. Add camera
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0, znear=0.1, zfar=10000.0)
        cam_pose = np.array(
            [
                [1.0, 0.0, 0.0, 17.0],
                [0.0, 0.0, 1.0, 1020.0],
                [0.0, -1.0, 0.0, -25.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        pr_scene.add(camera, pose=cam_pose)
        logger.info("Camera added.")

        return pr_scene

    except Exception as e:
        logger.error(f"Error setting up pyrender scene from GLB: {e}", exc_info=True)
        return None


# --- NEW Helper Function for Rendering, Cropping, and Saving ---
def _render_crop_and_save(
    pr_scene: pyrender.Scene,
    output_path: str,
    bg_color_float: List[float] = SCENE_BACKGROUND_COLOR_RGB,
    render_width: int = 1200,
    render_height: int = 960,
    padding_y: int = 0,  # Default vertical padding
    padding_x: int = 0,  # Default horizontal padding
) -> bool:
    """Renders the scene, crops based on content, and saves the image."""
    logger.info("Starting offscreen rendering...")
    try:
        renderer = pyrender.OffscreenRenderer(render_width, render_height)
        color, _ = renderer.render(pr_scene)
        renderer.delete()
        logger.info("Rendering complete.")
    except Exception as render_err:
        logger.error(f"Pyrender OffscreenRenderer failed: {render_err}", exc_info=True)
        return False

    # --- Cropping Logic ---
    logger.info("Calculating bounding box for cropping...")
    image_to_save = color  # Default to original image
    try:
        bg_color_uint8 = (np.array(bg_color_float) * 255).astype(np.uint8)
        mask = ~np.all(color[:, :, :3] == bg_color_uint8, axis=2)
        rows, cols = np.where(mask)

        if rows.size > 0 and cols.size > 0:
            ymin, ymax = rows.min(), rows.max()
            xmin, xmax = cols.min(), cols.max()
            # Apply padding separately
            ymin = max(0, ymin - padding_y)
            xmin = max(0, xmin - padding_x)
            ymax = min(render_height - 1, ymax + padding_y)
            xmax = min(render_width - 1, xmax + padding_x)

            if xmin < xmax and ymin < ymax:
                cropped_color = color[ymin : ymax + 1, xmin : xmax + 1]
                logger.info(
                    f"Cropping image to bounds: (xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax})"
                )
                image_to_save = cropped_color
            else:
                logger.warning(f"Invalid crop bounds (min>=max). Saving original.")
        else:
            logger.warning("No non-background pixels found. Saving original image.")

    except Exception as crop_err:
        logger.error(f"Error during image cropping: {crop_err}", exc_info=True)
        # Fallback to original image

    # --- Save the Image using PIL ---
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    logger.info(f"Saving final image to: {output_path}")
    try:
        img = Image.fromarray(image_to_save)
        img.save(output_path, format="PNG")
    except Exception as save_err:
        logger.error(f"Failed to save rendered image: {save_err}", exc_info=True)
        return False

    # Final check
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        logger.info(
            f"Successfully saved image to {output_path}, size: {os.path.getsize(output_path)} bytes"
        )
        return True
    else:
        logger.error(f"Failed to save image or image is empty: {output_path}")
        return False


async def generate_scene_with_paths_image(
    output_path: str, session: AsyncSession
) -> bool:
    logger.info("Entering generate_scene_with_paths_image (using helpers) function...")
    try:
        # --- 1. Fetch Device Data --- (Keep)
        transmitters_data, receivers_data = await get_active_devices_from_db_efficient(
            session
        )
        if not transmitters_data or not receivers_data:
            return False

        # --- 2. Sionna RT Path Calculation --- (Keep)
        logger.info("Setting up Sionna RT scene for path calculation...")
        scene_rt = load_scene(sionna.rt.scene.etoile)
        iso = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
        scene_rt.tx_array = iso
        scene_rt.rx_array = iso

        sionna_txs_rt = []  # Keep track of Sionna RT objects
        for tx_data in transmitters_data:
            if tx_data.position_list:
                sionna_tx = SionnaTransmitter(
                    tx_data.device_model.name,
                    position=tx_data.position_list,
                    orientation=tx_data.orientation_list,  # 使用儲存的方向信息
                )
                sionna_txs_rt.append(sionna_tx)
                add_to_scene_safe(scene_rt, sionna_tx)

        sionna_rxs_rt = []
        valid_rx_positions_exist = False
        for rx_data in receivers_data:
            if rx_data.position_list:
                sionna_rx = SionnaReceiver(
                    rx_data.device_model.name,
                    position=rx_data.position_list,
                    orientation=rx_data.orientation_list,  # 使用儲存的方向信息
                )
                sionna_rxs_rt.append(sionna_rx)
                add_to_scene_safe(scene_rt, sionna_rx)
                valid_rx_positions_exist = True

        if not valid_rx_positions_exist:
            logger.error("No receivers with valid positions for path calculation.")
            return False
        if not scene_rt.transmitters or not scene_rt.receivers:
            logger.error("No valid TX/RX added to Sionna RT scene.")
            return False

        logger.info("Calculating paths using Sionna RT solver...")
        solver = PathSolver()
        paths = solver(
            scene_rt,
            max_depth=6,
            los=True,
            specular_reflection=True,
            diffuse_reflection=False,
            refraction=True,
        )
        logger.info("Path calculation complete.")

        # --- 3. Setup Base Pyrender Scene using Helper ---
        pr_scene = _setup_pyrender_scene_from_glb()  # Helper uses this bg color
        if pr_scene is None:
            return False
        logger.info("Base pyrender scene setup complete.")

        # --- 4. Overlay Devices --- (Keep)
        logger.info("Overlaying devices onto pyrender scene...")
        # Define cone dimensions and rotation for downward pointing
        CONE_RADIUS = 12.0  # 放大圓點
        CONE_HEIGHT = 36.0  # 放大圓點
        # Rotate cone model (-90 deg around X) to align Trimesh +Z with Pyrender -Y (down)
        down_rotation_matrix = trimesh.transformations.rotation_matrix(
            -np.pi / 2, [1, 0, 0]
        )
        # Additional tilt (e.g., 45 degrees around X-axis)
        tilt_angle_rad = np.radians(45)  # Increased tilt
        tilt_rotation_matrix = trimesh.transformations.rotation_matrix(
            tilt_angle_rad, [1, 0, 0]
        )

        # New Colors with better contrast
        TX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 1.0, 0.0, 1.0]  # Bright Yellow (Keep)
        )
        RX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 0.27, 0.0, 1.0]  # Orange-Red
        )
        INT_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.4, 0.7, 1.0, 1.0]  # 較淺的藍色
        )
        # White material for outline
        WHITE_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 1.0, 1.0, 1.0]  # White
        )

        # Outline disk dimensions
        OUTLINE_RADIUS = CONE_RADIUS + 1.0  # 跟 cone 一起變大
        OUTLINE_HEIGHT = 0.5  # 保持不變

        # Add transmitters to scene
        for tx_data in transmitters_data:
            if tx_data.position_list:
                pos = tx_data.position_list
                mat = (
                    INT_MATERIAL_PYRENDER
                    if tx_data.transmitter_role == DeviceRole.JAMMER
                    else TX_MATERIAL_PYRENDER
                )
                try:
                    # Create colored cone
                    cone = trimesh.creation.cone(radius=CONE_RADIUS, height=CONE_HEIGHT)
                    device_mesh = pyrender.Mesh.from_trimesh(cone, material=mat)
                    # Create white outline disk (cylinder)
                    outline_disk = trimesh.creation.cylinder(
                        radius=OUTLINE_RADIUS, height=OUTLINE_HEIGHT
                    )
                    outline_mesh = pyrender.Mesh.from_trimesh(
                        outline_disk, material=WHITE_MATERIAL_PYRENDER
                    )

                    # Pose for cone (tip at ground, pointing down)
                    translation_matrix = trimesh.transformations.translation_matrix(
                        [pos[0], pos[2], pos[1]]
                    )  # Tip at ground Z=pos[2]
                    # Only apply down rotation, no tilt
                    cone_pose_matrix = translation_matrix @ down_rotation_matrix

                    # Pose for outline disk (centered at cone base, slightly below)
                    outline_center_z = (
                        pos[2] - OUTLINE_HEIGHT / 2 - 0.1
                    )  # Place slightly below cone tip
                    outline_translation_matrix = (
                        trimesh.transformations.translation_matrix(
                            [pos[0], outline_center_z, pos[1]]
                        )
                    )
                    outline_pose_matrix = outline_translation_matrix

                    # Add outline first, then cone
                    pr_scene.add(outline_mesh, pose=outline_pose_matrix)
                    pr_scene.add(device_mesh, pose=cone_pose_matrix)

                    logger.info(
                        f"Added TX Cone '{tx_data.device_model.name}' with outline to scene"
                    )
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding TX Cone '{tx_data.device_model.name}' to scene: {dev_err}",
                        exc_info=True,
                    )
        for rx_data in receivers_data:
            if rx_data.position_list:
                pos = rx_data.position_list
                mat = RX_MATERIAL_PYRENDER
                try:
                    # Create colored cone
                    cone = trimesh.creation.cone(radius=CONE_RADIUS, height=CONE_HEIGHT)
                    device_mesh = pyrender.Mesh.from_trimesh(cone, material=mat)
                    # Create white outline disk (cylinder)
                    outline_disk = trimesh.creation.cylinder(
                        radius=OUTLINE_RADIUS, height=OUTLINE_HEIGHT
                    )
                    outline_mesh = pyrender.Mesh.from_trimesh(
                        outline_disk, material=WHITE_MATERIAL_PYRENDER
                    )

                    # Pose for cone (tip at ground, pointing down)
                    translation_matrix = trimesh.transformations.translation_matrix(
                        [pos[0], pos[2], pos[1]]
                    )  # Tip at ground Z=pos[2]
                    # Only apply down rotation, no tilt
                    cone_pose_matrix = translation_matrix @ down_rotation_matrix

                    # Pose for outline disk (centered at cone base, slightly below)
                    outline_center_z = (
                        pos[2] - OUTLINE_HEIGHT / 2 - 0.1
                    )  # Place slightly below cone tip
                    outline_translation_matrix = (
                        trimesh.transformations.translation_matrix(
                            [pos[0], outline_center_z, pos[1]]
                        )
                    )
                    outline_pose_matrix = outline_translation_matrix

                    # Add outline first, then cone
                    pr_scene.add(outline_mesh, pose=outline_pose_matrix)
                    pr_scene.add(device_mesh, pose=cone_pose_matrix)

                    logger.info(
                        f"Added RX Cone '{rx_data.device_model.name}' with outline to scene"
                    )
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding RX Cone '{rx_data.device_model.name}' to scene: {dev_err}",
                        exc_info=True,
                    )
        logger.info("Devices overlay complete.")

        # --- 5. Overlay Ray Paths --- (Keep placeholder)
        logger.warning("Ray path overlay in pyrender is not yet implemented.")
        # TODO: Implement path overlay

        # --- 6. Render, Crop, and Save using Helper ---
        success = _render_crop_and_save(
            pr_scene,
            output_path,
            bg_color_float=SCENE_BACKGROUND_COLOR_RGB,
            padding_x=0,  # Set horizontal padding to 0
            padding_y=20,  # Keep vertical padding at 20 (or adjust if needed)
        )
        return success

    except ImportError as ie:
        logger.error(f"Import error: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error in generate_scene_with_paths_image: {e}", exc_info=True)
        return False


async def generate_constellation_plot(
    output_path: str, session: AsyncSession, bandwidth=20e6, jnr_db=10.0, ebno_db=10.0
) -> bool:
    """Generates constellation plot using active devices from the database via DeviceData."""
    logger.info("Entering generate_constellation_plot function...")
    temp_file_path: Optional[str] = None  # <--- 初始化臨時文件路徑變數

    try:
        # --- 1. Fetch Active Devices Data ---
        # 使用更高效率的函數
        transmitters_data, receivers_data = await get_active_devices_from_db_efficient(
            session
        )
        if not transmitters_data or not receivers_data:
            logger.error(
                "No active transmitters or receivers data found for constellation plot."
            )
            return False

        rx_data = receivers_data[0]
        if not rx_data.position_list:
            logger.error(
                f"Selected receiver '{rx_data.device_model.name}' has no valid position."
            )
            return False

        signal_txs_data = [
            tx
            for tx in transmitters_data
            if tx.transmitter_role == DeviceRole.DESIRED and tx.position_list
        ]
        jammer_txs_data = [
            tx
            for tx in transmitters_data
            if tx.transmitter_role == DeviceRole.JAMMER and tx.position_list
        ]

        if not signal_txs_data:
            logger.error("No active signal transmitter with valid position found.")
            return False
        signal_tx_data = signal_txs_data[0]

        # --- 2. Setup Scene and Add Devices ---
        scene = load_scene(sionna.rt.scene.etoile)
        iso = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
        scene.tx_array = iso
        scene.rx_array = iso

        added_tx_names: List[str] = []

        logger.info("Creating Sionna Transmitter/Receiver objects from DeviceData...")
        sionna_signal_tx = SionnaTransmitter(
            signal_tx_data.device_model.name,
            position=signal_tx_data.position_list,
            orientation=signal_tx_data.orientation_list,  # 使用儲存的方向信息
        )
        add_to_scene_safe(scene, sionna_signal_tx)
        added_tx_names.append(signal_tx_data.device_model.name)

        sionna_jammer_txs = []
        for int_tx_data in jammer_txs_data:
            sionna_int_tx = SionnaTransmitter(
                int_tx_data.device_model.name,
                position=int_tx_data.position_list,
                orientation=int_tx_data.orientation_list,  # 使用儲存的方向信息
                color=[0, 0, 0],  # 將干擾源顏色設為黑色
            )
            sionna_jammer_txs.append(sionna_int_tx)
            add_to_scene_safe(scene, sionna_int_tx)
            added_tx_names.append(int_tx_data.device_model.name)

        sionna_rx = SionnaReceiver(
            rx_data.device_model.name,
            position=rx_data.position_list,
            orientation=rx_data.orientation_list,  # 使用儲存的方向信息
        )
        add_to_scene_safe(scene, sionna_rx)

        # 如果方向值為默認值0，動態計算朝向
        if all(ori == 0.0 for ori in signal_tx_data.orientation_list):
            sionna_signal_tx.look_at(sionna_rx)

        for i, sint_tx in enumerate(sionna_jammer_txs):
            if all(ori == 0.0 for ori in jammer_txs_data[i].orientation_list):
                sint_tx.look_at(sionna_rx)

        if not scene.transmitters or not scene.receivers:
            logger.error(
                "No valid transmitters or receivers were added to the Sionna scene for constellation."
            )
            plt.close("all")
            return False

        # --- 3. Calculate Paths and Taps ---
        logger.info("Calculating paths for constellation...")
        solver = PathSolver()
        paths = solver(
            scene,
            max_depth=6,
            los=True,
            specular_reflection=True,
            diffuse_reflection=False,
            refraction=True,
        )
        logger.info("Calculating channel taps...")
        h_tf = paths.taps(l_min=0, l_max=0, bandwidth=bandwidth, normalize=False)

        h_np_raw = None
        if isinstance(h_tf, list):
            logger.info("paths.taps returned a list. Converting to NumPy array.")
            h_np_raw = np.array(h_tf, dtype=complex)
        elif hasattr(h_tf, "numpy"):
            logger.info("paths.taps returned a Tensor-like object. Calling .numpy().")
            h_np_raw = h_tf.numpy()
        else:
            logger.error(
                f"Unexpected type returned by paths.taps: {type(h_tf)}. Cannot process taps."
            )
            plt.close("all")
            return False
        h_np = np.squeeze(h_np_raw)
        logger.info(f"Raw Taps h_np shape after squeeze: {h_np.shape}")

        # Ensure h_np is at least 1D array like
        if not isinstance(h_np, np.ndarray) or h_np.ndim == 0:
            h_np = np.array([h_np]) if np.isscalar(h_np) else np.array(h_np)
        logger.info(f"Processed Taps h_np shape: {h_np.shape}")

        # --- 4. Assign Main and Jammer Channels ---
        scene_tx_names = added_tx_names
        taps_dim = h_np.shape[0] if h_np.ndim > 0 else 0
        logger.info(f"Transmitters added to scene (used for taps): {scene_tx_names}")
        logger.info(f"Taps dimension suggests {taps_dim} transmitters.")

        if len(scene_tx_names) != taps_dim and taps_dim > 0:
            logger.warning(
                f"Mismatch between added transmitters ({len(scene_tx_names)}) and taps dimension ({taps_dim})."
            )

        h_main_scalar = 0 + 0j  # Initialize as complex scalar
        h_int_total_scalar = 0 + 0j  # Initialize as complex scalar
        num_jammers_in_taps = 0

        # Iterate through the taps based on the order transmitters were added
        for i, tx_name in enumerate(scene_tx_names):
            if i < taps_dim:
                current_tap_element = h_np[i]
                # ***** 關鍵修正：如果 current_tap_element 仍然是數組/列表，取第一個元素 *****
                # Check if it's an iterable (list, numpy array) and not a scalar
                if isinstance(
                    current_tap_element, collections.abc.Iterable
                ) and not isinstance(current_tap_element, (str, bytes)):
                    if len(current_tap_element) > 0:
                        # Take the first element, assuming SISO or first tap/antenna
                        tap_scalar = current_tap_element[0]
                        logger.debug(
                            f"Tap for {tx_name} is iterable, taking first element: {tap_scalar}"
                        )
                    else:
                        logger.warning(
                            f"Tap for {tx_name} is an empty iterable. Using 0+0j."
                        )
                        tap_scalar = 0 + 0j
                else:
                    # It's already a scalar (or expected to be)
                    tap_scalar = current_tap_element
                    logger.debug(f"Tap for {tx_name} is scalar: {tap_scalar}")

                # Assign to h_main_scalar or add to h_int_total_scalar
                if tx_name == signal_tx_data.device_model.name:
                    h_main_scalar = complex(tap_scalar)  # Ensure it's complex
                elif tx_name in [itx.device_model.name for itx in jammer_txs_data]:
                    h_int_total_scalar += complex(
                        tap_scalar
                    )  # Ensure it's complex before adding
                    num_jammers_in_taps += 1
                # ***** 結束修正 *****
            else:
                logger.warning(
                    f"Transmitter '{tx_name}' (index {i}) not found in taps output (dim {taps_dim})."
                )

        logger.info(f"h_main_scalar: {h_main_scalar}")
        logger.info(
            f"h_int_total_scalar (sum of {num_jammers_in_taps} active jammers found in taps): {h_int_total_scalar}"
        )

        # --- 5. Baseband Simulation ---
        # ***** 關鍵修正：使用 h_main_scalar 和 h_int_total_scalar *****
        logger.info("Executing baseband signal simulation...")
        N_SYM = 4096
        bits = np.random.randint(0, 2, (N_SYM, 2))
        x = (1 - 2 * bits[:, 0] + 1j * (1 - 2 * bits[:, 1])) / np.sqrt(2.0)

        # h_main and h_int_total are now guaranteed to be complex scalars
        y_sig_raw = h_main_scalar * x
        y_int_raw = h_int_total_scalar * x

        mean_sig_power = np.mean(np.abs(y_sig_raw) ** 2)
        mean_int_power = np.mean(np.abs(y_int_raw) ** 2)
        scale = 0.0
        if mean_int_power > 1e-15:
            jnr_linear = 10 ** (jnr_db / 10.0)
            if jnr_linear > 1e-15:
                scale_factor_sq = mean_sig_power / (mean_int_power * jnr_linear)
                scale = np.sqrt(max(0, scale_factor_sq))
        y_int = y_int_raw * scale
        snr_db = ebno_db + 10 * np.log10(2.0)
        snr_linear = 10 ** (snr_db / 10.0)
        noise = np.zeros(N_SYM, dtype=complex)
        if mean_sig_power > 1e-15 and snr_linear > 1e-15:
            noise_power = mean_sig_power / snr_linear
            noise = np.sqrt(noise_power / 2.0) * (
                np.random.randn(N_SYM) + 1j * np.random.randn(N_SYM)
            )
        y_no_i = y_sig_raw + noise
        y_with_i = y_sig_raw + y_int + noise
        y_eq_no_i = np.zeros_like(y_no_i)
        y_eq_with_i = np.zeros_like(y_with_i)
        # Use h_main_scalar for equalization check
        if np.abs(h_main_scalar) > 1e-15:
            y_eq_no_i = y_no_i / h_main_scalar
            y_eq_with_i = y_with_i / h_main_scalar
        else:
            logger.warning(
                "Main channel gain h_main_scalar is near zero. Cannot equalize."
            )
        logger.info("Baseband simulation complete.")
        # ***** 結束修正 *****

        # --- 6. Plotting & Saving ---
        logger.info("Plotting constellation diagram...")
        fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
        all_y_eq = np.concatenate((y_eq_no_i, y_eq_with_i))
        valid_y_eq = all_y_eq[np.isfinite(all_y_eq)]
        if valid_y_eq.size > 0:
            max_lim = (
                max(np.abs(valid_y_eq.real).max(), np.abs(valid_y_eq.imag).max(), 1.5)
                * 1.1
            )
        else:
            max_lim = 1.65
        min_lim = -max_lim
        ax[0].scatter(y_eq_no_i.real, y_eq_no_i.imag, s=4, alpha=0.25)
        ax[0].set(
            title="No interference",
            xlabel="I",
            ylabel="Q",
            aspect="equal",
            xlim=[min_lim, max_lim],
            ylim=[min_lim, max_lim],
        )
        ax[0].grid(True)
        ax[1].scatter(y_eq_with_i.real, y_eq_with_i.imag, s=4, alpha=0.25)
        # Use h_int_total_scalar for title check
        ttl = (
            f"With jammer(s) (JNR = {jnr_db:.1f} dB)"
            if np.abs(h_int_total_scalar) > 1e-15
            else "Jammer(s) absent/weak"
        )
        ax[1].set(
            title=ttl,
            xlabel="I",
            ylabel="Q",
            aspect="equal",
            xlim=[min_lim, max_lim],
            ylim=[min_lim, max_lim],
        )
        ax[1].grid(True)
        plt.tight_layout()

        # --- 使用臨時文件保存 ---
        # 確保目標目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 直接保存到最終輸出路徑，避免臨時文件處理帶來的問題
        try:
            logger.info(f"Saving constellation diagram directly to: {output_path}")
            plt.savefig(output_path, bbox_inches="tight", dpi=100)
            plt.close(fig)  # 在保存後關閉圖表

            # 確認文件確實存在且不為空
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(
                    f"Successfully saved image to {output_path}, size: {os.path.getsize(output_path)} bytes"
                )
                return True
            else:
                logger.error(
                    f"Failed to generate image or image is empty: {output_path}"
                )
                return False
        except Exception as save_err:
            logger.error(
                f"Error saving image to {output_path}: {save_err}", exc_info=True
            )
            plt.close(fig)  # 確保關閉圖表
            return False

    except Exception as e:
        logger.error(f"Error in generate_constellation_plot: {e}", exc_info=True)
        plt.close("all")  # 確保關閉所有 matplotlib 圖表
        # 嘗試清理可能的臨時文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(
                    f"Cleaned up temporary file {temp_file_path} due to exception."
                )
            except OSError as remove_err:
                logger.warning(
                    f"Could not remove temporary file {temp_file_path} during exception handling: {remove_err}"
                )
        return False


# --- Refactor generate_empty_scene_image to use the helpers ---
def generate_empty_scene_image(output_path: str):
    """Generates a cropped scene image by rendering the GLB file (using helpers)."""
    logger.info(f"Entering generate_empty_scene_image function, calling helpers...")
    try:
        # 1. Setup scene using helper
        pr_scene = _setup_pyrender_scene_from_glb()  # Helper uses this bg color
        if pr_scene is None:
            return False

        # 2. Render, Crop, and Save using helper
        success = _render_crop_and_save(
            pr_scene,
            output_path,
            bg_color_float=SCENE_BACKGROUND_COLOR_RGB,
            padding_x=5,  # Set horizontal padding to 5
            padding_y=20,  # Keep vertical padding at 20 (or adjust if needed)
        )
        return success

    except ImportError as ie:
        logger.error(f"Import error in generate_empty_scene_image: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error rendering empty scene via helpers: {e}", exc_info=True)
        return False


# --- New Helper Function: Generate scene image with only devices ---
async def generate_scene_with_devices_image(
    output_path: str, session: AsyncSession
) -> bool:
    """Generates a scene image with devices but without RT paths."""
    logger.info("Entering generate_scene_with_devices_image function...")
    try:
        # --- 1. Fetch Device Data ---
        transmitters_data, receivers_data = await get_active_devices_from_db_efficient(
            session
        )
        if not transmitters_data and not receivers_data:
            logger.error("No active devices found in database.")
            return False

        # --- 2. Setup Base Pyrender Scene using Helper ---
        pr_scene = _setup_pyrender_scene_from_glb()  # Helper uses this bg color
        if pr_scene is None:
            return False
        logger.info("Base pyrender scene setup complete.")

        # --- 3. Overlay Devices ---
        logger.info("Overlaying devices onto pyrender scene...")
        # Define cone dimensions and rotation for downward pointing
        CONE_RADIUS = 12.0  # 放大圓點
        CONE_HEIGHT = 36.0  # 放大圓點
        # Rotate cone model (-90 deg around X) to align Trimesh +Z with Pyrender -Y (down)
        down_rotation_matrix = trimesh.transformations.rotation_matrix(
            -np.pi / 2, [1, 0, 0]
        )
        # Additional tilt (e.g., 45 degrees around X-axis)
        tilt_angle_rad = np.radians(45)  # Increased tilt
        tilt_rotation_matrix = trimesh.transformations.rotation_matrix(
            tilt_angle_rad, [1, 0, 0]
        )

        # New Colors with better contrast
        TX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 1.0, 0.0, 1.0]  # Bright Yellow (Keep)
        )
        RX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 0.27, 0.0, 1.0]  # Orange-Red
        )
        INT_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.4, 0.7, 1.0, 1.0]  # 較淺的藍色
        )
        # White material for outline
        WHITE_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 1.0, 1.0, 1.0]  # White
        )

        # Outline disk dimensions
        OUTLINE_RADIUS = CONE_RADIUS + 1.0  # 跟 cone 一起變大
        OUTLINE_HEIGHT = 0.5  # 保持不變

        # Add transmitters to scene
        for tx_data in transmitters_data:
            if tx_data.position_list:
                pos = tx_data.position_list
                mat = (
                    INT_MATERIAL_PYRENDER
                    if tx_data.transmitter_role == DeviceRole.JAMMER
                    else TX_MATERIAL_PYRENDER
                )
                try:
                    # Create colored cone
                    cone = trimesh.creation.cone(radius=CONE_RADIUS, height=CONE_HEIGHT)
                    device_mesh = pyrender.Mesh.from_trimesh(cone, material=mat)
                    # Create white outline disk (cylinder)
                    outline_disk = trimesh.creation.cylinder(
                        radius=OUTLINE_RADIUS, height=OUTLINE_HEIGHT
                    )
                    outline_mesh = pyrender.Mesh.from_trimesh(
                        outline_disk, material=WHITE_MATERIAL_PYRENDER
                    )

                    # Pose for cone (tip at ground, pointing down)
                    translation_matrix = trimesh.transformations.translation_matrix(
                        [pos[0], pos[2], pos[1]]
                    )  # Tip at ground Z=pos[2]
                    # Only apply down rotation, no tilt
                    cone_pose_matrix = translation_matrix @ down_rotation_matrix

                    # Pose for outline disk (centered at cone base, slightly below)
                    outline_center_z = (
                        pos[2] - OUTLINE_HEIGHT / 2 - 0.1
                    )  # Place slightly below cone tip
                    outline_translation_matrix = (
                        trimesh.transformations.translation_matrix(
                            [pos[0], outline_center_z, pos[1]]
                        )
                    )
                    outline_pose_matrix = outline_translation_matrix

                    # Add outline first, then cone
                    pr_scene.add(outline_mesh, pose=outline_pose_matrix)
                    pr_scene.add(device_mesh, pose=cone_pose_matrix)

                    logger.info(
                        f"Added TX Cone '{tx_data.device_model.name}' with outline to scene"
                    )
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding TX Cone '{tx_data.device_model.name}' to scene: {dev_err}",
                        exc_info=True,
                    )

        # Add receivers to scene
        for rx_data in receivers_data:
            if rx_data.position_list:
                pos = rx_data.position_list
                mat = RX_MATERIAL_PYRENDER
                try:
                    # Create colored cone
                    cone = trimesh.creation.cone(radius=CONE_RADIUS, height=CONE_HEIGHT)
                    device_mesh = pyrender.Mesh.from_trimesh(cone, material=mat)
                    # Create white outline disk (cylinder)
                    outline_disk = trimesh.creation.cylinder(
                        radius=OUTLINE_RADIUS, height=OUTLINE_HEIGHT
                    )
                    outline_mesh = pyrender.Mesh.from_trimesh(
                        outline_disk, material=WHITE_MATERIAL_PYRENDER
                    )

                    # Pose for cone (tip at ground, pointing down)
                    translation_matrix = trimesh.transformations.translation_matrix(
                        [pos[0], pos[2], pos[1]]
                    )  # Tip at ground Z=pos[2]
                    # Only apply down rotation, no tilt
                    cone_pose_matrix = translation_matrix @ down_rotation_matrix

                    # Pose for outline disk (centered at cone base, slightly below)
                    outline_center_z = (
                        pos[2] - OUTLINE_HEIGHT / 2 - 0.1
                    )  # Place slightly below cone tip
                    outline_translation_matrix = (
                        trimesh.transformations.translation_matrix(
                            [pos[0], outline_center_z, pos[1]]
                        )
                    )
                    outline_pose_matrix = outline_translation_matrix

                    # Add outline first, then cone
                    pr_scene.add(outline_mesh, pose=outline_pose_matrix)
                    pr_scene.add(device_mesh, pose=cone_pose_matrix)

                    logger.info(
                        f"Added RX Cone '{rx_data.device_model.name}' with outline to scene"
                    )
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding RX Cone '{rx_data.device_model.name}' to scene: {dev_err}",
                        exc_info=True,
                    )

        logger.info("Devices overlay complete.")

        # --- 4. Render, Crop, and Save using Helper ---
        success = _render_crop_and_save(
            pr_scene,
            output_path,
            bg_color_float=SCENE_BACKGROUND_COLOR_RGB,
            padding_x=5,  # Set horizontal padding to 5
            padding_y=20,  # Keep vertical padding at 20
        )
        return success

    except ImportError as ie:
        logger.error(f"Import error: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error in generate_scene_with_devices_image: {e}", exc_info=True)
        return False


# 新增函數: generate_cfr_plot
async def generate_cfr_plot(
    session: AsyncSession, output_path: str = str(CFR_PLOT_IMAGE_PATH)
) -> bool:
    """
    生成 Channel Frequency Response (CFR) 圖，基於 Sionna 的模擬。
    這是從 cfr.py 整合的功能。

    從資料庫中獲取接收器 (receiver)、發射器 (desired) 和干擾器 (jammer) 參數。
    """
    logger.info("Entering generate_cfr_plot function...")

    try:
        logger.info("Fetching active receivers from database...")
        active_receivers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.RECEIVER.value, active_only=True
        )

        if not active_receivers:
            logger.warning(
                "No active receivers found in database. Using default receiver parameters."
            )
            # 使用默認的接收器參數
            rx_name = "rx"
            rx_position = [0, 0, 20]
        else:
            # 使用第一個活動接收器的參數
            receiver = active_receivers[0]
            rx_name = receiver.name
            rx_position = [
                receiver.position_x,
                receiver.position_y,
                receiver.position_z,
            ]
            logger.info(f"Using receiver '{rx_name}' with position {rx_position}")

        # 從資料庫獲取活動的發射器 (desired)
        logger.info("Fetching active desired transmitters from database...")
        active_desired = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.DESIRED.value, active_only=True
        )

        # 從資料庫獲取活動的干擾器 (jammer)
        logger.info("Fetching active jammers from database...")
        active_jammers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.JAMMER.value, active_only=True
        )

        # 構建 TX_LIST (發射器和干擾器列表)
        TX_LIST = []

        # 添加發射器
        if not active_desired:
            logger.warning(
                "No active desired transmitters found in database. Simulation might not be meaningful."
            )
            # 添加默認的發射器參數 # REMOVED
        else:
            # 添加從資料庫獲取的發射器
            for i, tx in enumerate(active_desired):
                tx_name = tx.name
                tx_position = [tx.position_x, tx.position_y, tx.position_z]
                tx_orientation = [tx.orientation_x, tx.orientation_y, tx.orientation_z]
                tx_power = tx.power_dbm

                TX_LIST.append(
                    (tx_name, tx_position, tx_orientation, "desired", tx_power)
                )
                logger.info(
                    f"Added desired transmitter: {tx_name}, position: {tx_position}, orientation: {tx_orientation}, power: {tx_power} dBm"
                )

        # 添加干擾器
        if not active_jammers:
            logger.warning(
                "No active jammers found in database. Interference simulation will not run."
            )
            # 添加默認的干擾器參數 # REMOVED
        else:
            # 添加從資料庫獲取的干擾器
            for i, jammer in enumerate(active_jammers):
                jammer_name = jammer.name
                jammer_position = [
                    jammer.position_x,
                    jammer.position_y,
                    jammer.position_z,
                ]
                jammer_orientation = [
                    jammer.orientation_x,
                    jammer.orientation_y,
                    jammer.orientation_z,
                ]
                jammer_power = jammer.power_dbm

                TX_LIST.append(
                    (
                        jammer_name,
                        jammer_position,
                        jammer_orientation,
                        "jammer",
                        jammer_power,
                    )
                )
                logger.info(
                    f"Added jammer: {jammer_name}, position: {jammer_position}, orientation: {jammer_orientation}, power: {jammer_power} dBm"
                )

        # 檢查是否有足夠的發射器和干擾器
        if not TX_LIST:
            logger.error(
                "No transmitters or jammers available for simulation. Cannot proceed."
            )
            return False

        # 參數設置
        SCENE_NAME = str(NYCU_XML_PATH)
        logger.info(f"Loading scene from: {SCENE_NAME}")

        TX_ARRAY_CONFIG = {
            "num_rows": 1,
            "num_cols": 1,
            "vertical_spacing": 0.5,
            "horizontal_spacing": 0.5,
            "pattern": "iso",
            "polarization": "V",
        }
        RX_ARRAY_CONFIG = TX_ARRAY_CONFIG

        # 使用從資料庫獲取的接收器參數
        RX_CONFIG = (rx_name, rx_position)

        PATHSOLVER_ARGS = {
            "max_depth": 10,
            "los": True,
            "specular_reflection": True,
            "diffuse_reflection": False,
            "refraction": False,
            "synthetic_array": False,
            "seed": 41,
        }

        N_SYMBOLS = 1
        N_SUBCARRIERS = 1024
        SUBCARRIER_SPACING = 30e3
        EBN0_dB = 20.0

        # 場景設置
        logger.info("Setting up scene")
        scene = load_scene(SCENE_NAME)
        scene.tx_array = PlanarArray(**TX_ARRAY_CONFIG)
        scene.rx_array = PlanarArray(**RX_ARRAY_CONFIG)

        # 清除現有的發射器和接收器
        for name in list(scene.transmitters.keys()) + list(scene.receivers.keys()):
            scene.remove(name)

        # 添加發射器
        logger.info("Adding transmitters")

        def add_tx(scene, name, pos, ori, role, power_dbm):
            tx = SionnaTransmitter(
                name=name, position=pos, orientation=ori, power_dbm=power_dbm
            )
            tx.role = role
            scene.add(tx)
            return tx

        for name, pos, ori, role, p_dbm in TX_LIST:
            add_tx(scene, name, pos, ori, role, p_dbm)

        # 添加接收器
        logger.info(f"Adding receiver '{rx_name}' at position {rx_position}")
        rx_name, rx_pos = RX_CONFIG
        scene.add(SionnaReceiver(name=rx_name, position=rx_pos))

        # 分組發射器
        tx_names = list(scene.transmitters.keys())
        all_txs = [scene.get(n) for n in tx_names]
        idx_des = [i for i, tx in enumerate(all_txs) if tx.role == "desired"]
        idx_jam = [i for i, tx in enumerate(all_txs) if tx.role == "jammer"]

        # 檢查是否有發射器和干擾器
        if not idx_des:
            logger.warning(
                "No desired transmitters available in scene. CFR calculation may not be accurate."
            )
        if not idx_jam:
            logger.warning(
                "No jammers available in scene. Interference will not be present in plot."
            )

        # 計算 CFR
        logger.info("Computing CFR")
        freqs = subcarrier_frequencies(N_SUBCARRIERS, SUBCARRIER_SPACING)
        for name in tx_names:
            scene.get(name).velocity = [30, 0, 0]
        paths = PathSolver()(scene, **PATHSOLVER_ARGS)

        def dbm2w(dbm):
            return 10 ** (dbm / 10) / 1000

        tx_powers = [dbm2w(scene.get(n).power_dbm) for n in tx_names]
        ofdm_symbol_duration = 1 / SUBCARRIER_SPACING
        H_unit = paths.cfr(
            frequencies=freqs,
            sampling_frequency=1 / ofdm_symbol_duration,
            num_time_steps=N_SUBCARRIERS,
            normalize_delays=True,
            normalize=False,
            out_type="numpy",
        ).squeeze()  # shape: (num_tx, T, F)

        H_all = np.sqrt(np.array(tx_powers)[:, None, None]) * H_unit
        H = H_unit[:, 0, :]  # 取第一個時間步

        # 安全處理：確保有所需的發射器
        h_main = np.zeros(N_SUBCARRIERS, dtype=complex)
        if idx_des:
            h_main = sum(np.sqrt(tx_powers[i]) * H[i] for i in idx_des)

        h_intf = np.zeros(N_SUBCARRIERS, dtype=complex)
        if idx_jam:
            h_intf = sum(np.sqrt(tx_powers[i]) * H[i] for i in idx_jam)

        # 生成 QPSK+OFDM 符號
        logger.info("Generating QPSK+OFDM symbols")
        bits = np.random.randint(0, 2, (N_SYMBOLS, N_SUBCARRIERS, 2))
        bits_jam = np.random.randint(0, 2, (N_SYMBOLS, N_SUBCARRIERS, 2))
        X_sig = (1 - 2 * bits[..., 0] + 1j * (1 - 2 * bits[..., 1])) / np.sqrt(2)
        X_jam = (1 - 2 * bits_jam[..., 0] + 1j * (1 - 2 * bits_jam[..., 1])) / np.sqrt(
            2
        )

        Y_sig = X_sig * h_main[None, :]
        Y_int = X_jam * h_intf[None, :]
        p_sig = np.mean(np.abs(Y_sig) ** 2)
        N0 = p_sig / (10 ** (EBN0_dB / 10) * 2) if p_sig > 0 else 1e-10
        noise = np.sqrt(N0 / 2) * (
            np.random.randn(*Y_sig.shape) + 1j * np.random.randn(*Y_sig.shape)
        )
        Y_tot = Y_sig + Y_int + noise

        # 安全處理：避免除以零
        non_zero_mask = np.abs(h_main) > 1e-10
        y_eq_no_i = np.zeros_like(Y_sig)
        y_eq_with_i = np.zeros_like(Y_tot)

        if np.any(non_zero_mask):
            y_eq_no_i[:, non_zero_mask] = (Y_sig + noise)[:, non_zero_mask] / h_main[
                None, non_zero_mask
            ]
            y_eq_with_i[:, non_zero_mask] = (
                Y_tot[:, non_zero_mask] / h_main[None, non_zero_mask]
            )

        # 繪製星座圖和 CFR，然後保存到文件
        logger.info("Plotting constellation and CFR")
        fig, ax = plt.subplots(1, 3, figsize=(15, 4))
        ax[0].scatter(y_eq_no_i.real, y_eq_no_i.imag, s=4, alpha=0.25)
        ax[0].set(title="No interference", xlabel="Real", ylabel="Imag")
        ax[0].grid(True)

        ax[1].scatter(y_eq_with_i.real, y_eq_with_i.imag, s=4, alpha=0.25)
        ax[1].set(title="With interferer", xlabel="Real", ylabel="Imag")
        ax[1].grid(True)

        ax[2].plot(np.abs(h_main), label="|H_main|")
        ax[2].plot(np.abs(h_intf), label="|H_intf|")
        ax[2].set(title="Constellation & CFR", xlabel="Subcarrier Index")
        ax[2].legend()
        ax[2].grid(True)

        plt.tight_layout()

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存圖片
        logger.info(f"Saving plot to {output_path}")
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        # 檢查文件是否成功生成
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully saved CFR plot to {output_path}")
            return True
        else:
            logger.error(f"Failed to save plot to {output_path} or file is empty")
            return False

    except Exception as e:
        logger.exception(f"Error in generate_cfr_plot: {e}")
        # 確保關閉所有打開的圖表
        plt.close("all")
        return False


# 新增 SINR Map 生成函數
async def generate_sinr_map(
    session: AsyncSession,
    output_path: str,
    sinr_vmin: float = -40,
    sinr_vmax: float = 0,
    cell_size: float = 1.0,
    samples_per_tx: int = 10**7,
) -> bool:
    """
    生成 SINR (Signal-to-Interference-plus-Noise Ratio) 地圖

    從數據庫獲取發射器和接收器設置，計算並生成 SINR 地圖
    """
    logger.info("開始生成 SINR 地圖...")

    try:
        # GPU 設置
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            tf.config.experimental.set_memory_growth(gpus[0], True)
            logger.info("GPU 記憶體成長已啟用")
        else:
            logger.info("未找到 GPU，使用 CPU")

        # 從數據庫獲取活動的發射器 (desired)
        logger.info("從數據庫獲取活動的發射器...")
        active_desired = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.DESIRED.value, active_only=True
        )

        # 從數據庫獲取活動的干擾器 (jammer)
        logger.info("從數據庫獲取活動的干擾器...")
        active_jammers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.JAMMER.value, active_only=True
        )

        # 從數據庫獲取活動的接收器
        logger.info("從數據庫獲取活動的接收器...")
        active_receivers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.RECEIVER.value, active_only=True
        )

        # 檢查是否有足夠的設備
        if not active_desired and not active_jammers:
            logger.error("沒有活動的發射器或干擾器，無法生成 SINR 地圖")
            return False

        if not active_receivers:
            logger.warning("沒有活動的接收器，將使用預設接收器位置")
            rx_config = ("rx", [-30, 50, 20])
        else:
            # 使用第一個活動接收器
            receiver = active_receivers[0]
            rx_config = (
                receiver.name,
                [receiver.position_x, receiver.position_y, receiver.position_z],
            )

        # 構建 TX_LIST
        tx_list = []

        # 添加發射器
        for tx in active_desired:
            tx_name = tx.name
            tx_position = [tx.position_x, tx.position_y, tx.position_z]
            tx_orientation = [tx.orientation_x, tx.orientation_y, tx.orientation_z]
            tx_power = tx.power_dbm

            tx_list.append((tx_name, tx_position, tx_orientation, "desired", tx_power))
            logger.info(
                f"添加發射器: {tx_name}, 位置: {tx_position}, 方向: {tx_orientation}, 功率: {tx_power} dBm"
            )

        # 添加干擾器
        for jammer in active_jammers:
            jammer_name = jammer.name
            jammer_position = [jammer.position_x, jammer.position_y, jammer.position_z]
            jammer_orientation = [
                jammer.orientation_x,
                jammer.orientation_y,
                jammer.orientation_z,
            ]
            jammer_power = jammer.power_dbm

            tx_list.append(
                (
                    jammer_name,
                    jammer_position,
                    jammer_orientation,
                    "jammer",
                    jammer_power,
                )
            )
            logger.info(
                f"添加干擾器: {jammer_name}, 位置: {jammer_position}, 方向: {jammer_orientation}, 功率: {jammer_power} dBm"
            )

        # 如果沒有足夠的發射器，返回錯誤
        if not tx_list:
            logger.error("沒有可用的發射器或干擾器，無法生成 SINR 地圖")
            return False

        # 參數設置
        scene_name = str(NYCU_XML_PATH)
        logger.info(f"從 {scene_name} 加載場景")

        tx_array_config = {
            "num_rows": 1,
            "num_cols": 1,
            "vertical_spacing": 0.5,
            "horizontal_spacing": 0.5,
            "pattern": "iso",
            "polarization": "V",
        }
        rx_array_config = tx_array_config

        rmsolver_args = {
            "max_depth": 10,
            "cell_size": (cell_size, cell_size),
            "samples_per_tx": samples_per_tx,
        }

        # 場景設置
        logger.info("設置場景")
        scene = load_scene(scene_name)
        scene.tx_array = PlanarArray(**tx_array_config)
        scene.rx_array = PlanarArray(**rx_array_config)

        # 清除現有的發射器和接收器
        for name in list(scene.transmitters.keys()) + list(scene.receivers.keys()):
            scene.remove(name)

        # 添加發射器
        logger.info("添加發射器")

        def add_tx(scene, name, pos, ori, role, power_dbm):
            tx = SionnaTransmitter(
                name=name, position=pos, orientation=ori, power_dbm=power_dbm
            )
            tx.role = role
            scene.add(tx)
            return tx

        for name, pos, ori, role, p_dbm in tx_list:
            add_tx(scene, name, pos, ori, role, p_dbm)

        # 添加接收器
        rx_name, rx_pos = rx_config
        logger.info(f"添加接收器 '{rx_name}' 在位置 {rx_pos}")
        scene.add(SionnaReceiver(name=rx_name, position=rx_pos))

        # 按角色分組發射器
        all_txs = [scene.get(n) for n in scene.transmitters]
        idx_des = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "desired"
        ]
        idx_jam = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "jammer"
        ]

        if not idx_des and not idx_jam:
            logger.error("場景中沒有有效的發射器或干擾器")
            return False

        # 計算無線電地圖
        logger.info("計算無線電地圖")
        rm_solver = RadioMapSolver()
        rm = rm_solver(scene, **rmsolver_args)

        # 計算並繪製 SINR 地圖
        logger.info("計算 SINR 地圖")
        cc = rm.cell_centers.numpy()
        x_unique = cc[0, :, 0]
        y_unique = cc[:, 0, 1]
        rss_list = [rm.rss[i].numpy() for i in range(len(all_txs))]

        # 計算 SINR
        N0_map = 1e-12  # 噪聲功率

        # 檢查是否有目標發射器和干擾器
        if idx_des:
            rss_des = sum(rss_list[i] for i in idx_des)
        else:
            logger.warning("沒有目標發射器，將假設沒有信號")
            rss_des = (
                np.zeros_like(rss_list[0])
                if rss_list
                else np.zeros((len(y_unique), len(x_unique)))
            )

        if idx_jam:
            rss_jam = sum(rss_list[i] for i in idx_jam)
        else:
            logger.warning("沒有干擾器，將假設沒有干擾")
            rss_jam = (
                np.zeros_like(rss_list[0])
                if rss_list
                else np.zeros((len(y_unique), len(x_unique)))
            )

        # 計算 SINR (dB)，確保公式與原始 sinr.py 一致
        sinr_db = 10 * np.log10(
            np.clip(rss_des / (rss_des + rss_jam + N0_map), 1e-12, None)
        )

        # 繪製地圖
        logger.info("繪製 SINR 地圖")
        fig, ax = plt.subplots(figsize=(7, 5))
        X, Y = np.meshgrid(x_unique, y_unique)
        pcm = ax.pcolormesh(
            X, Y, sinr_db, shading="nearest", vmin=sinr_vmin + 10, vmax=sinr_vmax
        )
        fig.colorbar(pcm, ax=ax, label="SINR (dB)")

        # 繪製發射器和接收器
        ax.scatter(
            [t.position[0] for t in all_txs if getattr(t, "role", None) == "desired"],
            [t.position[1] for t in all_txs if getattr(t, "role", None) == "desired"],
            c="red",
            marker="^",
            s=100,
            label="Tx",
        )
        ax.scatter(
            [t.position[0] for t in all_txs if getattr(t, "role", None) == "jammer"],
            [t.position[1] for t in all_txs if getattr(t, "role", None) == "jammer"],
            c="red",
            marker="x",
            s=100,
            label="Jam",
        )

        # 獲取接收器
        rx_object = scene.get(rx_name)
        if rx_object:
            ax.scatter(
                rx_object.position[0],
                rx_object.position[1],
                c="green",
                marker="o",
                s=50,
                label="Rx",
            )

        ax.legend()
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title("SINR Map")
        ax.invert_yaxis()
        plt.tight_layout()

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存圖片
        logger.info(f"保存 SINR 地圖到 {output_path}")
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        # 檢查文件是否生成成功
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"成功保存 SINR 地圖到 {output_path}")
            return True
        else:
            logger.error(f"保存 SINR 地圖到 {output_path} 失敗或文件為空")
            return False

    except Exception as e:
        logger.exception(f"Error in generate_sinr_map: {e}")
        # 確保關閉所有打開的圖表
        plt.close("all")
        return False


# 新增 Doppler 圖生成函數
async def generate_doppler_plots(
    session: AsyncSession,
    unscaled_output_path: str = str(UNSCALED_DOPPLER_IMAGE_PATH),
    power_scaled_output_path: str = str(POWER_SCALED_DOPPLER_IMAGE_PATH),
) -> bool:
    """
    生成延遲多普勒圖，基於 doppler.py 中的功能

    生成兩個圖像：
    1. 未縮放的延遲多普勒圖
    2. 功率縮放的延遲多普勒圖

    從數據庫中獲取發射器和干擾器參數。
    """
    logger.info("開始生成延遲多普勒圖...")

    try:
        # GPU 設置
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            tf.config.experimental.set_memory_growth(gpus[0], True)
            logger.info("GPU 記憶體成長已啟用")
        else:
            logger.info("未找到 GPU，使用 CPU")

        # 從資料庫獲取活動的發射器 (desired)
        logger.info("從數據庫獲取活動的發射器...")
        active_desired = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.DESIRED.value, active_only=True
        )

        # 從資料庫獲取活動的干擾器 (jammer)
        logger.info("從數據庫獲取活動的干擾器...")
        active_jammers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.JAMMER.value, active_only=True
        )

        # 從資料庫獲取活動的接收器
        logger.info("從數據庫獲取活動的接收器...")
        active_receivers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.RECEIVER.value, active_only=True
        )

        # 構建 TX_LIST
        tx_list = []

        # 添加發射器
        if not active_desired:
            logger.warning("沒有活動的發射器，將無法生成有效的延遲多普勒圖")
            # 移除默認發射器
            # tx_list.extend([
            #     ("tx0", [-100, -100, 20], [np.pi * 5 / 6, 0, 0], "desired", 30),
            #     ("tx1", [-100, 50, 20], [np.pi / 6, 0, 0], "desired", 30),
            #     ("tx2", [100, -100, 20], [-np.pi / 2, 0, 0], "desired", 30),
            # ])
        else:
            # 添加從資料庫獲取的發射器
            for tx in active_desired:
                tx_name = tx.name
                tx_position = [tx.position_x, tx.position_y, tx.position_z]
                tx_orientation = [tx.orientation_x, tx.orientation_y, tx.orientation_z]
                tx_power = tx.power_dbm

                tx_list.append(
                    (tx_name, tx_position, tx_orientation, "desired", tx_power)
                )
                logger.info(
                    f"添加發射器: {tx_name}, 位置: {tx_position}, 方向: {tx_orientation}, 功率: {tx_power} dBm"
                )

        # 添加干擾器
        if not active_jammers:
            logger.warning("沒有活動的干擾器，圖中將不包含干擾信息")
        else:
            # 添加從資料庫獲取的干擾器
            for jammer in active_jammers:
                jammer_name = jammer.name
                jammer_position = [
                    jammer.position_x,
                    jammer.position_y,
                    jammer.position_z,
                ]
                jammer_orientation = [
                    jammer.orientation_x,
                    jammer.orientation_y,
                    jammer.orientation_z,
                ]
                jammer_power = jammer.power_dbm

                tx_list.append(
                    (
                        jammer_name,
                        jammer_position,
                        jammer_orientation,
                        "jammer",
                        jammer_power,
                    )
                )
                logger.info(
                    f"添加干擾器: {jammer_name}, 位置: {jammer_position}, 方向: {jammer_orientation}, 功率: {jammer_power} dBm"
                )

        # 檢查是否有任何發射器（包括干擾器）被添加
        if not tx_list:
            logger.error("數據庫中沒有活動的發射器或干擾器，無法生成延遲多普勒圖")
            return False

        # 接收器設置
        if not active_receivers:
            logger.warning("沒有活動的接收器，使用默認值")
            rx_config = ("rx", [0, 0, 20])
        else:
            # 使用第一個活動接收器
            receiver = active_receivers[0]
            rx_config = (
                receiver.name,
                [receiver.position_x, receiver.position_y, receiver.position_z],
            )
            logger.info(f"使用接收器 '{rx_config[0]}' 在位置 {rx_config[1]}")

        # 參數設置
        scene_name = str(NYCU_XML_PATH)
        logger.info(f"從 {scene_name} 加載場景")

        tx_array_config = {
            "num_rows": 1,
            "num_cols": 1,
            "vertical_spacing": 0.5,
            "horizontal_spacing": 0.5,
            "pattern": "iso",
            "polarization": "V",
        }
        rx_array_config = tx_array_config

        pathsolver_args = {
            "max_depth": 5,
            "max_num_paths_per_src": 1000,
            "los": True,
            "specular_reflection": True,
            "diffuse_reflection": False,
            "refraction": False,
            "synthetic_array": False,
            "seed": 41,
        }

        # OFDM 參數
        n_subcarriers = 512
        subcarrier_spacing = 30e3  # Hz
        num_ofdm_symbols = 512

        # 場景設置
        logger.info("設置場景")
        scene = load_scene(scene_name)
        scene.tx_array = PlanarArray(**tx_array_config)
        scene.rx_array = PlanarArray(**rx_array_config)

        # 清除現有的發射器和接收器
        for name in list(scene.transmitters.keys()) + list(scene.receivers.keys()):
            scene.remove(name)

        # 添加發射器
        logger.info("添加發射器和干擾器")

        def add_tx(scene, name, pos, ori, role, power_dbm):
            tx = SionnaTransmitter(
                name=name, position=pos, orientation=ori, power_dbm=power_dbm
            )
            tx.role = role
            scene.add(tx)
            return tx

        for name, pos, ori, role, p_dbm in tx_list:
            add_tx(scene, name, pos, ori, role, p_dbm)

        # 添加接收器
        rx_name, rx_pos = rx_config
        logger.info(f"添加接收器 '{rx_name}' 在位置 {rx_pos}")
        scene.add(SionnaReceiver(name=rx_name, position=rx_pos))

        # 為所有發射器分配速度
        for name, tx in scene.transmitters.items():
            tx.velocity = [30, 0, 0]

        # 按角色分組發射器
        tx_names = list(scene.transmitters.keys())
        all_txs = [scene.get(n) for n in tx_names]
        idx_des = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "desired"
        ]
        idx_jam = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "jammer"
        ]

        # 計算 CFR
        logger.info("計算 CFR")
        solver = PathSolver()
        try:
            paths = solver(scene, **pathsolver_args)
        except RuntimeError as e:
            logger.error(f"PathSolver 错误: {e}")
            logger.error(
                "嘗試減少 max_depth, max_num_paths_per_src, 或使用更簡單的場景。"
            )
            return False

        freqs = subcarrier_frequencies(n_subcarriers, subcarrier_spacing)
        ofdm_symbol_duration = 1 / subcarrier_spacing

        H_unit = paths.cfr(
            frequencies=freqs,
            sampling_frequency=1 / ofdm_symbol_duration,
            num_time_steps=num_ofdm_symbols,
            normalize_delays=True,
            normalize=False,
            out_type="numpy",
        )

        logger.info(f"H_unit shape before squeeze: {H_unit.shape}")
        H_unit = H_unit.squeeze()  # (num_tx, T, F)
        logger.info(f"H_unit shape after squeeze: {H_unit.shape}")

        # 計算線性功率
        tx_p_lin = (
            10 ** (np.array([tx.power_dbm for tx in all_txs]) / 10) / 1e3
        )  # (num_tx,)
        sqrtP = np.sqrt(tx_p_lin).reshape(-1, 1, 1)  # (num_tx, 1, 1)
        H_pw = H_unit * sqrtP  # (num_tx, T, F) * (num_tx, 1, 1)
        logger.info(f"H_pw shape: {H_pw.shape}")

        # 按角色分組求和（功率縮放通道）
        if idx_des:
            H_des = H_pw[idx_des].sum(axis=0)  # (T, F)
        else:
            H_des = np.zeros((num_ofdm_symbols, n_subcarriers), dtype=complex)

        if idx_jam:
            H_jam = H_pw[idx_jam].sum(axis=0)  # (T, F)
        else:
            H_jam = np.zeros((num_ofdm_symbols, n_subcarriers), dtype=complex)

        H_all = H_des + H_jam
        logger.info(f"H_des shape (power-scaled): {H_des.shape}")

        # 按角色分組求和（未縮放通道）
        if idx_des:
            H_des_unscaled = H_unit[idx_des].sum(axis=0)  # (T, F)
        else:
            H_des_unscaled = np.zeros((num_ofdm_symbols, n_subcarriers), dtype=complex)

        if idx_jam:
            H_jam_unscaled = H_unit[idx_jam].sum(axis=0)  # (T, F)
        else:
            H_jam_unscaled = np.zeros((num_ofdm_symbols, n_subcarriers), dtype=complex)

        H_all_unscaled = H_des_unscaled + H_jam_unscaled
        logger.info(f"H_des_unscaled shape: {H_des_unscaled.shape}")

        # 定義延遲多普勒轉換函數
        def to_delay_doppler(H_tf):
            logger.info(f"Input H_tf shape: {H_tf.shape}")
            Hf = np.fft.fftshift(H_tf, axes=-1)  # 頻率軸移位
            h_delay = np.fft.ifft(Hf, axis=-1, norm="ortho")  # 頻率到延遲
            h_dd = np.fft.fft(h_delay, axis=-2, norm="ortho")  # 時間到多普勒
            h_dd = np.fft.fftshift(h_dd, axes=-2)  # 多普勒軸移位
            logger.info(f"Output h_dd shape: {h_dd.shape}")
            return h_dd

        # 計算未縮放通道的延遲多普勒
        logger.info("計算未縮放通道的延遲多普勒")
        Hdd_des_unscaled = to_delay_doppler(H_des_unscaled)
        Hdd_jam_unscaled = to_delay_doppler(H_jam_unscaled)
        Hdd_all_unscaled = to_delay_doppler(H_all_unscaled)
        logger.info(f"Hdd_des_unscaled shape: {Hdd_des_unscaled.shape}")

        # 計算功率縮放通道的延遲多普勒
        logger.info("計算功率縮放通道的延遲多普勒")
        Hdd_des = to_delay_doppler(H_des)
        Hdd_jam = to_delay_doppler(H_jam)
        Hdd_all = to_delay_doppler(H_all)
        logger.info(f"Hdd_des shape (power-scaled): {Hdd_des.shape}")

        # 定義繪圖範圍
        T, F = Hdd_des.shape  # 應該是 (512, 512)
        offset = 20
        d_start, d_end = 0, offset * 2  # 延遲：前 40 個樣本
        t_mid = T // 2  # 多普勒：中心在 0 Hz
        t_start, t_end = t_mid - offset, t_mid + offset  # 多普勒：±20 個樣本

        # 坐標軸
        delay_bins = np.arange(F) * ((1 / subcarrier_spacing) / F) * 1e9  # ns
        doppler_bins = np.fft.fftshift(
            np.fft.fftfreq(T, d=1 / subcarrier_spacing)
        )  # Hz
        X, Y = np.meshgrid(delay_bins[d_start:d_end], doppler_bins[t_start:t_end])

        # --- 第一個圖：未縮放通道 ---
        logger.info("繪製未縮放通道的延遲多普勒圖")
        fig1 = plt.figure(figsize=(18, 5))
        fig1.suptitle("Delay-Doppler Plots (Unscaled Channels)")

        ax1 = fig1.add_subplot(131, projection="3d")
        Z_des_unscaled = np.abs(Hdd_des_unscaled[t_start:t_end, d_start:d_end])
        ax1.plot_surface(X, Y, Z_des_unscaled, cmap="viridis", edgecolor="none")
        ax1.set(
            title="Delay–Doppler |Desired|", xlabel="Delay (ns)", ylabel="Doppler (Hz)"
        )

        ax2 = fig1.add_subplot(132, projection="3d")
        Z_jam_unscaled = np.abs(Hdd_jam_unscaled[t_start:t_end, d_start:d_end])
        ax2.plot_surface(X, Y, Z_jam_unscaled, cmap="viridis", edgecolor="none")
        ax2.set(
            title="Delay–Doppler |Jammer|", xlabel="Delay (ns)", ylabel="Doppler (Hz)"
        )

        ax3 = fig1.add_subplot(133, projection="3d")
        Z_all_unscaled = np.abs(Hdd_all_unscaled[t_start:t_end, d_start:d_end])
        ax3.plot_surface(X, Y, Z_all_unscaled, cmap="viridis", edgecolor="none")
        ax3.set(title="Delay–Doppler |All|", xlabel="Delay (ns)", ylabel="Doppler (Hz)")

        plt.tight_layout()

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(unscaled_output_path), exist_ok=True)

        logger.info(f"保存未縮放圖到 {unscaled_output_path}")
        plt.savefig(unscaled_output_path, dpi=300, bbox_inches="tight")
        plt.close(fig1)  # 關閉圖表以釋放記憶體

        # --- 第二個圖：功率縮放通道 ---
        logger.info("繪製功率縮放通道的延遲多普勒圖")
        fig2 = plt.figure(figsize=(18, 5))
        fig2.suptitle("Delay-Doppler Plots (Power-Scaled Channels)")

        ax1 = fig2.add_subplot(131, projection="3d")
        Z_des = np.abs(Hdd_des[t_start:t_end, d_start:d_end])
        ax1.plot_surface(X, Y, Z_des, cmap="viridis", edgecolor="none")
        ax1.set(
            title="Delay–Doppler |Desired|", xlabel="Delay (ns)", ylabel="Doppler (Hz)"
        )

        ax2 = fig2.add_subplot(132, projection="3d")
        Z_jam = np.abs(Hdd_jam[t_start:t_end, d_start:d_end])
        ax2.plot_surface(X, Y, Z_jam, cmap="viridis", edgecolor="none")
        ax2.set(
            title="Delay–Doppler |Jammer|", xlabel="Delay (ns)", ylabel="Doppler (Hz)"
        )

        ax3 = fig2.add_subplot(133, projection="3d")
        Z_all = np.abs(Hdd_all[t_start:t_end, d_start:d_end])
        ax3.plot_surface(X, Y, Z_all, cmap="viridis", edgecolor="none")
        ax3.set(title="Delay–Doppler |All|", xlabel="Delay (ns)", ylabel="Doppler (Hz)")

        plt.tight_layout()

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(power_scaled_output_path), exist_ok=True)

        logger.info(f"保存功率縮放圖到 {power_scaled_output_path}")
        plt.savefig(power_scaled_output_path, dpi=300, bbox_inches="tight")
        plt.close(fig2)  # 關閉圖表以釋放記憶體

        # 檢查文件是否生成成功
        unscaled_success = (
            os.path.exists(unscaled_output_path)
            and os.path.getsize(unscaled_output_path) > 0
        )
        power_scaled_success = (
            os.path.exists(power_scaled_output_path)
            and os.path.getsize(power_scaled_output_path) > 0
        )

        if unscaled_success and power_scaled_success:
            logger.info("成功生成兩張延遲多普勒圖")
            return True
        else:
            if not unscaled_success:
                logger.error(f"未縮放圖片生成失敗: {unscaled_output_path}")
            if not power_scaled_success:
                logger.error(f"功率縮放圖片生成失敗: {power_scaled_output_path}")
            return False

    except Exception as e:
        logger.exception(f"生成延遲多普勒圖時發生錯誤: {e}")
        # 確保關閉所有打開的圖表
        plt.close("all")
        return False


# 新增函數: 整合 tf.py 的通道響應圖功能
async def generate_channel_response_plots(
    session: AsyncSession, output_path: str
) -> bool:
    """
    生成通道響應圖 (H_des, H_jam, H_all)，基於 tf.py 中的功能。
    從資料庫獲取接收器、發射器和干擾器參數。
    """
    logger.info("開始生成通道響應圖...")

    try:
        # 從資料庫獲取活動的發射器 (desired)
        logger.info("從數據庫獲取活動的發射器...")
        active_desired = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.DESIRED.value, active_only=True
        )

        # 從資料庫獲取活動的干擾器 (jammer)
        logger.info("從數據庫獲取活動的干擾器...")
        active_jammers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.JAMMER.value, active_only=True
        )

        # 從資料庫獲取活動的接收器
        logger.info("從數據庫獲取活動的接收器...")
        active_receivers = await crud_device.get_devices_by_role(
            db=session, role=DeviceRole.RECEIVER.value, active_only=True
        )

        # 檢查是否有足夠的設備進行模擬
        if not active_desired:
            logger.error("沒有活動的發射器，無法生成通道響應圖")
            return False

        if not active_receivers:
            logger.error("沒有活動的接收器，無法生成通道響應圖")
            return False

        # 構建 TX_LIST
        tx_list = []

        # 添加從資料庫獲取的發射器
        for tx in active_desired:
            tx_name = tx.name
            tx_position = [tx.position_x, tx.position_y, tx.position_z]
            tx_orientation = [tx.orientation_x, tx.orientation_y, tx.orientation_z]
            tx_power = tx.power_dbm

            tx_list.append((tx_name, tx_position, tx_orientation, "desired", tx_power))
            logger.info(
                f"添加發射器: {tx_name}, 位置: {tx_position}, 方向: {tx_orientation}, 功率: {tx_power} dBm"
            )

        # 添加從資料庫獲取的干擾器 (如果有)
        for jammer in active_jammers:
            jammer_name = jammer.name
            jammer_position = [
                jammer.position_x,
                jammer.position_y,
                jammer.position_z,
            ]
            jammer_orientation = [
                jammer.orientation_x,
                jammer.orientation_y,
                jammer.orientation_z,
            ]
            jammer_power = jammer.power_dbm

            tx_list.append(
                (
                    jammer_name,
                    jammer_position,
                    jammer_orientation,
                    "jammer",
                    jammer_power,
                )
            )
            logger.info(
                f"添加干擾器: {jammer_name}, 位置: {jammer_position}, 方向: {jammer_orientation}, 功率: {jammer_power} dBm"
            )

        # 接收器設置
        receiver = active_receivers[0]  # 已確認有接收器
        rx_config = (
            receiver.name,
            [receiver.position_x, receiver.position_y, receiver.position_z],
        )
        logger.info(f"使用接收器 '{rx_config[0]}' 在位置 {rx_config[1]}")

        # 從 config.py 取得場景路徑
        scene_name = str(NYCU_XML_PATH)
        logger.info(f"從 {scene_name} 加載場景")

        # 參數設置 (從 tf.py 移植)
        tx_array_config = {
            "num_rows": 1,
            "num_cols": 1,
            "vertical_spacing": 0.5,
            "horizontal_spacing": 0.5,
            "pattern": "iso",
            "polarization": "V",
        }
        rx_array_config = tx_array_config

        pathsolver_args = {
            "max_depth": 10,
            "los": True,
            "specular_reflection": True,
            "diffuse_reflection": False,
            "refraction": False,
            "synthetic_array": False,
            "seed": 41,
        }

        n_subcarriers = 1024
        subcarrier_spacing = 30e3
        num_ofdm_symbols = 1024

        # 場景設置
        logger.info("設置場景")
        scene = load_scene(scene_name)
        scene.tx_array = PlanarArray(**tx_array_config)
        scene.rx_array = PlanarArray(**rx_array_config)

        # 清除現有的發射器和接收器
        for name in list(scene.transmitters.keys()) + list(scene.receivers.keys()):
            scene.remove(name)

        # 添加發射器
        logger.info("添加發射器和干擾器")

        def add_tx(scene, name, pos, ori, role, power_dbm):
            tx = SionnaTransmitter(
                name=name, position=pos, orientation=ori, power_dbm=power_dbm
            )
            tx.role = role
            scene.add(tx)
            return tx

        for name, pos, ori, role, p_dbm in tx_list:
            add_tx(scene, name, pos, ori, role, p_dbm)

        # 添加接收器
        rx_name, rx_pos = rx_config
        logger.info(f"添加接收器 '{rx_name}' 在位置 {rx_pos}")
        scene.add(SionnaReceiver(name=rx_name, position=rx_pos))

        # 為所有發射器分配速度
        for name, tx in scene.transmitters.items():
            tx.velocity = [30, 0, 0]

        # 按角色分組發射器
        tx_names = list(scene.transmitters.keys())
        all_txs = [scene.get(n) for n in tx_names]
        idx_des = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "desired"
        ]
        idx_jam = [
            i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "jammer"
        ]

        # 計算路徑
        logger.info("計算路徑")
        solver = PathSolver()
        try:
            paths = solver(scene, **pathsolver_args)
        except RuntimeError as e:
            logger.error(f"PathSolver 錯誤: {e}")
            logger.error(
                "嘗試減少 max_depth, max_num_paths_per_src, 或使用更簡單的場景。"
            )
            return False

        # 計算 CFR
        logger.info("計算 CFR")
        freqs = subcarrier_frequencies(n_subcarriers, subcarrier_spacing)
        ofdm_symbol_duration = 1 / subcarrier_spacing

        H_unit = paths.cfr(
            frequencies=freqs,
            sampling_frequency=1 / ofdm_symbol_duration,
            num_time_steps=num_ofdm_symbols,
            normalize_delays=True,
            normalize=False,
            out_type="numpy",
        ).squeeze()  # shape: (num_tx, T, F)

        # 計算 H_all, H_des, H_jam
        logger.info("計算 H_all, H_des, H_jam")
        H_all = H_unit.sum(axis=0)

        # 安全檢查：確保有所需的發射器和干擾器
        H_des = np.zeros_like(H_all)
        if idx_des:
            H_des = H_unit[idx_des].sum(axis=0)

        H_jam = np.zeros_like(H_all)
        if idx_jam:
            H_jam = H_unit[idx_jam].sum(axis=0)

        # 準備繪圖網格
        logger.info("準備繪圖")
        T, F = H_des.shape
        t_axis = np.arange(T)
        f_axis = np.arange(F)
        T_mesh, F_mesh = np.meshgrid(t_axis, f_axis, indexing="ij")

        # 創建圖片並保存
        logger.info("繪製通道響應圖")
        fig = plt.figure(figsize=(18, 5))

        # 子圖 1: H_des
        ax1 = fig.add_subplot(131, projection="3d")
        ax1.plot_surface(
            F_mesh, T_mesh, np.abs(H_des), cmap="viridis", edgecolor="none"
        )
        ax1.set_xlabel("子載波")
        ax1.set_ylabel("OFDM 符號")
        ax1.set_title("‖H_des‖")

        # 子圖 2: H_jam
        ax2 = fig.add_subplot(132, projection="3d")
        ax2.plot_surface(
            F_mesh, T_mesh, np.abs(H_jam), cmap="viridis", edgecolor="none"
        )
        ax2.set_xlabel("子載波")
        ax2.set_ylabel("OFDM 符號")
        ax2.set_title("‖H_jam‖")

        # 子圖 3: H_all
        ax3 = fig.add_subplot(133, projection="3d")
        ax3.plot_surface(
            F_mesh, T_mesh, np.abs(H_all), cmap="viridis", edgecolor="none"
        )
        ax3.set_xlabel("子載波")
        ax3.set_ylabel("OFDM 符號")
        ax3.set_title("‖H_all‖")

        plt.tight_layout()

        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存圖片
        logger.info(f"保存通道響應圖到 {output_path}")
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        # 檢查文件是否生成成功
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"成功保存通道響應圖到 {output_path}")
            return True
        else:
            logger.error(f"保存通道響應圖到 {output_path} 失敗或文件為空")
            return False

    except Exception as e:
        logger.exception(f"生成通道響應圖時發生錯誤: {e}")
        # 確保關閉所有打開的圖表
        plt.close("all")
        return False
