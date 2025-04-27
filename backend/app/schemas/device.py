# backend/app/schemas/device.py
from typing import Optional, Union, List
from pydantic import BaseModel, Field as PydanticField
from app.db.models import DeviceType, TransmitterType


# --- Transmitter Schema --- (New)
class TransmitterSchema(BaseModel):
    transmitter_type: TransmitterType

    class Config:
        from_attributes = True


# --- Receiver Schema --- (Placeholder, if needed later)
# class ReceiverSchema(BaseModel):
#     pass
#     class Config:
#         from_attributes = True


# 基礎 Schema，包含 DeviceBase 的核心欄位
class DeviceBase(BaseModel):
    name: str
    x: float = PydanticField(default=0.0)
    y: float = PydanticField(default=0.0)
    z: float = PydanticField(default=0.0)
    active: bool = PydanticField(default=True)
    device_type: DeviceType


# 用於創建 Device 的 Schema
class DeviceCreate(DeviceBase):
    transmitter_type: Optional[TransmitterType] = None


# 用於更新 Device 的 Schema (所有欄位都是可選的)
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    active: Optional[bool] = None
    device_type: Optional[DeviceType] = None
    transmitter_type: Optional[TransmitterType] = (
        None  # 添加此欄位以支援直接更新transmitter_type
    )


# 資料庫中 Device 的基礎 Schema (包含 ID)
class DeviceInDBBase(DeviceBase):
    id: int

    class Config:
        from_attributes = True


# 用於 API 返回的 Device 完整 Schema
class Device(DeviceInDBBase):
    # Pydantic should now automatically populate this from the relationship
    transmitter: Optional[TransmitterSchema] = None
    # receiver: Optional[ReceiverSchema] = None # If Receiver schema is defined

    class Config:
        from_attributes = True


# 可設定參數版本，用於 Response 的 Schema
class DeviceParameters(DeviceBase):
    id: int
    transmitter: Optional[TransmitterSchema] = None  # Use nested schema

    class Config:
        from_attributes = True
