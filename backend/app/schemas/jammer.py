# backend/app/schemas/jammer.py
from typing import Optional
from pydantic import BaseModel, Field
from app.db.models import DeviceType, TransmitterType  # 引用現有 Enum
from app.schemas.device import (
    DeviceBase,
    DeviceUpdate as BaseDeviceUpdate,
)  # 重用 DeviceBase


# 基礎 Schema 繼承自 DeviceBase
class JammerBase(DeviceBase):
    """
    干擾源基礎 Schema
    重用 DeviceBase 定義的欄位，但可以覆蓋預設值或添加干擾源特有欄位
    """

    # 可以添加 Jammer 特有的屬性，例如：
    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None
    pass


# 用於創建 Jammer 的 Schema
class JammerCreate(JammerBase):
    # device_type 和 transmitter_type 會在 CRUD 操作中自動設定
    # 根據 JammerBase 繼承的欄位（來自 DeviceBase）
    pass


# 用於更新 Jammer 的 Schema (所有欄位可選)
class JammerUpdate(BaseDeviceUpdate):
    """
    重用 DeviceUpdate 定義的可選欄位，但可以添加干擾源特有的欄位
    """

    # power_dbm: Optional[float] = None
    # frequency_mhz: Optional[float] = None
    pass


# 資料庫中 Jammer 的基礎 Schema (包含 ID)
class JammerInDBBase(JammerBase):
    id: int
    device_type: DeviceType = DeviceType.TRANSMITTER
    transmitter_type: TransmitterType = TransmitterType.JAMMER

    class Config:
        orm_mode = True


# API 回應的 Schema
class Jammer(JammerInDBBase):
    pass
