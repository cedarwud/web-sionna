# backend/app/schemas/interferer.py
from typing import Optional, List
from pydantic import BaseModel, Field as PydanticField, validator
from app.db.models import DeviceType, TransmitterType # 引用現有 Enum

# 基礎 Schema，包含 DeviceBase 的核心欄位
class InterfererBase(BaseModel):
    name: str
    # 假設 position 輸入格式為 [longitude, latitude, altitude]
    position: List[float] = PydanticField(..., min_items=3, max_items=3)
    active: bool = True
    # 可以添加 Interferer 特有的屬性，例如：
    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None

    @validator('position')
    def position_must_have_three_coords(cls, v):
        if len(v) != 3:
            raise ValueError('Position must have exactly three coordinates [lon, lat, alt]')
        return v

# 用於創建 Interferer 的 Schema
class InterfererCreate(InterfererBase):
    # device_type 和 transmitter_type 會在 CRUD 操作中自動設定
    pass

# 用於更新 Interferer 的 Schema (所有欄位可選)
class InterfererUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[List[float]] = None
    active: Optional[bool] = None
    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None

    @validator('position')
    def position_must_have_three_coords_optional(cls, v):
        if v is not None and len(v) != 3:
            raise ValueError('Position must have exactly three coordinates [lon, lat, alt]')
        return v

# 資料庫中 Interferer 的基礎 Schema (包含 ID)
class InterfererInDBBase(InterfererBase):
    id: int
    device_type: DeviceType = DeviceType.TRANSMITTER
    transmitter_type: TransmitterType = TransmitterType.INTERFERER
    # 注意：從DB讀取時，position 可能為 WKT 字串或 None，需要轉換
    position_wkt: Optional[str] = PydanticField(None, alias='position') # 從DB讀取位置的 WKT

    class Config:
        orm_mode = True
        allow_population_by_field_name = True # 允許使用 alias

# API 回應的 Schema
class Interferer(InterfererInDBBase):
    # 如果需要在 API 回應中直接顯示 [lon, lat, alt] 格式，可以在這裡添加轉換邏輯
    # 或者讓前端處理 position_wkt
    pass