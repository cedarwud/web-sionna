
# ── 程式區 ───────────────────────────────────────────────────────────────
import os
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import sionna, sionna.rt
from sionna.rt import (load_scene, PlanarArray, Transmitter, Receiver,
                       PathSolver, RadioMapSolver, subcarrier_frequencies)

# GPU 設定
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
gpus = tf.config.list_physical_devices("GPU")
if gpus: tf.config.experimental.set_memory_growth(gpus[0], True)

# ── 參數區 ───────────────────────────────────────────────────────────────
# 場景與天線
SCENE_NAME      = sionna.rt.scene.etoile
TX_ARRAY_CONFIG = dict(num_rows=1, num_cols=1,
                       vertical_spacing=0.5, horizontal_spacing=0.5,
                       pattern="iso", polarization="V")
RX_ARRAY_CONFIG = TX_ARRAY_CONFIG

# 發射機設定： (name, position, orientation, role)

# (name, pos, ori, role, power_dbm)
TX_LIST = [
  ("tx0",  [-100,-100,20], [np.pi*5/6,0,0],     "desired", 10),
  ("tx1",  [-100,  50,20], [np.pi/6,  0,0],     "desired", 10),
  ("tx2",  [ 100,-100,20], [-np.pi/2,0,0],      "desired", 10),
  ("jam1", [ 100,  50,20], [np.pi/2,  0,0],     "jammer",  100),
  ("jam2", [ 50,  50,20], [np.pi/2,  0,0],     "jammer",  100),
  ("jam3", [ -50, -50,20], [np.pi/2,  0,0],     "jammer",  100),
]

RX_CONFIG      = ("rx", [0,0,50])  # (name, position)

# PathSolver 參數
PATHSOLVER_ARGS = dict(max_depth=6,
                       los=True,
                       specular_reflection=True,
                       diffuse_reflection=False,
                       refraction=True,
                       synthetic_array=False,
                       seed=41)

# RadioMapSolver 參數
RMSOLVER_ARGS   = dict(max_depth=5,
                       cell_size=(1.,1.),
                       samples_per_tx=10**7)

# OFDM / QPSK 參數
N_SYMBOLS       = 1
N_SUBCARRIERS   = 1024
SUBCARRIER_SPACING = 30e3  # Hz
num_ofdm_symbols = 1024 
num_subcarriers = 1024
subcarrier_spacing = 30e3

# 通道品質參數
JNR_dB          = 5.0
EBN0_dB         = 20.0

# 繪圖範圍（SINR dB）
SINR_VMIN       = -40
SINR_VMAX       =   0

# 1) 建立場景與天線配置
scene = load_scene(SCENE_NAME)
scene.tx_array = PlanarArray(**TX_ARRAY_CONFIG)
scene.rx_array = PlanarArray(**RX_ARRAY_CONFIG)
for tx_name in scene.transmitters.copy():  
    scene.remove(tx_name)
# 再把所有 receiver name 拿出來，一個個 remove
for rx_name in scene.receivers.copy():
    scene.remove(rx_name)

# 確認都清空了
assert len(scene.transmitters)==0 and len(scene.receivers)==0

# 2) 新增 Tx (含 role 標籤)
def add_tx(scene, name, pos, ori, role, power_dbm):
    tx = Transmitter(name=name, position=pos,
                     orientation=ori, power_dbm=power_dbm)
    tx.role = role
    scene.add(tx)
    return tx

# 迴圈時 unpack 五個欄位
for name, pos, ori, role, p_dbm in TX_LIST:
    add_tx(scene, name, pos, ori, role, p_dbm)


# 3) 新增 Rx
rx_name, rx_pos = RX_CONFIG
rx = Receiver(name=rx_name, position=rx_pos)
scene.add(rx)

# 4) 自動分組 indices
tx_names = scene.transmitters
all_txs   = [scene.get(n) for n in tx_names]
idx_des   = [i for i,tx in enumerate(all_txs) if getattr(tx,'role',None)=='desired']
idx_jam   = [i for i,tx in enumerate(all_txs) if getattr(tx,'role',None)=='jammer']

# 5) RadioMap 計算
rm_solver = RadioMapSolver()
rm = rm_solver(scene, **RMSOLVER_ARGS)

# 6) PathSolver 函式
solver = PathSolver()
def solve():
    return solver(scene, **PATHSOLVER_ARGS)

# 7) 計算 CFR
freqs = subcarrier_frequencies(N_SUBCARRIERS, SUBCARRIER_SPACING)
for name in scene.transmitters:
    scene.get(name).velocity = [30, 0, 0]   # 或者 jam1 用 [-30,0,0]
paths = solve()

my_cam = Camera(position=[0,0,1000], look_at=[0,1,0])
scene.render(camera=my_cam, resolution=[650, 500], num_samples=512, paths=paths, clip_at=20);