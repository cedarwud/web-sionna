# backend/app/schemas/device.py
from typing import Optional, List, Union
from pydantic import BaseModel, Field as PydanticField, validator
from app.db.models import DeviceType  # 引用現有 Enum

# 基礎 Schema，包含 DeviceBase 的核心欄位
class DeviceBase(BaseModel):
    name: str
    # 假設 position 輸入格式為 [longitude, latitude, altitude]
    position: List[float] = PydanticField(..., min_items=3, max_items=3)
    active: bool = True
    device_type: DeviceType

    @validator('position')
    def position_must_have_three_coords(cls, v):
        if len(v) != 3:
            raise ValueError('Position must have exactly three coordinates [lon, lat, alt]')
        return v

# 用於創建 Device 的 Schema
class DeviceCreate(DeviceBase):
    pass

# 用於更新 Device 的 Schema (所有欄位都是可選的)
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[List[float]] = None
    active: Optional[bool] = None
    device_type: Optional[DeviceType] = None

    @validator('position')
    def position_must_have_three_coords(cls, v):
        if v is not None and len(v) != 3:
            raise ValueError('Position must have exactly three coordinates [lon, lat, alt]')
        return v

# 資料庫中 Device 的基礎 Schema (包含 ID)
class DeviceInDBBase(DeviceBase):
    id: int
    # 注意：從DB讀取時，position 可能為 WKT 字串或 None，需要轉換
    position_wkt: Optional[str] = PydanticField(None, alias='position')  # 從DB讀取位置的 WKT

    class Config:
        orm_mode = True
        allow_population_by_field_name = True  # 允許使用 alias

# 用於 API 返回的 Device 完整 Schema
class Device(DeviceInDBBase):
    pass

# 可設定參數版本，用於 Response 的 Schema
class DeviceParameters(DeviceBase):
    id: int

    class Config:
        orm_mode = True 