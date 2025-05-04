from typing import Optional, Any
from sqlmodel import Field, SQLModel
from enum import Enum as PyEnum


# --- Enum Definitions ---
class DeviceRole(PyEnum):
    DESIRED = "desired"
    JAMMER = "jammer"
    RECEIVER = "receiver"


# --- SQLModel Definitions ---
class DeviceBase(SQLModel):
    name: str = Field(index=True, unique=True)
    x: int = Field(...)  # required
    y: int = Field(...)  # required
    z: int = Field(...)  # required
    orientation: float = Field(default=0.0)
    role: str = Field(...)  # required
    power: int = Field(default=0)
    active: bool = Field(default=True, index=True)


# Represents the table structure, inherits validation from DeviceBase
class Device(DeviceBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
