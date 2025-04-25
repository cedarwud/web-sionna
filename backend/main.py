# backend/main.py
import os
import sys
import tensorflow as tf

# --- 讀取環境變量並配置 GPU/CPU ---
# 先設置 TF 日誌級別
os.environ["TF_CPP_MIN_LOG_LEVEL"] = os.getenv("TF_CPP_MIN_LOG_LEVEL", "3")
tf.get_logger().setLevel("ERROR")

cuda_visible_devices = os.getenv("CUDA_VISIBLE_DEVICES")  # 讀取環境變量
force_cpu = cuda_visible_devices == "-1"

print(f">>> Detected CUDA_VISIBLE_DEVICES='{cuda_visible_devices}'")

if force_cpu:
    print(">>> CPU usage forced by CUDA_VISIBLE_DEVICES=-1.")
    # 理論上不需要額外操作，TF 在看不到 GPU 時會自動用 CPU
    # 可以選擇性地禁用 GPU 發現 (但通常設置環境變量足夠)
    # tf.config.set_visible_devices([], 'GPU')
else:
    # 嘗試配置 GPU (如果 CUDA_VISIBLE_DEVICES 沒設置、為空或指定了 GPU ID)
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        try:
            # TensorFlow 會自動根據 CUDA_VISIBLE_DEVICES 篩選可見的 GPU
            # 我們為第一個可見的 GPU 設置內存增長
            # 如果 CUDA_VISIBLE_DEVICES="0,1"，這裡 gpus[0] 就是實際的 GPU 0
            tf.config.experimental.set_memory_growth(gpus[0], True)
            print(
                f">>> Configured Visible GPU(s): {[gpu.name for gpu in gpus]} with memory growth on first visible GPU."
            )
        except Exception as e:  # 使用更通用的 Exception
            print(
                f"!!! Error configuring GPU: {e}. Check TensorFlow/CUDA setup. Falling back to CPU logic if possible."
            )
            # 如果 GPU 配置失敗，Sionna/TF 可能會自動回退或報錯，取決於它們的實現
    else:
        print(
            ">>> No compatible GPU detected by TensorFlow (or none visible due to CUDA_VISIBLE_DEVICES), will use CPU."
        )
# --- 結束 GPU/CPU 配置 ---

# --- 設定 Matplotlib 後端 (保持不變) ---
import matplotlib

try:
    matplotlib.use("Agg")
    print(">>> Matplotlib backend set to Agg.")
except Exception as e:
    print(f">>> Warning: Failed to set Matplotlib backend to Agg: {e}")
import matplotlib.pyplot as plt

# --- 結束設定 Matplotlib 後端 ---

print(f"Python executable: {sys.executable}")
print("Starting library imports...")
try:
    from fastapi import FastAPI, Depends, HTTPException
    from fastapi.responses import FileResponse
    from fastapi.middleware.cors import CORSMiddleware

    print("FastAPI related imports successful.")
    import sionna.rt
    from sionna.rt import (
        load_scene,
        Camera,
        Transmitter,
        Receiver,
        PlanarArray,
        PathSolver,
    )

    print("Sionna RT related imports successful.")
    import numpy as np  # <--- 確保導入 numpy

    print("Numpy import successful.")
except ImportError as e:
    print(f"!!! Error during import: {e}")
    # sys.exit(1)
print("Imports completed.")

# --- 配置 ---
OUTPUT_DIR = "rendered_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)
# 場景圖片路徑
SCENE_ORIGINAL_IMAGE_PATH = os.path.join(OUTPUT_DIR, "scene_original.png")
SCENE_WITH_PATHS_IMAGE_PATH = os.path.join(OUTPUT_DIR, "scene_with_paths.png")
CONSTELLATION_IMAGE_PATH = os.path.join(OUTPUT_DIR, "constellation_diagram.png")


# --- Helper function (保持不變) ---
def add_to_scene_safe(scene, device):
    try:
        scene.add(device)
        print(f"	Added '{device.name}' to the scene.")
    except ValueError:
        print(f"	Device '{device.name}' might already exist in the scene.")
        pass


# --- 新增：只渲染原始場景的函數 ---
def generate_scene_original_image(output_path: str):
    """只渲染 Etoile 場景，不包含 tx/rx 或路徑。"""
    print(">>> Entering generate_scene_original_image function...")
    try:
        print("	載入 Sionna 場景 ('etoile')...")
        scene = load_scene(sionna.rt.scene.etoile)
        print("	場景載入成功.")
        print("	定義攝影機...")
        my_cam = Camera(position=[0, 0, 1000], look_at=[0, 1, 0])
        print("	準備渲染原始場景...")
        fig = plt.figure()
        scene.render(
            camera=my_cam, resolution=[800, 600], num_samples=64
        )  # 可以用較低的採樣數加快速度
        print("	scene.render() (原始) 執行完畢.")
        print(f"	儲存原始場景圖像至 {output_path}...")
        plt.savefig(output_path, bbox_inches="tight", pad_inches=0, dpi=150)
        print("	原始場景圖像儲存成功.")
        plt.close(fig)
        print(f"<<< 原始場景已渲染並儲存至: {output_path}, 函數返回 True.")
        return True
    except Exception as e:
        print(f"!!! 在 generate_scene_original_image 中發生嚴重錯誤: {e}")
        import traceback

        traceback.print_exc()
        plt.close("all")
        print("<<< 原始場景渲染失敗，函數返回 False.")
        return False


# --- 渲染帶路徑場景的函數 (之前的 render_sionna_scene_with_paths) ---
# 建議重命名以更清晰地區分
# --- 渲染帶路徑場景的函數 ---
def generate_scene_with_paths_image(output_path: str):
    """渲染 Etoile 場景，包含 tx/rx 和路徑。"""
    print(">>> Entering generate_scene_with_paths_image function...")
    try:
        # 1. 載入場景
        print("	載入 Sionna 場景 ('etoile')...")
        scene = load_scene(sionna.rt.scene.etoile)
        print("	場景載入成功.")

        # 2. 設定天線陣列 (必需！)
        print("	設定天線陣列 (iso)...")
        iso = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
        scene.tx_array = iso  # <--- 確保這行存在且執行
        scene.rx_array = iso  # <--- 確保這行存在且執行
        print("	天線陣列設定完成.")

        # 3. 定義並添加 TX/RX (必需！)
        print("	定義發射器 (tx_main, tx_i) 和接收器 (rx)...")
        tx_main = Transmitter("tx_main", position=[0, 60, 2.0])
        tx_i = Transmitter("tx_i", position=[-100, 100, 2.0])
        rx = Receiver("rx", position=[0, 0, 1.5])
        add_to_scene_safe(scene, tx_main)  # <--- 確保這行存在且執行
        add_to_scene_safe(scene, tx_i)  # <--- 確保這行存在且執行
        add_to_scene_safe(scene, rx)  # <--- 確保這行存在且執行
        tx_main.look_at(rx)
        tx_i.look_at(rx)
        print("	TX/RX 定義並添加完成.")

        # 4. 初始化 PathSolver 並計算路徑 (必需！)
        print("	初始化 PathSolver 並計算路徑...")
        solver = PathSolver()
        paths = solver(  # <--- 現在 scene 應該有 tx_array 了
            scene,
            max_depth=6,
            los=True,
            specular_reflection=True,
            diffuse_reflection=False,
            refraction=True,
        )
        print(f"	路徑計算完成.")

        # 5. 定義攝影機
        print("	定義攝影機...")
        my_cam = Camera(position=[0, 0, 1000], look_at=[0, 1, 0])

        # 6. 渲染場景與路徑
        print("	準備渲染場景 (包含路徑)...")
        fig = plt.figure()
        scene.render(camera=my_cam, paths=paths, resolution=[800, 600], num_samples=128)
        print("	scene.render() (帶路徑) 執行完畢.")

        # 7. 保存圖像
        print(f"	儲存帶路徑圖像至 {output_path}...")
        # --- 保存圖像 try...except (可選但建議) ---
        try:
            plt.savefig(output_path, bbox_inches="tight", pad_inches=0, dpi=150)
            print("	帶路徑圖像儲存成功.")
        except Exception as save_err:
            print(f"!!! 錯誤：儲存帶路徑圖像到 {output_path} 時失敗: {save_err}")
            plt.close(fig)
            print("<<< 帶路徑場景渲染失敗（保存錯誤），函數返回 False.")
            return False  # 保存失敗則返回 False
        # --- 結束保存圖像 try...except ---

        # 8. 關閉圖形
        print("	關閉 Matplotlib Figure...")
        plt.close(fig)
        print(f"<<< 帶路徑場景已渲染並儲存至: {output_path}, 函數返回 True.")
        return True

    except Exception as e:
        print(f"!!! 在 generate_scene_with_paths_image 中發生嚴重錯誤: {e}")
        import traceback

        traceback.print_exc()
        plt.close("all")
        print("<<< 帶路徑場景渲染失敗，函數返回 False.")
        return False


# --- 新增：生成星座圖的函數 ---
def generate_constellation_plot(
    output_path: str, bandwidth=20e6, jnr_db=10.0, ebno_db=10.0
):
    """
    執行路徑查找、基帶模擬並生成星座圖。
    """
    print(">>> Entering generate_constellation_plot function...")
    try:
        # --- 1. 場景設置和路徑計算 (與渲染函數中類似，但需要獲取 Taps) ---
        print("	載入 Sionna 場景 ('etoile')...")
        scene = load_scene(sionna.rt.scene.etoile)
        print("	設定天線陣列 (iso)...")
        iso = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
        scene.tx_array = iso
        scene.rx_array = iso
        print("	定義 TX/RX...")
        tx_main = Transmitter("tx_main", position=[0, 60, 2.0])
        tx_i = Transmitter("tx_i", position=[-100, 100, 2.0])
        rx = Receiver("rx", position=[0, 0, 1.5])
        add_to_scene_safe(scene, tx_main)
        add_to_scene_safe(scene, tx_i)
        add_to_scene_safe(scene, rx)
        tx_main.look_at(rx)
        tx_i.look_at(rx)
        print("	計算路徑...")
        solver = PathSolver()
        paths = solver(
            scene,
            max_depth=6,
            los=True,
            specular_reflection=True,
            diffuse_reflection=False,
            refraction=True,
        )
        print("	路徑計算完成.")

        # --- 2. 從路徑計算通道響應 (Taps) ---
        print(f"	計算通道 Taps (bandwidth={bandwidth/1e6:.1f} MHz)...")
        # 注意: paths.taps() 返回的是 TensorFlow Tensor，需要轉為 numpy
        # 返回的 shape 可能是 (batch, rx, rx_ant, tx, tx_ant, taps) 或類似
        # 這裡假設 batch=1, rx=1, tx=2 (main and interferer), ants=1
        h_tf = paths.taps(
            l_min=0,
            l_max=0,
            bandwidth=bandwidth,
            sampling_frequency=bandwidth,  # sampling_frequency 參數可能需要（查文件）
            normalize=False,
            normalize_delays=False,  # 可能需要設為 False 以匹配 Notebook
            out_type="tf",
        )

        # 處理維度，假設我們只需要 main 和 interferer 的第一個 tap
        # 需要根據實際 h_tf 的 shape 調整索引！
        h_np = h_tf.numpy().squeeze()  # 嘗試壓縮掉單維度
        print(f"	原始 h_np shape: {h_np.shape}")

        # 確保 h_np 至少是一維的
        if h_np.ndim == 0:  # 如果結果是純量 (可能只有一條路徑且無天線?)
            h_np = np.array([h_np])  # 轉為一維數組

        if h_np.shape[0] >= 1:
            h_main = h_np[0]  # 主通道響應 (可能需要更複雜的索引)
        else:
            print("!!! 警告: 無法獲取主通道響應 (h_main)")
            h_main = 0 + 0j  # 設置為 0 以防錯誤

        if h_np.shape[0] >= 2:
            h_int = h_np[1]  # 干擾通道響應 (可能需要更複雜的索引)
        else:
            print("	未檢測到干擾通道響應 (h_int)")
            h_int = 0 + 0j  # 設置為 0

        print(f"	h_main: {h_main}, h_int: {h_int}")

        # --- 3. 基帶信號處理 (來自 Notebook) ---
        print("	執行基帶信號模擬...")
        N_SYM = 4096  # 符號數量
        # 生成 QPSK 符號
        bits = np.random.randint(0, 2, (N_SYM, 2))
        x = (1 - 2 * bits[:, 0] + 1j * (1 - 2 * bits[:, 1])) / np.sqrt(2.0)

        y_sig_raw = h_main * x
        y_int_raw = h_int * x

        # 計算干擾縮放因子
        mean_sig_power = np.mean(np.abs(y_sig_raw) ** 2)
        mean_int_power = np.mean(np.abs(y_int_raw) ** 2)

        if mean_int_power > 1e-15:  # 避免除以零
            scale = np.sqrt(mean_sig_power / mean_int_power / (10 ** (jnr_db / 10.0)))
        else:
            scale = 0.0  # 無干擾功率

        y_int = y_int_raw * scale

        # 計算噪聲
        # Eb/No = (Signal Power / Bits per Symbol) / (Noise Power / Bandwidth)
        # N0 = Signal Power / (Eb/No * Bits per Symbol) # 假設帶寬歸一化？
        # 或者更簡單地從 SNR 考慮: SNR = Signal Power / Noise Power
        # SNR_dB = EbNo_dB + 10*log10(BitsPerSymbol)
        # 這裡用 QPSK，每個符號 2 bits => 10*log10(2) approx 3 dB
        snr_db = ebno_db + 10 * np.log10(2.0)
        noise_power = mean_sig_power / (10 ** (snr_db / 10.0))
        noise = np.sqrt(noise_power / 2.0) * (
            np.random.randn(N_SYM) + 1j * np.random.randn(N_SYM)
        )

        y_no_i = y_sig_raw + noise
        y_with_i = y_sig_raw + y_int + noise

        # 信道均衡 (最簡單的迫零均衡)
        # 避免 h_main 為零
        if np.abs(h_main) > 1e-15:
            y_eq_no_i = y_no_i / h_main
            y_eq_with_i = y_with_i / h_main
        else:
            print("!!! 警告: 主通道響應 h_main 過小，無法均衡")
            y_eq_no_i = np.zeros_like(y_no_i)  # 或者其他處理
            y_eq_with_i = np.zeros_like(y_with_i)

        print("	基帶信號模擬完成.")

        # --- 4. 繪製星座圖 (來自 Notebook) ---
        print("	繪製星座圖...")
        fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))  # 創建 1x2 子圖

        # 子圖 1: 無干擾
        ax[0].scatter(y_eq_no_i.real, y_eq_no_i.imag, s=4, alpha=0.25)
        ax[0].set(
            title="No interference", xlabel="I", ylabel="Q", aspect="equal"
        )  # aspect='equal' 保持比例
        ax[0].grid(True)
        ax[0].set_xlim(
            min(y_eq_no_i.real.min(), -1.5), max(y_eq_no_i.real.max(), 1.5)
        )  # 調整範圍
        ax[0].set_ylim(min(y_eq_no_i.imag.min(), -1.5), max(y_eq_no_i.imag.max(), 1.5))

        # 子圖 2: 有干擾
        ax[1].scatter(y_eq_with_i.real, y_eq_with_i.imag, s=4, alpha=0.25)
        ttl = (
            f"With interferer (JNR = {jnr_db:.1f} dB)"
            if np.abs(h_int) > 1e-15
            else "Interferer absent"
        )
        ax[1].set(title=ttl, xlabel="I", ylabel="Q", aspect="equal")
        ax[1].grid(True)
        ax[1].set_xlim(
            min(y_eq_with_i.real.min(), -1.5), max(y_eq_with_i.real.max(), 1.5)
        )  # 調整範圍
        ax[1].set_ylim(
            min(y_eq_with_i.imag.min(), -1.5), max(y_eq_with_i.imag.max(), 1.5)
        )

        plt.tight_layout()  # 自動調整佈局
        print("	星座圖繪製完成.")

        # --- 5. 保存圖像 ---
        print(f"	儲存星座圖至 {output_path}...")
        plt.savefig(output_path, bbox_inches="tight", dpi=100)  # 保存而不是顯示
        print("	星座圖儲存成功.")
        plt.close(fig)  # 關閉圖形釋放記憶體
        print("	Matplotlib Figure 已關閉.")
        print(f"<<< 星座圖已生成並儲存至: {output_path}, 函數返回 True.")
        return True

    except Exception as e:
        print(f"!!! 在 generate_constellation_plot 中發生嚴重錯誤: {e}")
        import traceback

        traceback.print_exc()
        plt.close("all")
        print("<<< 星座圖生成失敗，函數返回 False.")
        return False


# --- FastAPI 應用程式實例 (保持不變) ---
print("Creating FastAPI app instance...")
app = FastAPI()
# ... (CORS Middleware 設定保持不變) ...
print("CORS middleware added.")


# --- API 端點 ---
# 新增：返回原始場景圖的端點
@app.get("/api/scene-image-original")
async def get_scene_image_original():
    print("--- Received request for /api/scene-image-original ---")
    if generate_scene_original_image(SCENE_ORIGINAL_IMAGE_PATH):
        if os.path.exists(SCENE_ORIGINAL_IMAGE_PATH):
            print(
                f"	原始場景圖存在，準備回傳 FileResponse for {SCENE_ORIGINAL_IMAGE_PATH}"
            )
            return FileResponse(SCENE_ORIGINAL_IMAGE_PATH, media_type="image/png")
        else:
            print(
                f"	!!! 錯誤: 原始圖生成成功但文件 {SCENE_ORIGINAL_IMAGE_PATH} 未找到。"
            )
            return {"error": "Failed to find original scene image after generation."}
    else:
        print("	!!! 錯誤: 原始場景渲染失敗。")
        return {"error": "Failed to render original scene"}


# 修改：之前的端點現在明確返回帶路徑的場景圖
@app.get("/api/scene-image-rt")  # <--- 修改了 URL 路徑以更清晰
async def get_scene_image_rt():
    print("--- Received request for /api/scene-image-rt ---")
    if generate_scene_with_paths_image(SCENE_WITH_PATHS_IMAGE_PATH):
        if os.path.exists(SCENE_WITH_PATHS_IMAGE_PATH):
            print(
                f"	帶路徑場景圖存在，準備回傳 FileResponse for {SCENE_WITH_PATHS_IMAGE_PATH}"
            )
            return FileResponse(SCENE_WITH_PATHS_IMAGE_PATH, media_type="image/png")
        else:
            print(
                f"	!!! 錯誤: 帶路徑圖生成成功但文件 {SCENE_WITH_PATHS_IMAGE_PATH} 未找到。"
            )
            return {"error": "Failed to find scene image with paths after rendering."}
    else:
        print("	!!! 錯誤: 帶路徑場景渲染失敗。")
        return {"error": "Failed to render scene with paths"}


# 新增的星座圖端點
@app.get("/api/constellation-diagram")
async def get_constellation_diagram():
    print("--- Received request for /api/constellation-diagram ---")
    # 調用新的生成函數
    if generate_constellation_plot(CONSTELLATION_IMAGE_PATH):
        if os.path.exists(CONSTELLATION_IMAGE_PATH):
            print(f"	星座圖存在，準備回傳 FileResponse for {CONSTELLATION_IMAGE_PATH}")
            return FileResponse(CONSTELLATION_IMAGE_PATH, media_type="image/png")
        else:
            print(f"	!!! 錯誤: 星座圖生成成功但文件 {CONSTELLATION_IMAGE_PATH} 未找到。")
            return {
                "error": "Failed to generate or find the constellation diagram after generation."
            }
    else:
        print("	!!! 錯誤: 星座圖生成失敗 (generate_constellation_plot returned False)。")
        return {"error": "Failed to generate constellation diagram"}


@app.get("/")
async def read_root():
    print("--- Received request for / ---")
    return {
        "message": "Sionna RT Backend is running (with scene and constellation endpoints)\n"
    }


# ... (其他的程式碼，例如 __main__ 測試塊保持不變) ...
print("API endpoints defined.")
print("Script loading complete. Ready for Uvicorn.")

if __name__ == "__main__":
    print("\n--- Running __main__ block for direct execution test ---")
    # 可以選擇性地測試新函數
    # print("--- Testing render_sionna_scene_with_paths directly ---")
    # if render_sionna_scene_with_paths("test_render_with_paths.png"):
    # 	print("--- Direct test: Scene rendering successful ---")
    # else:
    # 	print("--- Direct test: Scene rendering failed ---")

    print("--- Testing generate_constellation_plot directly ---")
    if generate_constellation_plot("test_constellation.png"):
        print("--- Direct test: Constellation generation successful ---")
    else:
        print("--- Direct test: Constellation generation failed ---")

    print("--- End of __main__ block ---")
