# backend/app/api/v1/endpoints/devices.py
import logging
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_session
from app.db.models import Device, DeviceType
from app.schemas.device import Device as DeviceSchema, DeviceCreate, DeviceUpdate
from app.crud import crud_device

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DeviceSchema)
async def create_new_device(
    *,
    session: AsyncSession = Depends(get_session),
    device_in: DeviceCreate,
) -> Any:
    """
    創建一個新的設備。
    """
    logger.info(f"API: Received request to create device: {device_in.name}")
    # 檢查名稱是否已存在
    existing_device = await crud_device.get_device_by_name(db=session, name=device_in.name)
    if existing_device:
        logger.warning(f"Device name '{device_in.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A device with this name already exists.",
        )
    try:
        created_device = await crud_device.create_device(db=session, obj_in=device_in)
        return DeviceSchema.from_orm(created_device)
    except Exception as e:
        logger.error(f"API Error creating device: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the device: {str(e)}",
        )

@router.get("/", response_model=List[DeviceSchema])
async def read_devices(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    device_type: Optional[DeviceType] = Query(None, description="Filter by device type"),
) -> Any:
    """
    獲取設備列表，可選按類型過濾。
    """
    logger.info(f"API: Received request to read devices (skip={skip}, limit={limit}, type={device_type})")
    devices = await crud_device.get_multi_devices(
        db=session, skip=skip, limit=limit, device_type=device_type
    )
    return [DeviceSchema.from_orm(device) for device in devices]

@router.get("/{device_id}", response_model=DeviceSchema)
async def read_device_by_id(
    device_id: int,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    根據 ID 獲取單個設備。
    """
    logger.info(f"API: Received request to read device with ID: {device_id}")
    device = await crud_device.get_device(db=session, device_id=device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceSchema.from_orm(device)

@router.put("/{device_id}", response_model=DeviceSchema)
async def update_existing_device(
    *,
    session: AsyncSession = Depends(get_session),
    device_id: int,
    device_in: DeviceUpdate,
) -> Any:
    """
    更新一個已存在的設備。
    """
    logger.info(f"API: Received request to update device ID: {device_id}")
    db_device = await crud_device.get_device(db=session, device_id=device_id)
    if not db_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # 檢查更新的名稱是否與其他 Device 衝突
    if device_in.name and device_in.name != db_device.name:
        stmt = select(Device).where(Device.name == device_in.name).where(Device.id != device_id)
        result = await session.execute(stmt)
        existing_device = result.scalar_one_or_none()
        if existing_device:
            logger.warning(f"Updated name '{device_in.name}' conflicts with another device.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another device with this updated name already exists.",
            )
    try:
        updated_device = await crud_device.update_device(
            db=session, db_obj=db_device, obj_in=device_in
        )
        return DeviceSchema.from_orm(updated_device)
    except Exception as e:
        logger.error(f"API Error updating device ID {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the device: {str(e)}",
        )

@router.delete("/{device_id}", response_model=DeviceSchema)
async def delete_device_by_id(
    *,
    session: AsyncSession = Depends(get_session),
    device_id: int,
) -> Any:
    """
    刪除一個設備。
    """
    logger.info(f"API: Received request to delete device ID: {device_id}")
    deleted_device = await crud_device.remove_device(db=session, device_id=device_id)
    if not deleted_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceSchema.from_orm(deleted_device) 