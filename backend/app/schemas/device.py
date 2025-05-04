# backend/app/schemas/device.py
from typing import Optional
from pydantic import BaseModel, Field as PydanticField
from app.db.models import DeviceRole


# 基礎 Schema，包含 DeviceBase 的核心欄位
class DeviceBase(BaseModel):
    name: str
    x: int
    y: int
    z: int
    orientation: float = PydanticField(default=0.0)
    role: str
    power: int = PydanticField(default=0)
    active: bool = PydanticField(default=True)


# 用於創建 Device 的 Schema
class DeviceCreate(DeviceBase):
    pass


# 用於更新 Device 的 Schema (所有欄位都是可選的)
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    z: Optional[int] = None
    orientation: Optional[float] = None
    role: Optional[str] = None
    power: Optional[int] = None
    active: Optional[bool] = None


# 資料庫中 Device 的基礎 Schema (包含 ID)
class DeviceInDBBase(DeviceBase):
    id: int

    class Config:
        from_attributes = True


# 用於 API 返回的 Device 完整 Schema
class Device(DeviceInDBBase):
    class Config:
        from_attributes = True


# 可設定參數版本，用於 Response 的 Schema
class DeviceParameters(DeviceBase):
    id: int

    class Config:
        from_attributes = True
