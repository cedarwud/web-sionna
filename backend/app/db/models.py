from typing import Optional, Any
from sqlmodel import Field, SQLModel, Relationship # Relationship 如果有用到關聯
from geoalchemy2 import Geometry # For PostGIS geometry types
from enum import Enum as PyEnum

# --- Enum Definitions ---
class DeviceType(PyEnum):
    TRANSMITTER = "transmitter"
    RECEIVER = "receiver"

class TransmitterType(PyEnum):
    SIGNAL = "signal"
    INTERFERER = "interferer"

# --- Geometry Type Definition ---
# 使用 WGS 84 SRID (EPSG:4326)
# POINTZ for 3D coordinates (x, y, z)
# spatial_index=True 建議加上以利空間查詢效能
GEOMETRY_TYPE = Geometry(geometry_type='POINTZ', srid=4326, spatial_index=True)


# --- SQLModel Definitions ---

class DeviceBase(SQLModel):
    name: str = Field(index=True, unique=True)
    device_type: DeviceType
    position: Optional[str] = Field(default=None, sa_column=GEOMETRY_TYPE)
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