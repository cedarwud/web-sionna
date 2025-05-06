# backend/app/api/v1/endpoints/devices.py
import logging
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.db.models import DeviceRole
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
    existing_device = await crud_device.get_device_by_name(
        db=session, name=device_in.name
    )
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
    role: Optional[str] = Query(None, description="Filter by device role"),
) -> Any:
    """
    獲取設備列表，可選按角色過濾。
    """
    logger.info(
        f"API: Received request to read devices (skip={skip}, limit={limit}, role={role})"
    )

    devices = await crud_device.get_multi_devices(
        db=session, skip=skip, limit=limit, role=role
    )

    return [DeviceSchema.from_orm(device) for device in devices]


@router.get("/jammers", response_model=List[DeviceSchema])
async def read_jammers(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    獲取干擾源列表。
    """
    logger.info(f"API: Received request to read jammers (skip={skip}, limit={limit})")
    jammers = await crud_device.get_jammers(db=session, skip=skip, limit=limit)
    return [DeviceSchema.from_orm(inf) for inf in jammers]


@router.get("/receivers", response_model=List[DeviceSchema])
async def read_receivers(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    獲取接收器列表。
    """
    logger.info(f"API: Received request to read receivers (skip={skip}, limit={limit})")
    receivers = await crud_device.get_receivers(db=session, skip=skip, limit=limit)
    return [DeviceSchema.from_orm(inf) for inf in receivers]


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    return DeviceSchema.from_orm(device)


@router.put("/{device_id}", response_model=DeviceSchema)
async def update_existing_device(
    *,
    session: AsyncSession = Depends(get_session),
    device_id: int,
    device_in: DeviceUpdate,
) -> Any:
    """
    更新現有設備。
    """
    logger.info(f"API: Received request to update device with ID: {device_id}")
    try:
        # 嘗試獲取設備
        device = await crud_device.get_device(db=session, device_id=device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )

        # 更新設備
        updated_device = await crud_device.update_device_by_id(
            db=session, device_id=device_id, device_in=device_in
        )
        return DeviceSchema.from_orm(updated_device)
    except HTTPException:
        # 直接重新拋出 HTTPException
        raise
    except Exception as e:
        # 記錄並包裝其他異常
        logger.error(f"API Error updating device: {e}", exc_info=True)
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
    刪除一個設備，並檢查 tx、rx、jammer 是否都至少一個。
    """
    logger.info(f"API: Received request to delete device with ID: {device_id}")
    # 先查出要刪除的設備
    device = await crud_device.get_device(db=session, device_id=device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    # 查詢刪除後剩下的 active tx/rx/jammer 數量
    all_active_devices = await crud_device.get_active_devices(db=session)
    # 排除即將刪除的這個設備
    remaining_devices = [d for d in all_active_devices if d.id != device_id]
    tx_count = sum(1 for d in remaining_devices if d.role == DeviceRole.DESIRED.value)
    rx_count = sum(1 for d in remaining_devices if d.role == DeviceRole.RECEIVER.value)
    jammer_count = sum(
        1 for d in remaining_devices if d.role == DeviceRole.JAMMER.value
    )
    if tx_count < 1 or rx_count < 1 or jammer_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系統必須至少有一個發射器 (tx)、接收器 (rx)、干擾源 (jammer)。刪除失敗。",
        )
    # 通過檢查才真的刪除
    deleted_device = await crud_device.remove_device(db=session, device_id=device_id)
    return DeviceSchema.from_orm(deleted_device)
