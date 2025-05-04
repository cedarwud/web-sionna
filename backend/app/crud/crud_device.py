# backend/app/crud/crud_device.py
import logging
from typing import List, Optional, Sequence, Any, Dict, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models import Device, DeviceRole
from app.schemas.device import DeviceCreate, DeviceUpdate

logger = logging.getLogger(__name__)


# --- Create Device ---
async def create_device(db: AsyncSession, *, obj_in: DeviceCreate) -> Device:
    """
    創建一個新的設備記錄。
    """
    logger.info(f"Attempting to create device: {obj_in.name}")
    try:
        # 創建 Device 記錄
        db_device = Device(
            name=obj_in.name,
            x=obj_in.x,
            y=obj_in.y,
            z=obj_in.z,
            orientation=obj_in.orientation,
            role=obj_in.role,
            power=obj_in.power,
            active=obj_in.active,
        )
        db.add(db_device)
        await db.commit()
        await db.refresh(db_device)
        logger.info(
            f"Successfully created device '{db_device.name}' with ID {db_device.id}"
        )
        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating device '{obj_in.name}': {e}", exc_info=True)
        raise  # 重新拋出異常，讓上層處理


# --- Get Device by ID ---
async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """
    根據 ID 獲取單個設備。
    """
    logger.debug(f"Fetching device with ID: {device_id}")
    stmt = select(Device).where(Device.id == device_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


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
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
) -> Sequence[Device]:
    """
    獲取設備列表，可選按角色過濾。
    """
    logger.debug(f"Fetching multiple devices (skip={skip}, limit={limit}, role={role})")

    # 基礎查詢
    query = select(Device)

    # 如果指定了角色，添加角色過濾條件
    if role:
        query = query.where(Device.role == role)

    # 添加分頁
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


# --- Get Jammers ---
async def get_jammers(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> Sequence[Device]:
    """
    獲取所有角色為 jammer 的設備。
    """
    return await get_multi_devices(db, skip=skip, limit=limit, role=DeviceRole.JAMMER)


# --- Get Receivers ---
async def get_receivers(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> Sequence[Device]:
    """
    獲取所有角色為 receiver 的設備。
    """
    return await get_multi_devices(db, skip=skip, limit=limit, role=DeviceRole.RECEIVER)


# --- Update Device by ID ---
async def update_device_by_id(
    db: AsyncSession, *, device_id: int, device_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    根據 ID 更新設備。
    """
    logger.info(f"Attempting to update device with ID: {device_id}")
    try:
        db_device = await get_device(db, device_id=device_id)
        if db_device is None:
            raise ValueError(f"Device with ID {device_id} not found.")

        return await update_device(db=db, db_obj=db_device, obj_in=device_in)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating device with ID {device_id}: {e}", exc_info=True)
        raise


# --- Remove Device ---
async def remove_device(db: AsyncSession, *, device_id: int) -> Optional[Device]:
    """
    根據 ID 刪除設備。
    """
    logger.debug(f"Removing device with ID: {device_id}")
    try:
        # 獲取設備
        db_device = await get_device(db, device_id=device_id)
        if db_device is None:
            logger.warning(f"Device with ID {device_id} not found for removal.")
            return None

        # 刪除設備
        await db.delete(db_device)
        await db.commit()
        logger.info(f"Successfully removed device with ID: {device_id}")

        return db_device
    except Exception as e:
        await db.rollback()
        logger.error(f"Error removing device with ID {device_id}: {e}", exc_info=True)
        raise


# --- Get Devices by Role ---
async def get_devices_by_role(
    db: AsyncSession,
    *,
    role: str,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> Sequence[Device]:
    """
    根據角色獲取設備列表。
    """
    logger.debug(f"Fetching devices with role: {role}")
    query = select(Device).where(Device.role == role)

    if active_only:
        query = query.where(Device.active == True)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


# --- Get Active Devices ---
async def get_active_devices(
    db: AsyncSession,
    *,
    role: Optional[str] = None,
) -> List[Device]:
    """
    獲取活躍的設備列表，可選按角色過濾。
    """
    logger.debug(f"Fetching active devices (role={role})")

    query = select(Device).where(Device.active == True)

    if role:
        query = query.where(Device.role == role)

    result = await db.execute(query)
    return result.scalars().all()


# --- Update Device ---
async def update_device(
    db: AsyncSession, *, db_obj: Device, obj_in: Union[DeviceUpdate, Dict[str, Any]]
) -> Device:
    """
    更新設備。
    """
    logger.debug(f"Updating device: {db_obj.name} (ID: {db_obj.id})")
    try:
        # 轉換輸入為字典
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        # 更新設備欄位
        for field in update_data:
            if field in update_data and hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        logger.info(f"Successfully updated device: {db_obj.name} (ID: {db_obj.id})")
        return db_obj
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating device {db_obj.name}: {e}", exc_info=True)
        raise
