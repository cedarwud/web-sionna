from typing import Optional, Any
from sqlmodel import Field, SQLModel, Relationship # Relationship 如果有用到關聯
from enum import Enum as PyEnum

# --- Enum Definitions ---
class DeviceType(PyEnum):
    TRANSMITTER = "transmitter"
    RECEIVER = "receiver"

class TransmitterType(PyEnum):
    SIGNAL = "signal"
    INTERFERER = "interferer"

# --- SQLModel Definitions ---

class DeviceBase(SQLModel):
    name: str = Field(index=True, unique=True)
    device_type: DeviceType
    x: float = Field(default=0.0)  # 經度 (longitude)
    y: float = Field(default=0.0)  # 緯度 (latitude)
    z: float = Field(default=0.0)  # 高度 (altitude)
    active: bool = Field(default=True, index=True) # 加入 active 欄位

# Represents the table structure, inherits validation from DeviceBase
class Device(DeviceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

# Transmitter specific data + link to Device
class Transmitter(SQLModel, table=True): # 直接繼承 SQLModel 建立新表
    # Foreign key linking to the device table, also primary key for this table
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        foreign_key="device.id" # 確保指向 device.id
    )
    transmitter_type: TransmitterType = Field(default=TransmitterType.SIGNAL)
    # 如果需要反向關聯 (從 Device 訪問 Transmitter)，可以加上 Relationship
    # device: Optional["Device"] = Relationship(back_populates="transmitter")


# Receiver specific data + link to Device
class Receiver(SQLModel, table=True): # 直接繼承 SQLModel 建立新表
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        foreign_key="device.id" # 確保指向 device.id
    )
    # 如果需要反向關聯
    # device: Optional["Device"] = Relationship(back_populates="receiver")

# --- Add Relationships to Device model if needed ---
# (需要確保 Device class 定義在 Transmitter/Receiver 之後，或者使用 forward reference)
# class Device(DeviceBase, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     # Define one-to-one relationships if needed (adjust based on actual relationship)
#     transmitter: Optional["Transmitter"] = Relationship(back_populates="device")
#     receiver: Optional["Receiver"] = Relationship(back_populates="device")
# Note: For one-to-one or one-to-many, the structure might differ slightly.
# The current setup implies Device is the primary entity, and Transmitter/Receiver
# are extensions linked by the same ID.