# backend/app/schemas/interferer.py
from typing import Optional
from pydantic import BaseModel, Field
from app.db.models import DeviceType, TransmitterType # 引用現有 Enum
from app.schemas.device import DeviceBase, DeviceUpdate as BaseDeviceUpdate # 重用 DeviceBase

# 基礎 Schema 繼承自 DeviceBase
class InterfererBase(DeviceBase):
    """
    干擾源基礎 Schema
    重用 DeviceBase 定義的欄位，但可以覆蓋預設值或添加干擾源特有欄位
    """
    # 可以添加 Interferer 特有的屬性，例如：
    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None
    pass

# 用於創建 Interferer 的 Schema
class InterfererCreate(InterfererBase):
    # device_type 和 transmitter_type 會在 CRUD 操作中自動設定
    # 根據 InterfererBase 繼承的欄位（來自 DeviceBase）
    pass

# 用於更新 Interferer 的 Schema (所有欄位可選)
class InterfererUpdate(BaseDeviceUpdate):
    """
    重用 DeviceUpdate 定義的可選欄位，但可以添加干擾源特有的欄位
    """
    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None
    pass

# 資料庫中 Interferer 的基礎 Schema (包含 ID)
class InterfererInDBBase(InterfererBase):
    id: int
    device_type: DeviceType = DeviceType.TRANSMITTER
    transmitter_type: TransmitterType = TransmitterType.INTERFERER

    class Config:
        orm_mode = True

# API 回應的 Schema
class Interferer(InterfererInDBBase):
    pass