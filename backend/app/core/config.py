import os
import logging

# --- Logging Setup ---
# (可以將 logging level 等也設為可配置)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Environment Variables & Basic Config ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("DATABASE_URL environment variable not set!")
    # 在實際應用中可能需要更優雅的處理方式
    raise ValueError("DATABASE_URL environment variable not set!")

# 檢查 URL 是否符合 asyncpg
if not DATABASE_URL.startswith("postgresql+asyncpg"):
    logger.warning(
        f"DATABASE_URL does not start with 'postgresql+asyncpg://'. Received: {DATABASE_URL}. Ensure it's correctly configured for async."
    )
    # 考慮是否要強制修正或拋出錯誤
    # if DATABASE_URL.startswith("postgresql://"):
    #    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


# --- Sionna/Simulation Constants ---
# Define the path relative to the backend script's location
# BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # backend/app -> backend -> root
# OUTPUT_DIR = os.path.join(BACKEND_DIR, "..", "frontend", "public", "rendered_images")
# Simplified relative path assuming execution from workspace root or backend/ directory
OUTPUT_DIR = "../frontend/public/rendered_images"
# 建立目錄的操作可以在應用程式啟動時或首次使用前執行
# os.makedirs(OUTPUT_DIR, exist_ok=True) # 移到 lifespan 或使用時檢查

# SCENE_ORIGINAL_IMAGE_PATH = os.path.join(OUTPUT_DIR, "scene_original.png") # Removed
SCENE_WITH_PATHS_IMAGE_PATH = os.path.join(OUTPUT_DIR, "scene_with_paths.png")
CONSTELLATION_IMAGE_PATH = os.path.join(OUTPUT_DIR, "constellation_diagram.png")
EMPTY_SCENE_IMAGE_PATH = os.path.join(OUTPUT_DIR, "empty_scene.png")


# --- GPU/CPU Configuration ---
# (這部分邏輯也可以放在這裡，或在需要時執行)
def configure_gpu_cpu():
    import tensorflow as tf

    os.environ["TF_CPP_MIN_LOG_LEVEL"] = os.getenv("TF_CPP_MIN_LOG_LEVEL", "3")
    tf.get_logger().setLevel("ERROR")  # Keep TF logs quiet unless necessary
    cuda_visible_devices = os.getenv("CUDA_VISIBLE_DEVICES")
    force_cpu = cuda_visible_devices == "-1"
    logger.info(f"Detected CUDA_VISIBLE_DEVICES='{cuda_visible_devices}'")
    if force_cpu:
        logger.info("CPU usage forced by CUDA_VISIBLE_DEVICES=-1.")
        # Explicitly disable GPU visibility in TensorFlow
        tf.config.set_visible_devices([], "GPU")
    else:
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            try:
                # Prefer setting memory growth on all visible GPUs if possible
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(
                    f"Configured Visible GPU(s): {[gpu.name for gpu in gpus]} with memory growth."
                )
            except RuntimeError as e:
                logger.error(
                    f"Error configuring GPU memory growth: {e}. Check TensorFlow/CUDA setup.",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during GPU configuration: {e}",
                    exc_info=True,
                )

        else:
            logger.info("No compatible GPU detected by TensorFlow, will use CPU.")
            # Ensure TF doesn't see any GPUs if none are intended
            tf.config.set_visible_devices([], "GPU")


# --- Matplotlib Backend ---
# (也可以放在這裡或在使用前設定)
def configure_matplotlib():
    import matplotlib

    try:
        matplotlib.use("Agg")
        logger.info("Matplotlib backend set to Agg.")
    except Exception as e:
        logger.warning(f"Failed to set Matplotlib backend to Agg: {e}", exc_info=True)


# 在需要時呼叫設定函數，例如在 lifespan 或 main.py 頂部
# configure_gpu_cpu()
# configure_matplotlib()
