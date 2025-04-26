# backend/app/crud/crud_device.py
import logging
from typing import List, Optional, Sequence, Any, Dict, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from geoalchemy2.functions import ST_GeomFromText, ST_AsText

from app.db.models import Device, Transmitter, Receiver, DeviceType, TransmitterType
from app.schemas.device import DeviceCreate, DeviceUpdate

logger = logging.getLogger(__name__)

# --- Helper to create WKT string ---
def create_point_wkt(lon: float, lat: float, alt: float) -> str:
    # 使用 SRID 4326 (WGS 84)
    return f'SRID=4326;POINT Z ({lon} {lat} {alt})'

# --- Create Device ---
async def create_device(db: AsyncSession, *, obj_in: DeviceCreate) -> Device:
    """
    創建一個新的設備記錄。
    根據設備類型，可能還會創建對應的 Transmitter 或 Receiver 記錄。
    """
    logger.info(f"Attempting to create device: {obj_in.name} of type {obj_in.device_type}")
    try:
        # 1. 創建 Device 記錄
        position_wkt = create_point_wkt(*obj_in.position)
        db_device = Device(
            name=obj_in.name,
            device_type=obj_in.device_type,
            position=position_wkt,  # 使用 WKT 字串
            active=obj_in.active
        )
        db.add(db_device)
        await db.flush()  # 刷新以獲取 db_device.id

        if db_device.id is None:
            raise ValueError("Failed to get ID for the new device.")

        # 2. 根據設備類型創建對應的記錄
        if obj_in.device_type == DeviceType.TRANSMITTER:
            # 默認創建 SIGNAL 類型的發射器
            db_transmitter = Transmitter(
                id=db_device.id,
                transmitter_type=TransmitterType.SIGNAL
            )
            db.add(db_transmitter)
        elif obj_in.device_type == DeviceType.RECEIVER:
            # 創建接收器
            db_receiver = Receiver(
                id=db_device.id
            )
            db.add(db_receiver)

        await db.commit()
        await db.refresh(db_device)
        logger.info(f"Successfully created device '{db_device.name}' with ID {db_device.id}")
        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating device '{obj_in.name}': {e}", exc_info=True)
        raise  # 重新拋出異常，讓上層處理

# --- Get Device by ID ---
async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """
    根據 ID 獲取單個設備。
    查詢會包含位置的 WKT 表示。
    """
    logger.debug(f"Fetching device with ID: {device_id}")
    stmt = (
        select(Device, ST_AsText(Device.position).label('position_wkt'))
        .where(Device.id == device_id)
    )
    result = await db.execute(stmt)
    db_obj_row = result.first()
    if db_obj_row:
        device_obj = db_obj_row[0]
        # 如果需要，可以將 WKT 字串存儲在設備物件的 position_wkt 屬性中
        # device_obj.position_wkt = db_obj_row[1]
        return device_obj
    return None

# --- Get Device by Name ---
async def get_device_by_name(db: AsyncSession, name: str) -> Optional[Device]:
    """
    根據名稱獲取單個設備。
    """
    logger.debug(f"Fetching device with name: {name}")
    stmt = select(Device).where(Device.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# --- Get Multiple Devices ---
async def get_multi_devices(
    db: AsyncSession, *, skip: int = 0, limit: int = 100, device_type: Optional[DeviceType] = None
) -> Sequence[Device]:
    """
    獲取設備列表，可選按類型過濾。
    """
    logger.debug(f"Fetching multiple devices (skip={skip}, limit={limit}, type={device_type})")
    
    # 基本查詢
    query = select(Device)
    
    # 如果指定了設備類型，添加類型過濾條件
    if device_type:
        query = query.where(Device.device_type == device_type)
    
    # 添加分頁
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

# --- Update Device ---
async def update_device(
    db: AsyncSession, *, db_obj: Device, obj_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    更新設備信息。
    """
    logger.info(f"Attempting to update device ID: {db_obj.id}")
    
    # 將 Pydantic 模型轉換為字典
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    # 處理 Position 更新
    if "position" in update_data and update_data["position"] is not None:
        position_wkt = create_point_wkt(*update_data["position"])
        update_data["position"] = position_wkt
    
    # 更新 Device 物件
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Successfully updated device ID: {db_obj.id}")
    return db_obj

# --- Delete Device ---
async def remove_device(db: AsyncSession, *, device_id: int) -> Optional[Device]:
    """
    根據 ID 刪除一個設備。
    由於外鍵關係設置為 ON DELETE CASCADE，相關的 Transmitter 或 Receiver 記錄會自動刪除。
    """
    logger.info(f"Attempting to delete device ID: {device_id}")
    # 先獲取物件以便返回
    db_obj = await get_device(db, device_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Successfully deleted device ID: {device_id}")
        return db_obj
    else:
        logger.warning(f"Device with ID {device_id} not found for deletion.")
        return None 