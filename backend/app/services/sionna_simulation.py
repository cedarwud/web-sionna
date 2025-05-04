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
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import collections.abc  # Import for checking iterable

# Import models and config from their new locations
from app.db.models import Device, DeviceRole
from app.core.config import OUTPUT_DIR
from app.crud import crud_device  # 導入整合後的 crud_device 模塊

# 新增導入 for GLB rendering
import trimesh
import pyrender
from PIL import Image
import io

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
        pos_list = [dev_model.x, dev_model.y, dev_model.z]
        device_data = DeviceData(
            device_model=dev_model,
            position_list=pos_list,
            transmitter_role=DeviceRole.DESIRED,
        )
        transmitters_data.append(device_data)
        logger.info(
            f"Processed Active Signal Transmitter: {dev_model.name}, Position: {pos_list}"
        )

    # 處理干擾源發射器
    for dev_model in jammer_txs:
        pos_list = [dev_model.x, dev_model.y, dev_model.z]
        device_data = DeviceData(
            device_model=dev_model,
            position_list=pos_list,
            transmitter_role=DeviceRole.JAMMER,
        )
        transmitters_data.append(device_data)
        logger.info(f"Processed Active Jammer: {dev_model.name}, Position: {pos_list}")

    # 處理接收器數據
    receivers_data: List[DeviceData] = []
    for dev_model in receivers:
        pos_list = [dev_model.x, dev_model.y, dev_model.z]
        device_data = DeviceData(device_model=dev_model, position_list=pos_list)
        receivers_data.append(device_data)
        logger.info(
            f"Processed Active Receiver: {dev_model.name}, Position: {pos_list}"
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
                [1.0, 0.0, 0.0, -25.0],
                [0.0, 0.0, 1.0, 700.0],
                [0.0, -1.0, 0.0, 0.0],
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
    render_width: int = 800,
    render_height: int = 800,
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
                )
                sionna_txs_rt.append(sionna_tx)
                add_to_scene_safe(scene_rt, sionna_tx)

        sionna_rxs_rt = []
        valid_rx_positions_exist = False
        for rx_data in receivers_data:
            if rx_data.position_list:
                sionna_rx = SionnaReceiver(
                    rx_data.device_model.name, position=rx_data.position_list
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
        DEVICE_SIZE = 5.0
        TX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.0, 0.0, 1.0, 1.0]
        )
        RX_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[1.0, 0.0, 0.0, 1.0]
        )
        INT_MATERIAL_PYRENDER = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.0, 0.0, 0.0, 1.0]
        )
        # Add device spheres to pr_scene...
        for tx_data in transmitters_data:
            if tx_data.position_list:
                pos = tx_data.position_list
                render_pos = [pos[0], pos[2] + DEVICE_SIZE, pos[1]]
                mat = (
                    INT_MATERIAL_PYRENDER
                    if tx_data.transmitter_role == DeviceRole.JAMMER
                    else TX_MATERIAL_PYRENDER
                )
                try:
                    sphere = trimesh.primitives.Sphere(radius=DEVICE_SIZE)
                    device_mesh = pyrender.Mesh.from_trimesh(sphere, material=mat)
                    pose_matrix = np.eye(4)
                    pose_matrix[:3, 3] = render_pos
                    pr_scene.add(device_mesh, pose=pose_matrix)
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding TX '{tx_data.device_model.name}': {dev_err}",
                        exc_info=True,
                    )
        for rx_data in receivers_data:
            if rx_data.position_list:
                pos = rx_data.position_list
                render_pos = [pos[0], pos[2] + DEVICE_SIZE, pos[1]]
                mat = RX_MATERIAL_PYRENDER
                try:
                    sphere = trimesh.primitives.Sphere(radius=DEVICE_SIZE)
                    device_mesh = pyrender.Mesh.from_trimesh(sphere, material=mat)
                    pose_matrix = np.eye(4)
                    pose_matrix[:3, 3] = render_pos
                    pr_scene.add(device_mesh, pose=pose_matrix)
                except Exception as dev_err:
                    logger.error(
                        f"Failed adding RX '{rx_data.device_model.name}': {dev_err}",
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
            signal_tx_data.device_model.name, position=signal_tx_data.position_list
        )
        add_to_scene_safe(scene, sionna_signal_tx)
        added_tx_names.append(signal_tx_data.device_model.name)

        sionna_jammer_txs = []
        for int_tx_data in jammer_txs_data:
            sionna_int_tx = SionnaTransmitter(
                int_tx_data.device_model.name,
                position=int_tx_data.position_list,
                color=[0, 0, 0],  # 將干擾源顏色設為黑色
            )
            sionna_jammer_txs.append(sionna_int_tx)
            add_to_scene_safe(scene, sionna_int_tx)
            added_tx_names.append(int_tx_data.device_model.name)

        sionna_rx = SionnaReceiver(
            rx_data.device_model.name, position=rx_data.position_list
        )
        add_to_scene_safe(scene, sionna_rx)

        sionna_signal_tx.look_at(sionna_rx)
        for sint_tx in sionna_jammer_txs:
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
