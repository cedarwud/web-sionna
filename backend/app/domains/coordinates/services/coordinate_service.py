import logging
import math
from typing import Tuple, Dict, Any, Optional

import numpy as np

from app.domains.coordinates.models.coordinate_model import (
    GeoCoordinate,
    CartesianCoordinate,
)
from app.domains.coordinates.interfaces.coordinate_service_interface import (
    CoordinateServiceInterface,
)

logger = logging.getLogger(__name__)

# --- GLB Coordinate Conversion Constants ---
ORIGIN_LATITUDE_GLB = 24.786667  # 真實世界原點緯度 (GLB (0,0) 對應點)
ORIGIN_LONGITUDE_GLB = 120.996944  # 真實世界原點經度 (GLB (0,0) 對應點)
# GLB (100, 100) -> (真實): (24.785833 N, 120.997778 E)
LATITUDE_SCALE_PER_GLB_Y = -0.000834 / 100  # 度 / GLB Y 單位
LONGITUDE_SCALE_PER_GLB_X = 0.000834 / 100  # 度 / GLB X 單位

# 地球參數
EARTH_RADIUS_KM = 6371.0  # 地球平均半徑 (公里)
WGS84_A = 6378137.0  # WGS-84 橢球體長半軸 (米)
WGS84_F = 1 / 298.257223563  # WGS-84 扁率
WGS84_B = WGS84_A * (1 - WGS84_F)  # WGS-84 橢球體短半軸 (米)


class CoordinateService(CoordinateServiceInterface):
    """座標轉換服務實現"""

    async def geo_to_cartesian(self, geo: GeoCoordinate) -> CartesianCoordinate:
        """將地理座標轉換為笛卡爾座標 (簡單投影)"""
        # 簡單球面投影，適合小區域
        lat_rad = math.radians(geo.latitude)
        lon_rad = math.radians(geo.longitude)

        x = EARTH_RADIUS_KM * math.cos(lat_rad) * math.cos(lon_rad)
        y = EARTH_RADIUS_KM * math.cos(lat_rad) * math.sin(lon_rad)
        z = EARTH_RADIUS_KM * math.sin(lat_rad)

        if geo.altitude is not None:
            # 添加高度 (單位轉換: 米 -> 公里)
            alt_km = geo.altitude / 1000.0
            scale = (EARTH_RADIUS_KM + alt_km) / EARTH_RADIUS_KM
            x *= scale
            y *= scale
            z *= scale

        return CartesianCoordinate(x=x, y=y, z=z)

    async def cartesian_to_geo(self, cartesian: CartesianCoordinate) -> GeoCoordinate:
        """將笛卡爾座標轉換為地理座標 (簡單投影)"""
        # 計算距離地心的距離
        r = math.sqrt(cartesian.x**2 + cartesian.y**2 + cartesian.z**2)

        # 計算地理座標
        lon_rad = math.atan2(cartesian.y, cartesian.x)
        lat_rad = math.asin(cartesian.z / r)

        # 轉換為度
        lat_deg = math.degrees(lat_rad)
        lon_deg = math.degrees(lon_rad)

        # 計算高度 (公里 -> 米)
        altitude = (r - EARTH_RADIUS_KM) * 1000.0

        return GeoCoordinate(
            latitude=lat_deg,
            longitude=lon_deg,
            altitude=altitude if altitude > 0.1 else None,  # 如果高度很小就設為 None
        )

    async def geo_to_ecef(self, geo: GeoCoordinate) -> CartesianCoordinate:
        """將地理座標轉換為地球中心地固座標 (ECEF) - 簡化版本"""
        # 簡化的 ECEF 轉換，不使用 skyfield
        lat_rad = math.radians(geo.latitude)
        lon_rad = math.radians(geo.longitude)
        h = geo.altitude or 0.0  # 高度，預設為 0

        # WGS84 橢球體參數
        a = WGS84_A  # 長半軸
        e2 = 2 * WGS84_F - WGS84_F**2  # 第一偏心率的平方

        # 計算主曲率半徑
        N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)

        # 計算 ECEF 座標
        x = (N + h) * math.cos(lat_rad) * math.cos(lon_rad)
        y = (N + h) * math.cos(lat_rad) * math.sin(lon_rad)
        z = (N * (1 - e2) + h) * math.sin(lat_rad)

        return CartesianCoordinate(x=x, y=y, z=z)

    async def ecef_to_geo(self, ecef: CartesianCoordinate) -> GeoCoordinate:
        """將地球中心地固座標 (ECEF) 轉換為地理座標 - 簡化版本"""
        # 簡化的 ECEF 到地理座標轉換
        x, y, z = ecef.x, ecef.y, ecef.z
        
        # WGS84 橢球體參數
        a = WGS84_A
        e2 = 2 * WGS84_F - WGS84_F**2
        
        # 經度計算
        lon_rad = math.atan2(y, x)
        
        # 緯度和高度計算（迭代法）
        p = math.sqrt(x**2 + y**2)
        lat_rad = math.atan2(z, p * (1 - e2))
        
        for _ in range(5):  # 迭代 5 次應該足夠精確
            N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
            h = p / math.cos(lat_rad) - N
            lat_rad = math.atan2(z, p * (1 - e2 * N / (N + h)))
        
        # 最終高度計算
        N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        h = p / math.cos(lat_rad) - N

        return GeoCoordinate(
            latitude=math.degrees(lat_rad),
            longitude=math.degrees(lon_rad),
            altitude=h,
        )

    async def bearing_distance(
        self, point1: GeoCoordinate, point2: GeoCoordinate
    ) -> Tuple[float, float]:
        """計算兩點間的方位角和距離"""
        # 轉換為弧度
        lat1 = math.radians(point1.latitude)
        lon1 = math.radians(point1.longitude)
        lat2 = math.radians(point2.latitude)
        lon2 = math.radians(point2.longitude)

        # 計算方位角
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
            lat2
        ) * math.cos(dlon)
        bearing_rad = math.atan2(y, x)
        bearing = math.degrees(bearing_rad)
        # 轉換為 0-360 度
        bearing = (bearing + 360) % 360

        # 使用 Haversine 公式計算距離
        a = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = EARTH_RADIUS_KM * c * 1000  # 轉換為米

        return bearing, distance

    async def destination_point(
        self, start: GeoCoordinate, bearing: float, distance: float
    ) -> GeoCoordinate:
        """根據起點、方位角和距離計算終點座標"""
        # 轉換為弧度
        lat1 = math.radians(start.latitude)
        lon1 = math.radians(start.longitude)
        bearing_rad = math.radians(bearing)

        # 距離轉換為公里
        distance_km = distance / 1000

        # 計算角距離
        angular_distance = distance_km / EARTH_RADIUS_KM

        # 計算終點座標
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular_distance)
            + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        lon2 = lon1 + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1),
            math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
        )

        # 轉換為度
        lat2_deg = math.degrees(lat2)
        lon2_deg = math.degrees(lon2)

        # 經度規範化到 -180 ~ 180
        lon2_deg = ((lon2_deg + 180) % 360) - 180

        return GeoCoordinate(
            latitude=lat2_deg,
            longitude=lon2_deg,
            altitude=start.altitude,  # 保持與起點相同的高度
        )

    async def utm_to_geo(
        self, easting: float, northing: float, zone_number: int, zone_letter: str
    ) -> GeoCoordinate:
        """將 UTM 座標轉換為地理座標"""
        # 簡單的 UTM 轉經緯度，實際應用中可能需要更複雜的庫
        k0 = 0.9996  # UTM 比例因子
        e = 0.00669438  # WGS-84 偏心率的平方
        e2 = e / (1 - e)

        # 確定半球
        northern = zone_letter >= "N"

        # 計算中央子午線
        cm = 6 * zone_number - 183

        # 調整 northing
        if not northern:
            northing = 10000000 - northing

        # 簡化的緯度計算
        lat_rad = northing / 6366197.724 / 0.9996

        # 實際應用中應使用專業庫如 pyproj 進行精確計算
        # UTM 轉換相當複雜，這裡僅作為簡化示例

        # 簡化實現 - 實際應該使用專業庫如 pyproj
        lat_deg = math.degrees(lat_rad)
        lon_deg = cm + math.degrees(
            math.atan(math.sinh(math.log(math.tan(math.pi / 4 + lat_rad / 2))))
        )

        return GeoCoordinate(latitude=lat_deg, longitude=lon_deg)

    async def geo_to_utm(self, geo: GeoCoordinate) -> Dict[str, Any]:
        """將地理座標轉換為 UTM 座標"""
        # 簡化的 UTM 區帶計算
        zone_number = int((geo.longitude + 180) / 6) + 1

        # 確定區帶字母
        if geo.latitude >= 72.0:
            zone_letter = "X"
        elif geo.latitude >= 64.0:
            zone_letter = "W"
        elif geo.latitude >= 56.0:
            zone_letter = "V"
        elif geo.latitude >= 48.0:
            zone_letter = "U"
        elif geo.latitude >= 40.0:
            zone_letter = "T"
        # ... 其他字母的計算
        else:
            # 簡化: 在赤道以南使用 M 到 A，以北使用 N 到 Z
            latitude_index = int((geo.latitude + 80) / 8)
            if latitude_index < 0:
                latitude_index = 0
            elif latitude_index > 20:
                latitude_index = 20
            zone_letter = "CDEFGHJKLMNPQRSTUVWX"[latitude_index]

        # UTM 轉換 - 這裡是簡化版，生產環境應該使用專業庫
        # 計算中央經線
        lon_origin = (zone_number - 1) * 6 - 180 + 3
        lon_rad = math.radians(geo.longitude)
        lat_rad = math.radians(geo.latitude)

        # 計算 UTM 參數
        N = WGS84_A / math.sqrt(1 - WGS84_F * (2 - WGS84_F) * (math.sin(lat_rad) ** 2))
        T = math.tan(lat_rad) ** 2
        C = (
            WGS84_F
            * (2 - WGS84_F)
            * (math.cos(lat_rad) ** 2)
            / (1 - WGS84_F * (2 - WGS84_F))
        )
        A = math.cos(lat_rad) * (lon_rad - math.radians(lon_origin))

        # 計算 easting 和 northing
        easting = 0.9996 * N * (A + (1 - T + C) * (A**3) / 6) + 500000
        northing = 0.9996 * (
            N
            * math.tan(lat_rad)
            * (
                1
                + math.cos(lat_rad) ** 2
                * (
                    (A**2) / 2
                    + (5 - 4 * T + 42 * C + 13 * C**2 - 28 * (WGS84_F * (2 - WGS84_F)))
                    * (A**4)
                    / 24
                )
            )
        )

        # 南半球調整
        if geo.latitude < 0:
            northing = northing + 10000000

        return {
            "easting": easting,
            "northing": northing,
            "zone_number": zone_number,
            "zone_letter": zone_letter,
        }
