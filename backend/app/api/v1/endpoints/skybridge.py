# backend/app/api/v1/endpoints/skybridge.py
from fastapi import APIRouter
import asyncio, math, os
from skyfield.api import EarthSatellite, load, wgs84

router = APIRouter(prefix="/skybridge")

# 初始化 Skyfield 衛星
ts = load.timescale()
l1 = os.getenv("SAT_TLE_LINE1")
l2 = os.getenv("SAT_TLE_LINE2")
if not l1 or not l2:
    raise RuntimeError("請在環境變數中設定 SAT_TLE_LINE1、SAT_TLE_LINE2")
sat = EarthSatellite(l1, l2, "LEO", ts)

# 全局狀態
state = {"snr": None, "link": False, "sat": {"lat": None, "lon": None, "alt_km": None}}


def estimate_snr(distance_km: float) -> float:
    """簡化自由空間模型估算 SNR"""
    if distance_km <= 0:
        return -1.0
    ref_snr = 30.0
    return ref_snr - 20 * math.log10(distance_km)


async def update_loop():
    """週期更新衛星位置與 SNR，不做容器控制"""
    while True:
        t = ts.now()
        geo = sat.at(t)
        subpt = wgs84.subpoint(geo)
        lat, lon, alt = (
            subpt.latitude.degrees,
            subpt.longitude.degrees,
            subpt.elevation.km,
        )
        # 固定距離示例 (550 km)，或用 haversine 計算
        dist = 550.0
        snr = estimate_snr(dist)
        state.update(
            snr=round(snr, 1),
            link=(snr >= 5.0),
            sat={"lat": round(lat, 4), "lon": round(lon, 4), "alt_km": round(alt, 3)},
        )
        await asyncio.sleep(1)


@router.on_event("startup")
async def start_background_loop():
    asyncio.create_task(update_loop())


@router.get("/status")
def get_status():
    """回傳最新 SNR、連線狀態與衛星座標"""
    return state
