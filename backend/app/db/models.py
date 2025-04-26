from typing import Optional, Any
from sqlmodel import Field, SQLModel, Relationship  # Relationship 如果有用到關聯
from enum import Enum as PyEnum

# --- Forward References for Relationships ---
# class Transmitter:
#     pass
# class Receiver:
#     pass


# --- Enum Definitions ---
class DeviceType(PyEnum):
    TRANSMITTER = "transmitter"
    RECEIVER = "receiver"


class TransmitterType(PyEnum):
    SIGNAL = "signal"
    INTERFERER = "interferer"


# --- SQLModel Definitions ---


# Forward declare Transmitter and Receiver for type hinting in Device
class Transmitter(SQLModel):  # Base definition for type hint
    id: Optional[int]
    transmitter_type: TransmitterType
    device: Optional["Device"]


class Receiver(SQLModel):  # Base definition for type hint
    id: Optional[int]
    device: Optional["Device"]


class DeviceBase(SQLModel):
    name: str = Field(index=True, unique=True)
    device_type: DeviceType
    x: float = Field(default=0.0)  # 經度 (longitude)
    y: float = Field(default=0.0)  # 緯度 (latitude)
    z: float = Field(default=0.0)  # 高度 (altitude)
    active: bool = Field(default=True, index=True)  # 加入 active 欄位


# Represents the table structure, inherits validation from DeviceBase
class Device(DeviceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Define one-to-one relationships
    # `sa_relationship_kwargs={'lazy': 'joined'}` can help auto-load related objects
    transmitter: Optional["Transmitter"] = Relationship(
        back_populates="device",
        sa_relationship_kwargs={
            "uselist": False,
            "lazy": "joined",
            "cascade": "all, delete-orphan",
        },
    )
    receiver: Optional["Receiver"] = Relationship(
        back_populates="device",
        sa_relationship_kwargs={
            "uselist": False,
            "lazy": "joined",
            "cascade": "all, delete-orphan",
        },
    )


# Transmitter specific data + link to Device
class Transmitter(SQLModel, table=True):  # Full definition
    id: Optional[int] = Field(default=None, primary_key=True, foreign_key="device.id")
    transmitter_type: TransmitterType = Field(default=TransmitterType.SIGNAL)
    # Back-populates the relationship in Device
    device: Optional[Device] = Relationship(
        back_populates="transmitter", sa_relationship_kwargs={"cascade": "all"}
    )


# Receiver specific data + link to Device
class Receiver(SQLModel, table=True):  # Full definition
    id: Optional[int] = Field(default=None, primary_key=True, foreign_key="device.id")
    # Back-populates the relationship in Device
    device: Optional[Device] = Relationship(
        back_populates="receiver", sa_relationship_kwargs={"cascade": "all"}
    )


# Update forward references if necessary (SQLModel often handles this implicitly)
# Device.model_rebuild()
# Transmitter.model_rebuild()
# Receiver.model_rebuild()
