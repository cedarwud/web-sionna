"""
Full-band CFR demo – Python 3.11 · TF 2.19 · Sionna 1.0.2
"""

# ── 參數區 ───────────────────────────────────────────────────────────────
# 場景與天線
# SCENE_NAME      = sionna.rt.scene.etoile
SCENE_NAME = "GIS.xml"
TX_ARRAY_CONFIG = dict(
    num_rows=1,
    num_cols=1,
    vertical_spacing=0.5,
    horizontal_spacing=0.5,
    pattern="iso",
    polarization="V",
)
RX_ARRAY_CONFIG = TX_ARRAY_CONFIG

# 發射機設定： (name, position, orientation, role)

# (name, pos, ori, role, power_dbm)
TX_LIST = [
    ("tx0", [-100, -100, 20], [np.pi * 5 / 6, 0, 0], "desired", 30),
    ("tx1", [-100, 50, 20], [np.pi / 6, 0, 0], "desired", 30),
    ("tx2", [100, -100, 20], [-np.pi / 2, 0, 0], "desired", 30),
    ("jam1", [100, 50, 20], [np.pi / 2, 0, 0], "jammer", 40),
    ("jam2", [50, 50, 20], [np.pi / 2, 0, 0], "jammer", 40),
    ("jam3", [-50, -50, 20], [np.pi / 2, 0, 0], "jammer", 40),
]


RX_CONFIG = ("rx", [0, 0, 20])  # (name, position)

# PathSolver 參數
PATHSOLVER_ARGS = dict(
    max_depth=10,
    los=True,
    specular_reflection=True,
    diffuse_reflection=False,
    refraction=False,
    synthetic_array=False,
    seed=41,
)

# RadioMapSolver 參數
RMSOLVER_ARGS = dict(max_depth=10, cell_size=(1.0, 1.0), samples_per_tx=10**7)

# OFDM / QPSK 參數
N_SYMBOLS = 1
N_SUBCARRIERS = 1024
SUBCARRIER_SPACING = 30e3  # Hz
num_ofdm_symbols = 1024
num_subcarriers = 1024
subcarrier_spacing = 30e3

# 通道品質參數
JNR_dB = 5.0
EBN0_dB = 20.0

# 繪圖範圍（SINR dB）
SINR_VMIN = -40
SINR_VMAX = 0


# ── 程式區 ───────────────────────────────────────────────────────────────
import os
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import sionna, sionna.rt
from sionna.rt import (
    load_scene,
    PlanarArray,
    Transmitter,
    Receiver,
    PathSolver,
    RadioMapSolver,
    subcarrier_frequencies,
)

# GPU 設定
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
gpus = tf.config.list_physical_devices("GPU")
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)

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
assert len(scene.transmitters) == 0 and len(scene.receivers) == 0


# 2) 新增 Tx (含 role 標籤)
def add_tx(scene, name, pos, ori, role, power_dbm):
    tx = Transmitter(name=name, position=pos, power_dbm=power_dbm)
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
all_txs = [scene.get(n) for n in tx_names]
idx_des = [i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "desired"]
idx_jam = [i for i, tx in enumerate(all_txs) if getattr(tx, "role", None) == "jammer"]

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
    scene.get(name).velocity = [30, 0, 0]  # 或者 jam1 用 [-30,0,0]
paths = solve()


def dbm2w(dbm):
    return 10 ** (dbm / 10) / 1000


tx_powers = [dbm2w(scene.get(n).power_dbm) for n in scene.transmitters]

ofdm_symbol_duration = 1 / subcarrier_spacing
delay_resolution = ofdm_symbol_duration / num_subcarriers
doppler_resolution = subcarrier_spacing / num_ofdm_symbols

H_unit = paths.cfr(
    frequencies=freqs,
    sampling_frequency=1 / ofdm_symbol_duration,
    num_time_steps=num_ofdm_symbols,  # ← 讓 Sionna 跑時間演變 (多普勒)
    normalize_delays=True,
    normalize=False,
    out_type="numpy",
).squeeze()  # shape: (num_tx, T, F)
# h_main = np.sum(H[idx_des, :], axis=0)
# h_intf = np.sum(H[idx_jam, :], axis=0)
print("H_unit.shape", H_unit.shape)

H_all = np.sqrt(np.array(tx_powers)[:, None, None]) * H_unit

H_des = H_all[idx_des].sum(axis=0)  # (T, F)
H_jam = H_all[idx_jam].sum(axis=0)  # (T, F)
print("H_des.shape", H_des.shape)
print("H_jam.shape", H_jam.shape)
H = H_unit[:, 0, :]
print("H.shape", H.shape)


def gray_64qam_mapper(b):  # b: (..., 6) bits
    """
    回傳複數 constellation，平均功率 = 1
    Gray mapping: [b0…b5] = [msb … lsb]
    I = 8-PAM(b0 b2 b4), Q = 8-PAM(b1 b3 b5)
    """
    b = np.asarray(b, dtype=int)
    assert b.shape[-1] == 6
    # split bits
    b0, b1, b2, b3, b4, b5 = [b[..., i] for i in range(6)]

    # Gray → 3‐bit binary
    def gray3_to_level(g2, g1, g0):
        # g2 g1 g0 = Gray bits, 得到 0…7
        bin2 = g2
        bin1 = g1 ^ bin2
        bin0 = g0 ^ bin1
        val = bin2 * 4 + bin1 * 2 + bin0
        return val

    I_idx = gray3_to_level(b0, b2, b4)
    Q_idx = gray3_to_level(b1, b3, b5)
    # 8-PAM levels: {-7,-5,-3,-1,+1,+3,+5,+7}
    pam = np.array([-7, -5, -3, -1, +1, +3, +5, +7])
    I = pam[I_idx]
    Q = pam[Q_idx]
    s = I + 1j * Q
    # Normalize to unit average power
    s = s / np.sqrt((42))  # E{|s|^2}=42 ⇒ 除√42≈6.4807
    return s


h_main = sum(np.sqrt(tx_powers[i]) * H[i] for i in idx_des)
h_intf = sum(np.sqrt(tx_powers[i]) * H[i] for i in idx_jam)
print("h_main.shape", h_main.shape)
print("h_intf.shape", h_intf.shape)


# # 8) 產生 QPSK+OFDM 符號
bits = np.random.randint(0, 2, (N_SYMBOLS, N_SUBCARRIERS, 2))
bits_jam = np.random.randint(0, 2, (N_SYMBOLS, N_SUBCARRIERS, 2))
X_sig = (1 - 2 * bits[..., 0] + 1j * (1 - 2 * bits[..., 1])) / np.sqrt(2)
X_jam = (1 - 2 * bits_jam[..., 0] + 1j * (1 - 2 * bits_jam[..., 1])) / np.sqrt(2)

Y_sig = X_sig * h_main[None, :]  # 跟舊程式同
Y_int = X_jam * h_intf[None, :]  # ……
p_sig = np.mean(np.abs(Y_sig) ** 2)
p_int = np.mean(np.abs(Y_int) ** 2)
# scale      = np.sqrt(p_sig/p_int/10**(JNR_dB/10)) if p_int>0 else 0
# Y_int     *= scale
N0 = p_sig / (10 ** (EBN0_dB / 10) * 2)
noise = np.sqrt(N0 / 2) * (
    np.random.randn(*Y_sig.shape) + 1j * np.random.randn(*Y_sig.shape)
)
Y_tot = Y_sig + Y_int + noise
y_eq_no_i = (Y_sig + noise) / h_main
y_eq_with_i = (Y_sig + Y_int + noise) / h_main
print("Y_sig.shape", Y_sig.shape)
print("Y_int.shape", Y_int.shape)
print("y_eq_no_i.shape", y_eq_no_i.shape)
print("y_eq_with_i.shape", y_eq_with_i.shape)

# +++++++++++++++++++++
# 9) 繪製星座 & CFR
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
ax[0].scatter(y_eq_no_i.real, y_eq_no_i.imag, s=4, alpha=0.25)
ax[1].scatter(y_eq_with_i.real, y_eq_with_i.imag, s=4, alpha=0.25)
ax[0].set(title="No interference")
ax[0].grid(True)
ax[1].set(title="With interferer ")
ax[1].grid(True)
ax[2].plot(np.abs(h_main), label="|H_main|")
ax[2].plot(np.abs(h_intf), label="|H_intf|")
ax[2].set(title="CFR Magnitude", xlabel="Subcarrier Index")
ax[2].legend()
ax[2].grid(True)
plt.tight_layout()
plt.show()
