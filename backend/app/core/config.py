import os
import logging
from pathlib import Path  # 確保導入 Path

# --- Logging Setup ---
# (可以將 logging level 等也設為可配置)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Environment Variables & Basic Config ---
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://user:password@db/app"
)  # 提供預設值以防萬一
if not DATABASE_URL:
    logger.critical(
        "DATABASE_URL environment variable not set and no default provided!"
    )
    raise ValueError("DATABASE_URL environment variable not set!")

# 檢查 URL 是否符合 asyncpg
if not DATABASE_URL.startswith("postgresql+asyncpg"):
    logger.warning(
        f"DATABASE_URL does not start with 'postgresql+asyncpg://'. Received: {DATABASE_URL}. Ensure it's correctly configured for async."
    )

# --- Path Configuration (using pathlib) ---
# 在容器內，/app 就是 backend 目錄的根
# config.py 位於 /app/app/core
CORE_DIR = Path(__file__).resolve().parent  # /app/app/core
APP_DIR = CORE_DIR.parent  # /app/app
# BACKEND_DIR = APP_DIR.parent              # 不需要再往上找，/app 就是後端根目錄
# PROJECT_ROOT = BACKEND_DIR.parent

# 靜態文件應該在 /app/app/static 下，因為 volume mount 是 ./backend:/app
STATIC_DIR = APP_DIR / "static"  # Correct path: /app/app/static
MODELS_DIR = STATIC_DIR / "models"  # Correct path: /app/app/static/models
STATIC_IMAGES_DIR = STATIC_DIR / "images"  # Correct path: /app/app/static/images

# 建立目錄
# STATIC_DIR.mkdir(parents=True, exist_ok=True) # 目錄應該由 volume mount 提供，不需在 config 創建
MODELS_DIR.mkdir(parents=True, exist_ok=True)  # 但確保子目錄存在是好的
STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# 定義 GLB 路徑 (基於修正後的 MODELS_DIR)
XIN_GLB_PATH = MODELS_DIR / "XIN.glb"
GLB_PATH = MODELS_DIR / "scene.glb"

# 舊版 OUTPUT_DIR，保持定義以兼容可能還在使用的地方，但指向新位置
OUTPUT_DIR = STATIC_IMAGES_DIR

# 圖片檔案完整路徑 (使用 Path 對象)
SCENE_WITH_PATHS_IMAGE_PATH = OUTPUT_DIR / "scene_with_paths.png"
CONSTELLATION_IMAGE_PATH = OUTPUT_DIR / "constellation_diagram.png"
EMPTY_SCENE_IMAGE_PATH = OUTPUT_DIR / "empty_scene.png"

# logger.info(f"Project Root (estimated): {PROJECT_ROOT}") # 不再需要
logger.info(f"Static Directory (in container): {STATIC_DIR}")
logger.info(f"Models Directory (in container): {MODELS_DIR}")
logger.info(f"Static Images Directory (in container): {STATIC_IMAGES_DIR}")
logger.info(f"XIN GLB Path (in container): {XIN_GLB_PATH}")
logger.info(f"Default GLB Path (in container): {GLB_PATH}")
logger.info(
    f"Scene with Paths Image Path (in container): {SCENE_WITH_PATHS_IMAGE_PATH}"
)
logger.info(f"Constellation Image Path (in container): {CONSTELLATION_IMAGE_PATH}")


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
