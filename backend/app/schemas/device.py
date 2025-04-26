# backend/app/schemas/device.py
from typing import Optional, Union
from pydantic import BaseModel
from app.db.models import DeviceType  # 引用現有 Enum

# 基礎 Schema，包含 DeviceBase 的核心欄位
class DeviceBase(BaseModel):
    name: str
    x: float = 0.0  # 經度 (longitude)
    y: float = 0.0  # 緯度 (latitude)
    z: float = 0.0  # 高度 (altitude)
    active: bool = True
    device_type: DeviceType

# 用於創建 Device 的 Schema
class DeviceCreate(DeviceBase):
    pass

# 用於更新 Device 的 Schema (所有欄位都是可選的)
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    active: Optional[bool] = None
    device_type: Optional[DeviceType] = None

# 資料庫中 Device 的基礎 Schema (包含 ID)
class DeviceInDBBase(DeviceBase):
    id: int

    class Config:
        orm_mode = True

# 用於 API 返回的 Device 完整 Schema
class Device(DeviceInDBBase):
    pass

# 可設定參數版本，用於 Response 的 Schema
class DeviceParameters(DeviceBase):
    id: int

    class Config:
        orm_mode = True 